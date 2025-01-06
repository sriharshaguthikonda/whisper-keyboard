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
import io
import time
import threading
import winsound
import logging

# Configure logging with both debug and error levels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler("wkey_errors.log"),  # Also log to file
    ],
)

import pyautogui
import numpy as np
import sounddevice as sd
import pythoncom
from scipy.io.wavfile import write as wav_write

import groq
from groq import Groq

import queue


from pynput.keyboard import Controller as KeyboardController, Key, Listener
from dotenv import load_dotenv

from faster_whisper import WhisperModel
from voice_commands import (
    execute_command_fuzzy,
    execute_command_run_with_tool,
    start_driver,
    driver,
)  # , driver_pid
from pause_all import is_sound_playing_windows_processing

from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


import pyaudio


from openwakeword.model import Model

import subprocess


from voice_activity_detection import VoiceDetector

# Initial setup and global variables
initial_volume = None  # Variable to store initial volume
transcript_queue = queue.Queue()
audio_buffer_queue = queue.Queue()

MAX_TRANSCRIPTION_ATTEMPTS = 3
TRANSCRIPTION_TIMEOUT = 30  # seconds
BACKUP_QUEUE_SIZE = 5

backup_audio_queue = queue.Queue(maxsize=BACKUP_QUEUE_SIZE)
failed_transcription_queue = queue.Queue()

load_dotenv()
key_label = os.environ.get("WKEY", "f24")
RECORD_KEY = Key[key_label]
keyboard_controller = KeyboardController()
recording = False
stream = None
audio_buffer = np.array([], dtype="float32")
sample_rate = 16000
model = WhisperModel("small.en", device="cuda", num_workers=8)
groq_model = "distil-whisper-large-v3-en"
# "whisper-large-v3"
play_pause_pressed = False
something_is_playing = False


Hey_computer_STT_prompt = """ 
1. possible words in the transcript which will form a sentence : [open start menu show windows search desktop minimize everything settings lock screen the computer take screenshot capture file explorer explore files run dialog command task manager restore all calculator notepad word excel powerpoint outlook paint console powershell edge chrome firefox sound control panel audio volume up increase down decrease play media music stop next track song skip previous replay device disk management network connections system properties date time ping google check internet connection flush dns reset cache restart voicemeeter set display fusion monitor profile negative invert]. 

2. there should be no puncuation in the output and all lower case.
"""  # Optional


p = pyaudio.PyAudio()
wake_stream = p.open(
    format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=16000
)
wake_stream.start_stream()


# Define beep sounds
START_BEEP = (2080, 100)  # Frequency in Hz, Duration in ms
STOP_BEEP = (440, 100)  # Lower frequency for stop
PASTE_BEEP = (1060, 100)  # Intermediate frequency for paste

# Locks for synchronization
recording_lock = threading.Lock()
audio_data_lock = threading.Lock()

# Initialize VoiceDetector
vad_detector = VoiceDetector()
is_speech = True


# ANSI Color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Additional ANSI Color codes
ORANGE = "\033[38;5;214m"
PINK = "\033[38;5;198m"

# Additional ANSI Color codes
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"


"""
 ######  ######## ########  ########    ###    ##     ## 
##    ##    ##    ##     ## ##         ## ##   ###   ### 
##          ##    ##     ## ##        ##   ##  #### #### 
 ######     ##    ########  ######   ##     ## ## ### ## 
      ##    ##    ##   ##   ##       ######### ##     ## 
##    ##    ##    ##    ##  ##       ##     ## ##     ## 
 ######     ##    ##     ## ######## ##     ## ##     ## 
"""


PRE_RECORDING_DURATION = 2  # seconds
BUFFER_SIZE = PRE_RECORDING_DURATION * sample_rate
channels = 1

pre_recording_buffer = np.zeros((BUFFER_SIZE, channels), dtype=np.float32)
buffer_index = 0
audio_buffer = []


# Add error handling to audio callback
def audio_callback(indata, frames, time, status):
    """Callback function for audio recording."""
    try:
        global buffer_index, audio_buffer
        if status:
            logging.debug(f"Audio callback status: {status}")
        with recording_lock:
            if recording:
                audio_buffer = np.append(audio_buffer, indata.flatten())
            else:
                end_index = buffer_index + frames
                if end_index > BUFFER_SIZE:
                    end_index = BUFFER_SIZE
                pre_recording_buffer[buffer_index:end_index] = indata[
                    : end_index - buffer_index
                ]
                buffer_index = (buffer_index + frames) % BUFFER_SIZE
    except Exception as e:
        logging.error(f"Error in audio callback: {e}", exc_info=True)


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


