"""
 ######  ##     ## ########   ######  ######## ########     ###     ######  ########
##    ## ##     ## ##     ## ##    ##    ##    ##     ##   ## ##   ##    ##    ##
##       ##     ## ##     ## ##          ##    ##     ##  ##   ##  ##          ##
 ######  ##     ## ########   ######     ##    ########  ##     ## ##          ##
      ## ##     ## ##     ##       ##    ##    ##   ##   ######### ##          ##
##    ## ##     ## ##     ## ##    ##    ##    ##    ##  ##     ## ##    ##    ##
 ######   #######  ########   ######     ##    ##     ## ##     ##  ######     ##
"""

"""
TODO this way doesnt work...this is using desk_stream which is actually sd.inputstream that is recording from the mic and also  and also subtracting from the mic so there is no point. We have to use a loopback device or Python PyAudio to achieve recording from the audio stream of desktop playing music.

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

import noisereduce as nr
from pydub import AudioSegment


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
# Create named queues for each thread
wake_word_queues = [queue.Queue() for _ in range(4)]


# Function to process each chunk
def process_chunk(queue, porcupine_instance, debounce, thread_name):
    while True:
        chunk = queue.get()
        if chunk is None:
            break
        pcm = chunk.astype(np.int16)
        keyword_index = porcupine_instance.process(pcm)
        if keyword_index >= 0 and debounce.is_allowed():
            if keyword_index == 0:
                print(f"{thread_name}: Custom wake word 'Hey Llama' detected!")
            elif keyword_index == 1:
                print(f"{thread_name}: Wake word 'Hey Google' detected!")
            elif keyword_index == 2:
                print(f"{thread_name}: Wake word 'OK Google' detected!")
            elif keyword_index == 4:
                print(f"{thread_name}: Wake word 'Computer' detected!")
            else:
                print(f"{thread_name}: Unknown wake word detected!")


# Initialize Porcupine instances
porcupine_instances = [
    pvporcupine.create(
        access_key=pico_access_key,
        keyword_paths=[
            custom_wake_word_path,
            KEYWORD_PATHS["hey google"],
            KEYWORD_PATHS["ok google"],
            KEYWORD_PATHS["alexa"],
            KEYWORD_PATHS["computer"],
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
        ],
        keywords=["avengers"],
    )
    for _ in range(4)
]


class Debounce:
    def __init__(self):
        self.last_detection_time = 0
        self.debounce_time = 1.0  # 1 second debounce time

    def is_allowed(self):
        current_time = time.time()
        if current_time - self.last_detection_time > self.debounce_time:
            self.last_detection_time = current_time
            return True
        return False


# Create and start named threads
thread_names = ["Thread-1", "Thread-2", "Thread-3", "Thread-4"]
threads = []
debounce = Debounce()
for i in range(4):
    thread = threading.Thread(
        target=process_chunk,
        args=(wake_word_queues[i], porcupine_instances[i], debounce, thread_names[i]),
    )
    thread.start()
    threads.append(thread)

p = pyaudio.PyAudio()
wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

"""
wake_stream = p.open(
    format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512
)

desk_stream = p.open(
    format=pyaudio.paInt16,
    # channels=default_speakers["maxOutputChannels"],
    channels=1,
    rate=int(default_speakers["defaultSampleRate"]),
    input=True,
    frames_per_buffer=1024,
    input_device_index=default_speakers["index"],
)

wake_stream.start_stream()
"""

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
 ######  ######## ########  ########    ###    ##     ##  ######  
##    ##    ##    ##     ## ##         ## ##   ###   ### ##    ## 
##          ##    ##     ## ##        ##   ##  #### #### ##       
 ######     ##    ########  ######   ##     ## ## ### ##  ######  
      ##    ##    ##   ##   ##       ######### ##     ##       ## 
##    ##    ##    ##    ##  ##       ##     ## ##     ## ##    ## 
 ######     ##    ##     ## ######## ##     ## ##     ##  ######  
"""


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


# Start capturing microphone audio
rec_mic_stream = sd.InputStream(
    callback=callback_mic_audio,
    channels=1,
    samplerate=sample_rate,
    blocksize=blocksize,
)

