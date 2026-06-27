import importlib
import io
import json
import types
import numpy as np
import pytest
import asyncio

@pytest.fixture
def fw_module():
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)
    yield mod
    if hasattr(mod, 'reset_state'):
        mod.reset_state()

def test_validate_audio_buffer(fw_module):
    sr = fw_module.sample_rate
    assert fw_module.validate_audio_buffer(None) is False
    assert fw_module.validate_audio_buffer(np.array([], dtype=np.float32)) is False
    assert fw_module.validate_audio_buffer([1,2,3]) is False
    short = np.zeros(int(sr * 0.05), dtype=np.float32)
    assert fw_module.validate_audio_buffer(short) is False
    good = np.zeros(int(sr * 0.2), dtype=np.float32)
    assert fw_module.validate_audio_buffer(good) is True


def test_default_manual_record_keys_use_right_ctrl(monkeypatch):
    monkeypatch.delenv("WKEY", raising=False)
    monkeypatch.delenv("WKEY_RECORD_KEYS", raising=False)
    monkeypatch.delenv("WKEY_ALLOW_ENV_OVERRIDES", raising=False)
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)

    assert mod.key_label == "ctrl_r"
    expected_labels = [
        label.strip()
        for label in mod.record_key_source.split(",")
        if label.strip()
    ]
    assert mod.RECORD_KEYS == {
        label: mod.SUPPORTED_RECORD_KEYS[label]
        for label in expected_labels
    }
    if "f24" in mod.RECORD_KEYS:
        assert mod.map_key_to_keyword_index(mod.Key.f24) == 0
    for label, key in mod.RECORD_KEYS.items():
        if label != "f24":
            assert mod.map_key_to_keyword_index(key) is None


def test_right_ctrl_config_is_supported(monkeypatch):
    monkeypatch.setenv("WKEY_ALLOW_ENV_OVERRIDES", "1")
    monkeypatch.setenv("WKEY_RECORD_KEYS", "f24,ctrl_r")
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)

    assert mod.RECORD_KEYS == {
        "f24": mod.Key.f24,
        "ctrl_r": mod.Key.ctrl_r,
    }
    assert mod.map_key_to_keyword_index(mod.Key.ctrl_r) is None


def test_stale_env_record_keys_ignored_without_override(monkeypatch):
    monkeypatch.delenv("WKEY_ALLOW_ENV_OVERRIDES", raising=False)
    monkeypatch.setenv("WKEY_RECORD_KEYS", "f24,ctrl_r")
    monkeypatch.setenv("WKEY_RUNTIME_MODE", "wakeword")
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)

    assert "ctrl_r" not in mod.RECORD_KEYS
    assert mod.RECORD_KEYS == {
        label.strip(): mod.SUPPORTED_RECORD_KEYS[label.strip()]
        for label in mod.record_key_source.split(",")
        if label.strip()
    }
    assert mod.runtime_mode == mod.runtime_mode_for_settings(mod.SETTINGS)


def test_broker_input_owner_disables_python_keyboard_listener(monkeypatch):
    monkeypatch.setenv("WKEY_INPUT_OWNER", "broker")
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)

    assert mod.is_keyboard_runtime_enabled() is True
    assert mod.is_python_keyboard_listener_enabled() is False


def test_python_input_owner_keeps_keyboard_listener(monkeypatch):
    monkeypatch.delenv("WKEY_INPUT_OWNER", raising=False)
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)

    assert mod.is_python_keyboard_listener_enabled() is True


def test_start_listener_uses_plain_key_callbacks(fw_module, monkeypatch):
    captured = {}

    class FakeListener:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def join(self):
            return None

    monkeypatch.setattr(fw_module, "Listener", FakeListener)
    monkeypatch.setattr(
        fw_module,
        "RECORD_KEYS",
        {"f24": fw_module.Key.f24, "ctrl_r": fw_module.Key.ctrl_r},
    )

    fw_module.start_listener()

    assert "event_filter" not in captured["kwargs"]


