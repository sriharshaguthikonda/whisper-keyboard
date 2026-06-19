from wkey.control_center_state import (
    apply_settings_values,
    build_settings_snapshot,
    provider_status,
)
from wkey.settings_manager import DEFAULT_HOTKEY_PROFILES


def test_provider_status_reports_presence_without_exposing_secret():
    status = provider_status({"GROQ_API_KEY": "secret-value"})

    assert status["groq"] == "configured"
    assert "secret-value" not in repr(status)


def test_settings_snapshot_includes_hotkeys_and_advanced_values():
    snapshot = build_settings_snapshot(
        {
            "record_keys": "f24,ctrl_l",
            "enable_wakeword_detection": True,
            "context_max_age_seconds": 75,
            "max_recording_seconds": 20,
            "google_wake_volume_hold_seconds": 1.5,
        },
        env={"GROQ_API_KEY": ""},
    )

    assert snapshot["runtime_mode"] == "combined"
    assert snapshot["record_keys"] == "f24,ctrl_r"
    assert snapshot["hotkey_profiles"]["dictation"]["trigger"] == "ctrl_r"
    assert snapshot["advanced"]["context_max_age_seconds"] == 75
    assert snapshot["advanced"]["max_recording_seconds"] == 20
    assert snapshot["advanced"]["google_wake_volume_hold_seconds"] == 1.5
    assert snapshot["providers"]["groq"] == "missing"


def test_apply_settings_values_clamps_advanced_fields_and_profiles():
    updated = apply_settings_values(
        {"hotkey_profiles": DEFAULT_HOTKEY_PROFILES},
        {
            "max_retries": "0",
            "context_max_age_seconds": "3601",
            "max_recording_seconds": "0",
            "google_wake_volume_hold_seconds": "-0.5",
            "hotkey_profiles": {
                "dictation": {"enabled": False, "trigger": "ctrl_r"},
                "command": {"enabled": True, "trigger": "f24"},
            },
        },
    )

    assert updated["max_retries"] == 1
    assert updated["context_max_age_seconds"] == 3600
    assert updated["max_recording_seconds"] == 1
    assert updated["google_wake_volume_hold_seconds"] == 0.0
    assert updated["hotkey_profiles"]["dictation"]["enabled"] is False
    assert updated["record_keys"] == "f24"


def test_apply_settings_values_persists_theme_and_tray_preferences():
    updated = apply_settings_values(
        {},
        {
            "ui_theme": "dark",
            "minimize_to_tray": False,
        },
    )

    assert updated["ui_theme"] == "dark"
    assert updated["minimize_to_tray"] is False

    fallback = apply_settings_values(
        {},
        {
            "ui_theme": "bad-theme",
            "minimize_to_tray": "yes",
        },
    )

    assert fallback["ui_theme"] == "system"
    assert fallback["minimize_to_tray"] is True


def test_apply_settings_values_persists_speaker_filter_controls():
    updated = apply_settings_values(
        {},
        {
            "speaker_filter_enabled": True,
            "speaker_filter_mode": "balanced",
            "speaker_filter_threshold": "0.83",
            "speaker_filter_profile_path": " I:/profiles/harsha.json ",
            "speaker_filter_enrollment_dir": " I:/Record_only_by_harsha ",
            "speaker_filter_negative_dir": " I:/Record_others_16k_wav ",
            "speaker_filter_apply_to": "all",
        },
    )

    assert updated["speaker_filter_enabled"] is True
    assert updated["speaker_filter_mode"] == "balanced"
    assert updated["speaker_filter_threshold"] == 0.83
    assert updated["speaker_filter_profile_path"] == "I:/profiles/harsha.json"
    assert updated["speaker_filter_enrollment_dir"] == "I:/Record_only_by_harsha"
    assert updated["speaker_filter_negative_dir"] == "I:/Record_others_16k_wav"
    assert updated["speaker_filter_apply_to"] == "dictation"


def test_settings_snapshot_includes_speaker_filter_state():
    snapshot = build_settings_snapshot(
        {
            "speaker_filter_enabled": True,
            "speaker_filter_mode": "custom",
            "speaker_filter_threshold": 0.91,
            "speaker_filter_profile_path": "I:/profiles/harsha.json",
            "speaker_filter_enrollment_dir": "I:/Record_only_by_harsha",
            "speaker_filter_negative_dir": "I:/Record_others_16k_wav",
        },
        env={},
    )

    assert snapshot["speaker_filter"] == {
        "enabled": True,
        "mode": "custom",
        "threshold": 0.91,
        "profile_path": "I:/profiles/harsha.json",
        "enrollment_dir": "I:/Record_only_by_harsha",
        "negative_dir": "I:/Record_others_16k_wav",
        "apply_to": "dictation",
    }
