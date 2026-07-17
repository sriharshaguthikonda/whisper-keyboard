import json
import os
import types

import pytest

from wkey import ask_ai_bridge


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ask chat gpt what time is it", "ask chatgpt what time is it"),
        ("ask chad gpt summarize this", "ask chatgpt summarize this"),
        ("ask chatgbt explain", "ask chatgpt explain"),
        ("ask chat gbt explain", "ask chatgpt explain"),
        ("ask chat g p t explain", "ask chatgpt explain"),
        ("ASK CHAT GPT explain", "ASK chatgpt explain"),
    ],
)
def test_normalize_ai_triggers(raw, expected):
    assert ask_ai_bridge.normalize_ai_triggers(raw) == expected


def test_write_job_atomic_schema(tmp_path):
    job_id, path, payload = ask_ai_bridge._write_job_atomic(
        str(tmp_path), "What is next?", job_id="20260707T000000000000Z_deadbeef"
    )

    assert job_id == "20260707T000000000000Z_deadbeef"
    assert path == str(tmp_path / "job_20260707T000000000000Z_deadbeef.json")
    assert not list(tmp_path.glob("*.tmp"))
    assert payload["id"] == job_id
    assert payload["text"] == "What is next?"
    assert "ts" in payload
    assert json.loads((tmp_path / f"job_{job_id}.json").read_text(encoding="utf-8")) == payload


def test_ask_chatgpt_claim_success_does_not_fallback(monkeypatch, tmp_path):
    settings = {
        "ask_ai_enabled": True,
        "ask_ai_model": "groq/compound",
        "ask_chatgpt_claim_timeout_sec": 12,
        "prompt_jobs_dir": str(tmp_path),
    }
    fallback_calls = []
    beeps = []
    original_write = ask_ai_bridge._write_job_atomic

    def write_and_claim(jobs_dir, question, job_id=None):
        result = original_write(jobs_dir, question, job_id="20260707T000000000000Z_deadbeef")
        (tmp_path / "job_20260707T000000000000Z_deadbeef.claimed.browser.json").write_text(
            "{}", encoding="utf-8"
        )
        return result

    monkeypatch.setattr(ask_ai_bridge, "_load_ask_ai_settings", lambda: settings)
    monkeypatch.setattr(ask_ai_bridge, "_write_job_atomic", write_and_claim)
    monkeypatch.setattr(ask_ai_bridge, "ask_ai", lambda question: fallback_calls.append(question))
    monkeypatch.setattr(ask_ai_bridge, "_beep", lambda pattern: beeps.append(pattern))

    assert ask_ai_bridge.ask_chatgpt("What is next?") is True
    assert fallback_calls == []
    assert beeps == [ask_ai_bridge.SUCCESS_BEEP]