def test_broker_input_owner_skips_python_listener_in_main(fw_module, monkeypatch):
    calls = []
    started = []
    fw_module.runtime_mode = "keyboard"

    monkeypatch.setenv("WKEY_INPUT_OWNER", "broker")
    monkeypatch.delenv("WKEY_BROKER_CONTROL", raising=False)
    monkeypatch.setattr(fw_module, "register_volume_timeout_recovery_hook", lambda: None)
    monkeypatch.setattr(fw_module, "init_keyboard_handler", lambda: None)
    monkeypatch.setattr(fw_module, "start_settings_watch", lambda: None)
    monkeypatch.setattr(fw_module, "init_wakeword_listener", lambda: calls.append("init_wake"))
    monkeypatch.setattr(fw_module, "initialize_wake_stream", lambda: calls.append("wake_stream"))
    monkeypatch.setattr(fw_module, "start_watchdog", lambda: None)
    monkeypatch.setattr(fw_module, "run_asyncio_in_thread", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "clean_transcript", lambda: None)
    monkeypatch.setattr(fw_module, "process_audio_async", lambda: None)
    monkeypatch.setattr(fw_module.voice_commands_module, "is_selenium_enabled", lambda: False, raising=False)
    monkeypatch.setattr(fw_module.threading, "Thread", lambda *a, **k: types.SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(fw_module, "wait_for_microphone", lambda: None)
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: True)
    monkeypatch.setattr(fw_module, "start_listener", lambda: calls.append("listener"))
    monkeypatch.setattr(fw_module, "start_thread", lambda target, name: started.append(name))
    monkeypatch.setattr(fw_module, "cleanup", lambda: None)
    monkeypatch.setattr(
        fw_module.time,
        "sleep",
        lambda seconds: (_ for _ in ()).throw(SystemExit()),
    )

    with pytest.raises(SystemExit):
        fw_module.main()

    assert "listener" not in calls
    assert "CleanTranscript" in started
    assert "ProcessAudio" in started


def test_broker_stdio_mode_skips_console_status_thread(fw_module, monkeypatch):
    calls = []
    started = []
    fw_module.runtime_mode = "keyboard"

    monkeypatch.setenv("WKEY_INPUT_OWNER", "broker")
    monkeypatch.setenv("WKEY_BROKER_CONTROL", "stdio")
    monkeypatch.setattr(fw_module, "register_volume_timeout_recovery_hook", lambda: None)
    monkeypatch.setattr(fw_module, "init_keyboard_handler", lambda: None)
    monkeypatch.setattr(fw_module, "start_settings_watch", lambda: None)
    monkeypatch.setattr(fw_module, "init_wakeword_listener", lambda: None)
    monkeypatch.setattr(fw_module, "initialize_wake_stream", lambda: None)
    monkeypatch.setattr(fw_module, "start_watchdog", lambda: None)
    monkeypatch.setattr(fw_module, "run_asyncio_in_thread", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "clean_transcript", lambda: None)
    monkeypatch.setattr(fw_module, "process_audio_async", lambda: None)
    monkeypatch.setattr(fw_module, "start_broker_control_stdio_thread", lambda: started.append("broker"))
    monkeypatch.setattr(fw_module.voice_commands_module, "is_selenium_enabled", lambda: False, raising=False)
    monkeypatch.setattr(
        fw_module.threading,
        "Thread",
        lambda *a, **k: calls.append(k.get("target")) or types.SimpleNamespace(start=lambda: None),
    )
    monkeypatch.setattr(fw_module, "wait_for_microphone", lambda: None)
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: True)
    monkeypatch.setattr(fw_module, "start_listener", lambda: None)
    monkeypatch.setattr(fw_module, "start_thread", lambda target, name: started.append(name))
    monkeypatch.setattr(fw_module, "cleanup", lambda: None)
    monkeypatch.setattr(
        fw_module.time,
        "sleep",
        lambda seconds: (_ for _ in ()).throw(SystemExit()),
    )

    with pytest.raises(SystemExit):
        fw_module.main()

    assert "broker" in started
    assert "CleanTranscript" in started
    assert "ProcessAudio" in started
    assert fw_module.display_pause_status not in calls


def test_wakeword_setting_off_keeps_manual_keys(fw_module, monkeypatch):
    closed = []
    fw_module.runtime_mode = "combined"
    monkeypatch.setattr(
        fw_module,
        "_close_wake_stream_for_recovery",
        lambda: closed.append("closed"),
    )

    settings = dict(fw_module.SETTINGS)
    settings["enable_wakeword_detection"] = False
    settings["record_keys"] = "f24,ctrl_r"
    settings["hotkey_profiles"] = None
    fw_module.apply_settings(settings)

    assert fw_module.runtime_mode == "keyboard"
    assert fw_module.is_keyboard_runtime_enabled() is True
    assert fw_module.is_wakeword_runtime_enabled() is False
    assert fw_module.RECORD_KEYS["f24"] == fw_module.Key.f24
    assert fw_module.RECORD_KEYS["ctrl_r"] == fw_module.Key.ctrl_r
    assert closed == ["closed"]


