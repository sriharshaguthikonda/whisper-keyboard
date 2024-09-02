import numpy as np
import sounddevice as sd
import collections
import threading
import keyboard
import time
from scipy.io.wavfile import write

# Constants
SAMPLE_RATE = 16000
CHANNELS = 1  # mono audio
PRE_RECORDING_DURATION = 2  # seconds
FILENAME = "recording.wav"
BUFFER_SIZE = PRE_RECORDING_DURATION * SAMPLE_RATE

# Globals
recording = False
pre_recording_buffer = np.zeros((BUFFER_SIZE, CHANNELS), dtype=np.float32)
audio_buffer = []
recording_lock = threading.Lock()
buffer_index = 0


def audio_callback(indata, frames, time, status):
    """Callback function for audio recording."""
    global buffer_index
    if status:
        print(f"Audio callback status: {status}")
    with recording_lock:
        if recording:
            audio_buffer.append(indata.copy())
        else:
            # Adjust buffer size dynamically
            end_index = buffer_index + frames
            if end_index > BUFFER_SIZE:
                end_index = BUFFER_SIZE
            pre_recording_buffer[buffer_index:end_index] = indata[
                : end_index - buffer_index
            ]
            buffer_index = (buffer_index + frames) % BUFFER_SIZE


def start_recording():
    """Start the recording."""
    global recording
    global audio_buffer
    global buffer_index

    audio_buffer = []
    buffer_index = 0

    # Start recording in pre-recording phase
    print("Pre-recording...")
    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback
    ):
        print("Press F24 to start recording.")
        while not keyboard.is_pressed("F24"):
            sd.sleep(100)  # Sleep for 100 ms to prevent high CPU usage

        # Start main recording
        recording = True
        print("Recording... Press F24 to stop.")
        while not keyboard.is_pressed("F24"):
            sd.sleep(100)  # Sleep for 100 ms to prevent high CPU usage

        sd.sleep(2000)
        recording = False


def save_audio():
    """Process and save the recorded audio."""
    print(f"Pre-recording buffer length: {BUFFER_SIZE}")

    # Convert pre-recording buffer to numpy array
    pre_recording_data = np.roll(pre_recording_buffer, -buffer_index, axis=0).flatten()

    # Convert main recording to numpy array
    audio_data = np.concatenate(
        [pre_recording_data] + [segment.flatten() for segment in audio_buffer], axis=0
    )

    # Save the recorded audio data to a WAV file
    write(FILENAME, SAMPLE_RATE, audio_data)
    print(f"Audio data saved to {FILENAME}")


def main():
    """Main function to start the recording process."""
    start_recording()
    save_audio()
    print("Done.")


if __name__ == "__main__":
    main()
