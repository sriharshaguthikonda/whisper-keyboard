import sounddevice as sd
import numpy as np
import wave

# Parameters
FORMAT = "int16"
CHANNELS = 1
RATE = 48000
RECORD_SECONDS = 3
OUTPUT_FILENAME = "simple_recording.wav"


# Function to record audio
def record_audio():
    print("Recording...")
    recording = sd.rec(
        int(RECORD_SECONDS * RATE), samplerate=RATE, channels=CHANNELS, dtype=FORMAT
    )
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")

    # Save the recording to a WAV file
    with wave.open(OUTPUT_FILENAME, "w") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 2 bytes for int16
        wf.setframerate(RATE)
        wf.writeframes(recording.tobytes())

    print(f"Recording saved as {OUTPUT_FILENAME}")


# Record audio
record_audio()
