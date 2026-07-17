import json
import types

from wkey import ask_ai_providers


def test_auto_selection_prefers_non_groq_provider_for_standard_work(monkeypatch, tmp_path):
    monkeypatch.setenv("WKEY_RUNTIME_DIR", str(tmp_path))
    candidates = [
        ask_ai_providers.ModelCandidate(
            provider="groq",
            model="openai/gpt-oss-120b",
            power_score=940,
            context_length=131072,
        ),
        ask_ai_providers.ModelCandidate(
            provider="cerebras",
            model="qwen-3-235b-a22b-instruct-2507",
            power_score=960,
            context_length=131072,
        ),
    ]

    selected = ask_ai_providers.select_model_for_question(
        "Explain how PATH updates work in PowerShell.", candidates
    )

    assert selected.provider == "cerebras"
    assert selected.model == "qwen-3-235b-a22b-instruct-2507"


def test_question_complexity_classification_drives_auto_model_choice():
    candidates = [
        ask_ai_providers.ModelCandidate(
            provider="cerebras",
            model="llama-3.3-70b",
            power_score=800,
            context_length=0,
        ),
        ask_ai_providers.ModelCandidate(
            provider="openrouter",
            model="deepseek/deepseek-r1-0528",
            power_score=1000,
            context_length=163840,
        ),
    ]

    simple = ask_ai_providers.select_model_for_question("What is PATH?", candidates)
    standard = ask_ai_providers.select_model_for_question(
        "Explain how this Ask-AI routing fix reduces rate limits.", candidates
    )
    complex_model = ask_ai_providers.select_model_for_question(
        "Design a robust multi-provider Ask-AI routing policy with failure handling.",
        candidates,
    )

    assert ask_ai_providers.classify_question_complexity("What is PATH?") == "simple"
    assert (
        ask_ai_providers.classify_question_complexity(
            "Explain how this Ask-AI routing fix reduces rate limits."
        )
        == "standard"
    )
    assert (
        ask_ai_providers.classify_question_complexity(
            "Design a robust multi-provider Ask-AI routing policy with failure handling."
        )
        == "complex"
    )
    assert simple.provider == "cerebras"
    assert standard.provider == "cerebras"
    assert complex_model.provider == "openrouter"


def test_deprecated_groq_compound_config_routes_to_auto(monkeypatch, tmp_path):
    monkeypatch.setenv("WKEY_RUNTIME_DIR", str(tmp_path))
    calls = []

    def fake_select(question, candidates, configured_model="auto"):
        calls.append(configured_model)
        return ask_ai_providers.ModelCandidate(
            provider="sambanova",
            model="Llama-4-Maverick-17B-128E-Instruct",
            power_score=845,
            context_length=128000,
        )

    monkeypatch.setattr(ask_ai_providers, "select_model_for_question", fake_select)
    monkeypatch.setattr(
        ask_ai_providers,
        "_candidate_models",
        lambda refresh=False: [
            ask_ai_providers.ModelCandidate(
                provider="sambanova",
                model="Llama-4-Maverick-17B-128E-Instruct",
                power_score=845,
                context_length=128000,
            )
        ],
    )
    monkeypatch.setattr(
        ask_ai_providers,
        "_post_chat_completion",
        lambda candidate, question, timeout_seconds, max_tokens: "Answer.",
    )

    result = ask_ai_providers.complete_ask_ai(
        "Question?", configured_model="groq/compound"
    )

    assert result.answer == "Answer."
    assert calls == ["auto"]


def test_completion_tries_next_provider_without_sdk_retries(monkeypatch, tmp_path):
    monkeypatch.setenv("WKEY_RUNTIME_DIR", str(tmp_path))
    attempts = []
    candidates = [
        ask_ai_providers.ModelCandidate(
            provider="cerebras",
            model="qwen-3-235b-a22b-instruct-2507",
            power_score=960,
            context_length=131072,
        ),
        ask_ai_providers.ModelCandidate(
            provider="sambanova",
            model="Llama-4-Maverick-17B-128E-Instruct",
            power_score=845,
            context_length=128000,
        ),
    ]

    monkeypatch.setattr(ask_ai_providers, "_candidate_models", lambda refresh=False: candidates)
    monkeypatch.setattr(
        ask_ai_providers,
        "select_model_for_question",
        lambda question, candidates, configured_model="auto": candidates[0],
    )

    def post(candidate, question, timeout_seconds, max_tokens):
        attempts.append((candidate.provider, candidate.model, max_tokens))
        if candidate.provider == "cerebras":
            raise ask_ai_providers.ProviderRequestError("rate_limit")
        return "Answer."

    monkeypatch.setattr(ask_ai_providers, "_post_chat_completion", post)

    result = ask_ai_providers.complete_ask_ai(
        "Question?", configured_model="auto", max_tokens=768
    )

    assert result.answer == "Answer."
    assert attempts == [
        ("cerebras", "qwen-3-235b-a22b-instruct-2507", 768),
        ("sambanova", "Llama-4-Maverick-17B-128E-Instruct", 768),
    ]


def test_model_catalog_parse_filters_groq_non_chat_models():
    payload = json.dumps(
        {
            "data": [
                {"id": "whisper-large-v3"},
                {"id": "openai/gpt-oss-120b", "context_window": 131072},
                {"id": "canopylabs/orpheus-v1-english"},
            ]
        }
    ).encode("utf-8")

    models = ask_ai_providers._parse_openai_models(payload, "groq")

    assert models == [
        ask_ai_providers.ModelCandidate(
            provider="groq",
            model="openai/gpt-oss-120b",
            power_score=940,
            context_length=131072,
        )
    ]


def test_unknown_large_parameter_models_do_not_outrank_known_reasoning_defaults():
    unknown_score = ask_ai_providers._score_model("provider/unknown-671b", 128000)
    known_score = ask_ai_providers._score_model("deepseek/deepseek-r1", 0)

    assert unknown_score == 900
    assert known_score == 1000
