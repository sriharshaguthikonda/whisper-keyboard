from wkey.settings_manager import (
    DEFAULT_RECORD_KEYS,
    build_backend_environment,
    normalize_record_key_label,
    normalize_record_keys,
    runtime_mode_for_settings,
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

    assert env["WKEY_RECORD_KEYS"] == "f24,ctrl_l"
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

    assert env["WKEY_RECORD_KEYS"] == "f24,ctrl_l"


def test_record_key_normalization_is_safe_for_capture_names():
    assert DEFAULT_RECORD_KEYS == "f24,ctrl_l"
    assert normalize_record_key_label("left ctrl") == "ctrl_l"
    assert normalize_record_key_label("left control") == "ctrl_l"
    assert normalize_record_key_label("right ctrl") == "ctrl_l"
    assert normalize_record_key_label("right control") == "ctrl_l"
    assert normalize_record_key_label("caps lock") is None
    assert normalize_record_key_label("F24") == "f24"
    assert normalize_record_key_label("space") is None
    assert normalize_record_keys("caps lock, F24") == "f24"
    assert normalize_record_keys("space") == DEFAULT_RECORD_KEYS
