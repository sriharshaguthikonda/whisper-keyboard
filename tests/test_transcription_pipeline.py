import asyncio
import queue

import numpy as np
import pytest


def test_transcription_pipeline_routes_computer_command(monkeypatch):
    from wkey.transcription_pipeline import TranscriptionPipeline

    audio_buffer = np.zeros(3200, dtype=np.float32)
    audio_queue = queue.Queue()
    audio_queue.put((audio_buffer, 1))
    transcript_queue = queue.Queue()

    async def fake_groq(byte_io, keyword_index, max_retries=3):
        _ = byte_io, keyword_index, max_retries
        return "computer open settings"

    def validate_audio_buffer(_):
        return True

    def model_getter():
        return None

    def gpu_available_getter():
        return False

    def initialize_local_model_cpu():
        return None

    def paste_transcript(*_):
        raise AssertionError("paste_transcript should not be called for keyword_index=1")

    global_state = {
        "last_successful_operation": 0,
        "consecutive_failures": 0,
        "is_processing": False,
    }

    pipeline = TranscriptionPipeline(
        audio_buffer_queue=audio_queue,
        transcript_queue=transcript_queue,
        settings_getter=lambda: {"fallback_to_groq": True, "max_retries": 1},
        sample_rate=16000,
        validate_audio_buffer=validate_audio_buffer,
        transcribe_with_groq_async=fake_groq,
        transcribe_with_local_model=lambda *_: "",
        model_getter=model_getter,
        gpu_available_getter=gpu_available_getter,
        initialize_local_model_cpu=initialize_local_model_cpu,
        paste_transcript=paste_transcript,
        beep=lambda *_: None,
        global_state=global_state,
    )

    async def stop_sleep(_):
        raise StopAsyncIteration()

    monkeypatch.setattr(asyncio, "sleep", stop_sleep)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(pipeline.process_audio_async())

    item = transcript_queue.get_nowait()
    assert item == ("open settings", 1)
