import asyncio
import io
import logging
from typing import Callable, Dict, Optional

import aiohttp
import numpy as np
from scipy.io.wavfile import write as wav_write


def transcribe_pre_recording_buffer(
    pre_recording_data,
    sample_rate: int,
    api_key: str,
    prompt: str,
    get_groq_audio_model: Callable[[], str],
    max_retries: int = 3,
    retry_delay: int = 2,
    timeout_total: float = 10.0,
):
    """Transcribe a short pre-recording buffer using Groq."""
    if not api_key:
        logging.error("Groq API key missing for pre-recording transcription")
        return ""

    try:
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, pre_recording_data)
        byte_io.seek(0)
    except Exception as e:
        logging.error("Error preparing pre-recording buffer: %s", e, exc_info=True)
        return ""

    async def _run():
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        model_name = get_groq_audio_model()
        timeout = aiohttp.ClientTimeout(
            total=timeout_total,
            connect=min(5.0, timeout_total),
            sock_read=max(1.0, timeout_total - 5.0),
        )

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    form_data = aiohttp.FormData()
                    audio_bytes = byte_io.getvalue()
                    form_data.add_field(
                        "file",
                        audio_bytes,
                        filename="pre_recording.wav",
                        content_type="audio/wav",
                    )
                    form_data.add_field("model", model_name)
                    form_data.add_field("response_format", "json")
                    form_data.add_field("prompt", prompt)
                    form_data.add_field("language", "en")
                    form_data.add_field("temperature", "0.0")

                    async with session.post(url, data=form_data, headers=headers) as response:
                        response_text = await response.text()
                        if response.status >= 400:
                            logging.error(
                                "Groq API error %s %s: %s",
                                response.status,
                                response.reason,
                                response_text,
                            )
                        response.raise_for_status()
                        transcription = await response.json()
                        return transcription.get("text", "").lower()
            except Exception as e:
                logging.error(
                    "Error in transcribe_pre_recording_buffer (attempt %s): %s",
                    attempt + 1,
                    e,
                    exc_info=True,
                )
                if attempt + 1 < max_retries:
                    await asyncio.sleep(retry_delay)

        return ""

    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        logging.error("Error in transcribe_pre_recording_buffer: %s", e, exc_info=True)
        return ""


