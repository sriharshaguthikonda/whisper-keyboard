"""TODO :  the merge was not complete we need to do more testing and do a complete merge of the code with other branches too"""

"""
##    ##  #######            ##     ## ####  ######
###   ## ##     ##           ###   ###  ##  ##    ##
####  ## ##     ##           #### ####  ##  ##
## ## ## ##     ##   #####   ## ### ##  ##  ##
##  #### ##     ##           ##     ##  ##  ##
##   ### ##     ##           ##     ##  ##  ##    ##
##    ##  #######            ##     ## ####  ######
"""

import os
import time
import threading
import winsound
import pyautogui
import numpy as np
import sounddevice as sd
import pythoncom
import io
from scipy.io.wavfile import write as wav_write
import groq
from groq import Groq
import torch
import queue
import logging
from pynput.keyboard import Controller as KeyboardController, Key, Listener
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from voice_commands import (
    execute_command_fuzzy,
    execute_command_run_with_tool,
    start_driver,
    get_volume,
    set_volume,
    driver,
)
from google_assistant import google_assistant
from pause_all import is_sound_playing_windows_processing
import pyaudio
from openwakeword.model import Model
from concurrent.futures import ThreadPoolExecutor
import win32clipboard
import ctypes
import webrtcvad
from voice_activity_detection import VoiceDetector
import sys
import traceback
from queue import Empty as QueueEmpty
from contextlib import contextmanager
import aiohttp
import asyncio

# Add global variables for pause functionality
global_pause_active = False
last_pause_check = 0

# Set up ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=6)

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("whisper_keyboard.log"),
        logging.StreamHandler(),
    ],
)

# ANSI Color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
ORANGE = "\033[38;5;214m"
PINK = "\033[38;5;198m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

# Initial setup and global variables
initial_volume = None
transcript_queue = queue.Queue()
audio_buffer_queue = queue.Queue()

# Initialize VoiceDetector
vad_detector = VoiceDetector()

load_dotenv()

# Get the key label from environment variables, default to 'f24' if not set
key_label = os.environ.get("WKEY", "f24")
RECORD_KEY = Key[key_label]

keyboard_controller = KeyboardController()
recording = False
stream = None
audio_buffer = np.array([], dtype="float32")
sample_rate = 16000

# Check if CUDA is available
if torch.cuda.is_available():
    model = WhisperModel("small.en", device="cuda", num_workers=8)
    logging.info(f"{GREEN}Initialized WhisperModel on CUDA{RESET}")
else:
    logging.warning(
        f"{YELLOW}CUDA device not available. Please ensure your system supports CUDA.{RESET}"
    )

groq_model = "whisper-large-v3"
play_pause_pressed = False
something_is_playing = False

Hey_computer_STT_prompt = None

api_key = os.getenv("GROQ_API_KEY")
global Groq_client
Groq_client = Groq(api_key=api_key)

p = pyaudio.PyAudio()
wake_stream = p.open(
    format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=16000
)
wake_stream.start_stream()

# Define beep sounds
START_BEEP = (2080, 100)
STOP_BEEP = (440, 100)
PASTE_BEEP = (1060, 100)

# Locks for synchronization
recording_lock = threading.Lock()
audio_data_lock = threading.Lock()

"""
 ######  ######## ########  ########    ###    ##     ## 
##    ##    ##    ##     ## ##         ## ##   ###   ### 
##          ##    ##     ## ##        ##   ##  #### #### 
 ######     ##    ########  ######   ##     ## ## ### ## 
      ##    ##    ##   ##   ##       ######### ##     ## 
##    ##    ##    ##    ##  ##       ##     ## ##     ## 
 ######     ##    ##     ## ######## ##     ## ##     ## 
"""

PRE_RECORDING_DURATION = 3
BUFFER_SIZE = PRE_RECORDING_DURATION * sample_rate
channels = 1

pre_recording_buffer = np.zeros((BUFFER_SIZE, channels), dtype=np.float32)
pre_recording_buffer_f24 = np.zeros(
    (sample_rate * 3, channels), dtype=np.float32
)
buffer_index = 0
audio_buffer = []

# Add a context manager for audio operations
@contextmanager
def audio_operation_guard():
    try:
        yield
    except Exception as e:
        logging.error(f"{RED}Audio operation failed: {e}{RESET}", exc_info=True)
        reset_state()

# Modify the audio callback for better error handling
def audio_callback(indata, frames, time, status):
    try:
        with audio_operation_guard():
            global buffer_index, audio_buffer

            if status:
                logging.warning(f"{YELLOW}Audio callback status: {status}{RESET}")
                return

            with recording_lock:
                if recording:
                    if isinstance(indata, np.ndarray):
                        audio_buffer = np.append(audio_buffer, indata.flatten())
                    else:
                        logging.error(
                            f"{RED}Invalid indata type: {type(indata)}{RESET}"
                        )
                else:
                    end_index = buffer_index + frames
                    if end_index > BUFFER_SIZE:
                        end_index = BUFFER_SIZE
                    pre_recording_buffer[buffer_index:end_index] = indata[
                        : end_index - buffer_index
                    ]
                    buffer_index = (buffer_index + frames) % BUFFER_SIZE

    except Exception as e:
        logging.error(f"{RED}Error in audio_callback: {e}{RESET}", exc_info=True)

