"""Runtime process helpers for the Whisper Keyboard backend."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Callable, Iterable, Mapping, Sequence

try:
    from .pause_flag_path import get_pause_flag_path
    from .settings_manager import (
        DEFAULT_SETTINGS,
        build_backend_environment,
        load_settings,
        normalize_record_keys,
        record_key_display_text,
        runtime_mode_for_settings,
    )
except ImportError:
    from pause_flag_path import get_pause_flag_path
    from settings_manager import (
        DEFAULT_SETTINGS,
        build_backend_environment,
        load_settings,
        normalize_record_keys,
        record_key_display_text,
        runtime_mode_for_settings,
    )


BACKEND_SCRIPT_NAME = "faster_whisper_Mother_of_all_wkey.py"
WKEY_DIR = Path(__file__).resolve().parent
REPO_ROOT = WKEY_DIR.parent
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_CONFIG_PATH = WKEY_DIR / "transcription_config.json"
DEFAULT_PYTHON_EXE = WORKSPACE_ROOT / "openai" / "Scripts" / "python.exe"


@dataclass(frozen=True)
class BackendProcess:
    pid: int
    command_line: str


@dataclass(frozen=True)
class RuntimeStatus:
    backend_pids: tuple[int, ...]
    running: bool
    runtime_mode: str
    active_keys: str
    pause_state: str
    config_path: str
    last_launch_command: str


def is_backend_command_line(command_line: str | None) -> bool:
    if not command_line:
        return False
    normalized = str(command_line).lower().replace("/", "\\")
    return BACKEND_SCRIPT_NAME.lower() in normalized


def _query_windows_process_rows() -> list[Mapping[str, object]]:
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def find_backend_processes(
    process_rows: Iterable[Mapping[str, object]] | None = None,
) -> list[BackendProcess]:
    rows = list(process_rows) if process_rows is not None else _query_windows_process_rows()
    processes: list[BackendProcess] = []
    for row in rows:
        command_line = str(row.get("CommandLine") or "")
        if not is_backend_command_line(command_line):
            continue
        try:
            pid = int(row.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        processes.append(BackendProcess(pid=pid, command_line=command_line))
    return processes


def build_launch_command(
    python_exe: str | os.PathLike[str] | None = None,
    repo_root: str | os.PathLike[str] | None = None,
) -> list[str]:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    interpreter = Path(python_exe) if python_exe is not None else DEFAULT_PYTHON_EXE
    if not interpreter.exists():
        interpreter = Path("python")
    return [str(interpreter), str(root / "wkey" / BACKEND_SCRIPT_NAME)]


def read_pause_state(path: str | os.PathLike[str] | None = None) -> str:
    pause_path = Path(path) if path is not None else Path(get_pause_flag_path(__file__))
    try:
        value = pause_path.read_text(encoding="utf-8").strip().upper()
    except OSError:
        return "UNKNOWN"
    return value or "UNKNOWN"


def get_runtime_status(
    settings: Mapping[str, object] | None = None,
    config_path: str | os.PathLike[str] | None = None,
    process_rows: Iterable[Mapping[str, object]] | None = None,
    pause_state_reader: Callable[[], str] | None = None,
) -> RuntimeStatus:
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    config = dict(settings or load_settings(path, DEFAULT_SETTINGS))
    config["record_keys"] = normalize_record_keys(config.get("record_keys"))
    processes = find_backend_processes(process_rows=process_rows)
    command = build_launch_command(repo_root=path.parent.parent)
    pause_state = pause_state_reader() if pause_state_reader else read_pause_state()
    return RuntimeStatus(
        backend_pids=tuple(process.pid for process in processes),
        running=bool(processes),
        runtime_mode=runtime_mode_for_settings(config),
        active_keys=record_key_display_text(config.get("record_keys")),
        pause_state=str(pause_state).upper(),
        config_path=str(path),
        last_launch_command=" ".join(command),
    )


def start_backend(
    settings: Mapping[str, object] | None = None,
    python_exe: str | os.PathLike[str] | None = None,
    repo_root: str | os.PathLike[str] | None = None,
    popen: Callable[..., subprocess.Popen] | None = None,
):
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    config = dict(settings or load_settings(root / "wkey" / "transcription_config.json"))
    command = build_launch_command(python_exe=python_exe, repo_root=root)
    env = build_backend_environment(config)
    kwargs = {
        "cwd": str(root / "wkey"),
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    launcher = popen or subprocess.Popen
    return launcher(command, **kwargs)


def stop_backend(
    process_rows: Iterable[Mapping[str, object]] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> list[int]:
    command_runner = runner or subprocess.run
    stopped: list[int] = []
    for process in find_backend_processes(process_rows=process_rows):
        command_runner(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        stopped.append(process.pid)
    return stopped


def restart_backend(
    settings: Mapping[str, object] | None = None,
    process_rows: Iterable[Mapping[str, object]] | None = None,
    stop_runner: Callable[..., subprocess.CompletedProcess] | None = None,
    **start_kwargs,
):
    stop_backend(process_rows=process_rows, runner=stop_runner)
    time.sleep(0.5)
    return start_backend(settings=settings, **start_kwargs)
