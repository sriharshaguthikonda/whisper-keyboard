# tts_engine.py
"""TTS engine for whisper-keyboard.

Extracted from voice_commands.py (Phase 6 split). Owns the TTS queues, the
worker threads that drain them, and the provider fallback chain.

Priority order (user directive - never reorder):
    1. edge-tts (Ava, server-side) - DEFAULT_EDGE_VOICE
    2. Kokoro (local)
    3. pyttsx4 (offline, opt-in via ENABLE_PYTTS_FALLBACK)

Public surface (re-exported by voice_commands.py for backward compatibility -
faster_whisper_Mother_of_all_wkey.py, tests, and conftest stubs all reach
these through voice_commands_module.*):
    TTS_queue, TTS_Audio_play_queue                  - queues fed by callers
    process_TTS_queue, process_TTS_Audio_play_queue  - worker loops (threads
        started automatically on import, same as before the split)
    text_to_speech(text, speed, volume, voice)       - primary async entry point
    fallback_kokoro_tts(text, speed, volume)         - local Kokoro fallback
    fallback_offline_tts(text, speed, volume)        - offline pyttsx4 fallback
"""

import os
import gc
import io
import math
import tempfile
import asyncio
import threading
import queue
import logging

import edge_tts
import pyttsx4

from pydub import AudioSegment
from pydub.playback import play


def _parse_csv_env(name: str, default_csv: str):
    raw = os.getenv(name, default_csv)
    return [item.strip() for item in raw.split(",") if item and item.strip()]


# TTS preferences: Ava first, then Edge voice backups, then local fallback.
DEFAULT_EDGE_VOICE = os.getenv("EDGE_TTS_PRIMARY_VOICE", "en-US-AvaNeural")
EDGE_TTS_FALLBACK_VOICES = _parse_csv_env(
    "EDGE_TTS_FALLBACK_VOICES",
    "en-US-JennyNeural,en-US-AriaNeural",
)
KOKORO_FALLBACK_VOICES = _parse_csv_env(
    "KOKORO_FALLBACK_VOICES",
    "af_jessica,af_sky",
)
DEFAULT_TTS_SPEED = float(os.getenv("TTS_DEFAULT_SPEED", "1.3"))
ENABLE_PYTTS_FALLBACK = os.getenv("ENABLE_PYTTS_FALLBACK", "0").strip().lower() not in (
    "0",
    "false",
    "no",
)


# Queue for sentences
TTS_queue = queue.Queue()


# Function to process the queue
def process_TTS_queue():
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        while True:
            sentence = TTS_queue.get()
            if sentence is None:  # Sentinel value to stop the worker
                break
            asyncio.run(text_to_speech(sentence, speed=DEFAULT_TTS_SPEED))
            TTS_queue.task_done()
    except Exception as e:
        logging.error(f"Error processing TTS queue: {e}", exc_info=True)
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


threading.Thread(target=process_TTS_queue, daemon=True).start()


# Function to process the queue
def process_TTS_Audio_play_queue():
    try:
        while True:
            item = TTS_Audio_play_queue.get()
            if item is None:  # Add sentinel check
                break
            fallback_text = None
            fallback_speed = 1.2
            fallback_volume = 1.0
            if isinstance(item, tuple):
                if len(item) >= 5:
                    audio_fp, audio_format, fallback_text, fallback_speed, fallback_volume = item
                elif len(item) == 2:
                    audio_fp, audio_format = item
                else:
                    audio_fp, audio_format = item[0], "mp3"
            else:
                audio_fp, audio_format = item, "mp3"
            audio_fp.seek(0)
            try:
                sound = AudioSegment.from_file(audio_fp, format=audio_format)
                play(sound)
            except Exception as e:
                logging.error(f"Error playing TTS audio: {e}", exc_info=True)
                if fallback_text:
                    if not fallback_kokoro_tts(fallback_text, fallback_speed, fallback_volume):
                        fallback_offline_tts(fallback_text, fallback_speed, fallback_volume)
            TTS_Audio_play_queue.task_done()
    except Exception as e:
        logging.error(f"Error processing TTS audio play queue: {e}", exc_info=True)


# Queue for sentences
TTS_Audio_play_queue = queue.Queue()
TTS_queue = queue.Queue()

# Start threads instead of using executor.submit
threading.Thread(target=process_TTS_Audio_play_queue, daemon=True).start()
threading.Thread(target=process_TTS_queue, daemon=True).start()


# Local Kokoro fallback
_kokoro_pipeline = None