async def transcribe_with_groq_async(
    byte_io: io.BytesIO,
    keyword_index: Optional[int],
    api_key: str,
    get_groq_audio_model: Callable[[], str],
    prompt: str,
    groq_session_holder: Dict[str, Optional[aiohttp.ClientSession]],
    max_retries: int = 3,
):
    """Async transcription via Groq API with retry logic."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    model_name = get_groq_audio_model()
    logging.info(
        "transcribe_with_groq_async: Starting with model %s (keyword_index=%s)",
        model_name,
        keyword_index,
    )
    if keyword_index == 1:
        logging.info(
            "transcribe_with_groq_async: Using wake-command prompt bias for 'computer'"
        )

    for attempt in range(max_retries):
        try:
            logging.info("transcribe_with_groq_async: Attempt %d of %d", attempt + 1, max_retries)
            
            # Create a fresh session for each request to avoid cross-event-loop issues
            timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
            logging.info("transcribe_with_groq_async: Creating new aiohttp session")
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logging.info("transcribe_with_groq_async: Building form data")
                form_data = aiohttp.FormData()
                audio_bytes = byte_io.getvalue()
                logging.info(
                    "transcribe_with_groq_async: Audio size = %d bytes (keyword_index=%s)",
                    len(audio_bytes),
                    keyword_index,
                )
                form_data.add_field(
                    "file",
                    audio_bytes,
                    filename="pre_recording.wav",
                    content_type="audio/wav",
                )
                form_data.add_field("model", model_name)
                form_data.add_field("response_format", "json")
                form_data.add_field("prompt", prompt)
                form_data.add_field("language", "en")
                form_data.add_field("temperature", "0.0")

                logging.info("transcribe_with_groq_async: Sending POST request to Groq")
                async with session.post(url, data=form_data, headers=headers) as response:
                    response_text = await response.text()
                    if response.status == 404:
                        logging.error("Groq API endpoint not found: %s", response.url)
                        response.raise_for_status()
                    if response.status >= 400:
                        logging.error(
                            "Groq API error %s %s: %s",
                            response.status,
                            response.reason,
                            response_text,
                        )
                    response.raise_for_status()
                    transcription = await response.json()
                    logging.info("transcribe_with_groq_async: Got transcription response")
                    return transcription["text"].lower()
        except aiohttp.ClientResponseError as e:
            logging.error(
                "Groq API client error: %s, message='%s', url='%s'",
                e.status,
                e.message,
                e.request_info.url,
                exc_info=True,
            )
            if e.status == 404:
                raise
        except Exception as e:
            logging.error("Unexpected error in transcribe_with_groq_async: %s", e, exc_info=True)
        logging.info("transcribe_with_groq_async: Sleeping before retry")
        await asyncio.sleep(2)

    logging.error("Failed to transcribe after %s attempts", max_retries)
    return None


def transcribe_with_local_model(audio_buffer, keyword_index, model, sample_rate: int):
    """Transcribe using local Whisper model if available."""
    try:
        _ = keyword_index  # reserved for prompt selection in future

        try:
            if model is None:
                logging.info("Local model not initialized")
                return ""
            logging.info("using WhisperModel on CUDA")
            byte_io = io.BytesIO()
            wav_write(byte_io, sample_rate, audio_buffer)
            byte_io.seek(0)
            segments, _ = model.transcribe(byte_io, language="en")
            transcription = " ".join(segment.text for segment in segments)
            logging.info(transcription)
            return transcription
        except Exception as e:
            logging.info("Faster Whisper error: %s", e)
            return "Transcription failed"
    except Exception as e:
        logging.error("Error in transcribe_with_local_model: %s", e, exc_info=True)
        return ""


def validate_audio_buffer(audio_buffer, sample_rate: int):
    """Validate audio buffer before processing."""
    try:
        if audio_buffer is None or len(audio_buffer) == 0:
            logging.warning("Empty audio buffer received")
            return False
        if not isinstance(audio_buffer, np.ndarray):
            logging.error("Invalid audio buffer type: %s", type(audio_buffer))
            return False
        if len(audio_buffer) < sample_rate * 0.1:
            logging.warning("Audio buffer too short")
            return False
        return True
    except Exception as e:
        logging.error("Error validating audio buffer: %s", e, exc_info=True)
        return False


def create_wav_buffer(audio_buffer, sample_rate: int):
    """Create a WAV byte buffer from numpy audio."""
    try:
        byte_io = io.BytesIO()
        wav_write(byte_io, sample_rate, audio_buffer)
        byte_io.seek(0)
        return byte_io
    except Exception as e:
        logging.error("Error creating WAV buffer: %s", e, exc_info=True)
        return None


async def get_transcript_with_retries(
    byte_io: io.BytesIO,
    keyword_index: Optional[int],
    settings: dict,
    api_key: str,
    get_groq_audio_model: Callable[[], str],
    prompt: str,
    groq_session_holder: Dict[str, Optional[aiohttp.ClientSession]],
    local_model,
    sample_rate: int,
):
    """Attempt Groq transcription with optional local fallback."""
    for attempt in range(settings.get("max_retries", 3)):
        try:
            if settings.get("fallback_to_groq", True):
                transcript = await transcribe_with_groq_async(
                    byte_io,
                    keyword_index,
                    api_key,
                    get_groq_audio_model,
                    prompt,
                    groq_session_holder,
                )
                if transcript:
                    return transcript.lower()
        except Exception as e:
            logging.error("Transcription attempt %s failed: %s", attempt + 1, e)
            if attempt == settings.get("max_retries", 3) - 1:
                return transcribe_with_local_model(byte_io, keyword_index, local_model, sample_rate)
            await asyncio.sleep(1)
    return None
