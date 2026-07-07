import json
import asyncio
import sys
import types
from pathlib import Path


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
    monkeypatch.setattr(voice_commands, "refresh_groq_model_rotators", lambda *a, **k: None)
    monkeypatch.setattr(voice_commands, "next_tool_use_model", lambda: "test-model")
    monkeypatch.setattr(voice_commands, "tool_function_registry", lambda namespace=None: {"ask_ai": ask_ai})
    monkeypatch.setattr(voice_commands.asyncio, "to_thread", fake_to_thread)

    assert asyncio.run(
        voice_commands.execute_command_run_with_tool("ask ai question", max_retries=1)
    )
    assert executed == ["Question?"]
    assert to_thread_calls == [(ask_ai, (), {"question": "Question?"})]