def test_apply_settings_updates_manual_record_keys(fw_module):
    settings = dict(fw_module.SETTINGS)
    settings["record_keys"] = "f24,ctrl_r"
    settings["hotkey_profiles"] = None
    fw_module.apply_settings(settings)

    assert fw_module.RECORD_KEYS == {
        "f24": fw_module.Key.f24,
        "ctrl_r": fw_module.Key.ctrl_r,
    }


def test_apply_settings_uses_hotkey_profile_trigger_for_f23(fw_module):
    settings = dict(fw_module.SETTINGS)
    profiles = dict(settings["hotkey_profiles"])
    profiles["dictation"] = dict(profiles["dictation"])
    profiles["command"] = dict(profiles["command"])
    profiles["dictation"]["enabled"] = True
    profiles["dictation"]["trigger"] = "f23"
    profiles["command"]["enabled"] = True
    profiles["command"]["trigger"] = "f24"
    settings["record_keys"] = "f24"
    settings["hotkey_profiles"] = profiles

    fw_module.apply_settings(settings)

    assert fw_module.RECORD_KEYS == {
        "f24": fw_module.Key.f24,
        "f23": fw_module.Key.f23,
    }
    assert fw_module.map_key_to_keyword_index(fw_module.Key.f24) == 0
    assert fw_module.map_key_to_keyword_index(fw_module.Key.f23) is None


def test_pending_manual_cancel_blocks_late_start(fw_module, monkeypatch):
    initialized = []
    releases = []
    fw_module.recording = False
    fw_module.recording_stop_in_progress = False
    fw_module.active_recording_session_id = 0

    monkeypatch.setattr(
        fw_module,
        "initialize_input_stream",
        lambda: initialized.append(True) or True,
    )
    monkeypatch.setattr(
        fw_module,
        "force_release_volume_ducking",
        lambda reason, level=fw_module.logging.WARNING: releases.append(reason),
    )
    monkeypatch.setattr(fw_module, "decrease_volume_all", lambda: None)
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "check_pause_status", lambda: False)

    fw_module.cancel_recording(None, "chord:c")
    fw_module.start_recording(None)

    assert initialized == []
    assert fw_module.recording is False
    assert fw_module.active_recording_session_id == 0
    assert "cancel_recording:chord:c" in releases


def test_activation_metrics_track_press_start_first_audio_and_queue(fw_module):
    events = []
    times = iter([10.0, 10.005, 10.012, 10.050])

    fw_module.reset_activation_metrics()
    fw_module.record_activation_event("hotkey_press", clock=lambda: next(times))
    fw_module.record_activation_event("recording_true", clock=lambda: next(times))
    fw_module.record_activation_event("first_audio_frame", clock=lambda: next(times))
    fw_module.record_activation_event("queued_audio", clock=lambda: next(times))
    status = fw_module.get_activation_status()

    assert [event["event"] for event in status["events"]] == [
        "hotkey_press",
        "recording_true",
        "first_audio_frame",
        "queued_audio",
    ]
    assert status["latest_event"] == "queued_audio"
    assert status["press_to_first_audio_ms"] == 12.0
    assert status["press_to_queued_audio_ms"] == 50.0


def test_backend_health_status_written_as_json(fw_module, tmp_path, monkeypatch):
    status_path = tmp_path / "backend_health.json"
    monkeypatch.setattr(fw_module, "BACKEND_HEALTH_STATUS_PATH", str(status_path))
    fw_module.runtime_mode = "combined"
    monkeypatch.setattr(fw_module, "RECORD_KEYS", {"f24": fw_module.Key.f24, "f23": fw_module.Key.f23})

    fw_module.reset_activation_metrics()
    fw_module.record_activation_event("hotkey_press", clock=lambda: 100.0)
    fw_module.write_backend_health_status(source="test", clock=lambda: 123.25)

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["pid"] == fw_module.os.getpid()
    assert payload["runtime_mode"] == "combined"
    assert payload["record_keys"] == ["f24", "f23"]
    assert payload["wakeword_enabled"] is True
    assert payload["source"] == "test"
    assert payload["activation"]["latest_event"] == "hotkey_press"


def test_input_overflow_logs_without_scheduling_recovery(fw_module, monkeypatch):
    recoveries = []
    fw_module.runtime_mode = "keyboard"
    fw_module.recording = False
    fw_module.recording_stop_in_progress = False

    class OverflowStatus:
        input_overflow = True

    class AlwaysBurst:
        def note_overflow(self):
            return True, 1

    monkeypatch.setattr(
        fw_module,
        "request_audio_recovery",
        lambda reason: recoveries.append(reason),
    )
    monkeypatch.setattr(fw_module, "overflow_burst_tracker", AlwaysBurst())

    fw_module.audio_callback(
        np.zeros((8, 1), dtype=np.float32),
        8,
        None,
        OverflowStatus(),
    )

    assert recoveries == []


