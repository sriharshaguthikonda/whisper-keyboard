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
import pyautogui

import numpy as np
import sounddevice as sd
import pythoncom
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
)  # , driver_pid
from pause_all import is_sound_playing_windows_processing


import pyaudio

from openwakeword.model import Model

from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=6)  # Change max_workers as needed


import win32clipboard
import ctypes

# Add to imports section
import webrtcvad
from voice_activity_detection import VoiceDetector

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("whisper_keyboard.log"),
        logging.StreamHandler(),  # This will also print to console
    ],
)

# ANSI Color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Initial setup and global variables
initial_volume = None  # Variable to store initial volume
transcript_queue = queue.Queue()
audio_buffer_queue = queue.Queue()

# Initialize VoiceDetector
vad_detector = VoiceDetector()

load_dotenv()


key_label = os.environ.get("WKEY", "f24")
RECORD_KEY = Key[key_label]

"""

# Get the key label from environment variables, default to 'f24' if not set
key_label = os.environ.get("WKEY", "ctrl_r")  # Use 'ctrl_r' for right control key

# Map the key label to the actual Key
RECORD_KEY = getattr(Key, key_label, None)

"""
keyboard_controller = KeyboardController()
recording = False
stream = None
audio_buffer = np.array([], dtype="float32")
sample_rate = 16000

# Check if CUDA is available
if torch.cuda.is_available():
    model = WhisperModel("small.en", device="cuda", num_workers=8)
    logging.info("Initialized WhisperModel on CUDA")
else:
    logging.warning(
        "CUDA device not available. Please ensure your system supports CUDA."
    )

# groq_model = "distil-whisper-large-v3-en"
groq_model = "whisper-large-v3-turbo"
# groq_model = "whisper-large-v3"
play_pause_pressed = False
something_is_playing = False


Hey_computer_STT_prompt = None
"""
Hey_computer_STT_prompt = "
1. possible words in the transcript which will form a sentence : [open start menu show windows search desktop minimize everything settings lock screen the take screenshot capture file explorer explore files run dialog command task manager restore all calculator notepad word excel powerpoint outlook paint console powershell edge chrome firefox sound control panel audio volume up increase down decrease play media music stop next track song skip previous replay device disk management network connections system properties date time ping google check internet connection flush dns reset cache restart voicemeeter set display fusion monitor profile negative invert]. 

2. there should be no puncuation in the output and all lower case.
"  # Optional
"""

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


"""
 ######  ######## ########  ########    ###    ##     ## 
##    ##    ##    ##     ## ##         ## ##   ###   ### 
##          ##    ##     ## ##        ##   ##  #### #### 
 ######     ##    ########  ######   ##     ## ## ### ## 
      ##    ##    ##   ##   ##       ######### ##     ## 
##    ##    ##    ##    ##  ##       ##     ## ##     ## 
 ######     ##    ##     ## ######## ##     ## ##     ## 
"""


PRE_RECORDING_DURATION = 3  # seconds
BUFFER_SIZE = PRE_RECORDING_DURATION * sample_rate
channels = 1

# for pre_recording_buffer_f24 for 2 second buffer is equlal to 16000 ie sample_rate*2
pre_recording_buffer = np.zeros((BUFFER_SIZE, channels), dtype=np.float32)
pre_recording_buffer_f24 = np.zeros(
    (sample_rate * 2, channels), dtype=np.float32
)  # 1 second buffer for F24
buffer_index = 0
audio_buffer = []


def audio_callback(indata, frames, time, status):
    """Callback function for audio recording."""
    global buffer_index
    global audio_buffer

    if status:
        logging.warning(f"Audio callback status: {status}")
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
    current_volume = get_volume()
    if initial_volume is None or current_volume != initial_volume:
        initial_volume = current_volume
    print(f"Decreasing volume from {initial_volume * 100}% to 10%")
    set_volume(0.1)  # Set volume to 10%


