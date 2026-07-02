from wkey.settings_manager import (
    DEFAULT_RECORD_KEYS,
    DEFAULT_HOTKEY_PROFILES,
    DEFAULT_SETTINGS,
    build_backend_environment,
    load_settings,
    normalize_record_key_label,
    normalize_record_keys,
    normalize_hotkey_profiles,
    record_keys_from_hotkey_profiles,
    runtime_mode_for_settings,
    save_settings,
)


def test_runtime_mode_for_wakeword_setting():
    assert runtime_mode_for_settings({"enable_wakeword_detection": True}) == "combined"
    assert runtime_mode_for_settings({"enable_wakeword_detection": False}) == "keyboard"
    assert runtime_mode_for_settings({}) == "keyboard"


def test_backend_environment_forces_manual_keys_and_runtime_mode():
    base_env = {
        "WKEY_RECORD_KEYS": "f24,ctrl_r",
        "WKEY_RUNTIME_MODE": "wakeword",
        "OTHER": "kept",
    }

    env = build_backend_environment(
        {"enable_wakeword_detection": False},
        base_env=base_env,
    )

    assert env["WKEY_RECORD_KEYS"] == "f24,ctrl_r"
    assert env["WKEY_RUNTIME_MODE"] == "keyboard"
    assert env["OTHER"] == "kept"


def test_backend_environment_uses_configured_manual_keys():
    env = build_backend_environment(
        {
            "enable_wakeword_detection": False,
            "record_keys": "f24,ctrl_r",
        },
        base_env={},
    )

    assert env["WKEY_RECORD_KEYS"] == "f24,ctrl_r"


def test_record_key_normalization_is_safe_for_capture_names():
    assert DEFAULT_RECORD_KEYS == "f24,ctrl_r"
    assert normalize_record_key_label("F23") == "f23"
    assert normalize_record_key_label("left ctrl") == "ctrl_r"
    assert normalize_record_key_label("left control") == "ctrl_r"
    assert normalize_record_key_label("right ctrl") == "ctrl_r"
    assert normalize_record_key_label("right control") == "ctrl_r"
    assert normalize_record_key_label("caps lock") is None
    assert normalize_record_key_label("F24") == "f24"
    assert normalize_record_key_label("space") is None
    assert normalize_record_keys("ctrl_l, F24") == DEFAULT_RECORD_KEYS
    assert normalize_record_keys("caps lock, F24") == "f24"
    assert normalize_record_keys("left ctrl") == "ctrl_r"
    assert normalize_record_keys("right ctrl") == "ctrl_r"
    assert normalize_record_keys("space") == DEFAULT_RECORD_KEYS


def test_speaker_filter_settings_are_normalized(tmp_path):
    config_path = tmp_path / "transcription_config.json"
    config_path.write_text(
        """
{
  "speaker_filter_enabled": "yes",
  "speaker_filter_mode": "strict",
  "speaker_filter_threshold": 2.0,
  "speaker_filter_profile_path": "  I:/profiles/harsha.json  ",
  "speaker_filter_enrollment_dir": "  I:/Record_only_by_harsha  ",
  "speaker_filter_negative_dir": "  I:/Record_others_16k_wav  ",
  "speaker_filter_apply_to": "all"
}
""",
        encoding="utf-8",
    )

    loaded = load_settings(str(config_path))

    assert loaded["speaker_filter_enabled"] is True
    assert loaded["speaker_filter_mode"] == "analysis"
    assert loaded["speaker_filter_threshold"] == 1.0
    assert loaded["speaker_filter_profile_path"] == "I:/profiles/harsha.json"
    assert loaded["speaker_filter_enrollment_dir"] == "I:/Record_only_by_harsha"
    assert loaded["speaker_filter_negative_dir"] == "I:/Record_others_16k_wav"
    assert loaded["speaker_filter_apply_to"] == "dictation"


def test_default_speaker_filter_settings_start_in_analysis_mode():
    loaded = load_settings("missing-transcription-config.json")

    assert loaded["speaker_filter_enabled"] is False
    assert loaded["speaker_filter_mode"] == "analysis"
    assert loaded["speaker_filter_threshold"] == 0.72
    assert loaded["speaker_filter_apply_to"] == "dictation"


