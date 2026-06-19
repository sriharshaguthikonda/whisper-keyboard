from wkey.settings_manager import (
    DEFAULT_RECORD_KEYS,
    DEFAULT_HOTKEY_PROFILES,
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


def test_f23_dictation_profile_derives_active_record_keys():
    profiles = normalize_hotkey_profiles(DEFAULT_HOTKEY_PROFILES)
    profiles["dictation"]["trigger"] = "f23"
    profiles["dictation"]["enabled"] = True
    profiles["command"]["trigger"] = "f24"
    profiles["command"]["enabled"] = True

    assert record_keys_from_hotkey_profiles(profiles) == "f24,f23"

    env = build_backend_environment(
        {
            "enable_wakeword_detection": False,
            "record_keys": "f24",
            "hotkey_profiles": profiles,
        },
        base_env={},
    )

    assert env["WKEY_RECORD_KEYS"] == "f24,f23"


def test_legacy_f23_record_keys_seed_dictation_profile():
    profiles = normalize_hotkey_profiles(None, record_keys="f24,f23")

    assert profiles["dictation"]["enabled"] is True
    assert profiles["dictation"]["trigger"] == "f23"
    assert record_keys_from_hotkey_profiles(profiles) == "f24,f23"


def test_default_hotkey_profiles_preserve_record_key_compatibility():
    profiles = normalize_hotkey_profiles(None, record_keys="f24,ctrl_l")

    assert profiles["dictation"]["trigger"] == "ctrl_r"
    assert profiles["dictation"]["enabled"] is True
    assert profiles["command"]["trigger"] == "f24"
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
        },
    )

    loaded = load_settings(settings_path)
    assert loaded["hotkey_profiles"]["dictation"]["enabled"] is False
    assert loaded["record_keys"] == "f24"
    assert loaded["context_max_age_seconds"] == 90
    assert loaded["max_recording_seconds"] == 12
    assert loaded["google_wake_volume_hold_seconds"] == 1.75
