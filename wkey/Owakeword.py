import os
import soundfile as sf
import numpy as np
import csv
from openwakeword.model import Model
from tkinter import Tk, filedialog

import winsound

# Load models (same as before)
MODEL_DIR = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper-keyboard\wkey\openwakeword_models\onnx"
model_paths = [
    os.path.join(MODEL_DIR, f)
    for f in os.listdir(MODEL_DIR)
    if f.endswith(".onnx") or f.endswith(".tflite")
]
owwModel = Model(wakeword_models=model_paths, inference_framework="onnx")

# CSV logging functionality (same as before)
CSV_LOG_FILE = "llama_wakeword_detection_log.csv"


def read_existing_data():
    data = {}
    if os.path.exists(CSV_LOG_FILE):
        with open(CSV_LOG_FILE, "r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                model_name = row["model_name"]
                data[model_name] = {
                    "false_positive": int(row["false_positive"]),
                    "true_positive": int(row["true_positive"]),
                }
    return data


def write_data_to_csv(data):
    with open(CSV_LOG_FILE, "w", newline="") as csvfile:
        fieldnames = ["model_name", "false_positive", "true_positive"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for model_name, values in data.items():
            writer.writerow(
                {
                    "model_name": model_name,
                    "false_positive": values["false_positive"],
                    "true_positive": values["true_positive"],
                }
            )


def log_to_csv(model_name, detection_status, test_mode):
    data = read_existing_data()
    if model_name not in data:
        data[model_name] = {
            "false_positive": 0,
            "true_positive": 0,
        }

    if test_mode == "false_positive" and detection_status == "Wakeword Detected!":
        data[model_name]["false_positive"] += 1
    elif test_mode == "true_positive" and detection_status == "Wakeword Detected!":
        data[model_name]["true_positive"] += 1

    write_data_to_csv(data)


def process_audio_files(audio_file_paths, chunk_size=1280, test_mode="true_positive"):
    """Process each audio file and run wakeword detection."""
    for file_path in audio_file_paths:
        print(f"Processing file: {file_path}")
        # Read audio file using soundfile (for 16-bit audio)
        audio_data, sample_rate = sf.read(file_path, dtype="int16")

        # Ensure the sample rate matches the model's input requirement
        assert sample_rate == 16000, "Audio file must be at 16kHz sample rate!"

        # Break audio data into chunks and feed them to the model
        for start_idx in range(0, len(audio_data), chunk_size):
            audio_chunk = audio_data[start_idx : start_idx + chunk_size]

            # Ensure the chunk is exactly the size needed (pad if necessary)
            if len(audio_chunk) < chunk_size:
                audio_chunk = np.pad(
                    audio_chunk, (0, chunk_size - len(audio_chunk)), mode="constant"
                )

            # Run the model's prediction on the audio chunk
            prediction = owwModel.predict(audio_chunk)

            # Log the results for each model
            for model_name in owwModel.models:
                score = owwModel.prediction_buffer[model_name][-1]  # Get the last score
                detection_status = (
                    "Wakeword Detected!" if score > 0.1 else "No wakeword"
                )
                log_to_csv(model_name, detection_status, test_mode)


def select_audio_files():
    """Open a dialog box to select audio files."""
    root = Tk()
    root.withdraw()  # Hide the root window
    # Allow the user to select multiple files
    audio_file_paths = filedialog.askopenfilenames(
        title="Select Audio Files", filetypes=[("WAV files", "*.wav")]
    )
    return list(audio_file_paths)


if __name__ == "__main__":
    test_mode = "true_positive"  # You can change this to "false_positive"
    #     test_mode = "false_positive"  # You can change this to "false_positive"

    # Open a dialog to select audio files
    audio_file_paths = select_audio_files()

    if audio_file_paths:
        # Process the selected audio files
        process_audio_files(audio_file_paths, chunk_size=1280, test_mode=test_mode)

    print(f"Testing completed in {test_mode} mode. Log updated.")

    # Frequency (Hz) and duration (ms)
    frequency = 1000  # Set Frequency To 1000 Hertz
    duration = 2000  # Set Duration To 500 ms == 0.5 second

    # Make the beep sound
    winsound.Beep(frequency, duration)
