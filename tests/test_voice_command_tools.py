import json
import asyncio
import sys
import types
from pathlib import Path

import pytest


def _prepare_voice_commands_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", types.ModuleType("edge_tts"))
    monkeypatch.setitem(sys.modules, "pyttsx4", types.ModuleType("pyttsx4"))
    monkeypatch.setitem(
        sys.modules,
        "pydub",
        types.SimpleNamespace(AudioSegment=types.SimpleNamespace()),
    )
    monkeypatch.setitem(
        sys.modules,
        "pydub.playback",
        types.SimpleNamespace(play=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        sys.modules["clipboard_utils"],
        "set_clipboard_content",
        lambda *args, **kwargs: None,
        raising=False,
    )
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "wkey"))
    from wkey import voice_commands

    return voice_commands


def _fake_tool_call_session(captured_messages, function_name, arguments):
    class FakeResponse:
        status = 200
        reason = "OK"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": function_name,
                                        "arguments": json.dumps(arguments),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            captured_messages.append(kwargs["json"]["messages"][-1]["content"])
            return FakeResponse()

    return FakeSession


def test_advertised_voice_tools_have_executor_registry_entries():
    from wkey.commands_and_tools import tools, tool_function_registry

    advertised = {
        item["function"]["name"]
        for item in tools
        if item.get("type") == "function" and "function" in item
    }
    registry = tool_function_registry()

    assert "open_startup_folder" in advertised
    assert "open_startup_folder" in registry
    assert advertised - set(registry) == set()


def test_ask_ai_tool_call_runs_in_worker_thread(monkeypatch):
    voice_commands = _prepare_voice_commands_import(monkeypatch)

    to_thread_calls = []
    executed = []

    class FakeResponse:
        status = 200
        reason = "OK"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "ask_ai",
                                        "arguments": json.dumps({"question": "Question?"}),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    def ask_ai(question):
        executed.append(question)
        return True

    def fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append((func, args, kwargs))

        async def runner():
            return func(*args, **kwargs)

        return runner()

    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(voice_commands, "_filtered_tools_for_llm", lambda: [])
    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: False)
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")
    monkeypatch.setattr(voice_commands, "tool_function_registry", lambda namespace=None: {"ask_ai": ask_ai})
    monkeypatch.setattr(voice_commands.asyncio, "to_thread", fake_to_thread)

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool("ask ai question", max_retries=1)
    )
    assert executed == ["Question?"]
    assert to_thread_calls == [(ask_ai, (), {"question": "Question?"})]


def test_direct_ask_chatgpt_bypasses_llm_classifier(monkeypatch):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    calls = []

    class BombSession:
        def __init__(self, *args, **kwargs):
            raise AssertionError("LLM classifier should not run for direct Ask-AI")

    def ask_chatgpt(question):
        calls.append(question)
        return True

    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", BombSession)
    monkeypatch.setattr(
        voice_commands,
        "tool_function_registry",
        lambda namespace=None: {"ask_chatgpt": ask_chatgpt},
    )

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool(
            "ask chat gpt do I need a new PowerShell to see PATH changes?",
            max_retries=1,
        )
    )
    assert calls == ["do I need a new PowerShell to see PATH changes?"]


@pytest.mark.parametrize("enabled", [False, True])
def test_ask_ai_tools_are_advertised_to_llm_classifier(monkeypatch, enabled):
    voice_commands = _prepare_voice_commands_import(monkeypatch)

    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: enabled)

    advertised = {
        item["function"]["name"]
        for item in voice_commands._filtered_tools_for_llm()
        if item.get("type") == "function"
    }

    assert "ask_chatgpt" in advertised
    assert "ask_ai" in advertised


def test_ask_chatgpt_routes_directly_before_llm_tool_call(monkeypatch):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    calls = []
    captured_messages = []
    raw = "ask chat gpt according to nice guidelines, what is the status of 2 week weight cancer referral pathway? no cancel that, ask this, see if there are any changes in the nice guidelines that are significant in the recent 6 months."
    expected_question = "according to nice guidelines, what is the status of 2 week weight cancer referral pathway? no cancel that, ask this, see if there are any changes in the nice guidelines that are significant in the recent 6 months"

    def ask_chatgpt(question):
        calls.append(("ask_chatgpt", question))
        return True

    monkeypatch.setattr(
        voice_commands,
        "tool_function_registry",
        lambda namespace=None: {"ask_chatgpt": ask_chatgpt},
    )
    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", _fake_tool_call_session(
        captured_messages,
        "ask_chatgpt",
        {"question": expected_question},
    ))
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool(raw, max_retries=1)
    )
    assert captured_messages == []
    assert calls == [("ask_chatgpt", expected_question)]