stream = sd.InputStream(
    callback=audio_callback,
    device=None,
    channels=1,
    samplerate=sample_rate,
    blocksize=int(sample_rate * 0.1),
)

"""
##     ##  #######  ##       ##     ## ##     ## ######## 
##     ## ##     ## ##       ##     ## ###   ### ##       
##     ## ##     ## ##       ##     ## #### #### ##       
##     ## ##     ## ##       ##     ## ## ### ## ######   
 ##   ##  ##     ## ##       ##     ## ##     ## ##       
  ## ##   ##     ## ##       ##     ## ##     ## ##       
   ###     #######  ########  #######  ##     ## ######## 
"""

def decrease_volume_all():
    global initial_volume
    try:
        current_volume = get_volume()
        if initial_volume is None or current_volume != initial_volume:
            initial_volume = current_volume
        print(f"Decreasing volume from {initial_volume * 100}% to 10%")
        set_volume(0.1)
    except Exception as e:
        logging.error(f"Error in decrease_volume_all: {e}", exc_info=True)

def restore_volume_all():
    global initial_volume
    try:
        if initial_volume is not None:
            set_volume(initial_volume)
            time.sleep(0.5)
            initial_volume = None
    except Exception as e:
        logging.error(f"Error in restore_volume_all: {e}", exc_info=True)

def monitor_sound_processing():
    pythoncom.CoInitialize()
    global something_is_playing
    while True:
        if not recording:
            something_is_playing = is_sound_playing_windows_processing(
                something_is_playing
            )

"""
 ######  ########    ###    ########  ########    ########  ########  ######  
##    ##    ##      ## ##   ##     ##    ##       ##     ## ##       ##    ## 
##          ##     ##   ##  ##     ##    ##       ##     ## ##       ##       
 ######     ##    ##     ## ########     ##       ########  ######   ##       
      ##    ##    ######### ##   ##      ##       ##   ##   ##       ##       
##    ##    ##    ##     ## ##    ##     ##       ##    ##  ##       ##    ## 
 ######     ##    ##     ## ##     ##    ##       ##     ## ########  ######   
"""

global True_positve_audio
True_positve_audio = True

def check_keywords_in_transcription(pre_recording_data, keyword_index):
    global True_positve_audio, recording
    try:
        pre_recording_transcript = transcribe_pre_recording_buffer(pre_recording_data)

        logging.error(
            f"pre_recording_transcript: {pre_recording_transcript} keyword_index: {keyword_index}"
        )

        if keyword_index == 1 and "computer" not in pre_recording_transcript.lower():
            True_positve_audio = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        elif keyword_index == 2 and "lama" not in pre_recording_transcript.lower():
            True_positve_audio = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        elif keyword_index == 3 and "jarvis" not in pre_recording_transcript.lower():
            True_positve_audio = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()

    except Exception as e:
        logging.error(f"Error in check_keywords_in_transcription: {e}", exc_info=True)

def start_recording(keyword_index=None):
    """Modified start_recording that checks pause status"""
    try:
        # Check if paused before starting
        if check_pause_status():
            logging.info(f"{YELLOW}Voice recognition is paused. Ignoring recording request.{RESET}")
            return
            
        global stream, recording, play_pause_pressed, something_is_playing, True_positve_audio

        with recording_lock:
            if recording:
                logging.info(f"{YELLOW}Recording is already in progress.{RESET}")
                return

            True_positve_audio = True
            recording = True

        logging.info(f"{GREEN}Starting recording...{RESET}")
        decrease_volume_all()

        try:
            if stream and stream.active:
                logging.info(f"{YELLOW}Stream is already active.{RESET}")
            else:
                try:
                    device_info = sd.default.device
                    logging.info(f"{CYAN}Using device: {device_info}{RESET}")
                    stream = sd.InputStream(
                        callback=audio_callback,
                        device=None,
                        channels=1,
                        samplerate=sample_rate,
                        blocksize=int(sample_rate * 0.1),
                    )
                    stream.start()
                except Exception as e:
                    logging.error(
                        f"{RED}Failed to start stream: {e}{RESET}", exc_info=True
                    )
                    time.sleep(2)
        except NameError:
            pass

        if something_is_playing:
            logging.info(f"{ORANGE}Something is playing, decreasing volume.{RESET}")
            decrease_volume_all()
            play_pause_pressed = True

        beep(START_BEEP)
        logging.info(f"{CYAN}Listening...{RESET}")

        if keyword_index is None:
            pass
        else:
            if pre_recording_buffer is not None and pre_recording_buffer.size > 0:
                pre_recording_data = np.roll(
                    pre_recording_buffer, -buffer_index, axis=0
                ).flatten()

                threading.Thread(
                    target=check_keywords_in_transcription,
                    args=(pre_recording_data, keyword_index),
                ).start()

    except Exception as e:
        logging.error(f"{RED}Error in start_recording: {e}{RESET}", exc_info=True)

