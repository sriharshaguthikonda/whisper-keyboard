from wkey.backend_process import (
    BACKEND_SCRIPT_NAME,
    find_backend_processes,
    get_runtime_status,
    is_backend_command_line,
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

