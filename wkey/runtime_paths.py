"""Runtime file locations for Whisper Keyboard."""

from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "WhisperKeyboard"
RUNTIME_DIR_NAME = "runtime"
RUNTIME_DIR_ENV = "WKEY_RUNTIME_DIR"


def _absolute_path(path: str | os.PathLike[str]) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    return resolved


def get_runtime_dir(env: os._Environ[str] | None = None) -> Path:
    values = env if env is not None else os.environ
    override = str(values.get(RUNTIME_DIR_ENV, "")).strip()
    if override:
        return _absolute_path(override)

    local_app_data = str(values.get("LOCALAPPDATA", "")).strip()
    if local_app_data:
        base_dir = _absolute_path(local_app_data)
    else:
        base_dir = Path.home() / "AppData" / "Local"
    return base_dir / APP_DIR_NAME / RUNTIME_DIR_NAME


def ensure_runtime_dir(env: os._Environ[str] | None = None) -> Path:
    runtime_dir = get_runtime_dir(env)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def runtime_path(filename: str, env: os._Environ[str] | None = None) -> Path:
    return get_runtime_dir(env) / filename