def test_volume_timeout_callback_releases_volume_without_audio_recovery(fw_module, monkeypatch):
    callbacks = []
    recoveries = []
    releases = []
    monkeypatch.setattr(
        fw_module.voice_commands_module,
        "register_volume_timeout_callback",
        lambda callback: callbacks.append(callback),
        raising=False,
    )
    monkeypatch.setattr(
        fw_module,
        "request_audio_recovery",
        lambda reason: recoveries.append(reason),
    )
    monkeypatch.setattr(
        fw_module,
        "force_release_volume_ducking",
        lambda reason, level=fw_module.logging.WARNING: releases.append(reason),
    )

    fw_module._volume_timeout_hook_registered = False
    fw_module.register_volume_timeout_recovery_hook()
    callbacks[0](2.0)

    assert recoveries == []
    assert releases == ["volume timeout 2.0s"]
    assert fw_module.manual_recording_suppressed_until > fw_module.time.time()


def test_system_resume_detection_is_noop_under_external_restart_policy(fw_module, monkeypatch):
    calls = []

    monkeypatch.setattr(fw_module, "set_pause_state", lambda value: calls.append(("pause", value)))
    monkeypatch.setattr(
        fw_module,
        "request_keyboard_listener_restart",
        lambda reason: calls.append(("restart", reason)),
    )
    monkeypatch.setattr(
        fw_module,
        "handle_resume_event",
        lambda reason: calls.append(("resume", reason)),
    )
    monkeypatch.setattr(
        fw_module,
        "request_audio_recovery",
        lambda reason: calls.append(("recovery", reason)),
    )

    fw_module.maybe_handle_system_resume("microphone monitor")

    assert calls == []


def test_keyboard_mode_starts_no_recovery_or_wake_monitor_threads(fw_module, monkeypatch):
    started = []
    fw_module.runtime_mode = "keyboard"

    monkeypatch.setattr(fw_module, "register_volume_timeout_recovery_hook", lambda: None)
    monkeypatch.setattr(fw_module, "init_keyboard_handler", lambda: None)
    monkeypatch.setattr(fw_module, "start_settings_watch", lambda: None)
    monkeypatch.setattr(fw_module, "init_wakeword_listener", lambda: started.append("init_wake"))
    monkeypatch.setattr(fw_module, "initialize_wake_stream", lambda: started.append("wake_stream"))
    monkeypatch.setattr(fw_module, "start_watchdog", lambda: None)
    monkeypatch.setattr(fw_module, "run_asyncio_in_thread", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "clean_transcript", lambda: None)
    monkeypatch.setattr(fw_module, "process_audio_async", lambda: None)
    monkeypatch.setattr(fw_module.voice_commands_module, "is_selenium_enabled", lambda: False, raising=False)
    monkeypatch.setattr(fw_module.threading, "Thread", lambda *a, **k: types.SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(
        fw_module,
        "wait_for_microphone",
        lambda: (_ for _ in ()).throw(SystemExit()),
    )
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: True)
    monkeypatch.setattr(fw_module, "start_listener", lambda: None)
    monkeypatch.setattr(
        fw_module,
        "start_thread",
        lambda target, name: started.append(name),
    )
    monkeypatch.setattr(fw_module, "cleanup", lambda: None)

    with pytest.raises(SystemExit):
        fw_module.main()

    assert "AudioRecovery" not in started
    assert "WakeWordListener" not in started
    assert "MicrophoneMonitor" not in started
    assert "init_wake" not in started
    assert "wake_stream" not in started
    assert "CleanTranscript" in started
    assert "ProcessAudio" in started


