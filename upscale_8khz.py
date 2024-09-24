import os
import torchaudio
from torchaudio.transforms import Resample
from tkinter import Tk, filedialog


def resample_audio(file_path, target_sample_rate=16000):
    waveform, sample_rate = torchaudio.load(file_path)
    resampler = Resample(orig_freq=sample_rate, new_freq=target_sample_rate)
    resampled_waveform = resampler(waveform)
    output_path = os.path.join(
        os.path.dirname(file_path), f"16k_uped_{os.path.basename(file_path)}"
    )
    torchaudio.save(output_path, resampled_waveform, target_sample_rate)
    print(
        f"Resampled {file_path} to {target_sample_rate} Hz and saved as {output_path}"
    )


def main():
    Tk().withdraw()  # Hide the root window
    file_paths = filedialog.askopenfilenames(
        title="Select audio files to resample", filetypes=[("WAV files", "*.wav")]
    )
    for file_path in file_paths:
        resample_audio(file_path)


if __name__ == "__main__":
    main()
