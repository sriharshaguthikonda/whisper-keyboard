"""
 ######  ##     ## ########   ######  ######## ########     ###     ######  ########
##    ## ##     ## ##     ## ##    ##    ##    ##     ##   ## ##   ##    ##    ##
##       ##     ## ##     ## ##          ##    ##     ##  ##   ##  ##          ##
 ######  ##     ## ########   ######     ##    ########  ##     ## ##          ##
      ## ##     ## ##     ##       ##    ##    ##   ##   ######### ##          ##
##    ## ##     ## ##     ## ##    ##    ##    ##    ##  ##     ## ##    ##    ##
 ######   #######  ########   ######     ##    ##     ## ##     ##  ######     ##
"""

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
# Initialize Porcupine with multiple wake words and higher sensitivity
porcupine = pvporcupine.create(
    access_key=pico_access_key,
    keyword_paths=[
        custom_wake_word_path,
        KEYWORD_PATHS["hey google"],
        KEYWORD_PATHS["ok google"],
        KEYWORD_PATHS["alexa"],
        KEYWORD_PATHS["computer"],
        KEYWORD_PATHS["jarvis"],
        # Add more default wake words as needed
    ],
    sensitivities=[0.85, 0.85, 0.65, 0.75, 0.75, 0.75],  # Adjust these values as needed
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
    global mic_stream, desktop_stream, mic_start_time, desktop_start_time
    global recording
    global play_pause_pressed
    global something_is_playing

    thread = threading.Thread(target=lambda: decrease_volume_all())
    thread.start()

    try:
        if mic_stream and mic_stream.active:
            mic_stream.stop()
        mic_stream.close()
    except NameError:
        pass

    try:
        mic_start_time = time.time()
        mic_stream = sd.InputStream(
            callback=callback_mic_audio,
            device=None,
            channels=1,
            samplerate=sample_rate,
            blocksize=int(sample_rate * 0.1),
        )
        mic_stream.start()
    except Exception as e:
        print(f"Failed to start microphone stream: {e}")
        time.sleep(2)

    try:
        desktop_start_time = time.time()
        desktop_stream = sd.InputStream(
            callback=callback_desktop_audio,
            device=None,
            channels=1,
            samplerate=sample_rate,
            blocksize=int(sample_rate * 0.1),
        )
        desktop_stream.start()
    except Exception as e:
        print(f"Failed to start desktop stream: {e}")
        time.sleep(2)

    if something_is_playing:
        print("Streams started")
        decrease_volume_all()
        play_pause_pressed = True
    else:
        print("Streams started")

    beep(START_BEEP)
    with recording_lock:
        recording = True
    print("Listening...")


def stop_recording(keyword_index):
    global mic_stream, desktop_stream
    global recording
    global play_pause_pressed
    global audio_buffer
    global desktop_audio_buffer
    global mic_audio_buffer

    thread = threading.Thread(target=lambda: restore_volume_all())
    thread.start()

    if mic_stream.active:
        mic_stream.stop()
        mic_stream.close()
    if desktop_stream.active:
        desktop_stream.stop()
        desktop_stream.close()

    # Ensure audio buffers are of equal length
    if len(mic_audio_buffer) != len(desktop_audio_buffer):
        if len(mic_audio_buffer) > len(desktop_audio_buffer):
            desktop_audio_buffer = np.pad(
                desktop_audio_buffer,
                (0, len(mic_audio_buffer) - len(desktop_audio_buffer)),
                "constant",
            )
        else:
            mic_audio_buffer = np.pad(
                mic_audio_buffer,
                (0, len(desktop_audio_buffer) - len(mic_audio_buffer)),
                "constant",
            )

    # Subtract desktop audio from mic audio
    aligned_audio = mic_audio_buffer - desktop_audio_buffer
    audio_buffer_queue.put((aligned_audio, keyword_index))

    if play_pause_pressed:
        restore_volume_all()
        play_pause_pressed = False
    beep(STOP_BEEP)

    # Clear the audio buffers after processing
    mic_audio_buffer = np.array([], dtype="float32")
    desktop_audio_buffer = np.array([], dtype="float32")

    with recording_lock:
        recording = False
    print("Transcribing...")


def on_press(key):
    if key == RECORD_KEY and not recording:
        start_recording()


def on_release(key):
    if key == RECORD_KEY and recording:
        stop_recording(None)


# Global buffers for audio data
desktop_audio_buffer = np.array([], dtype="float32")
mic_audio_buffer = np.array([], dtype="float32")

# Sample rate and blocksize (set according to your requirements)
sample_rate = 16000
blocksize = int(sample_rate * 0.1)


def callback_desktop_audio(indata, frames, time, status):
    global desktop_audio_buffer
    if status:
        print(status)
    desktop_audio_buffer = np.append(desktop_audio_buffer, indata.copy())


def callback_mic_audio(indata, frames, time, status):
    global mic_audio_buffer
    if status:
        print(status)
    mic_audio_buffer = np.append(mic_audio_buffer, indata.copy())


# Start capturing desktop audio
desktop_stream = sd.InputStream(
    callback=callback_desktop_audio,
    channels=1,
    samplerate=sample_rate,
    blocksize=blocksize,
)

# Start capturing microphone audio
mic_stream = sd.InputStream(
    callback=callback_mic_audio,
    channels=1,
    samplerate=sample_rate,
    blocksize=blocksize,
)

"""
# Subtract desktop audio from microphone audio
def subtract_audio():
    global desktop_audio_buffer, mic_audio_buffer

    if len(desktop_audio_buffer) > 0 and len(mic_audio_buffer) > 0:
        min_length = min(len(desktop_audio_buffer), len(mic_audio_buffer))
        processed_audio = (
            mic_audio_buffer[:min_length] - desktop_audio_buffer[:min_length]
        )

        # Clear buffers after processing
        desktop_audio_buffer = desktop_audio_buffer[min_length:]
        mic_audio_buffer = mic_audio_buffer[min_length:]

        return processed_audio
    return None
"""

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
                        start_recording()
                        time.sleep(5)
                        stop_recording(keyword_index)
                    elif keyword_index == 1:  # Default wake word: "Hey Google"
                        print("Wake word 'Hey Google' detected!")
                        decrease_volume_all()
                        time.sleep(5)
                        restore_volume_all()
                    elif keyword_index == 2:  # Default wake word: "OK Google"
                        print("Wake word 'OK Google' detected!")
                        decrease_volume_all()
                        time.sleep(5)
                        restore_volume_all()
                    elif keyword_index == 3:  # Default wake word: "Alexa"
                        print("Wake word 'Alexa' detected!")
                        # Define the action for "Alexa"
                    elif keyword_index == 4:  # Default wake word: "Computer"
                        print("Wake word 'Computer' detected!")
                        # Define the action for "Computer"
                    elif keyword_index == 5:  # Default wake word: "Jarvis"
                        print("Wake word 'Jarvis' detected!")
                        # Trigger voice command execution
                        start_recording()
                        time.sleep(3)
                        stop_recording(keyword_index)
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
                execute_command(transcript)
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