def test_combined_mode_uses_shared_wake_audio_without_py_audio_stream(fw_module, monkeypatch):
    started = []
    fw_module.runtime_mode = "combined"
    monkeypatch.setenv("WKEY_INPUT_OWNER", "python")

    monkeypatch.setattr(fw_module, "register_volume_timeout_recovery_hook", lambda: None)
    monkeypatch.setattr(fw_module, "init_keyboard_handler", lambda: None)
    monkeypatch.setattr(fw_module, "start_settings_watch", lambda: None)
    monkeypatch.setattr(fw_module, "init_wakeword_listener", lambda: started.append("init_wake"))
    monkeypatch.setattr(fw_module, "initialize_wake_stream", lambda: started.append("wake_stream"))
    monkeypatch.setattr(fw_module, "start_watchdog", lambda: None)
    monkeypatch.setattr(fw_module, "run_asyncio_in_thread", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "clean_transcript", lambda: None)
    monkeypatch.setattr(fw_module, "process_audio_async", lambda: None)
    monkeypatch.setattr(fw_module.voice_commands_module, "is_selenium_enabled", lambda: False, raising=False)
    monkeypatch.setattr(fw_module.threading, "Thread", lambda *a, **k: types.SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(
        fw_module,
        "wait_for_microphone",
        lambda: (_ for _ in ()).throw(SystemExit()),
    )
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: True)
    monkeypatch.setattr(fw_module, "start_listener", lambda: None)
    monkeypatch.setattr(
        fw_module,
        "start_thread",
        lambda target, name: started.append(name),
    )
    monkeypatch.setattr(fw_module, "cleanup", lambda: None)

    with pytest.raises(SystemExit):
        fw_module.main()

    assert "init_wake" in started
    assert "WakeWordListener" in started
    assert "wake_stream" not in started


def test_prerecord_keyword_check_gate_requires_wakeword_runtime_precheck_and_buffer(fw_module):
    settings = dict(fw_module.SETTINGS)
    settings["enable_pre_recording_keyword_check"] = True
    fw_module.SETTINGS = settings
    data = np.ones((8, 1), dtype=np.float32)

    fw_module.runtime_mode = "keyboard"
    assert fw_module.should_run_pre_recording_keyword_check(1, data) is False

    fw_module.runtime_mode = "combined"
    settings["enable_pre_recording_keyword_check"] = False
    assert fw_module.should_run_pre_recording_keyword_check(1, data) is False

    settings["enable_pre_recording_keyword_check"] = True
    assert fw_module.should_run_pre_recording_keyword_check(None, data) is False
    assert fw_module.should_run_pre_recording_keyword_check(0, data) is False
    assert fw_module.should_run_pre_recording_keyword_check(1, np.array([])) is False
    assert fw_module.should_run_pre_recording_keyword_check(1, data) is True


def test_start_recording_skips_prerecord_stt_when_precheck_disabled(fw_module, monkeypatch):
    started_targets = []
    settings = dict(fw_module.SETTINGS)
    settings["enable_pre_recording_keyword_check"] = False
    fw_module.SETTINGS = settings
    fw_module.runtime_mode = "combined"
    fw_module.something_is_playing = False
    fw_module.pre_recording_buffer = np.ones((8, 1), dtype=np.float32)
    fw_module.buffer_index = 0

    class CapturingThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
            self.target = target
            started_targets.append(target)

        def start(self):
            return None

    monkeypatch.setattr(fw_module.threading, "Thread", CapturingThread)
    monkeypatch.setattr(fw_module, "_schedule_recording_timeout", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "_run_start_feedback_async", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "decrease_volume_all", lambda: None)
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: True)
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "check_pause_status", lambda: False)

    fw_module.start_recording(1)

    assert fw_module.check_keywords_in_transcription not in started_targets
    assert fw_module.keyword_validation_event.is_set()


def test_start_recording_initializes_stream_before_feedback_thread(fw_module, monkeypatch):
    order = []
    fw_module.runtime_mode = "keyboard"
    fw_module.something_is_playing = False
    fw_module.recording = False
    fw_module.recording_stop_in_progress = False
    fw_module.active_recording_session_id = 0

    class CapturingThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
            self.target = target
            self.name = name

        def start(self):
            order.append(("thread_started", self.name))

    monkeypatch.setattr(fw_module.threading, "Thread", CapturingThread)
    monkeypatch.setattr(fw_module, "_schedule_recording_timeout", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "check_pause_status", lambda: False)
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: order.append("stream") or True)
    monkeypatch.setattr(fw_module, "decrease_volume_all", lambda: order.append("duck"))
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: order.append("beep"))

    fw_module.start_recording(None)

    assert order[0] == "stream"
    assert ("thread_started", "StartRecordingFeedback") in order
    assert "duck" not in order
    assert "beep" not in order


def test_start_recording_runs_prerecord_validation_once_when_enabled(fw_module, monkeypatch):
    started_targets = []
    settings = dict(fw_module.SETTINGS)
    settings["enable_pre_recording_keyword_check"] = True
    fw_module.SETTINGS = settings
    fw_module.runtime_mode = "combined"
    fw_module.something_is_playing = False
    fw_module.pre_recording_buffer = np.ones((8, 1), dtype=np.float32)
    fw_module.buffer_index = 0

    class CapturingThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
            self.target = target
            self.args = args

        def start(self):
            started_targets.append(self.target)

    monkeypatch.setattr(fw_module.threading, "Thread", CapturingThread)
    monkeypatch.setattr(fw_module, "_schedule_recording_timeout", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "_run_start_feedback_async", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "decrease_volume_all", lambda: None)
    monkeypatch.setattr(fw_module, "initialize_input_stream", lambda: True)
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "check_pause_status", lambda: False)

    fw_module.start_recording(1)

    assert started_targets == [fw_module.check_keywords_in_transcription]


