import importlib
import types

import numpy as np
import pytest


@pytest.fixture
def fw_module():
    module = importlib.import_module("wkey.faster_whisper_Mother_of_all_wkey")
    module = importlib.reload(module)
    yield module
    module.RESUME_RECOVERY_ENABLED = False


def test_resume_event_resets_keyboard_and_requests_audio_recovery(fw_module, monkeypatch):
    calls = []
    fw_module.RESUME_RECOVERY_ENABLED = True
    monkeypatch.setattr(
        fw_module,
        "reset_keyboard_handler_state",
        lambda reason, preserve_rearm=False: calls.append(("keyboard", reason)),
    )
    monkeypatch.setattr(
        fw_module,
        "request_audio_recovery",
        lambda reason: calls.append(("audio", reason)),
    )

    fw_module.handle_resume_event("watchdog gap 30.0s")

    assert calls == [
        ("keyboard", "watchdog gap 30.0s"),
        ("audio", "watchdog gap 30.0s"),
    ]


def test_resume_event_is_noop_when_recovery_disabled(fw_module, monkeypatch):
    fw_module.RESUME_RECOVERY_ENABLED = False
    monkeypatch.setattr(
        fw_module,
        "reset_keyboard_handler_state",
        lambda *args, **kwargs: pytest.fail("keyboard state must remain unchanged"),
    )
    monkeypatch.setattr(
        fw_module,
        "request_audio_recovery",
        lambda *args, **kwargs: pytest.fail("audio recovery must remain disabled"),
    )

    fw_module.handle_resume_event("disabled")


def test_audio_recovery_closes_old_stream_and_reopens_once(fw_module, monkeypatch):
    events = []
    fw_module.RESUME_RECOVERY_ENABLED = True
    fw_module.stream = object()
    monkeypatch.setattr(
        fw_module,
        "_close_input_stream_for_recovery",
        lambda: events.append("close"),
    )
    monkeypatch.setattr(
        fw_module,
        "initialize_input_stream",
        lambda: events.append("open") or True,
    )

    assert fw_module._perform_audio_recovery("resume") is True
    assert events == ["close", "open"]


def test_audio_recovery_requests_coalesce(fw_module):
    fw_module.RESUME_RECOVERY_ENABLED = True
    fw_module.audio_recovery_requested.clear()
    with fw_module.audio_recovery_state_lock:
        fw_module.audio_recovery_state["pending_reason"] = ""

    fw_module.request_audio_recovery("resume")
    fw_module.request_audio_recovery("resume")
    fw_module.request_audio_recovery("overflow")

    assert fw_module.audio_recovery_requested.is_set()
    with fw_module.audio_recovery_state_lock:
        assert fw_module.audio_recovery_state["pending_reason"] == "resume | overflow"


def test_stale_generation_callback_is_dropped(fw_module, monkeypatch):
    fw_module.RESUME_RECOVERY_ENABLED = True
    fw_module.audio_stream_generation = 4
    monkeypatch.setattr(
        fw_module,
        "audio_callback_impl",
        lambda **kwargs: pytest.fail("stale callback reached audio buffers"),
    )

    fw_module.audio_callback(
        np.ones((4, 1), dtype=np.float32),
        4,
        None,
        None,
        callback_generation=3,
    )


def test_watchdog_requests_recovery_for_stale_expected_audio(fw_module, monkeypatch):
    calls = []
    fw_module.RESUME_RECOVERY_ENABLED = True
    fw_module.LAST_AUDIO_CALLBACK_TS = 10.0
    fw_module.recording = True
    monkeypatch.setattr(fw_module.resume_gap_detector, "check", lambda: (False, 5.0))
    monkeypatch.setattr(fw_module, "request_audio_recovery", calls.append)

    fw_module.check_resume_audio_health(now=25.0)

    assert calls == ["audio_callback_stale age=15.0s"]


def test_watchdog_routes_detected_resume_gap(fw_module, monkeypatch):
    calls = []
    fw_module.RESUME_RECOVERY_ENABLED = True
    fw_module.recording = False
    monkeypatch.setattr(fw_module.resume_gap_detector, "check", lambda: (True, 30.0))
    monkeypatch.setattr(fw_module, "handle_resume_event", calls.append)

    fw_module.check_resume_audio_health(now=25.0)

    assert calls == ["monotonic_gap 30.0s"]


def test_overflow_burst_uses_in_app_recovery_when_enabled(fw_module, monkeypatch):
    recoveries = []
    shutdowns = []
    fw_module.RESUME_RECOVERY_ENABLED = True
    monkeypatch.setattr(fw_module.overflow_burst_tracker, "note_overflow", lambda: (True, 6))
    monkeypatch.setattr(fw_module, "request_audio_recovery", recoveries.append)
    monkeypatch.setattr(fw_module, "request_broker_control_shutdown", shutdowns.append)
    monkeypatch.setattr(fw_module, "write_backend_health_status", lambda **kwargs: None)
    monkeypatch.setattr(fw_module, "audio_callback_impl", lambda **kwargs: (0, []))

    fw_module.audio_callback(np.zeros((4, 1)), 4, None, types.SimpleNamespace(input_overflow=True))

    assert recoveries == ["input_overflow_burst"]
    assert shutdowns == []