def restore_volume_all():
    global initial_volume
    if initial_volume is not None:
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

    # this thread has to go if something_is_playing check is happening below
    decrease_volume_all()

    try:
        if stream and stream.active:
            # print("stream is active")
            pass
        else:
            try:
                device_info = sd.default.device
                logging.info(f"Using device: {device_info}")
                stream = sd.InputStream(
                    callback=audio_callback,
                    device=None,
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=int(sample_rate * 0.1),
                )
                stream.start()
            except Exception as e:
                logging.info(f"Failed to start stream: {e}")
                time.sleep(2)
    except NameError:
        pass

    if something_is_playing:
        # logging.info("Stream started")
        decrease_volume_all()
        play_pause_pressed = True
    else:
        # logging.info("Stream started")
        pass

    beep(START_BEEP)
    with recording_lock:
        recording = True
    logging.info(f"{CYAN}Listening...{RESET}")


"""
 ######  ########  #######  ########     ########  ########  ######  
##    ##    ##    ##     ## ##     ##    ##     ## ##       ##    ## 
##          ##    ##     ## ##     ##    ##     ## ##       ##       
 ######     ##    ##     ## ########     ########  ######   ##       
      ##    ##    ##     ## ##           ##   ##   ##       ##       
##    ##    ##    ##     ## ##           ##    ##  ##       ##    ## 
 ######     ##     #######  ##           ##     ## ########  ######  
"""


global recording_start_time


def adjust_vad_threshold():
    global audio_buffer  # Access the audio buffer to analyze current noise levels

    # Calculate RMS value of the audio buffer to assess noise levels
    if len(audio_buffer) > 0:
        rms = np.sqrt(np.mean(audio_buffer**2))  # Calculate RMS
    else:
        rms = 0.0  # Default to 0 if no audio

    # Define thresholds based on RMS values
    if rms < 0.01:  # Low noise level
        return 0.3  # Lower threshold for higher sensitivity
    elif rms < 0.05:  # Moderate noise level
        return 0.5  # Default threshold
    elif rms < 0.1:  # High noise level
        return 0.7  # Raise threshold for less sensitivity
    else:  # Very high noise level
        return 0.9  # Very high threshold to avoid false positives


def stop_recording(keyword_index):
    global \
        stream, \
        recording, \
        play_pause_pressed, \
        audio_buffer, \
        sample_rate, \
        recording_start_time, \
        vad_detector

    hard_stop_limit = 5  # Maximum recording time in seconds
    silent_time = 0
    recording_start_time = time.time()

    pre_recording_data = np.roll(pre_recording_buffer, -buffer_index, axis=0).flatten()

    if keyword_index == 1:
        stop_delay_threshold = (
            1  # Time to wait before stopping after no speech is detected
        )
    elif keyword_index == 2:
        stop_delay_threshold = (
            1  # Time to wait before stopping after no speech is detected
        )
    elif keyword_index is None:
        stop_delay_threshold = (
            0  # Time to wait before stopping after no speech is detected
        )
        pre_recording_data = np.roll(
            pre_recording_buffer_f24, -buffer_index, axis=0
        ).flatten()
    else:
        stop_delay_threshold = (
            2  # Time to wait before stopping after no speech is detected
        )

    while silent_time <= stop_delay_threshold:
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

                if is_speech:
                    silent_time = 0  # Reset silent time if speech is detected
                    logging.info("Voice detected, continuing recording...")
                else:
                    silent_time += 0.1  # Increment silent time if no speech is detected

            except Exception as e:
                logging.error(f"VAD error: {e}")
                silent_time += 0.1  # Increment on error

            # Check if the hard stop limit is reached
            if time.time() - recording_start_time > hard_stop_limit:
                logging.info("Hard stop limit reached, stopping recording.")
                break

            time.sleep(0.1)

    # Convert main recording to numpy array
    audio_buffer = np.concatenate(
        [pre_recording_data, audio_buffer],
        axis=0,
    )
    audio_buffer_queue.put((audio_buffer, keyword_index))

    # this thread has to go if play_pause_pressed check is happening below!
    restore_volume_all()

    # clearing the audio buffer - if not it will cause concat transcripts
    audio_buffer = np.array([], dtype="float32")

    if play_pause_pressed:
        restore_volume_all()
        play_pause_pressed = False

    beep(STOP_BEEP)
    with recording_lock:
        recording = False
    logging.info(f"{MAGENTA}Transcribing...{RESET}")