"""
 ######  ########  #######  ########     ########  ########  ######  
##    ##    ##    ##     ## ##     ##    ##     ## ##       ##    ## 
##          ##    ##     ## ##     ##    ##     ## ##       ##       
 ######     ##    ##     ## ########     ##       ########  ######   ##       
      ##    ##    ##     ## ##           ##       ##   ##   ##       ##       
##    ##    ##    ##     ## ##           ##    ##  ##       ##    ## 
 ######     ##     #######  ##           ##     ## ########  ######  
"""

def stop_recording(keyword_index):
    try:
        global stream, recording, play_pause_pressed, audio_buffer, sample_rate, recording_start_time, True_positve_audio, vad_detector

        if not recording:
            if play_pause_pressed:
                threading.Thread(target=restore_volume_all).start()
                play_pause_pressed = False
            beep(STOP_BEEP)
            return

        if not True_positve_audio:
            if play_pause_pressed:
                threading.Thread(target=restore_volume_all).start()
                play_pause_pressed = False
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            logging.info(
                f"{MAGENTA}True_positve_audio...is {True_positve_audio}{RESET}"
            )
            True_positve_audio = True
            return

        logging.info(f"{GREEN}Stopping recording...{RESET}")
        hard_stop_limit = 5
        silent_time = 0
        recording_start_time = time.time()

        pre_recording_data = np.roll(
            pre_recording_buffer, -buffer_index, axis=0
        ).flatten()

        if keyword_index == 1:
            stop_delay_threshold = 0.5
        elif keyword_index == 2:
            stop_delay_threshold = 1
        elif keyword_index == 3:
            stop_delay_threshold = 1
        elif keyword_index is None:
            pre_recording_data = np.roll(
                pre_recording_buffer_f24, -buffer_index, axis=0
            ).flatten()
            audio_buffer = np.concatenate([pre_recording_data, audio_buffer], axis=0)
            audio_buffer_queue.put((audio_buffer, keyword_index))

            threading.Thread(target=restore_volume_all).start()
            audio_buffer = np.array([], dtype="float32")

            if play_pause_pressed:
                threading.Thread(target=restore_volume_all).start()
                play_pause_pressed = False

            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            logging.info(f"{MAGENTA}Recording stopped. Processing audio...{RESET}")
            return
        else:
            stop_delay_threshold = 2

        while silent_time <= stop_delay_threshold:
            if stream.active:
                if isinstance(audio_buffer, list):
                    audio_buffer = np.array(audio_buffer)

                frame_duration = 30
                frame_size = int(sample_rate * frame_duration / 1000)
                audio_frame = audio_buffer[-frame_size:]
                audio_int16 = (audio_frame * 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()

                try:
                    is_speech = vad_detector.vad.is_speech(
                        audio_bytes, vad_detector.sample_rate
                    )
                    if is_speech:
                        silent_time = 0
                        logging.info(
                            f"{PINK}Voice detected, continuing recording...{RESET}"
                        )
                    else:
                        silent_time += 0.1
                except Exception as e:
                    logging.error(f"{RED}VAD error: {e}{RESET}", exc_info=True)
                    silent_time += 0.1

                if time.time() - recording_start_time > hard_stop_limit:
                    logging.info(
                        f"{ORANGE}Hard stop limit reached, stopping recording.{RESET}"
                    )
                    break

                time.sleep(0.1)
        audio_buffer = np.concatenate([pre_recording_data, audio_buffer], axis=0)
        audio_buffer_queue.put((audio_buffer.copy(), keyword_index))
        audio_buffer = np.array([], dtype="float32")

        threading.Thread(target=restore_volume_all).start()
        audio_buffer = np.array([], dtype="float32")

        if play_pause_pressed:
            threading.Thread(target=restore_volume_all).start()
            play_pause_pressed = False

        beep(STOP_BEEP)
        with recording_lock:
            recording = False
        logging.info(f"{MAGENTA}Recording stopped. Processing audio...{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error in stop_recording: {e}{RESET}", exc_info=True)
        reset_state()

DEBOUNCE_TIME = 0.5
last_key_press_time = 0
recording_thread = None

def on_press(key):
    """Modified key press handler that respects pause status"""
    try:
        global last_key_press_time, recording_thread, recording
        
        # Check if paused
        if check_pause_status():
            return
            
        current_time = time.time()
        if key == RECORD_KEY and not recording:
            if current_time - last_key_press_time > DEBOUNCE_TIME:
                last_key_press_time = current_time
                if recording is False:
                    logging.info(f"Key pressed: {key}")
                    threading.Thread(target=start_recording, args=(None,)).start()
    except Exception as e:
        logging.error(f"Error in on_press: {e}", exc_info=True)

def on_release(key):
    """Modified key release handler that respects pause status"""
    try:
        global last_key_press_time, recording_thread, recording
        
        # Check if paused
        if check_pause_status():
            return
            
        current_time = time.time()
        if key == RECORD_KEY and recording:
            if current_time - last_key_press_time > DEBOUNCE_TIME:
                last_key_press_time = current_time
                logging.info(f"Key released: {key}")
                threading.Thread(target=stop_recording, args=(None,)).start()
    except Exception as e:
        logging.error(f"Error in on_release: {e}", exc_info=True)

"""
 ######     ###    ##     ## ######## 
##    ##   ## ##   ##     ## ##       
##        ##   ##   ##     ## ##       
 ######  ##     ##  ##     ## ######   
      ## #########  ##   ##  ##       
##    ## ##     ##   ## ##   ##       
 ######  ##     ##    ###    ######## 
"""

def save_audio(
    audio_data,
    keyword_index,
    directory="J:\\Openwakeword_whisper_keyboard_training_data_hotword\\train",
    sample_rate=16000,
    type_of_audio=None,
):
    try:
        if not os.path.exists(directory):
            logging.info(f"cannot save data to {directory} because it does not exist")
            return

        base_filename = os.path.join(
            directory, f"{type_of_audio}_{keyword_index}_recording.wav"
        )
        filename = base_filename
        counter = 1

        while os.path.exists(filename):
            filename = os.path.join(
                directory, f"{type_of_audio}_{keyword_index}_recording_{counter}.wav"
            )
            counter += 1

        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val

        audio_data_int16 = np.int16(audio_data * 32767)
        wav_write(filename, sample_rate, audio_data_int16)
        logging.info(f"{GREEN}Audio saved as {filename}{RESET}")
    except Exception as e:
        logging.error(f"Error in save_audio: {e}", exc_info=True)

"""
 #######  ##      ## ##      ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
 #######   ###  ###   ###  ###  
"""

def check_pause_status():
    """Check if voice recognition should be paused"""
    global global_pause_active, last_pause_check
    
    current_time = time.time()
    if current_time - last_pause_check < 0.5:
        return global_pause_active
    
    last_pause_check = current_time
    
    try:
        if os.path.exists("voice_pause_flag.txt"):
            with open("voice_pause_flag.txt", "r") as f:
                status = f.read().strip()
                global_pause_active = (status == "PAUSED")
        else:
            global_pause_active = False
    except Exception as e:
        logging.error(f"Error checking pause status: {e}")
        global_pause_active = False
    
    return global_pause_active

def check_microphone():
    try:
        devices = sd.query_devices()
        for device in devices:
            if device["max_input_channels"] > 0:
                return True
        return False
    except Exception as e:
        logging.error(f"Error in check_microphone: {e}", exc_info=True)

def reinitialize_pyaudio():
    try:
        global p
        p.terminate()
        p = pyaudio.PyAudio()
    except Exception as e:
        logging.error(f"Error in reinitialize_pyaudio: {e}", exc_info=True)

def monitor_microphone_availability():
    try:
        global wake_stream, p
        while True:
            if not check_microphone():
                logging.info(
                    f"{RED}No microphone detected. Pausing wake word detection...{RESET}"
                )
                if wake_stream:
                    try:
                        wake_stream.stop_stream()
                        wake_stream.close()
                    except OSError as e:
                        logging.info(f"Error stopping stream: {e}")
                    finally:
                        wake_stream = None
            else:
                if (wake_stream is None) or (not wake_stream.is_active()):
                    logging.info(
                        f"{GREEN}Microphone detected. Resuming wake word detection...{RESET}"
                    )
                    try:
                        wake_stream = p.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            frames_per_buffer=16000,
                        )
                        wake_stream.start_stream()
                    except OSError as e:
                        logging.info(f"Failed to restart wake stream: {e}")
                        reinitialize_pyaudio()
                        wake_stream = None
                    except Exception as e:
                        logging.info(f"Unexpected error: {e}")

            time.sleep(10)
    except Exception as e:
        logging.error(f"Error in monitor_microphone_availability: {e}", exc_info=True)

