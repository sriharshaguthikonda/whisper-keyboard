import os
import io
import time
import threading
import pyautogui
import winsound
import clipboard
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
porcupine = pvporcupine.create(
    pico_access_key,
    keyword_paths=[custom_wake_word_path],
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
    if initial_volume is None:
        initial_volume = get_current_volume()
    print(f"Decreasing volume from {initial_volume * 100}% to 10%")
    set_volume(0.1)  # Set volume to 10%


def restore_volume_all():
    global initial_volume
    if initial_volume is not None:
        print(f"Restoring volume to {initial_volume * 100}%")
        set_volume(initial_volume)  # Restore to initial volume


def callback(indata, frames, time, status):
    global audio_buffer
    if status:
        print(status)
    with audio_data_lock:
        if recording:
            audio_buffer = np.append(audio_buffer, indata.copy())


stream = sd.InputStream(
    callback=callback,
    device=None,
    channels=1,
    samplerate=sample_rate,
    blocksize=int(sample_rate * 0.1),
)


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

    # this thread has to go if something_is_playing check is happening below Are you listening to me now?!
    thread = threading.Thread(target=lambda: decrease_volume_all())
    thread.start()

    try:
        if stream and stream.active:
            stream.stop()
        stream.close()
    except NameError:
        pass

    try:
        device_info = sd.default.device
        print(f"Using device: {device_info}")
        stream = sd.InputStream(
            callback=callback,
            device=None,
            channels=1,
            samplerate=sample_rate,
            blocksize=int(sample_rate * 0.1),
        )
        stream.start()
    except Exception as e:
        print(f"Failed to start stream: {e}")
        time.sleep(2)

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


def stop_recording():
    global stream
    global recording
    global play_pause_pressed
    global audio_buffer

    # this thread has to go if play_pause_pressed check is happening below!

    thread = threading.Thread(target=lambda: restore_volume_all())
    thread.start()

    if stream.active:
        audio_buffer_queue.put(audio_buffer)
        stream.stop()
        stream.close()
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
        stop_recording()


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


def monitor_microphone_availability():
    """Monitor microphone availability and control wake word detection accordingly."""
    global wake_stream
    while True:
        if not check_microphone():
            print("No microphone detected. Pausing wake word detection...")
            if wake_stream:
                wake_stream.stop()
                wake_stream.close()
                wake_stream = None
        else:
            if wake_stream is None:
                print("Microphone detected. Resuming wake word detection...")
                wake_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=512,
                )
                wake_stream.start_stream()

        time.sleep(5)  # Check every 5 seconds


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
                    print("Wake word detected!")
                    start_recording()
                    time.sleep(2)
                    stop_recording()
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
            time.sleep(5)  # Wait before retrying to avoid rapid retry loops
            if check_microphone():
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
                    wake_stream = None
            else:
                print("Microphone still not available. Retrying...")
                time.sleep(5)


def cleanup():
    if wake_stream:
        if wake_stream.active:
            wake_stream.stop()
        wake_stream.close()
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
            audio_buffer_for_processing = audio_buffer_queue.get(timeout=5)
            if audio_buffer_for_processing is None:
                break
            try:
                transcript = transcribe_with_groq(audio_buffer_for_processing)
            except groq.RateLimitError:
                print("Groq API rate limit reached, switching to local transcription.")
                transcript = transcribe_with_local_model(audio_buffer_for_processing)
            transcript_queue.put(transcript)
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
            transcript = transcript_queue.get()

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