# Define a debounce time (in seconds) to prevent rapid key presses
DEBOUNCE_TIME = 0.5  # Adjust this value as needed
last_key_press_time = 0


def on_press(key):
    global last_key_press_time
    current_time = time.time()
    if key == RECORD_KEY and not recording:
        if current_time - last_key_press_time > DEBOUNCE_TIME:
            last_key_press_time = current_time
            start_recording()


def on_release(key):
    global last_key_press_time
    current_time = time.time()
    if key == RECORD_KEY and recording:
        if current_time - last_key_press_time > DEBOUNCE_TIME:
            last_key_press_time = current_time
            stop_recording(None)


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
    # Ensure the directory exists
    if not os.path.exists(directory):
        logging.info(f"cannot save data to {directory} because it does not exist")
        """os.makedirs(directory)"""
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


"""
 #######  ##      ## ##      ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
 #######   ###  ###   ###  ###  
"""


def check_microphone():
    """Check if a microphone is available."""
    devices = sd.query_devices()
    for device in devices:
        if device["max_input_channels"] > 0:
            return True
    return False


def reinitialize_pyaudio():
    global p
    p.terminate()
    p = pyaudio.PyAudio()


def monitor_microphone_availability():
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
            if wake_stream is None:
                logging.info(
                    f"{GREEN}Microphone detected. Resuming wake word detection...{RESET}"
                )
                try:
                    wake_stream.start_stream()
                except OSError as e:
                    logging.info(f"Failed to restart wake stream: {e}")
                    reinitialize_pyaudio()  # Reinitialize PyAudio
                    wake_stream = None
                except Exception as e:
                    logging.info(f"Unexpected error: {e}")

        time.sleep(10)


# Hardcoded model paths
MODEL_PATHS = [
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_llama2.onnx",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_computer10.onnx",
"""    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\rey_lama.onnx","""
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_lama.onnx",
]

# Load the OpenWakeWord models
# Load the OpenWakeWord models with VAD threshold
owwModel = Model(
    wakeword_models=MODEL_PATHS, inference_framework="onnx", vad_threshold=0.5
)


CHUNK = 5120  # Optimal chunk size for OpenWakeWord
# originally 1280


# Define individual thresholds for each wake word model
THRESHOLDS = {
    0: 0.1,  # Threshold for "hey_lama"
    1: 0.1,  # Threshold for "hey_computer10"
    2: 0.1,
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
    logging.info(f"{GREEN}Listening for wake words...{RESET}")

    while True:
        try:
            if wake_stream:
                data = wake_stream.read(CHUNK, exception_on_overflow=False)
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
                    last_detection_time = current_time  # Update the last detection time

                    if keyword_index == 0:  # Custom wake word: "hey_llama2 "
                        """logging.info("\033[92mCustom wake word 'hey_llama2' detected!\033[0m")
                        start_recording()
                        time.sleep(3)
                        stop_recording(keyword_index)"""
                    elif keyword_index == 1:  # Custom wake word: "hey_computer9"
                        logging.info(
                            f"{BRIGHT_WHITE}{BOLD}Custom wake word 'hey_computer9' detected!{RESET}"
                        )
                        start_recording()
                        # time.sleep(1)
                        stop_recording(keyword_index)
                    elif keyword_index == 2:  # Custom wake word: "hey_llama2 "
                        logging.info(
                            f"{BRIGHT_WHITE}{BOLD}Custom wake word 'rey_lama' detected!{RESET}"
                        )
                        start_recording()
                        time.sleep(3)
                        stop_recording(keyword_index)
                    else:
                        logging.info("Unknown wake word detected!", keyword_index)

            else:
                logging.info("Waiting for microphone...")
                time.sleep(5)

        except OSError as e:
            logging.info(f"Audio stream error: {e}")
            if wake_stream:
                try:
                    if wake_stream.is_active():
                        wake_stream.stop_stream()
                    wake_stream.close()
                except OSError:
                    logging.info("Stream already closed or failed to close.")

            wake_stream = None

            # Attempt to reinitialize the wake word detection after an error
            time.sleep(10)  # Wait before retrying to avoid rapid retry loops


def cleanup():
    global wake_stream
    if wake_stream:
        try:
            if wake_stream.is_active():
                wake_stream.stop_stream()
            wake_stream.close()
        except OSError as e:
            logging.info(f"Error during cleanup: {e}")
        wake_stream = None
    # porcupine.delete()
    p.terminate()
    logging.info("Cleanup completed.")


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
    if keyword_index == 1:
        prompt = Hey_computer_STT_prompt  # Define your prompt as necessary
    else:
        prompt = None

    try:
        # Convert the audio buffer (NumPy array) to a byte stream in WAV format
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, audio_buffer)
        byte_io.seek(0)  # Rewind to the beginning of the byte stream

        # Send the byte stream directly to the Groq API
        transcription = client.audio.transcriptions.create(
            file=("audio_buffer.wav", byte_io.getvalue()),  # Use in-memory byte stream
            model=groq_model,
            prompt=prompt,
            response_format="json",
            language="en",
            temperature=0.0,
        )
        return transcription.text
    except Exception as e:
        logging.info(f"Groq API error: {e}")  # Log the error
        return transcribe_with_local_model(
            audio_buffer, keyword_index
        )  # Call local model after logging


