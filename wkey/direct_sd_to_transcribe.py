import sounddevice as sd
import numpy as np

# Initialize a global buffer to store the recorded audio
audio_buffer = np.array([], dtype='float32')

# Function to list all devices
def list_devices():
    print(sd.query_devices())


# Initialize audio_buffer as an empty 2D array
audio_buffer = np.empty((0, 1), dtype='float32')  # Make sure 'channels' is defined
audio_chunks = []


def build_recorded_audio():
    if not audio_chunks:
        return np.empty((0, 1), dtype='float32')
    return np.concatenate(audio_chunks, axis=0).astype('float32', copy=False)

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_chunks.append(indata[:frames].copy())



# Test recording function using InputStream
def test_recording(duration=5, sample_rate=16000, channels=1, device=None):
    global audio_buffer, audio_chunks
    print("Starting test recording with InputStream...")

    # Clear the buffer before starting a new recording
    audio_buffer = np.empty((0, channels), dtype='float32')
    audio_chunks = []
    
    with sd.InputStream(samplerate=sample_rate, channels=channels, callback=audio_callback):
        sd.sleep(duration * 1000)  # Wait for the specified duration (in milliseconds)

    audio_buffer = build_recorded_audio()
    if audio_buffer.size > 0:
        print(f"Captured {audio_buffer.size} samples.")
    else:
        print("No audio data captured.")

if __name__ == "__main__":
    list_devices()  # Uncomment this to print all available devices
    # You can specify the device index in test_recording if auto-selection doesn't work
    test_recording()
