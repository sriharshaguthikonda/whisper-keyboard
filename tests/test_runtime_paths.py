import os
from pathlib import Path

from wkey.runtime_paths import ensure_runtime_dir, get_runtime_dir, runtime_path


def test_runtime_dir_prefers_explicit_env(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "custom-runtime"
    monkeypatch.setenv("WKEY_RUNTIME_DIR", str(runtime_dir))

    assert get_runtime_dir() == runtime_dir
    assert runtime_path("backend_health_status.json") == (
        runtime_dir / "backend_health_status.json"
    )


def test_runtime_dir_defaults_to_localappdata(monkeypatch, tmp_path):
    localappdata = tmp_path / "LocalAppData"
    monkeypatch.delenv("WKEY_RUNTIME_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))

    assert get_runtime_dir() == localappdata / "WhisperKeyboard" / "runtime"


def test_ensure_runtime_dir_creates_directory(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("WKEY_RUNTIME_DIR", str(runtime_dir))

    assert ensure_runtime_dir() == runtime_dir
    assert runtime_dir.is_dir()


def test_runtime_dir_fallback_is_absolute(monkeypatch):
    monkeypatch.delenv("WKEY_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert get_runtime_dir().is_absolute()
    assert os.path.normpath(str(runtime_path("wkey-runtime.log"))).endswith(
        os.path.normpath("WhisperKeyboard/runtime/wkey-runtime.log")
    )
