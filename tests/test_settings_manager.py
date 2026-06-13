from wkey.settings_manager import build_backend_environment, runtime_mode_for_settings


def test_runtime_mode_for_wakeword_setting():
    assert runtime_mode_for_settings({"enable_wakeword_detection": True}) == "combined"
    assert runtime_mode_for_settings({"enable_wakeword_detection": False}) == "keyboard"


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

    assert env["WKEY_RECORD_KEYS"] == "f24,caps_lock"
    assert env["WKEY_RUNTIME_MODE"] == "keyboard"
    assert env["OTHER"] == "kept"
