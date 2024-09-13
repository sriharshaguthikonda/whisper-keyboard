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
import clipboard
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
from voice_commands import execute_command
from pause_all import is_sound_playing_windows_processing

from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


from vosk import Model, KaldiRecognizer
import pyaudio
import pvporcupine
from pvporcupine import KEYWORD_PATHS


# Initial setup and global variables
initial_volume = None  # Variable to store initial volume
transcript_queue = queue.Queue()
audio_buffer_queue = queue.Queue()

load_dotenv()
key_label = os.environ.get("WKEY", "f24")
RECORD_KEY = Key[key_label]
keyboard_controller = KeyboardController()
recording = False
stream = None
audio_buffer = np.array([], dtype="float32")
sample_rate = 8000
model = WhisperModel("small.en", device="cuda", num_workers=8)
groq_model = "distil-whisper-large-v3-en"
# "whisper-large-v3"
play_pause_pressed = False
something_is_playing = False


# Initialize components for wake word detection
model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\vosk-model-small-en-us-0.15"

if not os.path.exists(model_path):
    print("Model path does not exist. Exiting.")
    exit(1)

model = Model(model_path)
rec = KaldiRecognizer(model, 16000)
load_dotenv()
pico_access_key = os.getenv("PICO_ACCESS_KEY")

custom_wake_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"

hey_computer_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\hey-computer_en_windows_v3_0_0.ppn"

# Initialize Porcupine with multiple wake words and higher sensitivity
porcupine = pvporcupine.create(
    access_key=pico_access_key,
    keyword_paths=[
        custom_wake_word_path,
        KEYWORD_PATHS["hey google"],
        KEYWORD_PATHS["ok google"],
        KEYWORD_PATHS["alexa"],
        hey_computer_word_path,
        KEYWORD_PATHS["jarvis"],
        KEYWORD_PATHS["porcupine"],
        KEYWORD_PATHS["americano"],
        KEYWORD_PATHS["blueberry"],
        KEYWORD_PATHS["bumblebee"],
        KEYWORD_PATHS["grapefruit"],
        KEYWORD_PATHS["grasshopper"],
        KEYWORD_PATHS["hey barista"],
        KEYWORD_PATHS["hey siri"],
        KEYWORD_PATHS["pico clock"],
        KEYWORD_PATHS["picovoice"],
        KEYWORD_PATHS["terminator"],
    ],
    # Add more default wake words as needed
    sensitivities=[
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
        0.95,
    ],  # Adjust these values as needed
    keywords=["avengers"],
)


