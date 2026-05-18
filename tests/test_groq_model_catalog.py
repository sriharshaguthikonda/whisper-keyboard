import json
import urllib.error

import pytest

from wkey.groq_model_catalog import (
    ModelCatalogResult,
    classify_groq_model_error,
    filter_audio_stt_models,
    filter_tool_use_models,
    list_groq_models,
    normalize_model_name,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_list_groq_models_parses_sorted_unique_ids(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout, request.headers))
        return FakeResponse(
            {
                "data": [
                    {"id": "whisper-large-v3"},
                    {"id": "openai/gpt-oss-120b"},
                    {"id": "openai/gpt-oss-120b"},
                    {"id": ""},
                    {"not_id": "ignored"},
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    models = list_groq_models("gsk-test", timeout_seconds=3.0)

    assert models == ("openai/gpt-oss-120b", "whisper-large-v3")
    assert calls[0][0] == "https://api.groq.com/openai/v1/models"
    assert calls[0][1] == 3.0
    assert calls[0][2]["Authorization"] == "Bearer gsk-test"


def test_list_groq_models_raises_runtime_error_for_http_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="http_401"):
        list_groq_models("bad-key")


def test_filter_tool_use_models_prefers_configured_available_models():
    catalog = ModelCatalogResult(
        models=(
            "llama-3.3-70b-versatile",
            "openai/gpt-oss-120b",
            "whisper-large-v3",
        ),
        source="live",
        error=None,
    )

    resolved = filter_tool_use_models(
        configured_models=(
            "decommissioned-model",
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
        ),
        catalog=catalog,
    )

    assert resolved == ("openai/gpt-oss-120b", "llama-3.3-70b-versatile")


def test_filter_tool_use_models_uses_catalog_fallback_when_configured_are_missing():
    catalog = ModelCatalogResult(
        models=(
            "prompt-guard-86m",
            "whisper-large-v3",
            "qwen/qwen3-32b",
            "openai/gpt-oss-20b",
        ),
        source="live",
        error=None,
    )

    resolved = filter_tool_use_models(
        configured_models=("decommissioned-model",),
        catalog=catalog,
    )

    assert resolved == ("openai/gpt-oss-20b", "qwen/qwen3-32b")


def test_filter_audio_stt_models_keeps_only_whisper_models():
    catalog = ModelCatalogResult(
        models=("openai/gpt-oss-120b", "whisper-large-v3", "whisper-large-v3-turbo"),
        source="live",
        error=None,
    )

    resolved = filter_audio_stt_models(
        configured_models=("old-whisper", "whisper-large-v3"),
        catalog=catalog,
    )

    assert resolved == ("whisper-large-v3", "whisper-large-v3-turbo")


def test_filter_models_falls_back_to_configured_when_catalog_unknown():
    catalog = ModelCatalogResult(models=(), source="configured", error="timeout")

    assert filter_tool_use_models(
        configured_models=("model-a", "model-b"),
        catalog=catalog,
    ) == ("model-a", "model-b")


def test_normalize_model_name_maps_legacy_aliases():
    assert normalize_model_name("llama3-70b-8192") == "llama-3.3-70b-versatile"
    assert normalize_model_name(" gpt-oss-120b ") == "openai/gpt-oss-120b"


def test_classify_groq_model_error_detects_removed_model_body():
    body = '{"error":{"message":"The model moonshotai/kimi-k2-instruct-0905 does not exist"}}'

    result = classify_groq_model_error(404, body)

    assert result.is_model_error is True
    assert "model" in result.reason


def test_classify_groq_model_error_does_not_hide_auth_errors():
    result = classify_groq_model_error(401, '{"error":{"message":"invalid api key"}}')

    assert result.is_model_error is False
