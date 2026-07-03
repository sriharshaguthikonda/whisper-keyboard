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


def test_task_installer_reconciles_full_task_xml_and_verifies_action():
    script = read_script("Install-WKeyBrokerTask.ps1")

    assert '$LauncherArguments = "--log"' in script
    assert "Register-ScheduledTask" in script
    assert "-Xml $xml" in script
    assert "-Force" in script
    assert "Export-ScheduledTask" in script
    assert "Set-ScheduledTask" not in script
    assert "Start-WKeyBroker.bat" in script