p = pyaudio.PyAudio()
wake_stream = p.open(
    format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512
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


PRE_RECORDING_DURATION = 1  # seconds
BUFFER_SIZE = PRE_RECORDING_DURATION * 2000
channels = 1

pre_recording_buffer = np.zeros((BUFFER_SIZE, channels), dtype=np.float32)
buffer_index = 0
audio_buffer = []


def audio_callback(indata, frames, time, status):
    """Callback function for audio recording."""
    global buffer_index
    global audio_buffer
    if status:
        print(f"Audio callback status: {status}")
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


def get_current_volume():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    return volume.GetMasterVolumeLevelScalar()


def set_volume(volume_level):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(volume_level, None)


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
########  ########  ######   #######  ########  ########  #### ##    ##  ######   
##     ## ##       ##    ## ##     ## ##     ## ##     ##  ##  ###   ## ##    ##  
##     ## ##       ##       ##     ## ##     ## ##     ##  ##  ####  ## ##        
########  ######   ##       ##     ## ########  ##     ##  ##  ## ## ## ##   #### 
##   ##   ##       ##       ##     ## ##   ##   ##     ##  ##  ##  #### ##    ##  
##    ##  ##       ##    ## ##     ## ##    ##  ##     ##  ##  ##   ### ##    ##  
##     ## ########  ######   #######  ##     ## ########  #### ##    ##  ######   
"""


def start_recording():
    global stream
    global recording
    global play_pause_pressed
    global something_is_playing

    # this thread has to go if something_is_playing check is happening below
    thread = threading.Thread(target=lambda: decrease_volume_all())
    thread.start()

    try:
        if stream and stream.active:
            print("stream is active")
        else:
            try:
                device_info = sd.default.device
                print(f"Using device: {device_info}")
                stream = sd.InputStream(
                    callback=audio_callback,
                    device=None,
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=int(sample_rate * 0.1),
                )
                stream.start()
            except Exception as e:
                print(f"Failed to start stream: {e}")
                time.sleep(2)
    except NameError:
        pass

    if something_is_playing:
        print("Stream started")
        decrease_volume_all()
        play_pause_pressed = True
    else:
        print("Stream started")

    beep(START_BEEP)
    with recording_lock:
        recording = True
    print("Listening...")


def stop_recording(keyword_index):
    global stream
    global recording
    global play_pause_pressed
    global audio_buffer

    # this thread has to go if play_pause_pressed check is happening below!
    thread = threading.Thread(target=lambda: restore_volume_all())
    thread.start()

    if stream.active:
        # Convert pre-recording buffer to numpy array
        pre_recording_data = np.roll(
            pre_recording_buffer, -buffer_index, axis=0
        ).flatten()

        # Convert main recording to numpy array
        audio_buffer = np.concatenate(
            [pre_recording_data, audio_buffer],
            axis=0,
        )
        audio_buffer_queue.put((audio_buffer, keyword_index))
        audio_buffer = np.array([], dtype="float32")

    if play_pause_pressed:
        restore_volume_all()
        play_pause_pressed = False
    beep(STOP_BEEP)
    with recording_lock:
        recording = False
    print("Transcribing...")


def on_press(key):
    if key == RECORD_KEY and not recording:
        start_recording()


def on_release(key):
    if key == RECORD_KEY and recording:
        stop_recording(None)


"""
########  ####  ######   #######  
##     ##  ##  ##    ## ##     ## 
##     ##  ##  ##       ##     ## 
########   ##  ##       ##     ## 
##         ##  ##       ##     ## 
##         ##  ##    ## ##     ## 
##        ####  ######   #######  
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
                    wake_stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        frames_per_buffer=512,
                    )
                    wake_stream.start_stream()
                except OSError as e:
                    print(f"Failed to restart wake stream: {e}")
                    reinitialize_pyaudio()  # Reinitialize PyAudio
                    wake_stream = None
                except Exception as e:
                    print(f"Unexpected error: {e}")

        time.sleep(10)


def listen_for_wake_word():
    global wake_stream
    print("Listening for wake words...")
    while True:
        try:
            if wake_stream:
                data = wake_stream.read(512, exception_on_overflow=False)
                pcm = np.frombuffer(data, dtype=np.int16)

                # Check for wake word using Porcupine
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    if keyword_index == 0:  # Custom wake word: "Hey Llama"
                        print("Custom wake word 'Hey Llama' detected!")
                    elif keyword_index == 1:  # Default wake word: "Hey Google"
                        print("Wake word 'Hey Google' detected!")
                    elif keyword_index == 2:  # Default wake word: "OK Google"
                        print("Wake word 'OK Google' detected!")
                    elif keyword_index == 3:  # Default wake word: "Alexa"
                        print("Wake word 'Alexa' detected!")
                        # Define the action for "Alexa"
                    elif keyword_index == 4:  # Default wake word: "Computer"
                        print("Wake word 'Computer' detected!")
                        # Define the action for "Computer"
                    elif keyword_index == 5:  # Default wake word: "Jarvis"
                        print("Wake word 'Jarvis' detected!")
                        # Trigger voice command execution
                    elif keyword_index == 6:  # Default wake word: "Porcupine"
                        print("Wake word 'Porcupine' detected!")
                        # Define the action for "Porcupine"
                    elif keyword_index == 7:  # Default wake word: "Americano"
                        print("Wake word 'Americano' detected!")
                        # Define the action for "Americano"
                    elif keyword_index == 8:  # Default wake word: "Blueberry"
                        print("Wake word 'Blueberry' detected!")
                        # Define the action for "Blueberry"
                    elif keyword_index == 9:  # Default wake word: "Bumblebee"
                        print("Wake word 'Bumblebee' detected!")
                        # Define the action for "Bumblebee"
                    elif keyword_index == 10:  # Default wake word: "Grapefruit"
                        print("Wake word 'Grapefruit' detected!")
                        # Define the action for "Grapefruit"
                    elif keyword_index == 11:  # Default wake word: "Grasshopper"
                        print("Wake word 'Grasshopper' detected!")
                        # Define the action for "Grasshopper"
                    elif keyword_index == 12:  # Default wake word: "Hey Barista"
                        print("Wake word 'Hey Barista' detected!")
                        # Define the action for "Hey Barista"
                    elif keyword_index == 13:  # Default wake word: "Hey Siri"
                        print("Wake word 'Hey Siri' detected!")
                        # Define the action for "Hey Siri"
                    elif keyword_index == 14:  # Default wake word: "Pico Clock"
                        print("Wake word 'Pico Clock' detected!")
                        # Define the action for "Pico Clock"
                    elif keyword_index == 15:  # Default wake word: "Picovoice"
                        print("Wake word 'Picovoice' detected!")
                        # Define the action for "Picovoice"
                    elif keyword_index == 16:  # Default wake word: "Terminator"
                        print("Wake word 'Terminator' detected!")
                        # Define the action for "Terminator"
                    else:
                        print("Unknown wake word detected!")
                        # You can add more wake word conditions here
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

            # Attempt to reinitialize the wake word detection after an error
            time.sleep(10)  # Wait before retrying to avoid rapid retry loops
            # Microphone availability and wake stream initialization are now handled by monitor_microphone_availability


def cleanup():
    global wake_stream
    if wake_stream:
        try:
            if wake_stream.is_active():
                wake_stream.stop_stream()
            wake_stream.close()
        except OSError as e:
            print(f"Error during cleanup: {e}")
        wake_stream = None
    porcupine.delete()
    p.terminate()
    print("Cleanup completed.")


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


def transcribe_with_groq(audio_buffer):
    try:
        # Convert the audio buffer (NumPy array) to a byte stream in WAV format
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, audio_buffer)
        byte_io.seek(0)  # Rewind to the beginning of the byte stream

        # Send the byte stream directly to the Groq API
        transcription = client.audio.transcriptions.create(
            file=("audio_buffer.wav", byte_io.read()),  # Use in-memory byte stream
            model=groq_model,
            prompt="Specify context or spelling",
            response_format="json",
            language="en",
            temperature=0.0,
        )
        return transcription.text
    except Exception as e:
        print(f"Groq API error: {e}")
        raise


def transcribe_with_local_model(audio_buffer):
    segments, info = model.transcribe(
        audio_buffer, language="en", suppress_blank=True, vad_filter=True
    )
    transcript = " ".join([segment["text"] for segment in segments])
    return transcript


def process_audio_async():
    while True:
        try:
            audio_buffer_for_processing, keyword_index = audio_buffer_queue.get(
                timeout=5
            )
            if audio_buffer_for_processing is None:
                break
            try:
                transcript = transcribe_with_groq(audio_buffer_for_processing)
            except groq.RateLimitError:
                print("Groq API rate limit reached, switching to local transcription.")
                transcript = transcribe_with_local_model(audio_buffer_for_processing)
            transcript_queue.put((transcript, keyword_index))
            print(transcript)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"An error occurred during transcription: {e}")


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


# Function to clean transcript and paste it
def clean_transcript():
    while True:
        try:
            transcript, keyword_index = transcript_queue.get()
            if keyword_index == 5:
                threading.Thread(target=execute_command, args=(transcript,)).start()
            else:
                original_clipboard_content = clipboard.paste()
                clipboard.copy(transcript)
                pyautogui.hotkey("ctrl", "v")
                beep(PASTE_BEEP)
                print("Transcript pasted")
                time.sleep(0.1)
                clipboard.copy(original_clipboard_content)
                time.sleep(0.1)
                clipboard.copy(transcript)

        except Exception as e:
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


def main():
    global stream
    print("wkey is active. Hold down", RECORD_KEY, " to start dictating.")

    try:
        # Start the microphone monitoring thread
        threading.Thread(target=monitor_microphone_availability, daemon=True).start()

        # threading.Thread(target=monitor_sound_processing, daemon=True).start()
        threading.Thread(target=clean_transcript, daemon=True).start()
        threading.Thread(target=process_audio_async, daemon=True).start()
        threading.Thread(target=listen_for_wake_word, daemon=True).start()

        with stream:
            start_listener()
    except KeyboardInterrupt:
        print("Ctrl+C pressed. Exiting...")
    finally:
        if stream:
            if stream.active:
                stream.stop()
            stream.close()
        cleanup()
        restore_volume_all()
        print("Cleanup completed. Exiting...")


if __name__ == "__main__":
    main()
