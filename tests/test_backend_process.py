import importlib
from pathlib import Path

from wkey.backend_process import (
    BACKEND_SCRIPT_NAME,
    find_backend_processes,
    get_runtime_status,
    is_backend_command_line,
    read_backend_health_status,
)


def test_backend_process_matching_uses_target_script_name():
    assert is_backend_command_line(
        r'C:\Python\python.exe "C:\repo\wkey\faster_whisper_Mother_of_all_wkey.py"'
    )
    assert is_backend_command_line(
        f"python -u ./wkey/{BACKEND_SCRIPT_NAME}"
    )
    assert not is_backend_command_line("python ./wkey/Settings_GUI.py")
    assert not is_backend_command_line("")


def test_default_health_status_path_uses_runtime_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("WKEY_RUNTIME_DIR", str(tmp_path))
    import wkey.backend_process as backend_process

    backend_process = importlib.reload(backend_process)

    assert backend_process.DEFAULT_HEALTH_STATUS_PATH == (
        Path(tmp_path) / "backend_health_status.json"
    )


def test_find_backend_processes_filters_cim_rows():
    rows = [
        {"ProcessId": 123, "CommandLine": rf'python "wkey\{BACKEND_SCRIPT_NAME}"'},
        {"ProcessId": 456, "CommandLine": "python other.py"},
        {"ProcessId": None, "CommandLine": rf'python "wkey\{BACKEND_SCRIPT_NAME}"'},
    ]

    processes = find_backend_processes(process_rows=rows)

    assert [process.pid for process in processes] == [123]
    assert processes[0].command_line == rf'python "wkey\{BACKEND_SCRIPT_NAME}"'


def test_runtime_status_summarizes_process_settings_and_pause_state(tmp_path):
    config_path = tmp_path / "transcription_config.json"
    rows = [{"ProcessId": 321, "CommandLine": rf'python "wkey\{BACKEND_SCRIPT_NAME}"'}]

    status = get_runtime_status(
        settings={"enable_wakeword_detection": False, "record_keys": "f24,ctrl_l"},
        config_path=config_path,
        process_rows=rows,
        pause_state_reader=lambda: "PAUSED",
    )

    assert status.running is True
    assert status.backend_pids == (321,)
    assert status.runtime_mode == "keyboard"
    assert status.active_keys == "F24 or Right Ctrl"
    assert status.pause_state == "PAUSED"
    assert status.config_path == str(config_path)


def test_runtime_status_reports_task_running_backend_missing(tmp_path):
    health_path = tmp_path / "backend_health.json"
    health_path.write_text(
        '{"pid":999,"last_heartbeat":123.0,"runtime_mode":"combined"}',
        encoding="utf-8",
    )

    status = get_runtime_status(
        settings={"enable_wakeword_detection": True, "record_keys": "f24,f23"},
        config_path=tmp_path / "transcription_config.json",
        process_rows=[],
        pause_state_reader=lambda: "RUNNING",
        scheduled_task_state_reader=lambda: "Running",
        health_status_path=health_path,
    )

    assert status.running is False
    assert status.scheduled_task_state == "Running"
    assert status.health_summary == "task running but backend missing"
    assert status.backend_health["pid"] == 999


def test_read_backend_health_status_handles_missing_and_invalid_json(tmp_path):
    assert read_backend_health_status(tmp_path / "missing.json") == {}

    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")

    assert read_backend_health_status(bad) == {}
