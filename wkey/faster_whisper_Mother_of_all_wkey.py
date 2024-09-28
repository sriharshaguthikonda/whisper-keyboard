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


import pyautogui
import numpy as np
import sounddevice as sd
import pythoncom
from scipy.io.wavfile import write as wav_write

import groq
from groq import Groq

import queue
import asyncio


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

from openwakeword.model import Model


# import clipboard
# import win32clipboard as clipboard
import klembord

# Initialize klembord for clipboard operations
klembord.init()


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
sample_rate = 16000
model = WhisperModel("small.en", device="cuda", num_workers=8)
groq_model = "distil-whisper-large-v3-en"
# "whisper-large-v3"
play_pause_pressed = False
something_is_playing = False


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
            # print("stream is active")
            pass
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
        # print("Stream started")
        decrease_volume_all()
        play_pause_pressed = True
    else:
        # print("Stream started")
        pass

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
    global stream, recording, play_pause_pressed, audio_buffer, sample_rate

    stop_delay_threshold = (
        1.5  # Time to wait before stopping after no speech is detected
    )
    hard_stop_limit = 30  # Maximum recording time in seconds
    silent_time = 0
    recording_start_time = time.time()

    while silent_time < stop_delay_threshold:
        if stream.active:
            # Get the last frames of audio for VAD analysis
            audio_frame = audio_buffer[-1600:].tobytes()
            pcm = np.frombuffer(audio_frame, dtype=np.int16)

            # Dynamically adjust VAD threshold based on conditions (e.g., noise level)
            current_vad_threshold = (
                adjust_vad_threshold()
            )  # Custom function to adjust threshold
            prediction = owwModel.predict(pcm)
            vad_score = max(prediction.values())  # Get the highest VAD score

            if vad_score > current_vad_threshold:
                silent_time = 0  # Reset silent time if speech is detected
                print("Voice detected, continuing recording...")
            else:
                silent_time += 0.1  # Increment silent time if no speech is detected

            # Check if the hard stop limit is reached
            if time.time() - recording_start_time > hard_stop_limit:
                print("Hard stop limit reached, stopping recording.")
                break

            time.sleep(0.1)

    pre_recording_data = np.roll(pre_recording_buffer, -buffer_index, axis=0).flatten()

    # Convert main recording to numpy array
    audio_buffer = np.concatenate(
        [pre_recording_data, audio_buffer],
        axis=0,
    )
    audio_buffer_queue.put((audio_buffer, keyword_index))

    if play_pause_pressed:
        restore_volume_all()
        play_pause_pressed = False

    beep(STOP_BEEP)
    with recording_lock:
        recording = False
    print("Transcribing...")


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
    audio_data, keyword_index, directory="train", sample_rate=16000, type_of_audio=None
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
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_lama.onnx",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx\hey_computer10.onnx",
]

# Load the OpenWakeWord models
owwModel = Model(wakeword_models=MODEL_PATHS, inference_framework="onnx")

CHUNK = 1280  # Optimal chunk size for OpenWakeWord

# Define individual thresholds for each wake word model
THRESHOLDS = {
    0: 0.1,  # Threshold for "hey_lama"
    1: 0.3,  # Threshold for "hey_computer10"
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
    print("Listening for wake words...")

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
                recent_predictions = list(owwModel.prediction_buffer.values())[-8:]

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

                    if keyword_index == 0:  # Custom wake word: "Hey Llama"
                        print("Custom wake word 'hey_lama' detected!")
                        threading.Thread(target=start_recording).start()
                        time.sleep(5)
                        threading.Thread(
                            target=stop_recording, args=(keyword_index,)
                        ).start()
                    elif keyword_index == 1:  # Custom wake word: "Hey_cumputer"
                        print("Custom wake word 'hey_computer10' detected!")
                        threading.Thread(target=start_recording).start()
                        time.sleep(3)
                        threading.Thread(target=stop_recording, args=(1,)).start()
                    else:
                        print("Unknown wake word detected!", keyword_index)

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
    # porcupine.delete()
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

            transcript_lower = transcript.lower()
            if (
                "computer" in transcript_lower or "lama" in transcript_lower
            ):  # Adjust the threshold as needed
                transcript_queue.put((transcript, keyword_index))
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


"""
 ######  ##       #### ########  ########   #######     ###    ########  ########  
##    ## ##        ##  ##     ## ##     ## ##     ##   ## ##   ##     ## ##     ## 
##       ##        ##  ##     ## ##     ## ##     ##  ##   ##  ##     ## ##     ## 
##       ##        ##  ########  ########  ##     ## ##     ## ########  ##     ## 
##       ##        ##  ##        ##     ## ##     ## ######### ##   ##   ##     ## 
##    ## ##        ##  ##        ##     ## ##     ## ##     ## ##    ##  ##     ## 
 ######  ######## #### ##        ########   #######  ##     ## ##     ## ########  
"""


def get_clipboard_content():
    try:
        content = klembord.get("text/plain") or ""
        return content
    except Exception as e:
        return None


# Function to set clipboard content using klembord
def set_clipboard_content(text):
    try:
        # Set the clipboard content as plain text using klembord
        text_str = str(text)
        klembord.set_text(text_str)
    except Exception as e:
        print(f"Error setting clipboard content: {e}")


def clean_transcript():
    while True:
        try:
            transcript, keyword_index = transcript_queue.get()

            if keyword_index == 1:
                # Execute command when keyword_index is 4
                threading.Thread(target=execute_command, args=(transcript,)).start()
            else:
                # Get current clipboard content
                # original_clipboard_content = get_clipboard_content() or ""
                pass

                # Create the new clipboard content by appending the transcript
                #                 new_clipboard_content = (
                #                     f"{original_clipboard_content}\n{transcript}".strip())

                # Set the clipboard to the new content
                set_clipboard_content(transcript)

                # Simulate paste using pyautogui
                pyautogui.hotkey("ctrl", "v")

                # Beep to signal paste success
                beep(PASTE_BEEP)
                print("Transcript pasted")

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