def test_runtime_singleton_blocks_when_lock_unavailable(fw_module, monkeypatch, tmp_path):
    lock_path = tmp_path / "wkey_runtime.lock"
    lock_path.write_text("12345", encoding="utf-8")
    fw_module._runtime_lock_handle = None
    monkeypatch.setattr(
        fw_module,
        "_try_lock_runtime_file",
        lambda handle: (_ for _ in ()).throw(OSError("locked")),
    )

    assert fw_module.acquire_runtime_singleton(str(lock_path)) is False
    assert fw_module._runtime_lock_handle is None


def test_runtime_singleton_acquire_and_release(fw_module, tmp_path):
    lock_path = tmp_path / "wkey_runtime.lock"
    fw_module._runtime_lock_handle = None

    assert fw_module.acquire_runtime_singleton(str(lock_path)) is True
    fw_module.release_runtime_singleton()

    assert lock_path.read_text(encoding="utf-8") == str(fw_module.os.getpid())
    assert fw_module._runtime_lock_handle is None


def test_duplicate_manual_stop_is_idempotent(fw_module, monkeypatch):
    saved = []
    restored = []
    monkeypatch.setattr(fw_module, "save_manual_recording_if_configured", lambda *a, **k: saved.append(a))
    monkeypatch.setattr(fw_module, "_restore_volume_all_async", lambda *a, **k: restored.append(k))
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: None)

    fw_module.recording = True
    fw_module.recording_stop_in_progress = False
    fw_module.active_recording_session_id = 77
    fw_module.play_pause_pressed = False
    fw_module.buffer_index = 0
    fw_module.pre_recording_buffer_f24 = np.zeros((fw_module.sample_rate, 1), dtype=np.float32)
    fw_module.audio_buffer = np.ones(5, dtype=np.float32)

    while not fw_module.audio_buffer_queue.empty():
        fw_module.audio_buffer_queue.get()

    fw_module.stop_recording(None)
    fw_module.stop_recording(None)

    queued = []
    while not fw_module.audio_buffer_queue.empty():
        queued.append(fw_module.audio_buffer_queue.get())

    assert len(saved) == 1
    assert len(queued) == 1
    assert fw_module.recording is False
    assert fw_module.recording_stop_in_progress is False


def test_manual_stop_queues_single_combined_prerecord_and_recording_item(fw_module, monkeypatch):
    monkeypatch.setattr(fw_module, "save_manual_recording_if_configured", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "_restore_volume_all_async", lambda *a, **k: None)
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: None)

    fw_module.recording = True
    fw_module.recording_stop_in_progress = False
    fw_module.active_recording_session_id = 88
    fw_module.play_pause_pressed = False
    fw_module.buffer_index = 0
    fw_module.pre_recording_buffer_f24 = np.array(
        [1.0, 2.0, 3.0], dtype=np.float32
    ).reshape(-1, 1)
    fw_module.audio_buffer = np.array([4.0, 5.0], dtype=np.float32)

    while not fw_module.audio_buffer_queue.empty():
        fw_module.audio_buffer_queue.get()

    fw_module.stop_recording(None)

    queued_audio, idx = fw_module.audio_buffer_queue.get_nowait()
    assert idx is None
    assert np.allclose(queued_audio, [1.0, 2.0, 3.0, 4.0, 5.0])
    assert fw_module.audio_buffer_queue.empty()


def test_manual_stop_drops_immediate_tap_before_transcription(fw_module, monkeypatch):
    saved = []
    restored = []
    monkeypatch.setattr(fw_module, "save_manual_recording_if_configured", lambda *a, **k: saved.append(a))
    monkeypatch.setattr(fw_module, "_restore_volume_all_async", lambda *a, **k: restored.append(k))
    monkeypatch.setattr(fw_module, "beep", lambda *a, **k: None)

    fw_module.recording = True
    fw_module.recording_stop_in_progress = False
    fw_module.active_recording_session_id = 89
    fw_module.recording_start_time = fw_module.time.time()
    fw_module.play_pause_pressed = False
    fw_module.buffer_index = 0
    fw_module.pre_recording_buffer_f24 = np.array(
        [1.0, 2.0, 3.0], dtype=np.float32
    ).reshape(-1, 1)
    fw_module.audio_buffer = np.array([], dtype=np.float32)

    while not fw_module.audio_buffer_queue.empty():
        fw_module.audio_buffer_queue.get()

    fw_module.stop_recording(None)

    assert saved == []
    assert fw_module.audio_buffer_queue.empty()
    assert restored


