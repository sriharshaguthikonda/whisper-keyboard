import asyncio
import io
import queue

import numpy as np
import pytest
from scipy.io.wavfile import write as wav_write

from wkey.speaker_filter import SpeakerFilterResult


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


def _run_one_pipeline_cycle(monkeypatch, pipeline):
    async def stop_sleep(_):
        raise StopAsyncIteration()

    monkeypatch.setattr(asyncio, "sleep", stop_sleep)
    with pytest.raises(StopAsyncIteration):
        asyncio.run(pipeline.process_audio_async())


def _base_global_state():
    return {
        "last_successful_operation": 0,
        "consecutive_failures": 0,
        "is_processing": False,
    }


def _expected_wav_size(audio, sample_rate):
    byte_io = io.BytesIO()
    wav_write(byte_io, sample_rate, audio)
    return byte_io.getbuffer().nbytes


def test_manual_dictation_filters_audio_before_transcription(monkeypatch):
    from wkey.transcription_pipeline import TranscriptionPipeline

    class FakeSpeakerFilter:
        def __init__(self):
            self.calls = []

        def filter_audio(self, audio, sample_rate):
            self.calls.append((audio.copy(), sample_rate))
            return SpeakerFilterResult(
                audio=np.ones(10, dtype=np.float32),
                accepted_seconds=1.0,
                rejected_seconds=1.0,
                decision="filtered",
                scores=[0.9, 0.1],
                threshold=0.7,
                profile_loaded=True,
            )

    audio_buffer = np.zeros(20, dtype=np.float32)
    audio_queue = queue.Queue()
    audio_queue.put((audio_buffer, None))
    transcript_queue = queue.Queue()
    pasted = []
    groq_wav_sizes = []
    status_updates = []
    fake_filter = FakeSpeakerFilter()
    global_state = _base_global_state()

    async def fake_groq(byte_io, keyword_index, max_retries=3):
        _ = keyword_index, max_retries
        groq_wav_sizes.append(byte_io.getbuffer().nbytes)
        return "filtered text"

    pipeline = TranscriptionPipeline(
        audio_buffer_queue=audio_queue,
        transcript_queue=transcript_queue,
        settings_getter=lambda: {
            "fallback_to_groq": True,
            "max_retries": 1,
            "speaker_filter_enabled": True,
            "speaker_filter_apply_to": "dictation",
        },
        sample_rate=10,
        validate_audio_buffer=lambda _: True,
        transcribe_with_groq_async=fake_groq,
        transcribe_with_local_model=lambda *_: "",
        model_getter=lambda: None,
        gpu_available_getter=lambda: False,
        initialize_local_model_cpu=lambda: None,
        paste_transcript=lambda transcript, *_: pasted.append(transcript),
        beep=lambda *_: None,
        global_state=global_state,
        speaker_filter_getter=lambda: fake_filter,
        speaker_filter_status_writer=lambda status: status_updates.append(status),
    )

    _run_one_pipeline_cycle(monkeypatch, pipeline)

    assert len(fake_filter.calls) == 1
    assert np.array_equal(fake_filter.calls[0][0], audio_buffer)
    assert fake_filter.calls[0][1] == 10
    assert groq_wav_sizes == [_expected_wav_size(np.ones(10, dtype=np.float32), 10)]
    assert pasted == ["filtered text"]
    assert global_state["last_speaker_filter"]["decision"] == "filtered"
    assert global_state["last_speaker_filter"]["accepted_seconds"] == 1.0
    assert status_updates[-1]["decision"] == "filtered"
    assert status_updates[-1]["rejected_seconds"] == 1.0


def test_rejected_manual_dictation_does_not_transcribe_or_paste(monkeypatch):
    from wkey.transcription_pipeline import TranscriptionPipeline

    class RejectingSpeakerFilter:
        def filter_audio(self, audio, sample_rate):
            _ = audio, sample_rate
            return SpeakerFilterResult(
                audio=np.zeros((0,), dtype=np.float32),
                accepted_seconds=0.0,
                rejected_seconds=2.0,
                decision="rejected",
                scores=[0.1, 0.2],
                threshold=0.7,
                profile_loaded=True,
            )

    audio_queue = queue.Queue()
    audio_queue.put((np.zeros(20, dtype=np.float32), None))
    transcript_queue = queue.Queue()
    pasted = []
    beeps = []
    global_state = _base_global_state()

    async def fake_groq(*_args, **_kwargs):
        raise AssertionError("Rejected audio should not reach Groq")

    pipeline = TranscriptionPipeline(
        audio_buffer_queue=audio_queue,
        transcript_queue=transcript_queue,
        settings_getter=lambda: {
            "fallback_to_groq": True,
            "max_retries": 1,
            "speaker_filter_enabled": True,
            "speaker_filter_apply_to": "dictation",
        },
        sample_rate=10,
        validate_audio_buffer=lambda _: True,
        transcribe_with_groq_async=fake_groq,
        transcribe_with_local_model=lambda *_: "",
        model_getter=lambda: None,
        gpu_available_getter=lambda: False,
        initialize_local_model_cpu=lambda: None,
        paste_transcript=lambda transcript, *_: pasted.append(transcript),
        beep=lambda *args: beeps.append(args),
        global_state=global_state,
        speaker_filter_getter=lambda: RejectingSpeakerFilter(),
    )

    _run_one_pipeline_cycle(monkeypatch, pipeline)

    assert pasted == []
    assert transcript_queue.empty()
    assert beeps
    assert global_state["last_speaker_filter"]["decision"] == "rejected"


@pytest.mark.parametrize("keyword_index", [0, 1])
def test_command_routes_bypass_speaker_filter(monkeypatch, keyword_index):
    from wkey.transcription_pipeline import TranscriptionPipeline

    audio_queue = queue.Queue()
    audio_queue.put((np.zeros(20, dtype=np.float32), keyword_index))
    transcript_queue = queue.Queue()
    global_state = _base_global_state()

    async def fake_groq(byte_io, seen_keyword_index, max_retries=3):
        _ = byte_io, max_retries
        assert seen_keyword_index == keyword_index
        if keyword_index == 1:
            return "computer open settings"
        return "run command"

    def speaker_filter_getter():
        raise AssertionError("Command routes should bypass speaker filtering")

    pipeline = TranscriptionPipeline(
        audio_buffer_queue=audio_queue,
        transcript_queue=transcript_queue,
        settings_getter=lambda: {
            "fallback_to_groq": True,
            "max_retries": 1,
            "speaker_filter_enabled": True,
            "speaker_filter_apply_to": "dictation",
        },
        sample_rate=10,
        validate_audio_buffer=lambda _: True,
        transcribe_with_groq_async=fake_groq,
        transcribe_with_local_model=lambda *_: "",
        model_getter=lambda: None,
        gpu_available_getter=lambda: False,
        initialize_local_model_cpu=lambda: None,
        paste_transcript=lambda *_: None,
        beep=lambda *_: None,
        global_state=global_state,
        speaker_filter_getter=speaker_filter_getter,
    )

    _run_one_pipeline_cycle(monkeypatch, pipeline)

    if keyword_index == 1:
        assert transcript_queue.get_nowait() == ("open settings", 1)
    else:
        assert transcript_queue.get_nowait() == ("run command", 0)
    assert "last_speaker_filter" not in global_state
