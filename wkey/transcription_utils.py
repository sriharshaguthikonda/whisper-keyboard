import io
import os
import time
import queue
import pyautogui
import clipboard
import groq
from groq import Groq
from faster_whisper import WhisperModel
from scipy.io.wavfile import write as wav_write

from .beep_utils import beep, PASTE_BEEP

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

GROQ_MODEL = "distil-whisper-large-v3-en"
local_model = WhisperModel("small.en", device="cuda", num_workers=8)


def transcribe_with_groq(audio_buffer, sample_rate):
    try:
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, audio_buffer)
        byte_io.seek(0)
        transcription = client.audio.transcriptions.create(
            file=("audio_buffer.wav", byte_io.read()),
            model=GROQ_MODEL,
            prompt="Specify context or spelling",
            response_format="json",
            language="en",
            temperature=0.0,
        )
        return transcription.text
    except Exception as e:
        print(f"Groq API error: {e}")
        raise


def transcribe_with_local_model(audio_buffer):
    segments, _ = local_model.transcribe(
        audio_buffer, language="en", suppress_blank=True, vad_filter=True
    )
    return " ".join([segment["text"] for segment in segments])


def process_audio_async(audio_buffer_queue, transcript_queue, sample_rate):
    while True:
        try:
            audio_buffer_for_processing = audio_buffer_queue.get(timeout=5)
            if audio_buffer_for_processing is None:
                break
            try:
                transcript = transcribe_with_groq(audio_buffer_for_processing, sample_rate)
            except groq.RateLimitError:
                print("Groq API rate limit reached, switching to local transcription.")
                transcript = transcribe_with_local_model(audio_buffer_for_processing)
            transcript_queue.put(transcript)
            print(transcript)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"An error occurred during transcription: {e}")


def clean_transcript(transcript_queue):
    while True:
        try:
            transcript = transcript_queue.get()
            original_clipboard_content = clipboard.paste()
            clipboard.copy(transcript)
            pyautogui.hotkey("ctrl", "v")
            beep(PASTE_BEEP)
            print("Transcript pasted")
            time.sleep(0.1)
            clipboard.copy(original_clipboard_content)
            time.sleep(0.1)
            clipboard.copy(transcript)
        except Exception as e:
            print(f"An error occurred in clean_transcript: {e}")
