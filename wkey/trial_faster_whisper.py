import sounddevice as sd
import numpy as np
import keyboard
from scipy.io.wavfile import write
from faster_whisper import WhisperModel


# Function to record audio
def record_audio(duration, samplerate=16000):
    print("Recording...")
    recording = sd.rec(
        int(duration * samplerate), samplerate=samplerate, channels=1, dtype="float64"
    )
    sd.wait()
    print("Recording finished.")
    return recording


# Function to save audio to a file
def save_audio(filename, data, samplerate=16000):
    write(filename, samplerate, data)
    print(f"Audio saved to {filename}")


# Function to transcribe audio
def transcribe_audio(filename):
    model = WhisperModel("large-v2", device="cuda")
    segments, info = model.transcribe(filename, beam_size=5)
    print(
        f"Detected language '{info.language}' with probability {info.language_probability}"
    )
    for segment in segments:
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")


# Main function to handle key press and recording
def main():
    print("Press F24 to start recording...")
    keyboard.wait("f24")
    duration = 2  # Record for 10 seconds
    audio_data = record_audio(duration)
    save_audio("mic_recording.wav", audio_data)
    transcribe_audio("mic_recording.wav")
    print("Process completed.")


if __name__ == "__main__":
    main()