def transcribe_with_local_model(audio_buffer, keyword_index):
    # Define prompt based on keyword_index
    if keyword_index == 1:
        prompt = Hey_computer_STT_prompt
    else:
        prompt = None

    try:
        # Initialize Faster Whisper model
        #         model_path = "path_to_your_faster_whisper_model"  # Replace with your model path
        #         model = WhisperModel(device="cuda", compute_type="float16")
        #         model = WhisperModel("small.en", device="cuda", num_workers=8)
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
        # You can optionally call your fallback transcription function here
        return "Transcription failed"


"""    segments, info = model.transcribe(
        audio_buffer, language="en", suppress_blank=True, vad_filter=True
    )
    transcript = " ".join([segment["text"] for segment in segments])
    logging.info(transcript)
    return transcript"""


def process_audio_async():
    while True:
        try:
            audio_buffer_for_processing, keyword_index = audio_buffer_queue.get()
            if audio_buffer_for_processing is None:
                break
            try:
                transcript = transcribe_with_groq(
                    audio_buffer_for_processing, keyword_index
                )
            except groq.Error as e:  # This will catch all Groq API errors
                logging.info(
                    f"Groq API error occurred: {str(e)}, switching to local transcription."
                )
                transcript = transcribe_with_local_model(
                    audio_buffer_for_processing, keyword_index
                )
                """TODO :  this code was changed recently, check if it is working fine or not"""
            transcript_lower = transcript.lower()
            if (
                "computer" in transcript_lower or "lama" in transcript_lower
            ) and keyword_index is not None:  # Adjust the threshold as needed
                # Find the index of the keyword
                if "computer" in transcript_lower:
                    keyword_position = transcript_lower.index("computer")
                    stripped_transcript = transcript_lower
                    stripped_transcript = transcript_lower[
                        keyword_position + len("computer") :
                    ]
                    transcript_queue.put((stripped_transcript, keyword_index))
                    # Start the audio saving thread
                    executor.submit(
                        save_audio,
                        audio_buffer_for_processing,
                        keyword_index,
                        sample_rate=sample_rate,
                        type_of_audio="true_positive_hey_computer",
                    )
                elif "lama" in transcript_lower:
                    keyword_position = transcript_lower.index("lama")
                    stripped_transcript = transcript_lower[
                        keyword_position + len("lama") :
                    ]
                    transcript_queue.put((stripped_transcript, keyword_index))
                    executor.submit(
                        save_audio,
                        audio_buffer_for_processing,
                        keyword_index,
                        sample_rate=sample_rate,
                        type_of_audio="true_positive_hey_llama",
                    )
            elif keyword_index is None:
                transcript_queue.put((transcript, keyword_index))
                executor.submit(
                    save_audio,
                    audio_buffer_for_processing,
                    keyword_index,
                    sample_rate=sample_rate,
                    type_of_audio="my_voice_samples",
                )
            elif keyword_index == 2:
                executor.submit(
                    save_audio,
                    audio_buffer_for_processing,
                    keyword_index,
                    sample_rate=sample_rate,
                    type_of_audio="false_positive_rey_lama",
                )
            elif keyword_index == 0:
                executor.submit(
                    save_audio,
                    audio_buffer_for_processing,
                    keyword_index,
                    sample_rate=sample_rate,
                    type_of_audio="false_positive_hey_lama",
                )
            else:
                executor.submit(
                    save_audio,
                    audio_buffer_for_processing,
                    keyword_index,
                    sample_rate=sample_rate,
                    type_of_audio="false_positive_hey_computer",
                )
            logging.info(f"{YELLOW}{transcript}{RESET}")  # For transcript output
        except queue.Empty:
            continue
        except Exception as e:
            logging.info(f"An error occurred during transcription: {e}")


