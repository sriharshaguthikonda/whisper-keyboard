import os
import whisper
import pyautogui
import keyboard
import pyperclip
import winsound



from dotenv import load_dotenv
import sounddevice as sd
import numpy as np
from pynput.keyboard import Controller as KeyboardController, Key, Listener
from scipy.io import wavfile

from utils import process_transcript

load_dotenv()
key_label = os.environ.get("WKEY", "f24")
RECORD_KEY = Key[key_label]

# This flag determines when to record
recording = False

# This is where we'll store the audio
audio_data = []

# This is the sample rate for the audio
sample_rate = 16000

# Keyboard controller
keyboard_controller = KeyboardController()




# Define beep sounds
START_BEEP = (880, 200)  # Frequency in Hz, Duration in ms
STOP_BEEP = (440, 200)   # Lower frequency for stop
PASTE_BEEP = (660, 200)  # Intermediate frequency for paste

def beep(sound):
    winsound.Beep(sound[0], sound[1])



def apply_whisper(filepath: str, model_name: str = "tiny.en") -> str:
    # Load the model
    model = whisper.load_model(model_name)
    
    # Process the audio file
    result = model.transcribe(filepath)
    
    # Extract the transcript
    transcript = result["text"]
    return transcript


def on_press(key):
    global recording
    global audio_data
    
    if key == RECORD_KEY:
        if not recording:  # Start recording only if not already recording
            pyautogui.press('playpause')  # Pause media playback
            beep(START_BEEP)  # Play start beep sound
            recording = True
            audio_data.clear()  # Clear existing audio data
            print("Listening...")

def on_release(key):
    global recording
    
    if key == RECORD_KEY:
        if recording:  # Stop recording only if currently recording
            pyautogui.press('playpause')  # Unpause media playback
            beep(STOP_BEEP)  # Play stop beep sound
            recording = False
            print("Transcribing...")
            
            if not audio_data:
                print("No audio data recorded.")
                return

            try:
                audio_data_np = np.concatenate(audio_data, axis=0)
            except ValueError as e:
                print(e)
                return

            audio_data_int16 = (audio_data_np * np.iinfo(np.int16).max).astype(np.int16)
            wavfile.write('recording.wav', sample_rate, audio_data_int16)

            transcript = None
            try:
                transcript = apply_whisper('recording.wav')
            except Exception as e:
                print(f"An error occurred during transcription: {e}")

            if transcript:
                processed_transcript = process_transcript(transcript)
                print(processed_transcript)
                # Attempt to paste the transcript
                try:
                    pyperclip.copy(processed_transcript)
                    keyboard.send('ctrl+v')
                    beep(PASTE_BEEP)  # Play paste beep sound after pasting
                except Exception as e:
                    print(f"Error during paste operation: {e}")

def callback(indata, frames, time, status):
    if status:
        print(status)
    if recording:
        audio_data.append(indata.copy())  # make sure to copy the indata

def start_listener():
    try:
        with Listener(on_press=on_press, on_release=on_release) as listener:
            with sd.InputStream(callback=callback, channels=1, samplerate=sample_rate, blocksize=int(sample_rate * 0.1)):  # Adjust blocksize for longer duration
                listener.join()
    except KeyboardInterrupt:
        print("Ctrl+C pressed. Exiting...")
        # Perform any cleanup here if necessary
        # For example, closing files, stopping audio streams, etc.

def main():
    print(f"wkey is active. Hold down {key_label} to start dictating.")
    start_listener()

if __name__ == "__main__":
    main()
