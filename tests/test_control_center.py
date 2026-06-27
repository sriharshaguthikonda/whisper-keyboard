import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit

from wkey.backend_process import RuntimeStatus
from wkey.settings_manager import DEFAULT_SETTINGS, save_settings


_QT_APP = None


def qt_app():
    global _QT_APP
    _QT_APP = QApplication.instance() or QApplication(sys.argv)
    return _QT_APP


def test_control_center_exposes_speaker_filter_controls(tmp_path, monkeypatch):
    qt_app()
    import wkey.control_center as control_center

    monkeypatch.setattr(
        control_center,
        "get_runtime_status",
        lambda settings, config_path: RuntimeStatus(
            backend_pids=(),
            running=False,
            runtime_mode="keyboard",
            active_keys="F24, Right Ctrl",
            pause_state="RUNNING",
            config_path=str(config_path),
            last_launch_command="python backend",
        ),
    )
    monkeypatch.setattr(
        control_center.WhisperControlCenter,
        "_scheduled_task_summary",
        lambda self: "not checked",
    )
    config_path = tmp_path / "settings.json"
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "speaker_filter_enabled": True,
            "speaker_filter_mode": "balanced",
            "speaker_filter_threshold": 0.81,
            "speaker_filter_profile_path": str(tmp_path / "profile.json"),
            "speaker_filter_enrollment_dir": str(tmp_path / "positives"),
            "speaker_filter_negative_dir": str(tmp_path / "negatives"),
        }
    )
    save_settings(config_path, settings)

    window = control_center.WhisperControlCenter(config_path=config_path)
    try:
        assert isinstance(window.setting_widgets["speaker_filter_enabled"], QCheckBox)
        assert isinstance(window.setting_widgets["speaker_filter_mode"], QComboBox)
        assert isinstance(window.setting_widgets["speaker_filter_threshold"], QDoubleSpinBox)
        assert isinstance(window.setting_widgets["speaker_filter_profile_path"], QLineEdit)
        assert window.setting_widgets["speaker_filter_mode"].currentData() == "balanced"
        assert window.setting_widgets["speaker_filter_threshold"].value() == 0.81

        window.setting_widgets["speaker_filter_mode"].setCurrentText("Custom")
        window.setting_widgets["speaker_filter_threshold"].setValue(0.9)
        window.setting_widgets["speaker_filter_profile_path"].setText("I:/profiles/harsha.json")

        collected = window._collect_settings_values()

        assert collected["speaker_filter_enabled"] is True
        assert collected["speaker_filter_mode"] == "custom"
        assert collected["speaker_filter_threshold"] == 0.9
        assert collected["speaker_filter_profile_path"] == "I:/profiles/harsha.json"
        assert [window.theme_combo.itemData(i) for i in range(window.theme_combo.count())] == [
            "system",
            "dark",
            "light",
        ]
    finally:
        window.close()


def test_control_center_updates_speaker_filter_status_labels(tmp_path, monkeypatch):
    qt_app()
    import wkey.control_center as control_center

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({"thresholds": {"balanced": 0.76}}),
        encoding="utf-8",
    )
    status_path = tmp_path / "speaker_filter_status.json"
    status_path.write_text(
        json.dumps(
            {
                "decision": "filtered",
                "accepted_seconds": 1.25,
                "rejected_seconds": 0.75,
                "threshold": 0.76,
                "profile_loaded": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        control_center,
        "get_runtime_status",
        lambda settings, config_path: RuntimeStatus(
            backend_pids=(123,),
            running=True,
            runtime_mode="keyboard",
            active_keys="F24, Right Ctrl",
            pause_state="RUNNING",
            config_path=str(config_path),
            last_launch_command="python backend",
        ),
    )
    monkeypatch.setattr(
        control_center.WhisperControlCenter,
        "_scheduled_task_summary",
        lambda self: "not checked",
    )
    config_path = tmp_path / "settings.json"
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "speaker_filter_enabled": True,
            "speaker_filter_mode": "balanced",
            "speaker_filter_profile_path": str(profile_path),
        }
    )
    save_settings(config_path, settings)

    window = control_center.WhisperControlCenter(config_path=config_path)
    try:
        window.speaker_filter_status_path = status_path
        window.refresh_status()

        assert window.speaker_filter_profile_status_label.text() == "loaded"
        assert window.speaker_filter_threshold_status_label.text() == "balanced / 0.76"
        assert window.speaker_filter_last_decision_label.text() == "filtered"
        assert window.speaker_filter_last_duration_label.text() == "accepted 1.25s / rejected 0.75s"
    finally:
        window.close()


def test_control_center_shows_backend_health_summary(tmp_path, monkeypatch):
    qt_app()
    import wkey.control_center as control_center

    monkeypatch.setattr(
        control_center,
        "get_runtime_status",
        lambda settings, config_path: RuntimeStatus(
            backend_pids=(),
            running=False,
            runtime_mode="combined",
            active_keys="F24, F23",
            pause_state="RUNNING",
            config_path=str(config_path),
            last_launch_command="python backend",
            scheduled_task_state="Running",
            backend_health={"pid": 999},
            health_summary="task running but backend missing",
        ),
    )
    monkeypatch.setattr(
        control_center.WhisperControlCenter,
        "_scheduled_task_summary",
        lambda self: "Running",
    )
    config_path = tmp_path / "settings.json"
    save_settings(config_path, dict(DEFAULT_SETTINGS))

    window = control_center.WhisperControlCenter(config_path=config_path)
    try:
        window.refresh_status()

        assert window.backend_status_label.text() == "task running but backend missing"
        assert window.pid_label.text() == "-"
    finally:
        window.close()