def test_ask_chatgpt_timeout_deletes_pending_without_hidden_fallback_by_default(
    monkeypatch, tmp_path
):
    settings = {
        "ask_ai_enabled": True,
        "ask_ai_model": "groq/compound",
        "ask_chatgpt_claim_timeout_sec": 1,
        "prompt_jobs_dir": str(tmp_path),
    }
    fallback_calls = []
    monotonic_values = iter([0.0, 0.1, 1.1])

    monkeypatch.setattr(ask_ai_bridge, "_load_ask_ai_settings", lambda: settings)
    monkeypatch.setattr(ask_ai_bridge, "_new_job_id", lambda: "20260707T000000000000Z_deadbeef")
    monkeypatch.setattr(ask_ai_bridge.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(ask_ai_bridge.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ask_ai_bridge, "ask_ai", lambda question: fallback_calls.append(question) or True)
    monkeypatch.setattr(ask_ai_bridge, "_beep", lambda pattern: None)

    assert ask_ai_bridge.ask_chatgpt("Fallback question") is False
    assert fallback_calls == []
    assert not (tmp_path / "job_20260707T000000000000Z_deadbeef.json").exists()


def test_ask_chatgpt_timeout_can_fallback_when_enabled(monkeypatch, tmp_path):
    settings = {
        "ask_ai_enabled": True,
        "ask_ai_model": "auto",
        "ask_chatgpt_claim_timeout_sec": 1,
        "ask_chatgpt_fallback_to_ai": True,
        "prompt_jobs_dir": str(tmp_path),
    }
    fallback_calls = []
    monotonic_values = iter([0.0, 0.1, 1.1])

    monkeypatch.setattr(ask_ai_bridge, "_load_ask_ai_settings", lambda: settings)
    monkeypatch.setattr(ask_ai_bridge, "_new_job_id", lambda: "20260707T000000000000Z_deadbeef")
    monkeypatch.setattr(ask_ai_bridge.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(ask_ai_bridge.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ask_ai_bridge, "ask_ai", lambda question: fallback_calls.append(question) or True)

    assert ask_ai_bridge.ask_chatgpt("Fallback question") is True
    assert fallback_calls == ["Fallback question"]
    assert not (tmp_path / "job_20260707T000000000000Z_deadbeef.json").exists()


def test_cleanup_old_jobs_skips_delete_race(monkeypatch, tmp_path, caplog):
    pending = tmp_path / "job_old.json"
    claimed = tmp_path / "job_old.claimed.browser.json"
    pending.write_text("{}", encoding="utf-8")
    claimed.write_text("{}", encoding="utf-8")
    old_time = 1_000.0
    os.utime(pending, (old_time, old_time))
    os.utime(claimed, (old_time, old_time))

    removed = []
    original_remove = ask_ai_bridge.os.remove

    def remove_with_race(path):
        if path == str(pending):
            raise PermissionError("claimed concurrently")
        removed.append(path)
        original_remove(path)

    monkeypatch.setattr(ask_ai_bridge.os, "remove", remove_with_race)

    ask_ai_bridge._cleanup_old_jobs(str(tmp_path), now=old_time + ask_ai_bridge.JOB_MAX_AGE_SECONDS + 1)

    assert pending.exists()
    assert removed == [str(claimed)]
    assert not claimed.exists()
    assert "Failed to cleanup Ask-AI job file" not in caplog.text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ask chat gpt that explain the log", "explain the log"),
        ("please ask chatgbt to compare options", "compare options"),
        ("ask ai, write a note", "write a note"),
        ("ask the ai summarize this", "summarize this"),
        ("open settings", ""),
    ],
)
def test_extract_question_from_transcript(raw, expected):
    assert ask_ai_bridge.extract_question_from_transcript(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected_route", "expected_question"),
    [
        (
            "ask chat gpt according to nice guidelines, what is the status of 2 week weight cancer referral pathway? no cancel that, ask this, see if there are any changes in the nice guidelines that are significant in the recent 6 months.",
            "ask_chatgpt",
            "according to nice guidelines, what is the status of 2 week weight cancer referral pathway? no cancel that, ask this, see if there are any changes in the nice guidelines that are significant in the recent 6 months",
        ),
        (
            "ask ai if there have been any significant changes in the nice guidelines in the recent past six months.",
            "ask_ai",
            "if there have been any significant changes in the nice guidelines in the recent past six months",
        ),
        (
            "search rgpt if any guidelines have changed significantly in the last 6 months.",
            "ask_chatgpt",
            "if any guidelines have changed significantly in the last 6 months",
        ),
        (
            "rgpd if there are any significant nice guidelines that have changed in last 6 months.",
            "ask_chatgpt",
            "if there are any significant nice guidelines that have changed in last 6 months",
        ),
        ("search everything for kanata bat", None, ""),
        ("search rgpd file", None, ""),
        ("search rgpt file", None, ""),
    ],
)
def test_classify_direct_ask_ai_transcript(raw, expected_route, expected_question):
    route, question = ask_ai_bridge.classify_direct_ask_ai_transcript(raw)

    assert route == expected_route
    assert question == expected_question


def test_ask_ai_uses_provider_router_and_pastes(monkeypatch):
    settings = {
        "ask_ai_enabled": True,
        "ask_ai_model": "auto",
        "ask_chatgpt_claim_timeout_sec": 12,
        "prompt_jobs_dir": "unused",
    }
    pasted = []

    def complete_ask_ai(question, *, configured_model, timeout_seconds, max_tokens):
        assert question == "Question?"
        assert configured_model == "auto"
        assert timeout_seconds <= 20
        assert max_tokens <= 1024
        return types.SimpleNamespace(answer="Answer.", provider="cerebras", model="test-model")

    monkeypatch.setattr(ask_ai_bridge, "_load_ask_ai_settings", lambda: settings)
    monkeypatch.setattr(ask_ai_bridge, "complete_ask_ai", complete_ask_ai)
    monkeypatch.setattr(ask_ai_bridge.clipboard_utils, "paste_transcript", lambda text: pasted.append(text))

    assert ask_ai_bridge.ask_ai("Question?") is True
    assert pasted == ["Answer."]
