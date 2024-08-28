import numpy as np
import sounddevice as sd
import webrtcvad
import sys

# Configuration
sample_rate = 16000  # Sample rate in Hz
frame_duration_ms = 30  # Frame duration in milliseconds
vad = webrtcvad.Vad()
vad.set_mode(1)  # Set the VAD mode (0-3)


def audio_callback(indata, frames, time, status):
    if status:
        print(status)

    # Ensure indata is a numpy array and convert it to int16
    if len(indata) > 0:
        # Use only one channel for VAD
        audio_data = indata[:, 0].astype(np.int16)  # Convert to int16
        frame_size = int(
            sample_rate * frame_duration_ms / 1000
        )  # Frame size in samples

        # Process in chunks of frame_size
        for start in range(0, len(audio_data), frame_size):
            end = min(start + frame_size, len(audio_data))
            frame = audio_data[start:end]

            # If the frame is smaller than the required size, pad it
            if len(frame) < frame_size:
                frame = np.pad(frame, (0, frame_size - len(frame)), "constant")

            frame_bytes = frame.tobytes()

            # Check if speech is detected
            is_speech = vad.is_speech(frame_bytes, sample_rate)
            if is_speech:
                print("Speech detected")
            else:
                print("Silence detected")


def main():
    print("Listening... Press Ctrl+C to stop.")

    try:
        # Start the audio stream
        with sd.InputStream(
            samplerate=sample_rate, channels=1, dtype="int16", callback=audio_callback
        ):
            # Keep the program running
            while True:
                sd.sleep(100)  # Sleep for a short duration to keep the stream alive
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


"""
https://chatgpt.com/c/fefae84e-51f2-4620-92df-950a789d217e
"""
