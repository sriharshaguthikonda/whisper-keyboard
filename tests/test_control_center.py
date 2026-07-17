import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QScrollArea,
)

from wkey.backend_process import RuntimeStatus
from wkey.settings_manager import DEFAULT_SETTINGS, save_settings


_QT_APP = None


def qt_app():
    global _QT_APP
    _QT_APP = QApplication.instance() or QApplication(sys.argv)
    return _QT_APP


def _build_window(tmp_path, monkeypatch, settings_overrides=None):
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
    settings.update(settings_overrides or {})
    save_settings(config_path, settings)
    return control_center.WhisperControlCenter(config_path=config_path)


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


def test_control_center_stack_pages_are_scrollable(tmp_path, monkeypatch):
    qt_app()
    window = _build_window(tmp_path, monkeypatch)
    try:
        assert window.stack.count() == 7
        for index in range(window.stack.count()):
            page = window.stack.widget(index)
            assert isinstance(page, QScrollArea)
            assert page.widget() is not None
    finally:
        window.close()


def test_control_center_minimum_size_fits_small_screens(tmp_path, monkeypatch):
    qt_app()
    window = _build_window(tmp_path, monkeypatch)
    try:
        min_size = window.minimumSize()
        assert min_size.width() <= 640
        assert min_size.height() <= 480
    finally:
        window.close()


def test_control_center_resize_small_does_not_raise(tmp_path, monkeypatch):
    app = qt_app()
    window = _build_window(tmp_path, monkeypatch)
    try:
        window.resize(700, 500)
        window.show()
        app.processEvents()
    finally:
        window.close()


def test_geometry_needs_recenter_guard():
    from wkey.control_center import geometry_needs_recenter

    screen_rects = [QRect(0, 0, 1920, 1080)]
    onscreen = QRect(100, 100, 800, 600)
    offscreen = QRect(5000, 5000, 800, 600)

    assert geometry_needs_recenter(onscreen, screen_rects) is False
    assert geometry_needs_recenter(offscreen, screen_rects) is True
    assert geometry_needs_recenter(onscreen, []) is True


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