# Hardcoded model paths
MODEL_PATHS = [
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_jarvis_v0.1.onnx",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_computer10.onnx",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_lama.onnx",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_google.onnx",
]

owwModel = Model(
    wakeword_models=MODEL_PATHS, inference_framework="onnx", vad_threshold=0.3
)

CHUNK = 5120
THRESHOLDS = {
    0: 0.9,
    1: 0.1,
    2: 0.1,
    3: 0.1,
}
COOLDOWN_TIME = 6
last_detection_time = 0

"""
##       ####  ######  ######## ######## ##    ## 
##        ##  ##    ##    ##    ##       ###   ## 
##        ##  ##          ##    ##       ####  ## 
##        ##   ######     ##    ######   ## ## ## 
##        ##        ##    ##    ##       ##  #### 
##        ##  ##    ##    ##    ##       ##   ### 
######## ####  ######     ##    ######## ##    ## 
"""

def listen_for_wake_word():
    """Modified version of listen_for_wake_word that respects pause status"""
    global wake_stream, last_detection_time, recording
    print("Listening for wake words...")

    while True:
        try:
            if check_pause_status():
                time.sleep(1)
                continue
                
            if wake_stream:
                data = wake_stream.read(CHUNK, exception_on_overflow=False)
                pcm = np.frombuffer(data, dtype=np.int16)

                prediction = owwModel.predict(pcm)
                keyword_index = -1
                max_score = 0.0

                recent_predictions = list(owwModel.prediction_buffer.values())[-8:]

                for idx, scores in enumerate(recent_predictions):
                    if scores[-1] > max_score:
                        max_score = scores[-1]
                        keyword_index = idx

                current_time = time.time()
                if (
                    keyword_index >= 0
                    and max_score > THRESHOLDS.get(keyword_index, 0.4)
                    and (current_time - last_detection_time) > COOLDOWN_TIME
                    and not recording
                    and not check_pause_status()
                ):
                    last_detection_time = current_time

                    if keyword_index == 0:
                        print("Custom wake word 'hey_jarvis' detected!")
                        threading.Thread(target=start_recording).start()
                        time.sleep(3)
                        threading.Thread(target=stop_recording, args=(keyword_index,)).start()
                    elif keyword_index == 1:
                        print("Custom wake word 'hey_computer10' detected!")
                        threading.Thread(target=start_recording).start()
                        threading.Thread(target=stop_recording, args=(1,)).start()
                    elif keyword_index == 2:
                        print("Custom wake word 'hey_lama' detected!")
                        threading.Thread(target=start_recording).start()
                        threading.Thread(target=stop_recording, args=(2,)).start()
                    elif keyword_index == 3:
                        print("Custom wake word 'hey_google' detected!")
                        decrease_volume_all()
                        time.sleep(3)
                        restore_volume_all()
            else:
                print("Waiting for microphone...")
                time.sleep(5)

        except OSError as e:
            print(f"Audio stream error: {e}")
            if wake_stream:
                try:
                    if wake_stream.is_active():
                        wake_stream.stop_stream()
                    wake_stream.close()
                except OSError:
                    print("Stream already closed or failed to close.")
            wake_stream = None
            time.sleep(10)

