import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_launcher_uses_localappdata_runtime_dir():
    script = read_script("Start-WKeyBroker.ps1")

    assert "$RuntimeDir" in script
    assert "WhisperKeyboard" in script
    assert "backend_health_status.json" in script
    assert "wkey\\backend_health_status.json" not in script
    assert "wkey\\wkey_runtime.lock" not in script
    assert '"WKEY_RUNTIME_DIR"' in script


def test_launcher_supervises_broker_with_backoff():
    script = read_script("Start-WKeyBroker.ps1")

    assert "$ShouldSupervise" in script
    assert "MaxRestarts" in script
    assert "RestartDelaySeconds" in script
    assert "Start-BrokerOnce" in script
    assert "Restarting broker" in script


def test_launcher_streams_console_broker_output_without_exit_code_pollution():
    script = read_script("Start-WKeyBroker.ps1")
    start = script.index("function Start-BrokerOnce")
    end = script.index('if (-not (Test-Path -LiteralPath $BrokerManifest))', start)
    start_broker_once = script[start:end]

    assert "& $BrokerExe @brokerArgs | ForEach-Object { Write-Host $_ }" in start_broker_once
    assert "$brokerExitCode = $LASTEXITCODE" in start_broker_once
    assert "return [int]$brokerExitCode" in start_broker_once
    assert "return [int]$LASTEXITCODE" not in start_broker_once


def test_launcher_console_stream_pattern_preserves_native_exit_code(tmp_path):
    broker = tmp_path / "fake-broker.cmd"
    broker.write_text("@echo broker_python_child pid=123\n@exit /b 7\n", encoding="utf-8")

    command = (
        f'$BrokerExe = "{broker}"; '
        "$brokerArgs = @(); "
        '& $BrokerExe @brokerArgs | ForEach-Object { Write-Host $_ }; '
        "$brokerExitCode = $LASTEXITCODE; "
        "exit [int]$brokerExitCode"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 7
    assert "broker_python_child pid=123" in result.stdout


def test_task_installer_reconciles_full_task_xml_and_verifies_action():
    script = read_script("Install-WKeyBrokerTask.ps1")

    assert 'Start-WhisperKeyboard.ps1' in script
    assert '<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>' in script
    assert '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>' in script
    assert '<EventTrigger>' not in script
    assert '<RestartOnFailure>' in script
    assert "Register-ScheduledTask" in script
    assert "-Xml $xml" in script
    assert "-Force" in script
    assert "Export-ScheduledTask" in script
    assert "Set-ScheduledTask" not in script
    assert "Start-WKeyBroker.bat" not in script


def test_direct_python_launcher_has_no_broker_or_process_killing():
    script = read_script("Start-WhisperKeyboard.ps1")

    assert "faster_whisper_Mother_of_all_wkey.py" in script
    assert "WKEY_INPUT_OWNER" in script
    assert '"python"' in script
    assert "wkey-broker" not in script.lower()
    assert "Stop-Process" not in script
    assert "taskkill" not in script.lower()