def start_listener():
    try:
        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        logging.info("Ctrl+C pressed. Exiting...")


def beep(sound):
    frequency, duration = sound
    # Create and start a new thread for playing the sound
    # thread = threading.Thread(target=lambda: winsound.Beep(frequency, duration))
    # thread.start()
    winsound.Beep(frequency, duration)
    # Optionally join the thread if you want to wait for it to complete
    # thread.join()


"""
########  ########  ######  ######## ######## 
##     ## ##       ##    ## ##          ##    
##     ## ##       ##       ##          ##    
########  ######    ######  ######      ##    
##   ##   ##             ## ##          ##    
##    ##  ##       ##    ## ##          ##    
##     ## ########  ######  ########    ##    

"""


def reset_state():
    global recording, play_pause_pressed, audio_buffer
    recording = False
    play_pause_pressed = False
    audio_buffer = np.array([], dtype="float32")
    restore_volume_all()
    logging.info("State reset completed")


def monitor_state():
    while True:
        if recording and time.time() - recording_start_time > 60:
            logging.error("Recording stuck in active state")
            reset_state()
        time.sleep(60)


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


def get_clipboard_content():
    try:
        win32clipboard.OpenClipboard(0)
        data = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return data
    except win32clipboard.Error:
        logging.info("Failed to open the clipboard. Returning an empty string.")
        return ""


def send_input(text):
    for char in text:
        ctypes.windll.user32.keybd_event(ord(char.upper()), 0, 0, 0)
        ctypes.windll.user32.keybd_event(ord(char.upper()), 0, 2, 0)  # Release key


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
                ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # Ctrl key down
                ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)  # V key down
                ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)  # V key up
                ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)  # Ctrl key up
                # pyautogui.write(transcript)  # No delay, types out instantly
                beep(PASTE_BEEP)
                logging.info("Transcript pasted")

        except Exception as e:
            logging.info(f"An error occurred in clean_transcript: {e}")


"""
##     ##    ###    #### ##    ## 
###   ###   ## ##    ##  ###   ## 
#### ####  ##   ##   ##  ####  ## 
## ### ## ##     ##  ##  ## ## ## 
##     ## #########  ##  ##  #### 
##     ## ##     ##  ##  ##   ### 
##     ## ##     ## #### ##    ## 
"""


def main():
    global stream
    global driver
    global driver_pid
    global vad_detector  # Add this line

    logging.info(
        f"{CYAN}wkey is active. Hold down {BOLD}{RECORD_KEY}{RESET}{CYAN} to start dictating.{RESET}"
    )

    try:
        #        transcribe_with_local_model(pre_recording_buffer, 1)
        # Start the microphone monitoring thread
        executor.submit(monitor_microphone_availability)

        # threading.Thread(target=monitor_sound_processing, daemon=True).start()
        # Use ThreadPoolExecutor for background processes

        executor.submit(clean_transcript)
        executor.submit(process_audio_async)
        executor.submit(listen_for_wake_word)
        executor.submit(start_driver)
        executor.submit(monitor_state)

        with stream:
            start_listener()
    except KeyboardInterrupt:
        logging.info(f"{RED}Ctrl+C pressed. Exiting...{RESET}")
    finally:
        if stream:
            if stream.active:
                stream.stop()
            stream.close()
        cleanup()
        restore_volume_all()
        logging.info(f"{YELLOW}Cleanup completed. Exiting...{RESET}")
        # Clean up (close the browser)
        if driver:
            driver.quit()
        executor.shutdown(
            wait=True
        )  # Gracefully shutdown the executor, wait for threads to complete


if __name__ == "__main__":
    main()