def cleanup():
    try:
        global wake_stream
        if wake_stream:
            try:
                if wake_stream.is_active():
                    wake_stream.stop_stream()
                wake_stream.close()
            except OSError as e:
                logging.info(f"Error during cleanup: {e}")
            wake_stream = None
        p.terminate()
        logging.info("Cleanup completed.")
    except Exception as e:
        logging.error(f"Error in cleanup: {e}", exc_info=True)

"""
 ######   ########   #######   #######  
##    ##  ##     ## ##     ## ##     ## 
##        ##     ## ##     ## ##     ## 
##   #### ########  ##     ## ##     ## 
##    ##  ##   ##   ##     ## ##  ## ## 
##    ##  ##    ##  ##     ## ##    ##  
 ######   ##     ##  #######   ##### ## 
"""

transcribe_pre_recording_buffer_prompt = "you are downstream to hotword detection algorithm. check if you are able to detect the wake word 'computer' or 'lama' in the audio"

def transcribe_pre_recording_buffer(pre_recording_data, max_retries=3, retry_delay=2):
    try:
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, pre_recording_data)
        byte_io.seek(0)

        try:
            transcription = Groq_client.audio.transcriptions.create(
                file=("pre_recording.wav", byte_io.getvalue()),
                model=groq_model,
                response_format="json",
                prompt=transcribe_pre_recording_buffer_prompt,
                language="en",
                temperature=0.0,
            )
            return transcription.text.lower()
        except Exception as e:
            logging.error(
                f"{RED}Error in transcribe_pre_recording_buffer: {e}{RESET}",
                exc_info=True,
            )
            return ""

    except Exception as e:
        logging.error(
            f"{RED}Error in transcribe_pre_recording_buffer: {e}{RESET}", exc_info=True
        )
        return ""

async def transcribe_with_groq_async(byte_io, keyword_index, max_retries=3):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": groq_model,
        "response_format": "json",
        "prompt": "",
        "language": "en",
        "temperature": 0.0,
    }

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                form_data = aiohttp.FormData()
                form_data.add_field(
                    "file",
                    byte_io.getvalue(),
                    filename="pre_recording.wav",
                    content_type="audio/wav",
                )
                form_data.add_field("model", groq_model)
                form_data.add_field("response_format", "json")
                form_data.add_field("prompt", "")
                form_data.add_field("language", "en")
                form_data.add_field("temperature", "0.0")

                async with session.post(
                    url, data=form_data, headers=headers
                ) as response:
                    if response.status == 404:
                        logging.error(f"Groq API endpoint not found: {response.url}")
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=response.reason,
                            headers=response.headers,
                        )
                    response.raise_for_status()
                    transcription = await response.json()
                    return transcription["text"].lower()
        except aiohttp.ClientResponseError as e:
            logging.error(
                f"Groq API client error: {e.status}, message='{e.message}', url='{e.request_info.url}'",
                exc_info=True,
            )
            if e.status == 404:
                raise
        except Exception as e:
            logging.error(
                f"Unexpected error in transcribe_with_groq_async: {e}", exc_info=True
            )
        await asyncio.sleep(2)
    logging.error(f"Failed to transcribe after {max_retries} attempts")
    return None

