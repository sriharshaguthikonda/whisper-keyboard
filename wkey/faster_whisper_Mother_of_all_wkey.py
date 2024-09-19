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
import psutil
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
from voice_commands import execute_command, start_driver, driver  # , driver_pid
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

hey_llama_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"
hey_computer_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\hey-computer_en_windows_v3_0_0.ppn"

# Initialize Porcupine with multiple wake words and higher sensitivity
porcupine = pvporcupine.create(
    access_key=pico_access_key,
    keyword_paths=[
        hey_llama_word_path,
        KEYWORD_PATHS["hey google"],
        KEYWORD_PATHS["ok google"],
        KEYWORD_PATHS["alexa"],
        hey_computer_word_path,
        KEYWORD_PATHS["jarvis"],
        # Add more default wake words as needed
    ],
    sensitivities=[0.75, 0.85, 0.65, 0.75, 1, 0.65],  # Adjust these values as needed
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


PRE_RECORDING_DURATION = 2  # seconds
BUFFER_SIZE = PRE_RECORDING_DURATION * sample_rate
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
    threading.Thread(target=decrease_volume_all()).start()

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


"""
 ######  ########  #######  ########     ########  ########  ######  
##    ##    ##    ##     ## ##     ##    ##     ## ##       ##    ## 
##          ##    ##     ## ##     ##    ##     ## ##       ##       
 ######     ##    ##     ## ########     ########  ######   ##       
      ##    ##    ##     ## ##           ##   ##   ##       ##       
##    ##    ##    ##     ## ##           ##    ##  ##       ##    ## 
 ######     ##     #######  ##           ##     ## ########  ######  
"""


def stop_recording(keyword_index):
    global stream
    global recording
    global play_pause_pressed
    global audio_buffer
    global sample_rate

    # this thread has to go if play_pause_pressed check is happening below!
    threading.Thread(target=restore_volume_all()).start()

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
 ######     ###    ##     ## ######## 
##    ##   ## ##   ##     ## ##       
##        ##   ##  ##     ## ##       
 ######  ##     ## ##     ## ######   
      ## #########  ##   ##  ##       
##    ## ##     ##   ## ##   ##       
 ######  ##     ##    ###    ######## 
"""


def save_audio(
    audio_data, keyword_index, directory="train", sample_rate=8000, type_of_audio=None
):
    # Ensure the directory exists
    if not os.path.exists(directory):
        os.makedirs(directory)

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
    print(f"Audio saved as {filename}")


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
                        """decrease_volume_all()
                        time.sleep(5)
                        restore_volume_all()"""
                    elif keyword_index == 2:  # Default wake word: "OK Google"
                        print("Wake word 'OK Google' detected!")
                        """decrease_volume_all()
                        time.sleep(5)
                        restore_volume_all()"""
                    elif keyword_index == 3:  # Default wake word: "Alexa"
                        print("Wake word 'Alexa' detected!")
                        # Define the action for "Alexa"
                    elif keyword_index == 4:  # Default wake word: "Computer"
                        print("Wake word 'Computer' detected!")
                        # Define the action for "Computer"
                        start_recording()
                        time.sleep(2)
                        stop_recording(keyword_index)
                    elif keyword_index == 5:  # Default wake word: "Jarvis"
                        print("Wake word 'Jarvis' detected!")
                        # Trigger voice command execution

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
            if (
                "computer" or "hey Lama" in transcript.lower()
            ):  # Adjust the threshold as needed
                threading.Thread(
                    target=save_audio(
                        audio_data=audio_buffer_for_processing,
                        keyword_index=keyword_index,
                        sample_rate=sample_rate,
                        type_of_audio="true_positive",
                    )
                ).start()
            else:
                threading.Thread(
                    target=save_audio(
                        audio_data=audio_buffer_for_processing,
                        keyword_index=keyword_index,
                        sample_rate=sample_rate,
                        type_of_audio="false_positive",
                    )
                ).start()
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
            if keyword_index == 4:
                threading.Thread(target=execute_command, args=(transcript,)).start()
                # execute_command
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
    global driver
    global driver_pid

    print("wkey is active. Hold down", RECORD_KEY, " to start dictating.")

    try:
        # Start the microphone monitoring thread
        threading.Thread(target=monitor_microphone_availability, daemon=True).start()

        # threading.Thread(target=monitor_sound_processing, daemon=True).start()
        threading.Thread(target=clean_transcript, daemon=True).start()
        threading.Thread(target=process_audio_async, daemon=True).start()
        threading.Thread(target=listen_for_wake_word, daemon=True).start()
        threading.Thread(target=start_driver, daemon=True).start()

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
        # Clean up (close the browser)
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
