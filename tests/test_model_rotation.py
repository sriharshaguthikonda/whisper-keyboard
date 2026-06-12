from wkey.model_rotation import (
    ModelRotator,
    hydrate_groq_model_rotators,
    refresh_groq_model_rotators,
)


def test_model_rotator_skips_quarantined_model_until_cooldown_expires():
    now = [100.0]
    rotator = ModelRotator("tool_use", ["bad-model", "good-model"], clock=lambda: now[0])

    assert rotator.next() == "bad-model"

    rotator.mark_unavailable("bad-model", "model_unavailable_http_404", cooldown_seconds=60)

    assert rotator.next() == "good-model"

    now[0] = 161.0

    assert rotator.next() == "bad-model"


def test_model_rotator_falls_back_when_all_models_are_quarantined():
    rotator = ModelRotator("tool_use", ["model-a"], clock=lambda: 10.0)
    rotator.mark_unavailable("model-a", "model_unavailable_http_404", cooldown_seconds=60)

    assert rotator.next() == "model-a"


def test_model_rotator_skips_rate_limited_model_without_quarantine():
    now = [100.0]
    rotator = ModelRotator("tool_use", ["limited-model", "ready-model"], clock=lambda: now[0])

    assert rotator.next() == "limited-model"

    rotator.mark_rate_limited("limited-model", "rate_limit_http_429", cooldown_seconds=10)

    assert rotator.next() == "ready-model"

    now[0] = 111.0

    assert rotator.next() == "limited-model"


def test_refresh_groq_model_rotators_filters_catalog(monkeypatch):
    from wkey import model_rotation
    from wkey.groq_model_catalog import ModelCatalogResult

    monkeypatch.setattr(
        model_rotation,
        "get_groq_model_catalog",
        lambda api_key, **kwargs: ModelCatalogResult(
            models=(
                "llama-3.3-70b-versatile",
                "openai/gpt-oss-120b",
                "whisper-large-v3",
                "whisper-large-v3-turbo",
            ),
            source="live",
            error=None,
        ),
    )

    result = refresh_groq_model_rotators("gsk-test", force_refresh=True)

    assert result.source == "live"
    assert model_rotation.next_tool_use_model() == "openai/gpt-oss-120b"
    assert model_rotation.next_audio_stt_model() == "whisper-large-v3-turbo"


def test_active_static_defaults_drop_absent_legacy_models():
    from wkey import model_rotation

    assert "moonshotai/kimi-k2-instruct-0905" not in model_rotation.TOOL_USE_MODELS
    assert (
        "meta-llama/llama-4-maverick-17b-128e-instruct"
        not in model_rotation.TOOL_USE_MODELS
    )
    assert model_rotation.TOOL_USE_MODELS[0] == "openai/gpt-oss-120b"


def test_hydrate_groq_model_rotators_uses_cache_path_first(monkeypatch):
    from wkey import model_rotation
    from wkey.groq_model_catalog import ModelCatalogResult

    calls = []

    def fake_refresh(api_key, **kwargs):
        calls.append((api_key, kwargs))
        return ModelCatalogResult(
            models=("openai/gpt-oss-120b",),
            source="cache",
            error=None,
        )

    monkeypatch.setattr(model_rotation, "refresh_groq_model_rotators", fake_refresh)

    result = hydrate_groq_model_rotators("gsk-test", background=False)

    assert result.source == "cache"
    assert calls == [("gsk-test", {"force_refresh": False})]