def transcribe_with_local_model(audio_buffer, keyword_index):
    try:
        if keyword_index == 1:
            prompt = Hey_computer_STT_prompt
        else:
            prompt = None

        try:
            logging.info("using WhisperModel on CUDA")
            byte_io = io.BytesIO()
            wav_write(byte_io, sample_rate, audio_buffer)
            byte_io.seek(0)
            segments, _ = model.transcribe(byte_io, language="en")
            transcription = " ".join(segment.text for segment in segments)
            logging.info(transcription)
            return transcription
        except Exception as e:
            logging.info(f"Faster Whisper error: {e}")
            return "Transcription failed"
    except Exception as e:
        logging.error(f"Error in transcribe_with_local_model: {e}", exc_info=True)

result_queue = queue.Queue()

def run_asyncio_in_thread(loop, coro):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

async def process_audio_async():
    while True:
        try:
            global_state["is_processing"] = True

            try:
                audio_buffer_for_processing, keyword_index = audio_buffer_queue.get(
                    timeout=1
                )
            except QueueEmpty:
                global_state["is_processing"] = False
                await asyncio.sleep(0.1)
                continue

            if not validate_audio_buffer(audio_buffer_for_processing):
                global_state["consecutive_failures"] += 1
                continue

            byte_io = io.BytesIO()
            wav_write(byte_io, sample_rate, audio_buffer_for_processing)
            byte_io.seek(0)

            try:
                transcript = await transcribe_with_groq_async(byte_io, keyword_index)
                if transcript is None:
                    logging.error("Transcription returned None")
                    continue
            except groq.RateLimitError:
                logging.error(
                    "Groq API rate limit reached, switching to local transcription."
                )
                transcript = transcribe_with_local_model(audio_buffer_for_processing)

            transcript_lower = transcript.lower()

            if keyword_index is None:
                logging.info("pasing f24 transcription")
                paste_transcript(transcript)
                continue
            elif keyword_index == 1:
                if "computer" in transcript_lower:
                    keyword_position = transcript_lower.index("computer")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("computer") :
                    ]
                    logging.info(f"Processing computer command: {stripped_transcript}")
                    transcript_queue.put((stripped_transcript.strip(), keyword_index))
                    continue
            elif keyword_index == 2:
                if "lama" in transcript_lower:
                    keyword_position = transcript_lower.index("lama")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("lama") :
                    ]
                    logging.info(f"Processing lama command: {stripped_transcript}")
                    paste_transcript(stripped_transcript)
                    continue
            elif keyword_index == 3:
                if "google" in transcript_lower:
                    keyword_position = transcript_lower.index("google")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("google") :
                    ]
                    logging.info(f"Processing google command: {stripped_transcript}")
                    continue

            global_state["last_successful_operation"] = time.time()
            global_state["consecutive_failures"] = 0

        except Exception as e:
            logging.error(f"{RED}Process audio error: {e}{RESET}", exc_info=True)
            global_state["consecutive_failures"] += 1
            if global_state["consecutive_failures"] > 3:
                await asyncio.sleep(1)

        finally:
            global_state["is_processing"] = False

def validate_audio_buffer(audio_buffer):
    try:
        if audio_buffer is None or len(audio_buffer) == 0:
            logging.warning(f"{YELLOW}Empty audio buffer received{RESET}")
            return False
        if not isinstance(audio_buffer, np.ndarray):
            logging.error(
                f"{RED}Invalid audio buffer type: {type(audio_buffer)}{RESET}"
            )
            return False
        if len(audio_buffer) < sample_rate * 0.1:
            logging.warning(f"{YELLOW}Audio buffer too short{RESET}")
            return False
        return True
    except Exception as e:
        logging.error(f"{RED}Error validating audio buffer: {e}{RESET}", exc_info=True)
        return False

def create_wav_buffer(audio_buffer):
    try:
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, audio_buffer)
        byte_io.seek(0)
        return byte_io
    except Exception as e:
        logging.error(f"{RED}Error creating WAV buffer: {e}{RESET}", exc_info=True)
        return None

async def get_transcript_with_retries(byte_io, keyword_index, max_retries=3):
    for attempt in range(max_retries):
        try:
            transcript = await transcribe_with_groq_async(byte_io, keyword_index)
            if transcript:
                return transcript.lower()
        except Exception as e:
            logging.error(
                f"{RED}Transcription attempt {attempt + 1} failed: {e}{RESET}"
            )
            if attempt == max_retries - 1:
                return transcribe_with_local_model(byte_io, keyword_index)
            await asyncio.sleep(1)
    return None

async def process_transcript(transcript, keyword_index, audio_buffer):
    try:
        if keyword_index is None:
            if len(transcript) > 3:
                paste_transcript(transcript)
        elif keyword_index == 1 and "computer" in transcript:
            keyword_pos = transcript.index("computer")
            stripped = transcript[key_pos + len("computer") :].strip()
            if stripped:
                transcript_queue.put((stripped, keyword_index))
        elif keyword_index == 2 and "lama" in transcript:
            keyword_pos = transcript.index("lama")
            stripped = transcript[key_pos + len("lama") :].strip()
            if stripped:
                paste_transcript(stripped)
        else:
            logging.info(f"{YELLOW}No matching keyword found in transcript{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error processing transcript: {e}{RESET}", exc_info=True)