def _get_kokoro_pipeline():
    global _kokoro_pipeline
    if _kokoro_pipeline is not None:
        return _kokoro_pipeline
    try:
        from kokoro import KPipeline
    except Exception as e:
        logging.warning(f"Kokoro not available: {e}")
        return None
    try:
        _kokoro_pipeline = KPipeline(lang_code="a")
        return _kokoro_pipeline
    except Exception as e:
        logging.error(f"Failed to initialize Kokoro pipeline: {e}", exc_info=True)
        return None


def _time_stretch_audio(audio, speed: float):
    if not speed or speed == 1.0:
        return audio
    try:
        import librosa
    except Exception as e:
        logging.warning(f"librosa not available for speed change: {e}")
        return audio
    try:
        return librosa.effects.time_stretch(audio, rate=speed)
    except Exception as e:
        logging.warning(f"Speed change failed: {e}")
        return audio


def _kokoro_speak(text: str, voice_id: str, speed: float = 1.2, volume: float = 1.0) -> bool:
    pipeline = _get_kokoro_pipeline()
    if pipeline is None:
        return False
    try:
        import numpy as np
        import soundfile as sf
    except Exception as e:
        logging.warning(f"Kokoro deps missing: {e}")
        return False

    try:
        audio_chunks = []
        for _, _, audio in pipeline(text, voice=voice_id):
            if audio is None:
                continue
            audio_chunks.append(audio)
        if not audio_chunks:
            return False
        audio = np.concatenate(audio_chunks)
        audio = _time_stretch_audio(audio, speed)
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(out_path, audio, 24000)
        try:
            sound = AudioSegment.from_file(out_path, format="wav")
            if volume and volume != 1.0:
                try:
                    sound = sound + (20 * math.log10(volume))
                except Exception:
                    pass
            play(sound)
        finally:
            try:
                os.remove(out_path)
            except Exception:
                pass
        return True
    except Exception as e:
        logging.error(f"Kokoro playback failed ({voice_id}): {e}", exc_info=True)
        return False


def fallback_kokoro_tts(text: str, speed: float = 1.2, volume: float = 1.0) -> bool:
    for voice_id in KOKORO_FALLBACK_VOICES:
        if _kokoro_speak(text, voice_id, speed, volume):
            return True
    return False


# Function to convert text to speech using edge-tts and play using pydub with speed adjustment
async def text_to_speech(text, speed=DEFAULT_TTS_SPEED, volume=1, voice=None):
    rate = "+" + str(int((speed - 1) * 100)) + "%"
    voice_candidates = []
    if voice:
        voice_candidates.append(voice)
    else:
        voice_candidates.append(DEFAULT_EDGE_VOICE)
        voice_candidates.extend(EDGE_TTS_FALLBACK_VOICES)

    # Deduplicate while preserving order.
    deduped_candidates = []
    seen = set()
    for candidate in voice_candidates:
        if candidate and candidate not in seen:
            deduped_candidates.append(candidate)
            seen.add(candidate)

    last_edge_error = None
    for selected_voice in deduped_candidates:
        try:
            communicate = edge_tts.Communicate(text, selected_voice, rate=rate)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            if not audio_bytes:
                raise ValueError("No audio received from edge-tts.")

            audio_fp = io.BytesIO(audio_bytes)
            audio_fp.seek(0)
            TTS_Audio_play_queue.put((audio_fp, "mp3", text, speed, volume))
            logging.info("Edge TTS voice selected: %s", selected_voice)
            return
        except Exception as e:
            last_edge_error = e
            logging.warning("Edge TTS failed for voice %s: %s", selected_voice, e)

    logging.error("All Edge TTS voices failed: %s", last_edge_error, exc_info=True)
    print("Falling back to local TTS...")
    if not fallback_kokoro_tts(text, speed, volume):
        if ENABLE_PYTTS_FALLBACK:
            fallback_offline_tts(text, speed, volume)
        else:
            logging.warning("pyttsx4 fallback is disabled; no local TTS fallback left.")


# Offline TTS fallback using pyttsx4
def fallback_offline_tts(text, speed=1.2, volume=1):
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        # Initialize pyttsx4 engine
        engine = pyttsx4.init()

        # Set the speed (words per minute)
        engine.setProperty("rate", int(200 * speed))

        # Set the volume (0.0 to 1.0)
        engine.setProperty("volume", volume)

        # Speak the text
        engine.say(text)
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:
            pass
        engine = None
        gc.collect()

    except Exception as e:
        logging.error(f"Error executing fallback_offline_tts: {e}", exc_info=True)
        print(f"Offline TTS failed: {e}")
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass
