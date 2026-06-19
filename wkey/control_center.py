"""Qt control center for Whisper Keyboard."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import threading

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from .backend_process import (
        BACKEND_SCRIPT_NAME,
        DEFAULT_CONFIG_PATH,
        REPO_ROOT,
        RuntimeStatus,
        get_runtime_status,
        read_pause_state,
        restart_backend,
        start_backend,
        stop_backend,
    )
    from .control_center_state import (
        BOOLEAN_SETTING_FIELDS,
        FLOAT_SETTING_LIMITS,
        INTEGER_SETTING_LIMITS,
        apply_settings_values,
        build_settings_snapshot,
    )
    from .pause_control import set_pause_state, toggle_pause_state
    from .pause_flag_path import get_pause_flag_path
    from .settings_manager import (
        DEFAULT_SETTINGS,
        SPEAKER_FILTER_MODES,
        load_settings,
        normalize_hotkey_profiles,
        save_settings,
    )
except ImportError:
    from backend_process import (
        BACKEND_SCRIPT_NAME,
        DEFAULT_CONFIG_PATH,
        REPO_ROOT,
        RuntimeStatus,
        get_runtime_status,
        read_pause_state,
        restart_backend,
        start_backend,
        stop_backend,
    )
    from control_center_state import (
        BOOLEAN_SETTING_FIELDS,
        FLOAT_SETTING_LIMITS,
        INTEGER_SETTING_LIMITS,
        apply_settings_values,
        build_settings_snapshot,
    )
    from pause_control import set_pause_state, toggle_pause_state
    from pause_flag_path import get_pause_flag_path
    from settings_manager import (
        DEFAULT_SETTINGS,
        SPEAKER_FILTER_MODES,
        load_settings,
        normalize_hotkey_profiles,
        save_settings,
    )


SECTION_NAMES = (
    "Dashboard",
    "Hotkeys",
    "Transcription",
    "Voice Commands",
    "Diagnostics",
    "Startup",
    "Logs",
)

HOTKEY_PROFILE_ORDER = (
    "dictation",
    "command",
    "pause_resume",
    "pause_15m",
    "pause_60m",
    "wake_mode_toggle",
    "restart_backend",
    "df_diagnostic",
)

TRIGGER_PRESETS = {
    "dictation": ("ctrl_r", "f23", ""),
    "command": ("f24", ""),
    "pause_resume": ("ctrl+shift+p", ""),
    "pause_15m": ("ctrl+shift+1", ""),
    "pause_60m": ("ctrl+shift+2", ""),
    "wake_mode_toggle": ("", "ctrl+shift+w"),
    "restart_backend": ("", "ctrl+shift+r"),
    "df_diagnostic": ("d+f",),
}

SETTING_LABELS = {
    "use_local_gpu": "Local GPU",
    "use_local_cpu": "Local CPU",
    "fallback_to_groq": "Groq fallback",
    "enable_edge_selenium": "Edge automation",
    "enable_wakeword_detection": "Wake words",
    "enable_pre_recording_keyword_check": "Wake pre-check",
    "enable_transcript_context_memory": "Context memory",
    "max_retries": "Groq retries",
    "stt_context_items": "STT context items",
    "stt_context_chars": "STT context chars",
    "router_context_items": "Router context items",
    "router_context_chars": "Router context chars",
    "context_max_age_seconds": "Context max age",
    "max_recording_seconds": "Max recording seconds",
    "google_wake_volume_hold_seconds": "Wake volume hold",
}


class WhisperControlCenter(QMainWindow):
    diagnostic_finished = pyqtSignal(str)

    def __init__(self, config_path: str | os.PathLike[str] | None = None):
        super().__init__()
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self.settings = load_settings(self.config_path, DEFAULT_SETTINGS)
        self.hotkey_profiles = normalize_hotkey_profiles(
            self.settings.get("hotkey_profiles"), self.settings.get("record_keys")
        )
        self.status: RuntimeStatus | None = None
        self.tray_icon: QSystemTrayIcon | None = None
        self.section_buttons: dict[str, QListWidgetItem] = {}
        self.hotkey_widgets: dict[str, dict[str, object]] = {}
        self.setting_widgets: dict[str, object] = {}
        self.speaker_filter_status_path = REPO_ROOT / "wkey" / "speaker_filter_status.json"

        self.setWindowTitle("Whisper Keyboard Control Center")
        self.setMinimumSize(960, 640)
        self.resize(1120, 720)

        self.diagnostic_finished.connect(self._diagnostic_complete)
        self._build_ui()
        self._setup_tray()
        self._connect_system_theme_updates()
        self._apply_theme()
        self.refresh_all()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(5000)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        for name in SECTION_NAMES:
            item = QListWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))
            self.sidebar.addItem(item)
            self.section_buttons[name] = item
        self.sidebar.currentRowChanged.connect(self._set_section)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._dashboard_section())
        self.stack.addWidget(self._hotkeys_section())
        self.stack.addWidget(self._transcription_section())
        self.stack.addWidget(self._voice_commands_section())
        self.stack.addWidget(self._diagnostics_section())
        self.stack.addWidget(self._startup_section())
        self.stack.addWidget(self._logs_section())
        self.sidebar.setCurrentRow(0)

    def _connect_system_theme_updates(self):
        app = QApplication.instance()
        if app is None:
            return
        try:
            app.paletteChanged.connect(lambda *_: self._apply_theme())
        except Exception:
            pass
        try:
            app.styleHints().colorSchemeChanged.connect(lambda *_: self._apply_theme())
        except Exception:
            pass

    def _system_prefers_dark(self):
        app = QApplication.instance()
        palette = app.palette() if app is not None else self.palette()
        return palette.color(QPalette.ColorRole.Window).lightness() < 128

    def _effective_theme_mode(self):
        mode = str(self.settings.get("ui_theme", "system")).strip().lower()
        if mode == "dark":
            return "dark"
        if mode == "light":
            return "light"
        return "dark" if self._system_prefers_dark() else "light"

    def _apply_theme(self):
        if self._effective_theme_mode() == "dark":
            self._apply_dark_style()
        else:
            self._apply_light_style()

    def _apply_light_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f7f8fa; color: #1f2933; font-family: Segoe UI; }
            QListWidget#sidebar { background: #17212b; color: #d9e2ec; border: none; padding: 10px 0; }
            QListWidget#sidebar::item { padding: 12px 18px; border-left: 4px solid transparent; }
            QListWidget#sidebar::item:selected { background: #243447; border-left-color: #2f80ed; color: white; }
            QLabel#title { font-size: 22px; font-weight: 600; }
            QLabel#sectionTitle { font-size: 18px; font-weight: 600; }
            QLabel#statusValue { font-size: 18px; font-weight: 600; }
            QFrame#metric, QGroupBox { background: white; border: 1px solid #d7dde5; border-radius: 6px; }
            QGroupBox { margin-top: 10px; padding: 14px 12px 12px 12px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QPushButton { background: #ffffff; border: 1px solid #bcc7d3; border-radius: 5px; padding: 8px 12px; }
            QPushButton:hover { border-color: #2f80ed; }
            QPushButton#primary { background: #2f80ed; color: white; border-color: #2f80ed; }
            QPushButton#danger { background: #c62828; color: white; border-color: #c62828; }
            QTextEdit { background: #0f1720; color: #e5edf5; border: 1px solid #273445; border-radius: 5px; }
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit { min-height: 30px; background: white; border: 1px solid #bcc7d3; border-radius: 4px; padding: 3px 6px; }
            """
        )

    def _apply_dark_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #111820; color: #e5edf5; font-family: Segoe UI; }
            QListWidget#sidebar { background: #0b1218; color: #c9d4df; border: none; padding: 10px 0; }
            QListWidget#sidebar::item { padding: 12px 18px; border-left: 4px solid transparent; }
            QListWidget#sidebar::item:selected { background: #192938; border-left-color: #4f9cf9; color: white; }
            QLabel#title { font-size: 22px; font-weight: 600; }
            QLabel#sectionTitle { font-size: 18px; font-weight: 600; }
            QLabel#statusValue { font-size: 18px; font-weight: 600; color: #f2f6fa; }
            QFrame#metric, QGroupBox { background: #17212b; border: 1px solid #2f4153; border-radius: 6px; }
            QGroupBox { margin-top: 10px; padding: 14px 12px 12px 12px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QPushButton { background: #1f2d3a; color: #e5edf5; border: 1px solid #3a4d61; border-radius: 5px; padding: 8px 12px; }
            QPushButton:hover { border-color: #4f9cf9; }
            QPushButton#primary { background: #1f6feb; color: white; border-color: #1f6feb; }
            QPushButton#danger { background: #b42318; color: white; border-color: #b42318; }
            QTextEdit { background: #0b1218; color: #e5edf5; border: 1px solid #2f4153; border-radius: 5px; }
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit { min-height: 30px; background: #111820; color: #e5edf5; border: 1px solid #3a4d61; border-radius: 4px; padding: 3px 6px; }
            QCheckBox { spacing: 8px; }
            """
        )

    def _page(self, title: str):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        label = QLabel(title)
        label.setObjectName("title")
        layout.addWidget(label)
        return page, layout

    def _metric(self, title: str):
        frame = QFrame()
        frame.setObjectName("metric")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        title_label = QLabel(title)
        value_label = QLabel("-")
        value_label.setObjectName("statusValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return frame, value_label

    def _dashboard_section(self):
        page, layout = self._page("Dashboard")
        grid = QGridLayout()
        grid.setSpacing(10)
        metrics = [
            ("Backend", "backend_status_label"),
            ("PID", "pid_label"),
            ("Runtime", "runtime_label"),
            ("Active Keys", "active_keys_label"),
            ("Pause State", "pause_state_label"),
            ("Config", "config_label"),
        ]
        for index, (title, attr) in enumerate(metrics):
            frame, label = self._metric(title)
            setattr(self, attr, label)
            grid.addWidget(frame, index // 3, index % 3)
        layout.addLayout(grid)

        controls = QHBoxLayout()
        start = QPushButton("Start")
        start.setObjectName("primary")
        start.clicked.connect(self.start_backend)
        controls.addWidget(start)
        stop = QPushButton("Stop")
        stop.setObjectName("danger")
        stop.clicked.connect(self.stop_backend)
        controls.addWidget(stop)
        restart = QPushButton("Restart")
        restart.clicked.connect(self.restart_backend)
        controls.addWidget(restart)
        pause = QPushButton("Pause / Resume")
        pause.clicked.connect(self.toggle_pause)
        controls.addWidget(pause)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_all)
        controls.addWidget(refresh)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System", "system")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.currentIndexChanged.connect(self.set_theme_mode)
        controls.addWidget(QLabel("Theme"))
        controls.addWidget(self.theme_combo)
        self.minimize_to_tray_check = QCheckBox("Minimize to tray")
        self.minimize_to_tray_check.stateChanged.connect(self.set_minimize_to_tray)
        controls.addWidget(self.minimize_to_tray_check)
        controls.addStretch(1)
        layout.addLayout(controls)

        providers = QGroupBox("Provider Status")
        provider_layout = QGridLayout(providers)
        self.groq_label = QLabel("-")
        self.local_label = QLabel("-")
        provider_layout.addWidget(QLabel("Groq"), 0, 0)
        provider_layout.addWidget(self.groq_label, 0, 1)
        provider_layout.addWidget(QLabel("Local"), 1, 0)
        provider_layout.addWidget(self.local_label, 1, 1)
        layout.addWidget(providers)
        layout.addStretch(1)
        return page

    def _hotkeys_section(self):
        page, layout = self._page("Hotkeys")
        self.hotkey_container = QWidget()
        hotkey_layout = QVBoxLayout(self.hotkey_container)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        hotkey_layout.setSpacing(10)

        for profile_id in HOTKEY_PROFILE_ORDER:
            hotkey_layout.addWidget(self._hotkey_row(profile_id))

        layout.addWidget(self.hotkey_container)
        actions = QHBoxLayout()
        defaults = QPushButton("Right Ctrl + F24 Defaults")
        defaults.clicked.connect(self.reset_hotkeys)
        actions.addWidget(defaults)
        save = QPushButton("Save Hotkeys")
        save.setObjectName("primary")
        save.clicked.connect(self.save_hotkeys)
        actions.addWidget(save)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _hotkey_row(self, profile_id: str):
        profile = self.hotkey_profiles[profile_id]
        group = QGroupBox(profile["label"])
        row = QHBoxLayout(group)
        enabled = QCheckBox("Enabled")
        enabled.setChecked(bool(profile.get("enabled")))
        trigger = QComboBox()
        trigger.setEditable(True)
        for preset in TRIGGER_PRESETS.get(profile_id, ("",)):
            trigger.addItem(preset)
        current_trigger = str(profile.get("trigger", ""))
        if current_trigger and trigger.findText(current_trigger) < 0:
            trigger.addItem(current_trigger)
        trigger.setCurrentText(current_trigger)
        if profile_id == "df_diagnostic":
            enabled.setEnabled(False)
            trigger.setEnabled(False)
        row.addWidget(enabled)
        row.addWidget(QLabel("Trigger"))
        row.addWidget(trigger, 1)
        row.addWidget(QLabel("Diagnostic only" if profile.get("diagnostic") else profile.get("action", "")))
        self.hotkey_widgets[profile_id] = {"enabled": enabled, "trigger": trigger}
        return group

    def _transcription_section(self):
        page, layout = self._page("Transcription")
        bool_group = QGroupBox("Runtime")
        bool_layout = QGridLayout(bool_group)
        for index, key in enumerate(BOOLEAN_SETTING_FIELDS):
            widget = QCheckBox(SETTING_LABELS[key])
            self.setting_widgets[key] = widget
            bool_layout.addWidget(widget, index // 2, index % 2)
        layout.addWidget(bool_group)

        advanced_group = QGroupBox("Advanced")
        advanced_layout = QGridLayout(advanced_group)
        row = 0
        for key, (minimum, maximum) in INTEGER_SETTING_LIMITS.items():
            widget = QSpinBox()
            widget.setRange(minimum, maximum)
            self.setting_widgets[key] = widget
            advanced_layout.addWidget(QLabel(SETTING_LABELS[key]), row, 0)
            advanced_layout.addWidget(widget, row, 1)
            row += 1
        for key, (minimum, maximum) in FLOAT_SETTING_LIMITS.items():
            widget = QDoubleSpinBox()
            widget.setDecimals(2)
            widget.setSingleStep(0.25)
            widget.setRange(minimum, maximum)
            self.setting_widgets[key] = widget
            advanced_layout.addWidget(QLabel(SETTING_LABELS[key]), row, 0)
            advanced_layout.addWidget(widget, row, 1)
            row += 1
        layout.addWidget(advanced_group)

        speaker_group = QGroupBox("Target Speaker Filter")
        speaker_layout = QGridLayout(speaker_group)
        speaker_enabled = QCheckBox("Enable for dictation")
        self.setting_widgets["speaker_filter_enabled"] = speaker_enabled
        speaker_layout.addWidget(speaker_enabled, 0, 0, 1, 2)

        mode_combo = QComboBox()
        for mode in SPEAKER_FILTER_MODES:
            mode_combo.addItem(mode.replace("_", " ").title(), mode)
        self.setting_widgets["speaker_filter_mode"] = mode_combo
        self.speaker_filter_mode_combo = mode_combo
        speaker_layout.addWidget(QLabel("Mode"), 1, 0)
        speaker_layout.addWidget(mode_combo, 1, 1)

        threshold = QDoubleSpinBox()
        threshold.setDecimals(2)
        threshold.setSingleStep(0.01)
        threshold.setRange(0.0, 1.0)
        self.setting_widgets["speaker_filter_threshold"] = threshold
        speaker_layout.addWidget(QLabel("Custom threshold"), 2, 0)
        speaker_layout.addWidget(threshold, 2, 1)

        path_fields = (
            ("speaker_filter_profile_path", "Profile path"),
            ("speaker_filter_enrollment_dir", "Enrollment folder"),
            ("speaker_filter_negative_dir", "Negative folder"),
        )
        for offset, (key, label_text) in enumerate(path_fields, start=3):
            field = QLineEdit()
            self.setting_widgets[key] = field
            speaker_layout.addWidget(QLabel(label_text), offset, 0)
            speaker_layout.addWidget(field, offset, 1)

        status_row = 6
        self.speaker_filter_profile_status_label = QLabel("-")
        self.speaker_filter_threshold_status_label = QLabel("-")
        self.speaker_filter_last_decision_label = QLabel("-")
        self.speaker_filter_last_duration_label = QLabel("-")
        speaker_layout.addWidget(QLabel("Profile"), status_row, 0)
        speaker_layout.addWidget(self.speaker_filter_profile_status_label, status_row, 1)
        speaker_layout.addWidget(QLabel("Effective threshold"), status_row + 1, 0)
        speaker_layout.addWidget(self.speaker_filter_threshold_status_label, status_row + 1, 1)
        speaker_layout.addWidget(QLabel("Last decision"), status_row + 2, 0)
        speaker_layout.addWidget(self.speaker_filter_last_decision_label, status_row + 2, 1)
        speaker_layout.addWidget(QLabel("Last duration"), status_row + 3, 0)
        speaker_layout.addWidget(self.speaker_filter_last_duration_label, status_row + 3, 1)
        layout.addWidget(speaker_group)

        actions = QHBoxLayout()
        save = QPushButton("Save Settings")
        save.setObjectName("primary")
        save.clicked.connect(self.save_transcription_settings)
        actions.addWidget(save)
        restart = QPushButton("Save + Restart Backend")
        restart.clicked.connect(self.save_and_restart)
        actions.addWidget(restart)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _voice_commands_section(self):
        page, layout = self._page("Voice Commands")
        group = QGroupBox("Automation")
        grid = QGridLayout(group)
        self.voice_edge_label = QLabel("-")
        self.voice_context_label = QLabel("-")
        self.voice_groq_label = QLabel("-")
        grid.addWidget(QLabel("Edge automation"), 0, 0)
        grid.addWidget(self.voice_edge_label, 0, 1)
        grid.addWidget(QLabel("Context memory"), 1, 0)
        grid.addWidget(self.voice_context_label, 1, 1)
        grid.addWidget(QLabel("Groq"), 2, 0)
        grid.addWidget(self.voice_groq_label, 2, 1)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _diagnostics_section(self):
        page, layout = self._page("Diagnostics")
        controls = QHBoxLayout()
        self.diagnostic_seconds = QSpinBox()
        self.diagnostic_seconds.setRange(1, 300)
        self.diagnostic_seconds.setValue(30)
        controls.addWidget(QLabel("Seconds"))
        controls.addWidget(self.diagnostic_seconds)
        run = QPushButton("Run D+F Diagnostic")
        run.setObjectName("primary")
        run.clicked.connect(self.run_key_diagnostic)
        controls.addWidget(run)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.diagnostic_output = QTextEdit()
        self.diagnostic_output.setReadOnly(True)
        layout.addWidget(self.diagnostic_output, 1)
        return page

    def _startup_section(self):
        page, layout = self._page("Startup")
        group = QGroupBox("Current Startup")
        grid = QGridLayout(group)
        bat_path = REPO_ROOT.parent / "Whisper.bat"
        self.bat_path_label = QLabel(str(bat_path))
        self.task_status_label = QLabel("-")
        self.launch_command_label = QLabel("-")
        self.launch_command_label.setWordWrap(True)
        grid.addWidget(QLabel("Batch file"), 0, 0)
        grid.addWidget(self.bat_path_label, 0, 1)
        grid.addWidget(QLabel("Scheduled task"), 1, 0)
        grid.addWidget(self.task_status_label, 1, 1)
        grid.addWidget(QLabel("Backend command"), 2, 0)
        grid.addWidget(self.launch_command_label, 2, 1)
        layout.addWidget(group)
        refresh = QPushButton("Refresh Startup Status")
        refresh.clicked.connect(self.refresh_startup_status)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _logs_section(self):
        page, layout = self._page("Logs")
        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh Logs")
        refresh.clicked.connect(self.refresh_logs)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.logs_output = QTextEdit()
        self.logs_output.setReadOnly(True)
        layout.addWidget(self.logs_output, 1)
        return page

    def _set_section(self, index: int):
        if index >= 0:
            self.stack.setCurrentIndex(index)
            if SECTION_NAMES[index] == "Logs":
                self.refresh_logs()
            elif SECTION_NAMES[index] == "Startup":
                self.refresh_startup_status()

    def _collect_hotkey_profiles(self):
        profiles = copy.deepcopy(self.hotkey_profiles)
        for profile_id, widgets in self.hotkey_widgets.items():
            enabled = widgets["enabled"].isChecked()
            trigger = widgets["trigger"].currentText().strip().lower()
            profiles[profile_id]["enabled"] = enabled
            profiles[profile_id]["trigger"] = trigger
        return normalize_hotkey_profiles(profiles, self.settings.get("record_keys"))

    def _collect_settings_values(self):
        values = {}
        for key, widget in self.setting_widgets.items():
            if isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                values[key] = widget.currentData() or widget.currentText()
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                values[key] = widget.value()
        values["hotkey_profiles"] = self._collect_hotkey_profiles()
        values["ui_theme"] = self.theme_combo.currentData()
        values["minimize_to_tray"] = self.minimize_to_tray_check.isChecked()
        values["speaker_filter_apply_to"] = "dictation"
        return values

    def _load_widgets_from_settings(self):
        theme_mode = str(self.settings.get("ui_theme", "system"))
        theme_index = self.theme_combo.findData(theme_mode)
        old_block = self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.theme_combo.blockSignals(old_block)

        old_block = self.minimize_to_tray_check.blockSignals(True)
        self.minimize_to_tray_check.setChecked(
            bool(self.settings.get("minimize_to_tray", True))
        )
        self.minimize_to_tray_check.blockSignals(old_block)

        for key, widget in self.setting_widgets.items():
            value = self.settings.get(key, DEFAULT_SETTINGS.get(key))
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                index = widget.findData(value)
                widget.setCurrentIndex(index if index >= 0 else 0)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value or ""))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
        for profile_id, widgets in self.hotkey_widgets.items():
            profile = self.hotkey_profiles[profile_id]
            widgets["enabled"].setChecked(bool(profile.get("enabled")))
            widgets["trigger"].setCurrentText(str(profile.get("trigger", "")))

    def refresh_all(self):
        self.settings = load_settings(self.config_path, DEFAULT_SETTINGS)
        self.hotkey_profiles = normalize_hotkey_profiles(
            self.settings.get("hotkey_profiles"), self.settings.get("record_keys")
        )
        self._load_widgets_from_settings()
        self._apply_theme()
        self.refresh_status()
        self.refresh_startup_status()
        self.refresh_logs()

    def refresh_status(self):
        self.status = get_runtime_status(settings=self.settings, config_path=self.config_path)
        snapshot = build_settings_snapshot(self.settings)
        self.backend_status_label.setText("Running" if self.status.running else "Stopped")
        self.pid_label.setText(", ".join(str(pid) for pid in self.status.backend_pids) or "-")
        self.runtime_label.setText(self.status.runtime_mode)
        self.active_keys_label.setText(self.status.active_keys)
        self.pause_state_label.setText(self.status.pause_state)
        self.config_label.setText(Path(self.status.config_path).name)
        self.groq_label.setText(snapshot["providers"]["groq"])
        self.local_label.setText(snapshot["providers"]["local"])
        self.voice_edge_label.setText("enabled" if self.settings.get("enable_edge_selenium") else "disabled")
        self.voice_context_label.setText(
            "enabled" if self.settings.get("enable_transcript_context_memory") else "disabled"
        )
        self.voice_groq_label.setText(snapshot["providers"]["groq"])
        self._refresh_speaker_filter_status(snapshot["speaker_filter"])

    def _resolve_configured_path(self, value):
        path = Path(str(value or ""))
        if path.is_absolute():
            return path
        return REPO_ROOT / path

    def _read_json_file(self, path):
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _effective_speaker_filter_threshold(self, speaker_settings, profile_path):
        mode = speaker_settings["mode"]
        if mode == "custom":
            return float(speaker_settings["threshold"])
        profile = self._read_json_file(profile_path)
        thresholds = profile.get("thresholds") if isinstance(profile, dict) else None
        if isinstance(thresholds, dict) and mode in thresholds:
            try:
                return float(thresholds[mode])
            except Exception:
                pass
        return float(speaker_settings["threshold"])

    def _refresh_speaker_filter_status(self, speaker_settings):
        enabled = bool(speaker_settings["enabled"])
        profile_path = self._resolve_configured_path(speaker_settings["profile_path"])
        profile_loaded = profile_path.exists()
        if not enabled:
            self.speaker_filter_profile_status_label.setText("disabled")
        else:
            self.speaker_filter_profile_status_label.setText(
                "loaded" if profile_loaded else "missing"
            )

        threshold = self._effective_speaker_filter_threshold(
            speaker_settings, profile_path
        )
        self.speaker_filter_threshold_status_label.setText(
            f"{speaker_settings['mode']} / {threshold:.2f}"
        )

        status = self._read_json_file(self.speaker_filter_status_path)
        decision = str(status.get("decision") or "-")
        accepted = status.get("accepted_seconds")
        rejected = status.get("rejected_seconds")
        self.speaker_filter_last_decision_label.setText(decision)
        if accepted is None or rejected is None:
            self.speaker_filter_last_duration_label.setText("-")
        else:
            self.speaker_filter_last_duration_label.setText(
                f"accepted {float(accepted):.2f}s / rejected {float(rejected):.2f}s"
            )

    def save_hotkeys(self):
        self.settings = apply_settings_values(
            self.settings,
            {"hotkey_profiles": self._collect_hotkey_profiles()},
        )
        self.hotkey_profiles = self.settings["hotkey_profiles"]
        save_settings(self.config_path, self.settings)
        self.refresh_status()

    def set_theme_mode(self, *_):
        self.settings = apply_settings_values(
            self.settings,
            {"ui_theme": self.theme_combo.currentData()},
        )
        save_settings(self.config_path, self.settings)
        self._apply_theme()

    def set_minimize_to_tray(self, *_):
        self.settings = apply_settings_values(
            self.settings,
            {"minimize_to_tray": self.minimize_to_tray_check.isChecked()},
        )
        save_settings(self.config_path, self.settings)

    def reset_hotkeys(self):
        self.hotkey_profiles = normalize_hotkey_profiles(None, "f24,ctrl_r")
        self.settings = apply_settings_values(self.settings, {"hotkey_profiles": self.hotkey_profiles})
        self._load_widgets_from_settings()

    def save_transcription_settings(self):
        self.settings = apply_settings_values(self.settings, self._collect_settings_values())
        self.hotkey_profiles = self.settings["hotkey_profiles"]
        save_settings(self.config_path, self.settings)
        self.refresh_status()

    def save_and_restart(self):
        self.save_transcription_settings()
        self.restart_backend()

    def start_backend(self):
        self.save_transcription_settings()
        try:
            start_backend(self.settings)
        except Exception as exc:
            QMessageBox.warning(self, "Backend Start Failed", str(exc))
        self.refresh_status()

    def stop_backend(self):
        try:
            stop_backend()
        except Exception as exc:
            QMessageBox.warning(self, "Backend Stop Failed", str(exc))
        self.refresh_status()

    def restart_backend(self):
        self.save_transcription_settings()
        try:
            restart_backend(self.settings)
        except Exception as exc:
            QMessageBox.warning(self, "Backend Restart Failed", str(exc))
        self.refresh_status()

    def toggle_pause(self):
        pause_flag_path = get_pause_flag_path(__file__)
        current_paused = read_pause_state(pause_flag_path) == "PAUSED"
        try:
            toggle_pause_state(pause_flag_path, current_paused)
        except TypeError:
            set_pause_state(pause_flag_path, not current_paused)
        except Exception as exc:
            QMessageBox.warning(self, "Pause Toggle Failed", str(exc))
        self.refresh_status()

    def refresh_startup_status(self):
        self.launch_command_label.setText(
            self.status.last_launch_command if self.status else f"python wkey\\{BACKEND_SCRIPT_NAME}"
        )
        self.task_status_label.setText(self._scheduled_task_summary())

    def _scheduled_task_summary(self):
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-ScheduledTask -TaskName Whisper -ErrorAction SilentlyContinue | "
                    "Select-Object TaskName,State | ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception as exc:
            return f"unavailable: {exc}"
        if result.returncode != 0 or not result.stdout.strip():
            return "not found"
        return result.stdout.strip()

    def run_key_diagnostic(self):
        seconds = int(self.diagnostic_seconds.value())
        manifest = REPO_ROOT / "native" / "wkey-broker" / "Cargo.toml"
        command = [
            "cargo",
            "run",
            "--manifest-path",
            str(manifest),
            "--",
            "--diagnose-keys",
            "--seconds",
            str(seconds),
        ]
        self.diagnostic_output.setPlainText("Running diagnostic...")

        def _worker():
            try:
                result = subprocess.run(
                    command,
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=seconds + 90,
                    check=False,
                )
                output = "\n".join(
                    part for part in (result.stdout.strip(), result.stderr.strip()) if part
                )
                self.diagnostic_finished.emit(output or f"exit code {result.returncode}")
            except Exception as exc:
                self.diagnostic_finished.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _diagnostic_complete(self, output: str):
        summary_lines = []
        for line in output.splitlines():
            lower = line.lower()
            if any(
                token in lower
                for token in (
                    "candidates",
                    "quick",
                    "interrupt",
                    "cancel",
                    "trigger",
                    "decisions",
                    "diagnostic",
                )
            ):
                summary_lines.append(line)
        self.diagnostic_output.setPlainText("\n".join(summary_lines) or output)

    def refresh_logs(self):
        log_paths = [
            REPO_ROOT / "whisper_keyboard.log",
            REPO_ROOT / "voice_commands.log",
            REPO_ROOT / "wkey_errors.log",
            REPO_ROOT / "wkey" / "wkey_errors.log",
        ]
        sections = []
        for path in log_paths:
            if not path.exists():
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            tail = "\n".join(lines[-80:])
            sections.append(f"== {path.name} ==\n{tail}")
        self.logs_output.setPlainText("\n\n".join(sections) or "No log files found.")

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon.fromTheme("audio-headset")
        if icon.isNull():
            icon = self.windowIcon()
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Whisper Keyboard")

        tray_menu = QMenu(self)
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        pause_action = QAction("Pause / Resume", self)
        pause_action.triggered.connect(self.toggle_pause)
        tray_menu.addAction(pause_action)

        restart_action = QAction("Restart Backend", self)
        restart_action.triggered.connect(self.restart_backend)
        tray_menu.addAction(restart_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_application(self):
        if self.tray_icon is not None:
            self.tray_icon.hide()
        QApplication.quit()

    def _should_minimize_to_tray(self):
        return bool(self.settings.get("minimize_to_tray", True)) and self.tray_icon is not None

    def changeEvent(self, event):
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self._should_minimize_to_tray()
        ):
            QTimer.singleShot(0, self.hide)

    def closeEvent(self, event):
        if self._should_minimize_to_tray():
            event.ignore()
            self.hide()
            if self.tray_icon is not None:
                self.tray_icon.showMessage(
                    "Whisper Keyboard",
                    "Still running in tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    1500,
                )
            return
        super().closeEvent(event)


def main():
    app = QApplication([])
    window = WhisperControlCenter()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