# Add error handling to volume controls
def get_current_volume():
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume_level = volume.GetMasterVolumeLevelScalar()
        rounded_volume = round(volume_level, 2)
        return rounded_volume
    except Exception as e:
        logging.error(f"Error getting volume: {e}", exc_info=True)
        return 0.5  # Return default value


def set_volume(volume_level):
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(volume_level, None)
    except Exception as e:
        logging.error(f"Error setting volume: {e}", exc_info=True)


def decrease_volume_all():
    global initial_volume
    current_volume = get_current_volume()
    if initial_volume is None or current_volume != initial_volume:
        initial_volume = current_volume
    print(f"Decreasing volume from {initial_volume * 100}% to 10%")
    set_volume(0.1)  # Set volume to 10%


def restore_volume_all():
    global initial_volume
    if initial_volume is not None:
        print(f"Restoring volume to {initial_volume * 100}%")
        set_volume(initial_volume)  # Restore to initial volume
        initial_volume = None  # Reset initial volume after restoring


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


def start_recording():
    global stream
    global recording
    global play_pause_pressed
    global something_is_playing

    logging.debug("Starting recording process")
    # this thread has to go if something_is_playing check is happening below
    threading.Thread(target=decrease_volume_all()).start()

    try:
        if stream and stream.active:
            logging.debug("Stream is already active")
            pass
        else:
            try:
                device_info = sd.default.device
                logging.info(f"{CYAN}Using audio device: {device_info}{RESET}")
                logging.debug(f"Initializing stream with device: {device_info}")
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
                    f"Failed to initialize audio stream: {str(e)}", exc_info=True
                )
                logging.info(f"{RED}Failed to start stream: {e}{RESET}")
                time.sleep(2)
    except NameError:
        logging.error(
            "NameError in start_recording - stream not defined", exc_info=True
        )
        pass

    if something_is_playing:
        # print("Stream started")
        decrease_volume_all()
        play_pause_pressed = True
    else:
        # print("Stream started")
        pass

    beep(START_BEEP)
    with recording_lock:
        recording = True
    logging.info(f"{BRIGHT_GREEN}Listening...{RESET}")


"""
 ######  ########  #######  ########     ########  ########  ######  
##    ##    ##    ##     ## ##     ##    ##     ## ##       ##    ## 
##          ##    ##     ## ##     ##    ##     ## ##       ##       
 ######     ##    ##     ## ########     ########  ######   ##       
      ##    ##    ##     ## ##           ##   ##   ##       ##       
##    ##    ##    ##     ## ##           ##    ##  ##       ##    ## 
 ######     ##     #######  ##           ##     ## ########  ######  
"""


# Add error handling to VAD
def adjust_vad_threshold():
    try:
        if len(audio_buffer) > 0:
            rms = np.sqrt(np.mean(audio_buffer**2))
        else:
            rms = 0.0

        if rms < 0.01:
            return 0.3
        elif rms < 0.05:
            return 0.5
        elif rms < 0.1:
            return 0.7
        else:
            return 0.9
    except Exception as e:
        logging.error(f"Error in VAD threshold calculation: {e}", exc_info=True)
        return 0.5  # Return default threshold