def test_ask_ai_routes_directly_before_llm_tool_call(monkeypatch):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    calls = []
    captured_messages = []
    raw = "ask ai if there have been any significant changes in the nice guidelines in the recent past six months."
    expected_question = "if there have been any significant changes in the nice guidelines in the recent past six months"

    def ask_ai(question):
        calls.append(("ask_ai", question))
        return True

    monkeypatch.setattr(
        voice_commands,
        "tool_function_registry",
        lambda namespace=None: {"ask_ai": ask_ai},
    )
    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", _fake_tool_call_session(
        captured_messages,
        "ask_ai",
        {"question": expected_question},
    ))
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool(raw, max_retries=1)
    )
    assert captured_messages == []
    assert calls == [("ask_ai", expected_question)]


def test_rgpt_search_phrase_can_route_to_ask_chatgpt_tool(monkeypatch):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    calls = []
    captured_messages = []
    raw = "search rgpt if any guidelines have changed significantly in the last 6 months."
    expected_question = "if any guidelines have changed significantly in the last 6 months"

    def ask_chatgpt(question):
        calls.append(("ask_chatgpt", question))
        return True

    def search_everything(query=""):
        calls.append(("search_everything", query))
        return True

    monkeypatch.setattr(
        voice_commands,
        "tool_function_registry",
        lambda namespace=None: {
            "ask_chatgpt": ask_chatgpt,
            "search_everything": search_everything,
        },
    )
    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", _fake_tool_call_session(
        captured_messages,
        "ask_chatgpt",
        {"question": expected_question},
    ))
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool(raw, max_retries=1)
    )
    assert captured_messages == []
    assert calls == [("ask_chatgpt", expected_question)]


@pytest.mark.parametrize(
    "raw",
    [
        "search at chatgpt, how to add adp devices to the path.",
        "sir, chatgpt, if there are any significant changes in the nice guidelines in the past six months?",
    ],
)
def test_log_chatgpt_phrases_go_to_llm_classifier_before_compound_split(monkeypatch, raw):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    calls = []

    class FakeResponse:
        status = 200
        reason = "OK"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {"choices": [{"message": {"content": ""}}]}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            calls.append(kwargs["json"]["messages"][-1]["content"])
            return FakeResponse()

    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")

    asyncio.run(voice_commands.execute_command_run_with_tool(raw, max_retries=1))
    assert calls[0] == raw


def test_llm_classifier_uses_small_completion_budget(monkeypatch):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    budgets = []

    class FakeResponse:
        status = 200
        reason = "OK"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {"choices": [{"message": {"content": ""}}]}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            budgets.append(kwargs["json"]["max_tokens"])
            return FakeResponse()

    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")

    asyncio.run(voice_commands.execute_command_run_with_tool("open notepad", max_retries=1))

    assert budgets == [256]


@pytest.mark.parametrize(
    "query",
    [
        "search everything for kanata bat",
        "search kanata bat",
    ],
)
def test_local_everything_searches_still_use_tool_router(monkeypatch, query):
    voice_commands = _prepare_voice_commands_import(monkeypatch)
    executed = []
    to_thread_calls = []

    class FakeResponse:
        status = 200
        reason = "OK"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "search_everything",
                                        "arguments": json.dumps({"query": "kanata bat"}),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    def search_everything(query=""):
        executed.append(query)
        return True

    def fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append((func, args, kwargs))

        async def runner():
            return func(*args, **kwargs)

        return runner()

    monkeypatch.setattr(voice_commands, "_is_ask_ai_voice_enabled", lambda: True)
    monkeypatch.setattr(voice_commands.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(voice_commands, "_filtered_tools_for_llm", lambda: [])
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")
    monkeypatch.setattr(
        voice_commands,
        "tool_function_registry",
        lambda namespace=None: {"search_everything": search_everything},
    )
    monkeypatch.setattr(voice_commands.asyncio, "to_thread", fake_to_thread)

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool(
            query, max_retries=1
        )
    )
    assert executed == ["kanata bat"]
    assert to_thread_calls == [(search_everything, (), {"query": "kanata bat"})]
