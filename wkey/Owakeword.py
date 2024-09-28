import os
import pyaudio
import numpy as np
from openwakeword.model import Model
import argparse
from collections import defaultdict
import signal
import sys

# Hardcoded model directory
MODEL_DIR = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx"  # Update this path

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
    default="onnx",
    required=False,
)

args = parser.parse_args()

# Get all .tflite and .onnx model paths in the specified directory
model_paths = [
    os.path.join(args.model_dir, f)
    for f in os.listdir(args.model_dir)
    if f.endswith(".onnx") or f.endswith(".tflite")
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

# Initialize highest score tracker and wakeword count dictionary
highest_score = 0
highest_model = ""
wakeword_count = defaultdict(int)  # Dictionary to count detections for each model


def signal_handler(sig, frame):
    """Handle Ctrl+C to log and print activations at the end."""
    print("\n\n")
    print("#" * 100)
    print("Wakeword Detection Summary:")
    print("#" * 100)

    # Sort wake words by detection count and print the results
    sorted_wakewords = sorted(
        wakeword_count.items(), key=lambda item: item[1], reverse=True
    )

    for model, count in sorted_wakewords:
        print(f"{model}: {count} detections")

    # Exit the program gracefully
    sys.exit(0)


# Register signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    # Generate output string header
    print("\n\n")
    print("#" * 100)
    print(
        "Listening for wakewords... Press Ctrl+C to stop and see activations summary."
    )
    print("#" * 100)
    print("\n" * (n_models * 3))

    while True:
        try:
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

                # Increment count if wake word detected (score > 0.5)
                if score_value > 0.5:
                    wakeword_count[mdl] += 1

            # Print results table
            print("\033[F" * (4 * n_models + 1))
            print(output_string_header, "                             ", end="\r")

        except Exception as e:
            # Handle audio input issues or other exceptions gracefully
            print(f"Error: {e}")


"""


####################################################################################################
Wakeword Detection Summary:
####################################################################################################

false positives


hey_computer7: 99 detections
hey_computer6: 45 detections
heycomputer5: 43 detections
hey_computer10: 37 detections
hey_llama: 27 detections
hey_lama: 21 detections
hey_computer9: 20 detections
hey_cumputer: 14 detections
heycomputer3: 14 detections
heycomputer4: 13 detections
hey_llama2: 12 detections
heylama: 11 detections
hey_computer: 7 detections
heycomputer: 6 detections
heycomputer2: 6 detections
hey_jarvis_v0.1: 5 detections
hey_computer_personal: 4 detections
hey_google: 2 detections
hey_computer8: 1 detections
hey_computer11: 1 detections

"""


"""
true positives

hey_computer6: 2207 detections
hey_computer10: 2019 detections
hey_computer7: 1306 detections
hey_computer9: 1164 detections
heycomputer4: 951 detections
heycomputer5: 947 detections
heycomputer3: 895 detections
hey_computer8: 639 detections
hey_cumputer: 599 detections
heycomputer2: 183 detections
heycomputer: 144 detections
hey_computer (2): 47 detections
hey_computer: 35 detections
hey_llama: 30 detections
hey_llama2: 28 detections
hey_computer_personal: 24 detections
hey_lama: 20 detections
hey_computer11: 14 detections
heycomputer1: 13 detections
hey_mycroft_v0.1: 6 detections
heylama: 2 detections


"""