def stop_recording(keyword_index):
    logging.debug(f"Stopping recording with keyword_index: {keyword_index}")
    global stream, recording, play_pause_pressed, audio_buffer, sample_rate, is_speech

    hard_stop_limit = 15  # Maximum recording time in seconds
    silent_time = 0
    recording_start_time = time.time()

    if keyword_index == 1:
        logging.debug("Using short stop delay for keyword command")
        stop_delay_threshold = (
            0.5  # Time to wait before stopping after no speech is detected
        )
    elif keyword_index is None:
        transcript = ""
        logging.debug("Processing immediate stop for F24 key")
        # stop_delay_threshold = (0  # Time to wait before stopping after no speech is detected )
        # pre_recording_data = np.roll(pre_recording_buffer_f24, -buffer_index, axis=0).flatten()
        #         audio_buffer_queue.put((audio_buffer, keyword_index))
        transcript = transcribe_with_retries(audio_buffer, keyword_index)

        set_clipboard_content(transcript)

        pyautogui.hotkey("ctrl", "v")
        beep(PASTE_BEEP)
        print("Transcript pasted")

        threading.Thread(target=restore_volume_all()).start()

        # clearing the audio buffer - if not it will cause concat transcripts
        audio_buffer = np.array([], dtype="float32")

        if play_pause_pressed:
            threading.Thread(target=restore_volume_all()).start()
            play_pause_pressed = False

        with recording_lock:
            recording = False
        print(f"{MAGENTA}Recording stopped. Processing audio...{RESET}")

        transcript = ""
        return
    else:
        logging.debug("Using standard stop delay")
        stop_delay_threshold = (
            2  # Time to wait before stopping after no speech is detected
        )

    while silent_time < stop_delay_threshold:
        if stream.active:
            if isinstance(audio_buffer, list):
                audio_buffer = np.array(audio_buffer)

            # Get the last frames of audio for VAD analysis (30ms frame)
            frame_duration = 30  # ms
            frame_size = int(sample_rate * frame_duration / 1000)
            audio_frame = audio_buffer[-frame_size:]

            # Convert to int16 format required by webrtcvad
            audio_int16 = (audio_frame * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            try:
                # Use the VoiceDetector instance for voice detection
                is_speech = vad_detector.vad.is_speech(
                    audio_bytes, vad_detector.sample_rate
                )

            except Exception as e:
                logging.error(f"{RED}VAD error: {e}{RESET}", exc_info=True)
                silent_time += 0.1  # Increment on error

            if is_speech:
                silent_time = 0  # Reset silent time if speech is detected
                logging.info(f"{PINK}Voice detected, continuing recording...{RESET}")
            else:
                silent_time += 0.1  # Increment silent time if no speech is detected

            # Check if the hard stop limit is reached
            if time.time() - recording_start_time > hard_stop_limit:
                logging.info(
                    f"{ORANGE}Hard stop limit reached, stopping recording.{RESET}"
                )
                break

            time.sleep(0.1)

    logging.info(f"{BRIGHT_BLUE}Processing audio...{RESET}")
    pre_recording_data = np.roll(pre_recording_buffer, -buffer_index, axis=0).flatten()

    # Convert main recording to numpy array
    audio_buffer = np.concatenate(
        [pre_recording_data, audio_buffer],
        axis=0,
    )
    audio_buffer_queue.put((audio_buffer, keyword_index))

    # this thread has to go if play_pause_pressed check is happening below!
    threading.Thread(target=restore_volume_all()).start()

    # clearing the audio buffer - if not it will cause concat transcripts
    audio_buffer = np.array([], dtype="float32")

    if play_pause_pressed:
        restore_volume_all()
        play_pause_pressed = False

    beep(STOP_BEEP)
    with recording_lock:
        recording = False
    logging.info(f"{BRIGHT_CYAN}Transcribing...{RESET}")


def on_press(key):
    if key == RECORD_KEY and not recording:
        threading.Thread(target=start_recording).start()


def on_release(key):
    if key == RECORD_KEY and recording:
        threading.Thread(target=stop_recording, args=(None,)).start()


"""
 ######     ###    ##     ## ######## 
##    ##   ## ##   ##     ## ##       
##        ##   ##  ##     ## ##       
 ######  ##     ## ##     ## ######   
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
        # Ensure the directory exists
        if not os.path.exists(directory):
            logging.info(f"cannot save data to {directory} because it does not exist")
            return

        # Construct the base filename
        base_filename = os.path.join(
            directory, f"{type_of_audio}_{keyword_index}_recording.wav"
        )
        filename = base_filename
        counter = 1

        # Increment filename if it already exists
        while os.path.exists(filename):
            filename = os.path.join(
                directory, f"{type_of_audio}_{keyword_index}_recording_{counter}.wav"
            )
            counter += 1

        # Ensure audio data is in the range [-1.0, 1.0]
        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val  # Normalize the data if necessary

        # Convert audio data to int16 format (expected by wav_write)
        audio_data_int16 = np.int16(audio_data * 32767)

        # Save the audio file using scipy.io.wavfile.write
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


# Add error handling to device initialization
def check_microphone():
    try:
        devices = sd.query_devices()
        for device in devices:
            if device["max_input_channels"] > 0:
                return True
        return False
    except Exception as e:
        logging.error(f"Error checking microphone: {e}", exc_info=True)
        return False


def reinitialize_pyaudio():
    global p
    p.terminate()
    p = pyaudio.PyAudio()


def monitor_microphone_availability():
    global wake_stream, p
    while True:
        if not check_microphone():
            print("No microphone detected. Pausing wake word detection...")
            if wake_stream:
                try:
                    wake_stream.stop_stream()
                    wake_stream.close()
                except OSError as e:
                    print(f"Error stopping stream: {e}")
                finally:
                    wake_stream = None
        else:
            if wake_stream is None:
                print("Microphone detected. Resuming wake word detection...")
                try:
                    wake_stream.start_stream()
                except OSError as e:
                    print(f"Failed to restart wake stream: {e}")
                    reinitialize_pyaudio()  # Reinitialize PyAudio
                    wake_stream = None
                except Exception as e:
                    print(f"Unexpected error: {e}")

        time.sleep(10)


# Hardcoded model paths
MODEL_PATHS = [
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_llama.onnx",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_computer10.onnx",
]

# Load the OpenWakeWord models
# Load the OpenWakeWord models with VAD threshold
owwModel = Model(
    wakeword_models=MODEL_PATHS, inference_framework="onnx", vad_threshold=0.5
)


CHUNK = 5120  # Optimal chunk size for OpenWakeWord
# originally 1280
#  you will have to change this also below recent_predictions originally -8

# Define individual thresholds for each wake word model
THRESHOLDS = {
    0: 0.1,  # Threshold for "hey_lama"
    1: 0.1,  # Threshold for "hey_computer10"
}

COOLDOWN_TIME = 6  # Cooldown time in seconds after detecting a wake word
last_detection_time = 0  # Time when the last wake word was detected


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
    global wake_stream, last_detection_time, recording

    logging.info(f"{YELLOW}Listening for wake words...{RESET}")

    while True:
        try:
            if wake_stream:
                data = wake_stream.read(CHUNK, exception_on_overflow=False)
                logging.debug(f"Read chunk of size: {len(data)}")

                pcm = np.frombuffer(data, dtype=np.int16)

                # Check for wake word using OpenWakeWord
                prediction = owwModel.predict(pcm)
                keyword_index = -1  # Default to no detection
                max_score = 0.0

                # Limit to only the most recent prediction scores for speed
                recent_predictions = list(owwModel.prediction_buffer.values())[-3:]

                # Find the highest score among detected keywords
                for idx, scores in enumerate(recent_predictions):
                    if scores[-1] > max_score:  # Check last score for this prediction
                        max_score = scores[-1]
                        keyword_index = idx

                # Use individual threshold for each wake word
                current_time = time.time()
                if (
                    keyword_index >= 0
                    and max_score
                    > THRESHOLDS.get(
                        keyword_index, 0.4
                    )  # Use threshold specific to keyword_index
                    and (current_time - last_detection_time) > COOLDOWN_TIME
                    and not recording
                ):
                    logging.debug(f"Wake word detected with score: {max_score}")
                    last_detection_time = current_time  # Update the last detection time

                    if keyword_index == 0:  # Custom wake word: "hey_llama2 "
                        logging.info(
                            f"{BRIGHT_MAGENTA}Wake word 'hey_llama' detected!{RESET}"
                        )
                        threading.Thread(target=start_recording).start()
                        time.sleep(3)
                        threading.Thread(
                            target=stop_recording, args=(keyword_index,)
                        ).start()
                    elif keyword_index == 1:  # Custom wake word: "hey_computer10"
                        logging.info(
                            f"{BRIGHT_YELLOW}Wake word 'hey_computer10' detected!{RESET}"
                        )
                        threading.Thread(target=start_recording).start()
                        # time.sleep(1)
                        threading.Thread(target=stop_recording, args=(1,)).start()
                    else:
                        logging.info(
                            f"{ORANGE}Unknown wake word detected: {keyword_index}{RESET}"
                        )

            else:
                logging.debug("No wake stream available")
                logging.info(f"{PINK}Waiting for microphone...{RESET}")
                time.sleep(5)

        except OSError as e:
            logging.error(
                f"Critical error in wake word detection: {str(e)}", exc_info=True
            )
            print(f"Audio stream error: {e}")
            if wake_stream:
                try:
                    if wake_stream.is_active():
                        wake_stream.stop_stream()
                    wake_stream.close()
                except OSError:
                    print("Stream already closed or failed to close.")

            wake_stream = None

            # Attempt to reinitialize the wake word detection after an error
            time.sleep(10)  # Wait before retrying to avoid rapid retry loops


def cleanup():
    global wake_stream
    try:
        if wake_stream:
            try:
                if wake_stream.is_active():
                    wake_stream.stop_stream()
                wake_stream.close()
            except OSError as e:
                print(f"Error during cleanup: {e}")
            wake_stream = None
        # porcupine.delete()
        p.terminate()
        print("Cleanup completed.")
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}", exc_info=True)


"""
 ######   ########   #######   #######  
##    ##  ##     ## ##     ## ##     ## 
##        ##     ## ##     ## ##     ## 
##   #### ########  ##     ## ##     ## 
##    ##  ##   ##   ##     ## ##  ## ## 
##    ##  ##    ##  ##     ## ##    ##  
 ######   ##     ##  #######   ##### ## 
"""


api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)


def transcribe_with_groq(audio_buffer, keyword_index):
    transcription = ""
    if keyword_index == 1:
        prompt = Hey_computer_STT_prompt
    else:
        prompt = None

    try:
        # Convert the audio buffer (NumPy array) to a byte stream in WAV format
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, audio_buffer)
        byte_io.seek(0)  # Rewind to the beginning of the byte stream

        # Send the byte stream directly to the Groq API - removed await
        transcription = client.audio.transcriptions.create(
            file=("audio_buffer.wav", byte_io.read()),  # Use in-memory byte stream
            model=groq_model,
            prompt=prompt,
            response_format="json",
            language="en",
            temperature=0.0,
        )
        return transcription.text
    except Exception as e:
        logging.error(f"Groq API error: {str(e)}", exc_info=True)
        print(f"Groq API error: {e}")
        raise


def transcribe_with_local_model(audio_buffer, keyword_index):
    try:
        transcription = ""
        # Define prompt based on keyword_index
        if keyword_index == 1:
            prompt = Hey_computer_STT_prompt
        else:
            prompt = None

        try:
            logging.info("using WhisperModel on CUDA")
            # Convert audio buffer (NumPy array) to WAV format in-memory
            byte_io = io.BytesIO()
            wav_write(byte_io, sample_rate, audio_buffer)
            byte_io.seek(0)

            # Decode audio
            segments, _ = model.transcribe(byte_io, language="en")

            # Combine transcribed text from all segments
            transcription = " ".join(segment.text for segment in segments)
            logging.info(transcription)
            return transcription
        except Exception as e:
            logging.info(f"Faster Whisper error: {e}")
            return "Transcription failed"
    except Exception as e:
        logging.error(f"Error in transcribe_with_local_model: {e}", exc_info=True)


def transcribe_with_retries(
    audio_buffer, keyword_index, max_attempts=MAX_TRANSCRIPTION_ATTEMPTS
):
    """Attempt transcription multiple times with fallback"""
    for attempt in range(max_attempts):
        try:
            logging.debug(f"Transcription attempt {attempt + 1}/{max_attempts}")

            # Try Groq first with a timeout using threading.Timer
            transcription_done = threading.Event()
            transcription_result = [None]
            transcription_error = [None]

            def transcribe():
                try:
                    transcription_result[0] = transcribe_with_groq(
                        audio_buffer, keyword_index
                    )
                    transcription_done.set()
                except Exception as e:
                    transcription_error[0] = e
                    transcription_done.set()

            transcription_thread = threading.Thread(target=transcribe)
            transcription_thread.daemon = True
            transcription_thread.start()

            # Wait for transcription with timeout
            if not transcription_done.wait(TRANSCRIPTION_TIMEOUT):
                logging.error("Groq transcription timed out")
                # If timeout, try next attempt
                continue

            # Check if transcription succeeded
            if transcription_error[0]:
                raise transcription_error[0]
            if transcription_result[0]:
                return transcription_result[0]

            # If we get here with no result, try next attempt
            continue

        except Exception as e:
            logging.error(
                f"Transcription attempt {attempt + 1} failed: {e}", exc_info=True
            )
            if attempt == max_attempts - 1:
                # On last attempt, try local model
                logging.info(f"{YELLOW}Falling back to local transcription{RESET}")
                return transcribe_with_local_model(audio_buffer, keyword_index)

    return None  # If all attempts fail


"""
   ###     ######  ##    ## ##    ##  ######  
  ## ##   ##    ##  ##  ##  ###   ## ##    ## 
 ##   ##  ##         ####   ####  ## ##       
##     ##  ######     ##    ## ## ## ##       
#########       ##    ##    ##  #### ##       
##     ## ##    ##    ##    ##   ### ##    ## 
##     ##  ######     ##    ##    ##  ######  
"""


def process_audio_async():
    logging.debug("Starting async audio processing")

    while True:
        try:
            audio_buffer_for_processing, keyword_index = audio_buffer_queue.get(
                timeout=5
            )

            if audio_buffer_for_processing is None:
                logging.debug("Received stop signal")
                break

            # Store backup copy of audio before processing
            try:
                backup_audio_queue.put_nowait(
                    (audio_buffer_for_processing.copy(), keyword_index)
                )
            except queue.Full:
                backup_audio_queue.get()  # Remove oldest item if queue is full
                backup_audio_queue.put(
                    (audio_buffer_for_processing.copy(), keyword_index)
                )

            try:
                logging.info(f"{CYAN}Transcribing audio...{RESET}")
                transcript = transcribe_with_local_model(
                    audio_buffer_for_processing, keyword_index
                )

                if not transcript or transcript.isspace():
                    raise ValueError("Empty transcript received")

                # Process successful transcript
                transcript_lower = transcript.lower()
                if (
                    "computer" in transcript_lower or "lama" in transcript_lower
                ) and keyword_index is not None:  # Adjust the threshold as needed
                    # Find the index of the keyword
                    if "computer" in transcript_lower:
                        keyword_position = transcript_lower.index("computer")
                    else:
                        keyword_position = transcript_lower.index("lama")

                    # Strip the part of the transcript before the keyword
                    stripped_transcript = transcript[
                        keyword_position:
                    ]  # Keep from the keyword to the end

                    # Put the stripped transcript on the queue
                    transcript_queue.put((stripped_transcript, keyword_index))

                    # Start the audio saving thread
                    threading.Thread(
                        target=save_audio,
                        args=(
                            audio_buffer_for_processing,
                            keyword_index,
                            "J:\\Openwakeword_whisper_keyboard_training_data_hotword\\train",
                            sample_rate,
                            "true_positive",
                        ),
                    ).start()

                elif keyword_index is None:
                    # transcript_queue.put((transcript, keyword_index))
                    # this is being handled in the stop recording functino itself so we are skipping here
                    pass
                else:
                    threading.Thread(
                        target=save_audio,
                        args=(
                            audio_buffer_for_processing,
                            keyword_index,
                            "J:\\Openwakeword_whisper_keyboard_training_data_hotword\\train",
                            sample_rate,
                            "false_positive",
                        ),
                    ).start()
                print(transcript)

                logging.info(f"{GREEN}Transcription completed: {transcript}{RESET}")

            except Exception as e:
                logging.error(f"Transcription failed: {e}", exc_info=True)

                # Recover audio from backup queue if needed
                try:
                    backup_audio, backup_keyword = backup_audio_queue.get_nowait()
                    failed_transcription_queue.put((backup_audio, backup_keyword))
                    logging.info(
                        f"{YELLOW}Audio saved to failed transcription queue{RESET}"
                    )
                except queue.Empty:
                    logging.error("No backup audio available")

        except queue.Empty:
            continue
        except Exception as e:
            logging.error(
                f"Critical error in audio processing: {str(e)}", exc_info=True
            )


def start_listener():
    try:
        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        print("Ctrl+C pressed. Exiting...")


def beep(sound):
    frequency, duration = sound
    # Create and start a new thread for playing the sound
    # thread = threading.Thread(target=lambda: winsound.Beep(frequency, duration))
    # thread.start()
    winsound.Beep(frequency, duration)
    # Optionally join the thread if you want to wait for it to complete
    # thread.join()


"""
 ######  ##       #### ########  ########   #######     ###    ########  ########  
##    ## ##        ##  ##     ## ##     ## ##     ##   ## ##   ##     ## ##     ## 
##       ##        ##  ##     ## ##     ## ##     ##  ##   ##  ##     ## ##     ## 
##       ##        ##  ########  ########  ##     ## ##     ## ########  ##     ## 
##       ##        ##  ##        ##     ## ##     ## ######### ##   ##   ##     ## 
##    ## ##        ##  ##        ##     ## ##     ## ##     ## ##    ##  ##     ## 
 ######  ######## #### ##        ########   #######  ##     ## ##     ## ########  
"""


# Add error handling to clipboard operations
def set_clipboard_content(text):
    try:
        subprocess.run("clip", text=True, input=text)
    except Exception as e:
        logging.error(f"Error setting clipboard content: {e}", exc_info=True)
        # Try alternative method
        try:
            import win32clipboard

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text)
            win32clipboard.CloseClipboard()
        except Exception as e2:
            logging.error(f"Backup clipboard method failed: {e2}", exc_info=True)


def get_clipboard_content():
    return subprocess.run(
        ["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True
    ).stdout.strip()


def clean_transcript():
    while True:
        try:
            transcript, keyword_index = transcript_queue.get()

            if keyword_index == 1:
                if not execute_command_run_with_tool(transcript):
                    execute_command_fuzzy(transcript)
                else:
                    pass
            else:
                set_clipboard_content(transcript)
                time.sleep(0.5)  # Ensure clipboard is updated
                pyautogui.hotkey("ctrl", "v")
                beep(PASTE_BEEP)
                print("Transcript pasted")

        except Exception as e:
            logging.error(
                f"An error occurred in clean_transcript: {str(e)}", exc_info=True
            )
            print(f"An error occurred in clean_transcript: {e}")


"""
##     ##    ###    #### ##    ## 
###   ###   ## ##    ##  ###   ## 
#### ####  ##   ##   ##  ####  ## 
## ### ## ##     ##  ##  ## ## ## 
##     ## #########  ##  ##  #### 
##     ## ##     ##  ##  ##   ### 
##     ## ##     ## #### ##    ## 
"""


def process_failed_transcriptions():
    """Background worker to retry failed transcriptions"""
    while True:
        try:
            audio, keyword_index = failed_transcription_queue.get(timeout=30)
            logging.info(f"{YELLOW}Retrying failed transcription{RESET}")

            try:
                transcript = transcribe_with_local_model(audio, keyword_index)
                if transcript:
                    transcript_queue.put((transcript, keyword_index))
                    logging.info(f"{GREEN}Recovery successful{RESET}")
            except Exception as e:
                logging.error(f"Recovery failed: {e}", exc_info=True)

        except queue.Empty:
            continue


def main():
    global stream
    global driver
    global driver_pid

    logging.debug("Initializing main application")
    logging.info(
        f"{BOLD}{GREEN}wkey is active. Hold down {RECORD_KEY} to start dictating.{RESET}"
    )

    try:
        logging.debug("Starting background threads")
        # Start the microphone monitoring thread
        threading.Thread(target=monitor_microphone_availability, daemon=True).start()

        # threading.Thread(target=monitor_sound_processing, daemon=True).start()
        threading.Thread(target=clean_transcript, daemon=True).start()
        threading.Thread(target=process_audio_async, daemon=True).start()
        threading.Thread(target=listen_for_wake_word, daemon=True).start()
        threading.Thread(target=start_driver, daemon=True).start()
        threading.Thread(target=process_failed_transcriptions, daemon=True).start()

        with stream:
            start_listener()
    except KeyboardInterrupt:
        logging.info("Application terminated by user")
        logging.debug("Received keyboard interrupt")
        logging.info(f"{YELLOW}Ctrl+C pressed. Exiting...{RESET}")
    except Exception as e:
        logging.error(f"Critical application error: {str(e)}", exc_info=True)
    finally:
        logging.debug("Performing cleanup")
        if stream:
            if stream.active:
                stream.stop()
            stream.close()
        cleanup()
        restore_volume_all()
        logging.info(f"{MAGENTA}Cleanup completed. Exiting...{RESET}")
        # Clean up (close the browser)
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
