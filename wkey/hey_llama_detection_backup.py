from vosk import Model, KaldiRecognizer
import os
import pyaudio
import numpy as np
import pvporcupine

# Vosk model path
model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\vosk-model-small-en-us-0.15"

if not os.path.exists(model_path):
    print("Model path does not exist. Exiting.")
    exit(1)

model = Model(model_path)
rec = KaldiRecognizer(model, 16000)
pico_access_key = os.getenv("PICO_ACCESS_KEY")

# Initialize Porcupine with custom wake word
hey_llama_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"
porcupine = pvporcupine.create(
    pico_access_key,
    keyword_paths=[hey_llama_word_path],
)

# Initialize PyAudio
p = pyaudio.PyAudio()

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
        pcm = np.frombuffer(data, dtype=np.int16)

        # Check for wake word using Porcupine
        keyword_index = porcupine.process(pcm)
        if keyword_index >= 0:
            print("Wake word detected!")
            # After wake word detection, use Vosk for speech recognition
            if rec.AcceptWaveform(data):
                result = rec.Result()
                result_text = result.lower()
                print("Recognized speech:", result_text)
except KeyboardInterrupt:
    print("\nStopped by user")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    porcupine.delete()


"""
https://console.picovoice.ai/
https://www.bing.com/chat?form=NTPCHB

import os
import pyaudio
import numpy as np
from vosk import Model, KaldiRecognizer
import pvporcupine

class WakeWordDetector:
    def __init__(self, vosk_model_path, porcupine_model_path, access_key):
        if not os.path.exists(vosk_model_path):
            raise ValueError("Vosk model path does not exist.")
        
        self.model = Model(vosk_model_path)
        self.rec = KaldiRecognizer(self.model, 16000)
        
        self.porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[porcupine_model_path])
        
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512
        )
        self.stream.start_stream()

    def listen(self):
        print("Listening for wake words...")
        try:
            while True:
                data = self.stream.read(512, exception_on_overflow=False)
                pcm = np.frombuffer(data, dtype=np.int16)
                
                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    print("Wake word detected!")
                    if self.rec.AcceptWaveform(data):
                        result = self.rec.Result()
                        result_text = result.lower()
                        print("Recognized speech:", result_text)
                        return result_text
        except KeyboardInterrupt:
            print("\nStopped by user")
        finally:
            self.cleanup()

    def cleanup(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.porcupine.delete()

# Example usage
if __name__ == "__main__":
    vosk_model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\vosk-model-small-en-us-0.15"
    porcupine_model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"
    access_key = 'YOUR_ACCESS_KEY'
    
    detector = WakeWordDetector(vosk_model_path, porcupine_model_path, access_key)
    detector.listen()

from hey_llama_detection import WakeWordDetector

vosk_model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\vosk-model-small-en-us-0.15"
porcupine_model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"
access_key = 'YOUR_ACCESS_KEY'

detector = WakeWordDetector(vosk_model_path, porcupine_model_path, access_key)
result_text = detector.listen()

print("Final recognized text:", result_text)
"""