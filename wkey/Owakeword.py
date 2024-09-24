import os
import pyaudio
import numpy as np
from openwakeword.model import Model
import argparse

# Hardcoded model directory
MODEL_DIR = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models"  # Update this path

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
    "--model_dir",
    help="The directory containing models to load",
    type=str,
    default=MODEL_DIR,  # Use the hardcoded directory
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

# Get all .tflite model paths in the specified directory
model_paths = [
    os.path.join(args.model_dir, f)
    for f in os.listdir(args.model_dir)
    if f.endswith(".tflite")
]

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
    wakeword_models=model_paths, inference_framework=args.inference_framework
)

n_models = len(owwModel.models.keys())

# Initialize highest score tracker
highest_score = 0
highest_model = ""

if __name__ == "__main__":
    # Generate output string header
    print("\n\n")
    print("#" * 100)
    print("Listening for wakewords...")
    print("#" * 100)
    print("\n" * (n_models * 3))

    while True:
        # Get audio
        audio = np.frombuffer(mic_stream.read(CHUNK), dtype=np.int16)

        # Feed to openWakeWord model
        prediction = owwModel.predict(audio)

        # Column titles
        n_spaces = 16
        output_string_header = """
            Model Name         | Score | Wakeword Status
            --------------------------------------
            """

        for mdl in owwModel.prediction_buffer.keys():
            # Add scores in formatted table
            scores = list(owwModel.prediction_buffer[mdl])
            curr_score = format(scores[-1], ".20f").replace("-", "")
            score_value = scores[-1]

            output_string_header += f"""{mdl}{" "*(n_spaces - len(mdl))}   | {curr_score[0:5]} | {"--"+" "*20 if score_value <= 0.1 else "Wakeword Detected!"}
            """

            # Check if this is the highest score recorded
            if score_value > highest_score:
                highest_score = score_value
                highest_model = mdl

        # Print results table
        print("\033[F" * (4 * n_models + 1))
        print(output_string_header, "                             ", end="\r")

        # Stop if the highest score is recorded
        if highest_score > 0.5:
            print("\n\n")
            print("#" * 100)
            print(f"Highest score recorded: {highest_score} by model {highest_model}")
            print("#" * 100)
            break