def test_prerecording_duration_settings_default_and_clamp(tmp_path):
    config_path = tmp_path / "transcription_config.json"
    config_path.write_text(
        """
{
  "manual_pre_recording_seconds": 99,
  "wake_pre_recording_seconds": -2
}
""",
        encoding="utf-8",
    )

    loaded = load_settings(config_path)

    assert DEFAULT_SETTINGS["manual_pre_recording_seconds"] == 2.0
    assert DEFAULT_SETTINGS["wake_pre_recording_seconds"] == 2.0
    assert loaded["manual_pre_recording_seconds"] == 5.0
    assert loaded["wake_pre_recording_seconds"] == 0.0


def test_f23_dictation_profile_derives_active_record_keys():
    profiles = normalize_hotkey_profiles(DEFAULT_HOTKEY_PROFILES)
    profiles["dictation"]["triggers"] = ["f23", "ctrl_r+shift+a", "a"]
    profiles["dictation"]["enabled"] = True
    profiles["command"]["triggers"] = ["f24", "ctrl_r+shift+f24"]
    profiles["command"]["enabled"] = True

    normalized = normalize_hotkey_profiles(profiles)

    assert record_keys_from_hotkey_profiles(normalized) == "f24,f23"
    assert normalized["dictation"]["triggers"] == ["f23", "ctrl_r+shift+a"]
    assert normalized["dictation"]["trigger"] == "f23"

    env = build_backend_environment(
        {
            "enable_wakeword_detection": False,
            "record_keys": "f24",
            "hotkey_profiles": normalized,
        },
        base_env={},
    )

    assert env["WKEY_RECORD_KEYS"] == "f24,f23"
    assert "ctrl_r+shift+a" in env["WKEY_HOTKEY_PROFILES"]


def test_legacy_f23_record_keys_seed_dictation_profile():
    profiles = normalize_hotkey_profiles(None, record_keys="f24,f23")

    assert profiles["dictation"]["enabled"] is True
    assert profiles["dictation"]["trigger"] == "f23"
    assert profiles["dictation"]["triggers"] == ["f23"]
    assert record_keys_from_hotkey_profiles(profiles) == "f24,f23"


def test_default_hotkey_profiles_preserve_record_key_compatibility():
    profiles = normalize_hotkey_profiles(None, record_keys="f24,ctrl_l")

    assert profiles["dictation"]["trigger"] == "ctrl_r"
    assert profiles["dictation"]["triggers"] == ["ctrl_r"]
    assert profiles["dictation"]["enabled"] is True
    assert profiles["command"]["trigger"] == "f24"
    assert profiles["command"]["triggers"] == ["f24"]
    assert profiles["command"]["enabled"] is True
    assert profiles["df_diagnostic"]["trigger"] == "d+f"
    assert profiles["df_diagnostic"]["enabled"] is False
    assert profiles["df_diagnostic"]["diagnostic"] is True
    assert record_keys_from_hotkey_profiles(profiles) == DEFAULT_RECORD_KEYS


def test_hotkey_profile_save_load_roundtrip_keeps_advanced_settings(tmp_path):
    settings_path = tmp_path / "transcription_config.json"
    profiles = normalize_hotkey_profiles(DEFAULT_HOTKEY_PROFILES)
    profiles["dictation"]["enabled"] = False

    assert save_settings(
        settings_path,
        {
            "record_keys": "f24,ctrl_r",
            "hotkey_profiles": profiles,
            "context_max_age_seconds": 90,
            "max_recording_seconds": 12,
            "google_wake_volume_hold_seconds": 1.75,
            "speaker_filter_enabled": True,
            "speaker_filter_mode": "balanced",
            "speaker_filter_threshold": 0.82,
            "speaker_filter_profile_path": "I:/profiles/harsha.json",
        },
    )

    loaded = load_settings(settings_path)
    assert loaded["hotkey_profiles"]["dictation"]["enabled"] is False
    assert loaded["record_keys"] == "f24"
    assert loaded["context_max_age_seconds"] == 90
    assert loaded["max_recording_seconds"] == 12
    assert loaded["google_wake_volume_hold_seconds"] == 1.75
    assert loaded["speaker_filter_enabled"] is True
    assert loaded["speaker_filter_mode"] == "balanced"
    assert loaded["speaker_filter_threshold"] == 0.82
    assert loaded["speaker_filter_profile_path"] == "I:/profiles/harsha.json"


def test_speaker_filter_enabled_toggle_roundtrip(tmp_path):
    settings_path = tmp_path / "transcription_config.json"

    assert save_settings(settings_path, {"speaker_filter_enabled": True})
    assert load_settings(settings_path)["speaker_filter_enabled"] is True

    assert save_settings(settings_path, {"speaker_filter_enabled": False})
    assert load_settings(settings_path)["speaker_filter_enabled"] is False
