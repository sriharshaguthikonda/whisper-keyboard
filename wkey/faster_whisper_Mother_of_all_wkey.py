"""
##     ##    ###    #### ##    ##
###   ###   ## ##    ##  ###   ##
#### ####  ##   ##   ##  ####  ##
## ### ## ##     ##  ##  ## ## ##
##     ## #########  ##  ##  ####
##     ## ##     ##  ##  ##   ###
##     ## ##     ## #### ##    ##
"""

import os
import time
import threading
import pyautogui
import numpy as np
import sounddevice as sd
import pythoncom
import queue
from pynput.keyboard import Controller as KeyboardController, Key, Listener
from dotenv import load_dotenv

from voice_commands import execute_command
from pause_all import is_sound_playing_windows_processing
from wkey.volume_manipulation import decrease_volume_all, restore_volume_all
from wkey.beep_utils import beep, START_BEEP, STOP_BEEP, PASTE_BEEP
from wkey.transcription_utils import process_audio_async, clean_transcript



from vosk import Model, KaldiRecognizer
import pyaudio
import pvporcupine


# Initial setup and global variables
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


# Locks for synchronization
recording_lock = threading.Lock()
audio_data_lock = threading.Lock()


"""
##     ##  #######  ##             ###    ########        ## 
##     ## ##     ## ##            ## ##   ##     ##       ## 
##     ## ##     ## ##           ##   ##  ##     ##       ## 
##     ## ##     ## ##          ##     ## ##     ##       ## 
 ##   ##  ##     ## ##          ######### ##     ## ##    ## 
  ## ##   ##     ## ##          ##     ## ##     ## ##    ## 
   ###     #######  ########    ##     ## ########   ######  
"""


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


def listen_for_wake_word():
    print("Listening for wake words...")
    while True:
        data = wake_stream.read(512, exception_on_overflow=False)
        pcm = np.frombuffer(data, dtype=np.int16)

        # Check for wake word using Porcupine
        keyword_index = porcupine.process(pcm)
        if keyword_index >= 0:
            print("Wake word detected!")
            start_recording()
            time.sleep(2)
            stop_recording()


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


def start_listener():
    try:
        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        print("Ctrl+C pressed. Exiting...")


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
        # threading.Thread(target=monitor_sound_processing, daemon=True).start()
        threading.Thread(target=clean_transcript, args=(transcript_queue,), daemon=True).start()
        threading.Thread(target=process_audio_async, args=(audio_buffer_queue, transcript_queue, sample_rate), daemon=True).start()
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
