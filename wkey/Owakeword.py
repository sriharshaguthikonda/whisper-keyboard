import pyaudio
import numpy as np
from openwakeword.model import Model
import argparse

# Hardcoded model path
MODEL_PATH = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\hey_computer.tflite"  # Update this path

# Parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "--chunk_size",
    help="How much audio (in number of samples) to predict on at once",
    type=int,
    default=1280,
    required=False,
)
parser.add_argument(
    "--model_path",
    help="The path of a specific model to load",
    type=str,
    default=MODEL_PATH,  # Use the hardcoded path
    required=False,
)
parser.add_argument(
    "--inference_framework",
    help="The inference framework to use (either 'onnx' or 'tflite')",
    type=str,
    default="tflite",
    required=False,
)

args = parser.parse_args()

# Get microphone stream
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = args.chunk_size
audio = pyaudio.PyAudio()
mic_stream = audio.open(
    format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
)

# Load pre-trained openwakeword models
owwModel = Model(
    wakeword_models=[args.model_path], inference_framework=args.inference_framework
)

n_models = len(owwModel.models.keys())

# Run capture loop continuously, checking for wakewords
if __name__ == "__main__":
    print("\n\n")
    print("#" * 100)
    print("Listening for wakewords...")
    print("#" * 100)
    print("\n" * (n_models * 3))

    while True:
        # Get audio
        audio_data = np.frombuffer(mic_stream.read(CHUNK), dtype=np.int16)

        # Feed to openWakeWord model
        prediction = owwModel.predict(audio_data)

        # Column titles
        n_spaces = 16
        output_string_header = """
            Model Name         | Score | Wakeword Status
            --------------------------------------
            """

        detected = False  # Flag for wake word detection

        for mdl in owwModel.prediction_buffer.keys():
            # Add scores in formatted table
            scores = list(owwModel.prediction_buffer[mdl])
            curr_score = format(scores[-1], ".20f").replace("-", "")

            if scores[-1] > 0.5:  # Wake word detection threshold
                detected = True
                output_string_header += f"""{mdl}{" "*(n_spaces - len(mdl))}   | {curr_score[0:5]} | Wakeword Detected!\n"""
            else:
                output_string_header += f"""{mdl}{" "*(n_spaces - len(mdl))}   | {curr_score[0:5]} | --{" " * 20}\n"""

        # Print results only if a wake word is detected
        if detected:
            print("\033[F" * (4 * n_models + 1))
            print(output_string_header, "                             ", end="\r")
