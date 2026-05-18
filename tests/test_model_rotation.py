from wkey.model_rotation import ModelRotator, refresh_groq_model_rotators


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


def test_refresh_groq_model_rotators_filters_catalog(monkeypatch):
    from wkey import model_rotation
    from wkey.groq_model_catalog import ModelCatalogResult

    monkeypatch.setattr(
        model_rotation,
        "get_groq_model_catalog",
        lambda api_key, force_refresh=False: ModelCatalogResult(
            models=("openai/gpt-oss-120b", "whisper-large-v3"),
            source="live",
            error=None,
        ),
    )

    result = refresh_groq_model_rotators("gsk-test", force_refresh=True)

    assert result.source == "live"
    assert model_rotation.next_tool_use_model() == "openai/gpt-oss-120b"
    assert model_rotation.next_audio_stt_model() == "whisper-large-v3"