def start_listener():
    try:
        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        logging.info("Ctrl+C pressed. Exiting...")
    except Exception as e:
        logging.error(f"Error in start_listener: {e}", exc_info=True)

def beep(sound):
    try:
        frequency, duration = sound
        winsound.Beep(frequency, duration)
    except Exception as e:
        logging.error(f"Error in beep: {e}", exc_info=True)

"""
########  ########  ######  ######## ######## ##    ## 
##     ## ##       ##    ## ##          ##    
##     ## ##       ##       ##          ##    
########  ######    ######  ######      ##    
##   ##   ##             ## ##          ##    
##    ##  ##       ##    ## ##          ##    
##     ## ########  ######  ########    ##    
"""

def reset_state():
    try:
        global recording, play_pause_pressed, audio_buffer
        recording = False
        play_pause_pressed = False
        audio_buffer = np.array([], dtype="float32")
        threading.Thread(target=restore_volume_all).start()
        logging.info("State reset completed")
    except Exception as e:
        logging.error(f"Error in reset_state: {e}", exc_info=True)

def monitor_state():
    try:
        while True:
            if recording and time.time() - recording_start_time > 60:
                logging.error("Recording stuck in active state")
                reset_state()
            time.sleep(60)
    except Exception as e:
        logging.error(f"Error in monitor_state: {e}", exc_info=True)

"""
 ######  ##       #### ########  ########   #######     ###    ########  ########  
##    ## ##        ##  ##     ## ##     ## ##     ##   ## ##   ##     ## ##     ## 
##       ##        ##  ##     ## ##     ## ##     ##  ##   ##  ##     ## ##     ## 
##       ##        ##  ########  ########  ##     ## ##     ## ########  ##     ## 
##       ##        ##  ##        ##     ## ##     ## ######### ##   ##   ##     ## 
##    ## ##        ##  ##        ##     ## ##     ## ##     ## ##    ##  ##     ## 
 ######  ######## #### ##        ########   #######  ##     ## ##     ## ########  
"""

def set_clipboard_content(text):
    try:
        success = False
        while not success:
            try:
                win32clipboard.OpenClipboard(0)
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text)
                win32clipboard.CloseClipboard()
                success = True
            except win32clipboard.Error:
                logging.info("Failed to open the clipboard. Retrying in 1 second...")
                time.sleep(0.5)
    except Exception as e:
        logging.error(f"Error in set_clipboard_content: {e}", exc_info=True)

def get_clipboard_content():
    try:
        win32clipboard.OpenClipboard(0)
        data = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return data
    except win32clipboard.Error:
        logging.info("Failed to open the clipboard. Returning an empty string.")
        return ""
    except Exception as e:
        logging.error(f"Error in get_clipboard_content: {e}", exc_info=True)

def send_input(text):
    try:
        for char in text:
            ctypes.windll.user32.keybd_event(ord(char.upper()), 0, 0, 0)
            ctypes.windll.user32.keybd_event(ord(char.upper()), 0, 2, 0)
    except Exception as e:
        logging.error(f"Error in send_input: {e}", exc_info=True)

def paste_transcript(transcript):
    try:
        set_clipboard_content(transcript)
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
        beep(PASTE_BEEP)
        logging.info("Transcript pasted")
    except Exception as e:
        logging.error(f"Error in paste_transcript: {e}", exc_info=True)

def run_command_with_retry(transcript):
    try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if execute_command_run_with_tool(transcript):
                    return
            except Exception as e:
                logging.error(
                    f"Error in execute_command_run_with_tool: {e}", exc_info=True
                )
            time.sleep(2)
        logging.error(f"Failed to execute command after {max_retries} attempts")
    except Exception as e:
        logging.error(f"Error in run_command_with_retry: {e}", exc_info=True)

async def clean_transcript():
    try:
        while True:
            try:
                transcript, keyword_index = transcript_queue.get()
                logging.error(f"Transcript received in clean_transcript: {transcript}")
                if keyword_index == 1:
                    logging.error(
                        f"Transcript sent for execute_command_run_with_tool: {transcript}"
                    )
                    await execute_command_run_with_tool(transcript)
                elif keyword_index == 2:
                    pass
                elif keyword_index == 3:
                    logging.error(f"google assistant command: {transcript}")
                    await google_assistant(transcript)
                else:
                    logging.info(f"Unknown keyword index {keyword_index}")
                logging.info(
                    f"{BRIGHT_GREEN}Say 'Hey computer' or 'rey lama' wake word...{RESET}"
                )
            except Exception as e:
                logging.error(
                    f"An error occurred in clean_transcript: {e}", exc_info=True
                )
    except Exception as e:
        logging.error(f"Error in clean_transcript: {e}", exc_info=True)

