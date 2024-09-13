# hey_llama_detection.py

from vosk import Model, KaldiRecognizer
import pyaudio
import pvporcupine


# Initialize components for wake word detection
model_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\vosk-model-small-en-us-0.15"

if not os.path.exists(model_path):
    print("Model path does not exist. Exiting.")
    exit(1)

model = Model(model_path)
rec = KaldiRecognizer(model, 16000)
load_dotenv()
pico_access_key = os.getenv("PICO_ACCESS_KEY")

hey_llama_word_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\porcupine\Hey-llama_en_windows_v3_0_0.ppn"
porcupine = pvporcupine.create(
    pico_access_key,
    keyword_paths=[hey_llama_word_path],
)


p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512
)
stream.start_stream()


def listen_for_wake_word():
    print("Listening for wake words...")
    while True:
        data = stream.read(512, exception_on_overflow=False)
        pcm = np.frombuffer(data, dtype=np.int16)

        # Check for wake word using Porcupine
        keyword_index = porcupine.process(pcm)
        if keyword_index >= 0:
            print("Wake word detected!")
            start_recording()
            time.sleep(2)
            stop_recording()


def cleanup():
    if stream:
        if stream.active:
            stream.stop()
        stream.close()
    porcupine.delete()
    p.terminate()
    print("Cleanup completed.")