def test_create_wav_buffer(fw_module):
    data = np.zeros(fw_module.sample_rate, dtype=np.float32)
    buf = fw_module.create_wav_buffer(data)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_check_pause_status(tmp_path, fw_module, monkeypatch):
    flag = tmp_path / 'voice_pause_flag.txt'

    def fake_pause_check(flag_path, last_pause_check, global_pause_active, min_interval=0.5):
        paused = flag.exists() and flag.read_text().strip() == 'PAUSED'
        return paused, 1, paused

    monkeypatch.setattr(fw_module, 'pause_check_impl', fake_pause_check)
    flag.write_text('PAUSED')
    fw_module.last_pause_check = 0
    assert fw_module.check_pause_status() is True
    flag.write_text('RUNNING')
    fw_module.last_pause_check = 0
    assert fw_module.check_pause_status() is False
    flag.unlink()
    fw_module.last_pause_check = 0
    assert fw_module.check_pause_status() is False


def test_beep(fw_module, monkeypatch):
    called = {}
    def fake(freq, dur):
        called['freq'] = freq
        called['dur'] = dur
    monkeypatch.setattr(fw_module.winsound, 'Beep', fake)
    fw_module.beep((440, 100))
    assert called == {'freq': 440, 'dur': 100}


def test_volume_functions(fw_module, monkeypatch):
    class DummyLeaseManager:
        def begin_duck(self, reason):
            return 0.5, 1

        def end_duck(self, reason):
            return 0.5, 0, True

        def try_snapshot_state(self):
            return {
                "lease_count": 0,
                "restore_pending": False,
                "restore_target": None,
            }

    monkeypatch.setattr(fw_module, 'volume_lease_manager', DummyLeaseManager())
    fw_module.initial_volume = None
    fw_module.decrease_volume_all()
    assert fw_module.initial_volume == 0.5
    fw_module.restore_volume_all()
    assert fw_module.initial_volume is None


