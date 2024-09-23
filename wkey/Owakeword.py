import sounddevice as sd
import numpy as np
from openwakeword.model import Model
import argparse

# Hardcoded model paths
MODEL_PATHS = [
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\hey_llama.tflite",
    r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\hey_computer.tflite",
    # Add paths to other models if needed
]

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
    "--model_paths",
    help="The paths of specific models to load",
    type=str,
    nargs="+",
    default=MODEL_PATHS,  # Use the hardcoded paths
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

# Load pre-trained openwakeword models
owwModel = Model(
    wakeword_models=args.model_paths, inference_framework=args.inference_framework
)

n_models = len(owwModel.models.keys())


# Callback function to process audio chunks
def callback(indata, frames, time, status):
    audio_data = np.frombuffer(indata, dtype=np.int16)
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


# Start the audio stream
with sd.InputStream(
    callback=callback,
    channels=1,
    samplerate=16000,
    dtype="int16",
    blocksize=args.chunk_size,
):
    print("\n\n")
    print("#" * 100)
    print("Listening for wakewords...")
    print("#" * 100)
    print("\n" * (n_models * 3))

    while True:
        sd.sleep(1000)