"""
##     ##    ###    #### ##    ## 
###   ###   ## ##    ##  ###   ## 
#### ####  ##   ##   ##  ####  ## 
## ### ## ##     ##  ##  ## ## ## 
##     ## #########  ##  ##  #### 
##     ## ##     ##  ##  ##   ### 
##     ## ##     ## #### ##    ## 
"""

def display_pause_status():
    """Display current pause status in console"""
    while True:
        try:
            if check_pause_status():
                print(f"{RED}🔴 VOICE RECOGNITION PAUSED{RESET}")
            else:
                print(f"{GREEN}🟢 Voice recognition active - Say 'Hey computer' or wake word...{RESET}")
            time.sleep(10)
        except Exception as e:
            logging.error(f"Error in display_pause_status: {e}")
            time.sleep(10)

def start_thread(target, name):
    try:
        def run_with_restart():
            while True:
                try:
                    target()
                except Exception as e:
                    logging.error(
                        f"Thread {name} crashed with exception: {e}", exc_info=True
                    )
                    time.sleep(5)

        thread = threading.Thread(target=run_with_restart, name=name, daemon=True)
        thread.start()
        return thread
    except Exception as e:
        logging.error(f"Error in start_thread: {e}", exc_info=True)

global_state = {
    "last_successful_operation": time.time(),
    "consecutive_failures": 0,
    "is_processing": False,
}

def monitor_program_health():
    try:
        while True:
            current_time = time.time()
            if global_state["consecutive_failures"] > 5:
                logging.error(
                    f"{RED}Too many consecutive failures. Resetting state...{RESET}"
                )
                reset_all_states()

            if current_time - global_state["last_successful_operation"] > 30:
                logging.error(
                    f"{RED}No successful operations in 30 seconds. Resetting state...{RESET}"
                )
                reset_all_states()

            time.sleep(5)
    except Exception as e:
        logging.error(
            f"{RED}Error in monitor_program_health: {e}{RESET}", exc_info=True
        )

def reset_all_states():
    try:
        global recording, play_pause_pressed, audio_buffer, stream, wake_stream

        with recording_lock:
            recording = False

        play_pause_pressed = False
        audio_buffer = np.array([], dtype="float32")

        while not audio_buffer_queue.empty():
            try:
                audio_buffer_queue.get_nowait()
            except QueueEmpty:
                break

        while not transcript_queue.empty():
            try:
                transcript_queue.get_nowait()
            except QueueEmpty:
                break

        if stream and stream.active:
            try:
                stream.stop()
                stream.close()
            except:
                pass

        stream = sd.InputStream(
            callback=audio_callback,
            device=None,
            channels=1,
            samplerate=sample_rate,
            blocksize=int(sample_rate * 0.1),
        )
        stream.start()

        if wake_stream:
            try:
                wake_stream.stop_stream()
                wake_stream.close()
            except:
                pass
            wake_stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=16000,
            )
            wake_stream.start_stream()

        global_state["consecutive_failures"] = 0
        global_state["last_successful_operation"] = time.time()
        global_state["is_processing"] = False

        threading.Thread(target=restore_volume_all).start()
        logging.info(f"{GREEN}All states reset successfully{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error in reset_all_states: {e}{RESET}", exc_info=True)

def main():
    global stream
    global driver
    global driver_pid

    logging.info(
        f"{CYAN}wkey is active. Hold down {BOLD}{RECORD_KEY}{RESET}{CYAN} to start dictating.{RESET}"
    )

    def exception_handler(exc_type, exc_value, exc_traceback):
        logging.error(
            f"{RED}Unhandled exception:{RESET}",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = exception_handler

    try:
        start_thread(listen_for_wake_word, "WakeWordListener")
        start_thread(monitor_microphone_availability, "MicrophoneMonitor")
        loop2 = asyncio.new_event_loop()
        start_thread(
            lambda: run_asyncio_in_thread(loop2, clean_transcript()), "CleanTranscript"
        )
        loop = asyncio.new_event_loop()
        start_thread(
            lambda: run_asyncio_in_thread(loop, process_audio_async()), "ProcessAudio"
        )
        threading.Thread(target=start_driver, daemon=True).start()
        threading.Thread(target=display_pause_status, daemon=True).start()

        with stream:
            start_listener()

        while True:
            time.sleep(1)

    except Exception as e:
        logging.error(
            f"{RED}Critical error in main: {str(e)}\n{traceback.format_exc()}{RESET}"
        )
        reset_all_states()
    finally:
        try:
            if stream and stream.active:
                stream.stop()
                stream.close()
            cleanup()
            threading.Thread(target=restore_volume_all).start()
            logging.info(f"{YELLOW}Cleanup completed. Exiting...{RESET}")
            if driver:
                driver.quit()
        except Exception as e:
            logging.error(
                f"{RED}Error during cleanup: {str(e)}\n{traceback.format_exc()}{RESET}"
            )

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(
                f"{RED}Fatal error: {str(e)}\n{traceback.format_exc()}{RESET}"
            )
            time.sleep(5)