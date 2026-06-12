import asyncio
import io

import numpy as np

from wkey.groq_model_catalog import classify_groq_model_error
from wkey.transcription_utils import (
    transcribe_pre_recording_buffer,
    transcribe_with_groq_async,
)


class FakePostContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeResponse:
    def __init__(self, status, body, *, reason="OK"):
        self.status = status
        self.reason = reason
        self.body = body

    async def text(self):
        return self.body

    async def json(self):
        return {"text": "hello world"}

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"http_{self.status}")


class FakeClientSession:
    responses = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        response = self.responses.pop(0)
        return FakePostContext(response)


def test_stt_404_model_error_is_recoverable():
    body = '{"error":{"message":"model whisper-old is not supported"}}'

    result = classify_groq_model_error(400, body)

    assert result.is_model_error
    assert result.reason == "model_unavailable_http_400"


def test_transcribe_with_groq_async_reports_model_failure_and_retries(monkeypatch):
    FakeClientSession.responses = [
        FakeResponse(
            400,
            '{"error":{"message":"model whisper-old is not supported"}}',
            reason="Bad Request",
        ),
        FakeResponse(200, "{}"),
    ]
    models = iter(["whisper-old", "whisper-large-v3-turbo"])
    failures = []

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("wkey.transcription_utils.aiohttp.ClientSession", FakeClientSession)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    result = asyncio.run(
        transcribe_with_groq_async(
            io.BytesIO(b"fake-audio"),
            None,
            "gsk-test",
            lambda: next(models),
            "prompt",
            {"session": None},
            max_retries=2,
            report_model_failure=lambda model, reason: failures.append((model, reason)),
        )
    )

    assert result == "hello world"
    assert failures == [("whisper-old", "model_unavailable_http_400")]


def test_transcribe_with_groq_async_reports_rate_limit_without_model_failure(monkeypatch):
    FakeClientSession.responses = [
        FakeResponse(
            429,
            '{"error":{"message":"rate limit exceeded"}}',
            reason="Too Many Requests",
        ),
        FakeResponse(200, "{}"),
    ]
    models = iter(["whisper-large-v3-turbo", "whisper-large-v3"])
    failures = []
    rate_limits = []

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("wkey.transcription_utils.aiohttp.ClientSession", FakeClientSession)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    result = asyncio.run(
        transcribe_with_groq_async(
            io.BytesIO(b"fake-audio"),
            None,
            "gsk-test",
            lambda: next(models),
            "prompt",
            {"session": None},
            max_retries=2,
            report_model_failure=lambda model, reason: failures.append((model, reason)),
            report_rate_limit=lambda model, reason: rate_limits.append((model, reason)),
        )
    )

    assert result == "hello world"
    assert failures == []
    assert rate_limits == [("whisper-large-v3-turbo", "rate_limit_http_429")]


def test_transcribe_pre_recording_buffer_reports_model_failure_and_retries(monkeypatch):
    FakeClientSession.responses = [
        FakeResponse(
            400,
            '{"error":{"message":"model whisper-old is not supported"}}',
            reason="Bad Request",
        ),
        FakeResponse(200, "{}"),
    ]
    models = iter(["whisper-old", "whisper-large-v3-turbo"])
    failures = []

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("wkey.transcription_utils.aiohttp.ClientSession", FakeClientSession)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    result = transcribe_pre_recording_buffer(
        np.zeros(32, dtype=np.int16),
        16000,
        "gsk-test",
        "prompt",
        lambda: next(models),
        max_retries=2,
        retry_delay=0,
        report_model_failure=lambda model, reason: failures.append((model, reason)),
    )

    assert result == "hello world"
    assert failures == [("whisper-old", "model_unavailable_http_400")]