# Define device indexes (you might need to modify these based on your system)
desk_device = "Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO), Windows WASAPI"

# Create input streams for microphone and desktop audio
wake_stream = sd.InputStream(samplerate=48000, channels=1, device=None, dtype="int16")
desk_stream = sd.InputStream(
    samplerate=48000, channels=1, device=desk_device, dtype="int16"
)

# Start both streams
wake_stream.start()
desk_stream.start()
rec_mic_stream.start()


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
    global wake_stream, desk_stream, p
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
            elif desk_stream is None:
                try:
                    desk_stream.start_stream()
                except OSError as e:
                    print(f"Failed to restart wake stream: {e}")
                    reinitialize_pyaudio()  # Reinitialize PyAudio
                    desk_stream = None
                except Exception as e:
                    print(f"Unexpected error: {e}")

        time.sleep(10)


"""

def normalize_audio(data):
    max_val = np.max(np.abs(data))
    if max_val == 0:
        return data
    return data / max_val


scaling_factor = 0.9  # Adjust this factor to avoid over-subtraction

"""
# Assume other imports and global variables like porcupine, wake_stream, desk_stream, and scaling_factor


def normalize_audio_rms(data, rate, target_rms=-20.0):
    audio_segment = AudioSegment(
        data.tobytes(),
        frame_rate=rate,
        sample_width=data.dtype.itemsize,
        channels=1,
    )
    rms = audio_segment.rms
    change_in_dBFS = target_rms - audio_segment.dBFS
    normalized_audio = audio_segment.apply_gain(change_in_dBFS)
    return np.array(normalized_audio.get_array_of_samples(), dtype=np.int16)


def match_rms_levels(original_data, processed_data):
    original_audio = AudioSegment(
        original_data.tobytes(),
        frame_rate=48000,
        sample_width=original_data.dtype.itemsize,
        channels=1,
    )
    processed_audio = AudioSegment(
        processed_data.tobytes(),
        frame_rate=48000,
        sample_width=processed_data.dtype.itemsize,
        channels=1,
    )
    change_in_dBFS = original_audio.dBFS - processed_audio.dBFS
    matched_audio = processed_audio.apply_gain(change_in_dBFS)
    return np.array(matched_audio.get_array_of_samples(), dtype=np.int16)


def listen_for_wake_word(scaling_factor=1.0):
    global desk_stream, wake_stream

    try:
        while True:
            # Read from the wake word audio stream (microphone)
            wake_data = wake_stream.read(2048)[0]  # Reading 2048 samples
            wake_data = wake_data.flatten()  # Convert from 2D array to 1D array

            if desk_stream.active:
                pass
            else:
                desk_stream.start()
            # Read from the desktop audio stream
            desk_data = desk_stream.read(2048)[0]  # Reading 2048 samples
            desk_data = desk_data.flatten()  # Convert from 2D array to 1D array

            # Ensure both streams have sufficient length
            if len(wake_data) < 2048 or len(desk_data) < 2048:
                continue  # Skip this iteration if data is insufficient

            # Normalize both audio streams to target RMS
            wake_data = normalize_audio_rms(wake_data, sample_rate)
            desk_data = normalize_audio_rms(desk_data, sample_rate)

            # Perform noise reduction using noisereduce
            noise_cancelled_data = nr.reduce_noise(
                y=wake_data,
                sr=sample_rate,
                y_noise=desk_data,
                prop_decrease=1.0,  # Adjust if needed
                device="cuda",  # If CUDA is available, otherwise omit this
                use_torch=True,
            )

            # Split noise_cancelled_data into 4 chunks of 512 frames
            chunks = [noise_cancelled_data[i : i + 512] for i in range(0, 2048, 512)]

            # Send chunks to the respective named queues
            for i in range(4):
                wake_word_queues[i].put(chunks[i])

            time.sleep(0.1)  # Adding a small sleep to avoid excessive CPU usage

    except OSError as e:
        print(f"Audio stream error: {e}")
        time.sleep(10)  # Wait before retrying to avoid rapid retry loops
    finally:
        # Stop and close streams on exit
        wake_stream.stop()
        wake_stream.close()
        desk_stream.stop()
        desk_stream.close()

        # Stop threads
        for q in wake_word_queues:
            q.put(None)


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
