import sounddevice as sd
import numpy as np
import keyboard
import torch
from nemo.collections.asr.models import ClusteringDiarizer


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
    sd.write(filename, data, samplerate)
    print(f"Audio saved to {filename}")


# Function to perform diarization
def diarize_audio(audio_data, samplerate=16000):
    diarizer = ClusteringDiarizer(cfg="diarizer.yaml")
    audio_tensor = torch.tensor(audio_data, dtype=torch.float32).unsqueeze(0)
    diarizer.diarize(audio_tensor)
    print("Diarization completed.")


# Main function to handle key press and recording
def main():
    print("Press F24 to start recording...")
    keyboard.wait("f24")
    duration = 10  # Record for 10 seconds
    audio_data = record_audio(duration)
    save_audio("mic_recording.wav", audio_data)
    diarize_audio(audio_data)
    print("Process completed.")


if __name__ == "__main__":
    main()
