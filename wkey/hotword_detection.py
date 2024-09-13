from vosk import Model, KaldiRecognizer
import os
import pyaudio
import numpy as np
import noisereduce as nr
import librosa
import pvporcupine

# Load noise sample for noise reduction
noise_sample_path = "baseline_recording_for_noise_reduction.wav"
noise_sample, sr_noise_sample = librosa.load(noise_sample_path, sr=16000)

# Vosk model path
model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\vosk-model-small-en-us-0.15"

if not os.path.exists(model_path):
    print("Model path does not exist. Exiting.")
    exit(1)

model = Model(model_path)
rec = KaldiRecognizer(model, 16000)

# Initialize Porcupine with custom wake word
hey_llama_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"
porcupine = pvporcupine.create(
    access_key="*********",
    keyword_paths=[hey_llama_word_path],
)

# Initialize PyAudio
p = pyaudio.PyAudio()


# Function to process and reduce noise from audio
def reduce_noise(data, rate):
    audio_float32 = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    reduced_noise_audio = nr.reduce_noise(
        y=audio_float32, y_noise=noise_sample, sr=rate
    )
    return reduced_noise_audio.astype(np.int16).tobytes()


# PyAudio stream
stream = p.open(
    format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512
)

stream.start_stream()

# Main loop
try:
    print("Listening for wake words...")
    while True:
        data = stream.read(512, exception_on_overflow=False)
        # Reduce noise
        processed_data = reduce_noise(data, 16000)
        pcm = np.frombuffer(processed_data, dtype=np.int16)

        # Check for wake word using Porcupine
        keyword_index = porcupine.process(pcm)
        if keyword_index >= 0:
            print("Wake word detected!")
            # After wake word detection, use Vosk for speech recognition
            if rec.AcceptWaveform(processed_data):
                result = rec.Result()
                result_text = result.lower()
                print("Recognized speech:", result_text)
        else:
            print("No wake word detected.")
except KeyboardInterrupt:
    print("\nStopped by user")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    porcupine.delete()
