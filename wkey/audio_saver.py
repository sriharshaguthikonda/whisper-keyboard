"""Utilities for saving recorded audio to disk."""

import os
import logging
from datetime import datetime

import numpy as np
from scipy.io.wavfile import write as wav_write

GREEN = "\033[92m"
RESET = "\033[0m"


def save_audio(
    audio_data,
    keyword_index,
    directory="J:\\Openwakeword_whisper_keyboard_training_data_hotword\\train",
    sample_rate=16000,
    type_of_audio=None,
):
    try:
        if not os.path.exists(directory):
            logging.info(f"cannot save data to {directory} because it does not exist")
            return

        base_filename = os.path.join(
            directory, f"{type_of_audio}_{keyword_index}_recording.wav"
        )
        filename = base_filename
        counter = 1

        while os.path.exists(filename):
            filename = os.path.join(
                directory,
                f"{type_of_audio}_{keyword_index}_recording_{counter}.wav",
            )
            counter += 1

        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val

        audio_data_int16 = np.int16(audio_data * 32767)
        wav_write(filename, sample_rate, audio_data_int16)
        logging.info(f"{GREEN}Audio saved as {filename}{RESET}")
    except Exception as e:
        logging.error(f"Error in save_audio: {e}", exc_info=True)


def save_manual_recording_if_configured(
    audio_data,
    keyword_index,
    sample_rate=16000,
    target_dir=r"I:\Record_harsha",
):
    try:
        if audio_data is None or len(audio_data) == 0:
            return
        if not os.path.isdir(target_dir):
            return

        key_label_local = "f24" if keyword_index == 0 else "ctrl_r"
        duration_ms = int((len(audio_data) / sample_rate) * 1000)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        base_name = f"manual_{key_label_local}_{timestamp}_{duration_ms}ms.wav"
        filename = os.path.join(target_dir, base_name)
        counter = 1
        while os.path.exists(filename):
            filename = os.path.join(
                target_dir,
                f"manual_{key_label_local}_{timestamp}_{duration_ms}ms_{counter}.wav",
            )
            counter += 1

        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val
        audio_data_int16 = np.int16(audio_data * 32767)
        wav_write(filename, sample_rate, audio_data_int16)
        logging.info(f"{GREEN}Saved manual recording: {filename}{RESET}")
    except Exception as e:
        logging.error(f"Error saving manual recording: {e}", exc_info=True)
