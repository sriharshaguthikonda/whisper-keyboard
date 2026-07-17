from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_broker_launcher_files_removed():
    assert not (REPO_ROOT / "Start-WKeyBroker.bat").exists()
    assert not (REPO_ROOT / "scripts" / "Start-WKeyBroker.ps1").exists()


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
    assert "-WindowStyle Hidden" in script
    assert '-File "' in script
    assert '$exportedXml -notlike "*-WindowStyle Hidden*"' in script
    assert '$exportedXml -like "*-Console*"' in script
    assert '$exportedXml -like "*EventTrigger*"' in script


def test_direct_python_launcher_has_no_broker_or_process_killing():
    script = read_script("Start-WhisperKeyboard.ps1")

    assert "faster_whisper_Mother_of_all_wkey.py" in script
    assert "WKEY_INPUT_OWNER" in script
    assert '"python"' in script
    assert "wkey-broker" not in script.lower()
    assert "Stop-Process" not in script
    assert "taskkill" not in script.lower()


def test_direct_python_launcher_logs_both_streams_and_exit_code():
    script = read_script("Start-WhisperKeyboard.ps1")

    assert "whisper-keyboard-startup.log" in script
    assert "*>> $LogPath" in script
    assert "$ExitCode" in script
    assert "Add-Content -LiteralPath $LogPath -Value $ExitLine" in script
    assert "exited with code" in script
