import os
from pydub import AudioSegment
from tkinter import Tk, filedialog


def upscale_wav_files(directory_path):
    for filename in os.listdir(directory_path):
        if filename.endswith(".wav"):
            file_path = os.path.join(directory_path, filename)
            audio = AudioSegment.from_wav(file_path)
            # Check if the sample rate is 8000 Hz
            if audio.frame_rate == 8000:
                # Resample to 16000 Hz
                audio = audio.set_frame_rate(16000)
                # Save the upscaled file
                new_file_path = os.path.join(directory_path, f"upscaled_{filename}")
                audio.export(new_file_path, format="wav")
                print(f"Upscaled {filename} to 16kHz")
            else:
                print(f"{filename} is not 8kHz, skipping.")


# Use Tkinter to select the folder at runtime
root = Tk()
root.withdraw()  # Hide the root window
directory_path = filedialog.askdirectory(title="Select Folder Containing WAV Files")
if directory_path:
    upscale_wav_files(directory_path)
else:
    print("No folder selected.")