def test_save_audio(tmp_path, fw_module):
    data = np.zeros(fw_module.sample_rate // 2, dtype=np.float32)
    fw_module.save_audio(data, 1, directory=str(tmp_path), sample_rate=fw_module.sample_rate, type_of_audio='test')
    files = list(tmp_path.glob('test_1_recording*.wav'))
    assert len(files) == 1


def test_transcribe_pre_recording_buffer(fw_module, monkeypatch):
    captured = {}

    def fake_pre_recording(*args, **kwargs):
        captured["kwargs"] = kwargs
        return "hello"

    monkeypatch.setattr(fw_module, 'transcribe_pre_recording_buffer_util', fake_pre_recording)
    data = np.zeros(fw_module.sample_rate // 10, dtype=np.float32)
    text = fw_module.transcribe_pre_recording_buffer(data)
    assert text == 'hello'
    assert captured["kwargs"]["report_model_failure"] is fw_module.note_audio_stt_model_failure
    assert captured["kwargs"]["report_rate_limit"] is fw_module.note_audio_stt_rate_limit


def test_transcribe_with_groq_async_wrapper_passes_model_callbacks(fw_module, monkeypatch):
    captured = {}

    async def fake_groq(*args, **kwargs):
        captured["kwargs"] = kwargs
        return "hello"

    monkeypatch.setattr(fw_module, 'transcribe_with_groq_async_util', fake_groq)

    result = asyncio.run(fw_module.transcribe_with_groq_async(io.BytesIO(b"audio"), None))

    assert result == "hello"
    assert captured["kwargs"]["report_model_failure"] is fw_module.note_audio_stt_model_failure
    assert captured["kwargs"]["report_rate_limit"] is fw_module.note_audio_stt_rate_limit


def test_transcribe_with_local_model(fw_module, monkeypatch):
    class Seg:
        def __init__(self, text):
            self.text = text
    fw_module.model = types.SimpleNamespace()
    monkeypatch.setattr(
        fw_module.model,
        'transcribe',
        lambda audio, language='en': ([Seg('hello'), Seg('world')], None),
        raising=False,
    )
    data = np.zeros(fw_module.sample_rate // 10, dtype=np.float32)
    text = fw_module.transcribe_with_local_model(data, 0)
    assert text == 'hello world'


def test_get_transcript_with_retries(fw_module, monkeypatch):
    calls = []
    async def fake_groq(byte_io, keyword_index):
        calls.append('remote')
        if len(calls) < 2:
            raise Exception('fail')
        return 'remote text'
    monkeypatch.setattr(fw_module, 'transcribe_with_groq_async', fake_groq)
    monkeypatch.setattr(fw_module, 'transcribe_with_local_model', lambda b, k: 'local text')
    byte_io = fw_module.create_wav_buffer(np.zeros(fw_module.sample_rate // 10, dtype=np.float32))
    result = asyncio.run(fw_module.get_transcript_with_retries(byte_io, 1, max_retries=3))
    assert result == 'remote text'
    assert calls == ['remote', 'remote']


def test_target_speaker_filter_factory_uses_settings_and_cache(fw_module, monkeypatch):
    calls = []

    class FakeFilter:
        pass

    def fake_create_filter_from_settings(settings, logger=None):
        calls.append((dict(settings), logger))
        return FakeFilter()

    monkeypatch.setattr(
        fw_module, "create_filter_from_settings", fake_create_filter_from_settings
    )
    fw_module.SETTINGS.update(
        {
            "speaker_filter_enabled": True,
            "speaker_filter_mode": "balanced",
            "speaker_filter_threshold": 0.81,
            "speaker_filter_profile_path": "I:/profiles/harsha.json",
            "speaker_filter_apply_to": "dictation",
        }
    )

    first = fw_module.get_target_speaker_filter()
    second = fw_module.get_target_speaker_filter()

    assert first is second
    assert len(calls) == 1
    assert calls[0][0]["speaker_filter_mode"] == "balanced"
    assert calls[0][0]["speaker_filter_threshold"] == 0.81

    fw_module.SETTINGS["speaker_filter_threshold"] = 0.7
    third = fw_module.get_target_speaker_filter()

    assert third is not first
    assert len(calls) == 2

    fw_module.SETTINGS["speaker_filter_enabled"] = False
    assert fw_module.get_target_speaker_filter() is None


def test_transcription_pipeline_receives_target_speaker_filter_getter(fw_module):
    fw_module.transcription_pipeline = None

    pipeline = fw_module.init_transcription_pipeline()

    assert pipeline.speaker_filter_getter is fw_module.get_target_speaker_filter
    assert pipeline.speaker_filter_status_writer is fw_module.write_target_speaker_status


def test_target_speaker_status_writer_outputs_json(fw_module, tmp_path):
    status_path = tmp_path / "speaker_filter_status.json"
    fw_module.SPEAKER_FILTER_STATUS_PATH = str(status_path)

    fw_module.write_target_speaker_status(
        {
            "decision": "filtered",
            "accepted_seconds": 1.0,
            "rejected_seconds": 0.5,
        }
    )

    assert json.loads(status_path.read_text(encoding="utf-8")) == {
        "decision": "filtered",
        "accepted_seconds": 1.0,
        "rejected_seconds": 0.5,
    }


def test_reset_state(fw_module, monkeypatch):
    monkeypatch.setattr(fw_module, 'restore_volume_all', lambda: None)
    fw_module.recording = True
    fw_module.play_pause_pressed = True
    fw_module.audio_buffer = np.ones(5, dtype=np.float32)
    fw_module.reset_state()
    assert fw_module.recording is False
    assert fw_module.play_pause_pressed is False
    assert fw_module.audio_buffer == []


def test_stop_recording_includes_pre_buffer(fw_module, monkeypatch):
    monkeypatch.setattr(fw_module, 'restore_volume_all', lambda: None)
    monkeypatch.setattr(fw_module, 'beep', lambda *a, **k: None)

    fw_module.recording = True
    fw_module.play_pause_pressed = False
    fw_module.stream = types.SimpleNamespace(active=False)
    fw_module.buffer_index = 0

    fw_module.pre_recording_buffer = np.arange(
        fw_module.BUFFER_SIZE, dtype=np.float32
    ).reshape(-1, 1)
    fw_module.audio_buffer = np.array([10.0, 11.0, 12.0], dtype=np.float32)

    while not fw_module.audio_buffer_queue.empty():
        fw_module.audio_buffer_queue.get()

    fw_module.stop_recording(None)

    queued_audio, idx = fw_module.audio_buffer_queue.get_nowait()
    assert idx is None
    assert len(queued_audio) == len(fw_module.pre_recording_buffer_f24) + 3
    assert np.allclose(queued_audio[-3:], [10.0, 11.0, 12.0])


def test_audio_recovery_non_volume_reason_is_noop(fw_module):
    assert fw_module._perform_audio_recovery("test-cooldown") is False
