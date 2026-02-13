import sys
import os
import time
import threading
from datetime import datetime, timedelta
import json
import subprocess
from settings_manager import (
    load_settings as settings_load,
    save_settings as settings_save,
    DEFAULT_SETTINGS as TRANSCRIPTION_DEFAULTS,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QSystemTrayIcon, QMenu, QFrame, QGridLayout, QSizePolicy,
    QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import win32con
    import win32gui
except ImportError:
    win32con = None
    win32gui = None

class VoicePauseController(QMainWindow):
    def __init__(self):
        super().__init__()
        
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        self.setWindowTitle("Voice Recognition Control")
        self.setMinimumSize(400, 400)
        self.resize(600, 600)
        
        self.is_paused = False
        self.pause_start_time = None
        self.total_pause_time = 0
        self.session_start_time = datetime.now()
        self.is_dark_theme = True
        self.timed_pause_end = None
        self.last_action = None

        
        self.last_time_check = datetime.now()
        self.time_jump_threshold = timedelta(seconds=120)

        self.config_file = "voice_pause_config.json"
        self.transcription_config_file = "transcription_config.json"
        self._loading_transcription_settings = False
        
        self.setup_gui()
        self.load_config()
        self.load_transcription_settings()
        self.setup_tray()
        self.setup_hotkeys()
        self.load_theme()
        self.start_status_thread()

        # Timer for countdown updates
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)
        
        # Test buttons commented out but kept for future use
        # self.add_test_buttons()

    def simulate_time_jump(self, minutes=5):
        """Simulate a time jump for testing purposes"""
        self.last_time_check = datetime.now() - timedelta(minutes=minutes)
        print(f"Simulated time jump of {minutes} minutes")
        self.error_label.setText(f"Simulated {minutes}-min time jump for testing")
        
    # def add_test_buttons(self):
    #     """Add test buttons to the GUI"""
    #     test_frame = QFrame()
    #     test_layout = QHBoxLayout(test_frame)
    #     test_layout.setContentsMargins(0, 0, 0, 0)
        
    #     btn_2min = QPushButton("Test 2-min Jump")
    #     btn_2min.clicked.connect(lambda: self.simulate_time_jump(2))
    #     btn_2min.setToolTip("Simulate 2-minute time jump for testing")
    #     test_layout.addWidget(btn_2min)
        
    #     btn_5min = QPushButton("Test 5-min Jump")
    #     btn_5min.clicked.connect(lambda: self.simulate_time_jump(5))
    #     btn_5min.setToolTip("Simulate 5-minute time jump for testing")
    #     test_layout.addWidget(btn_5min)
        
    #     self.main_layout.addWidget(test_frame)

    def setup_gui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(12)

        # Header section (empty for now, title moved to status panel)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        self.main_layout.addLayout(header_layout)

        # Content layout
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(12)
        self.main_layout.addLayout(self.content_layout)

        # Left panel: Status
        self.status_panel = QFrame()
        self.status_panel.setObjectName("statusPanel")
        self.status_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        status_layout = QVBoxLayout(self.status_panel)
        status_layout.setContentsMargins(10, 10, 10, 10)
        status_layout.setSpacing(8)
        
        # Add title to status panel
        title_label = QLabel("Voice Control")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setMinimumHeight(40)
        title_label.setToolTip("Voice Recognition Control Panel")
        status_layout.addWidget(title_label)
        
        # Add theme toggle button
        self.theme_button = QPushButton("Switch to Light Theme")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.theme_button.setFont(QFont("Segoe UI", 9))
        self.theme_button.setMinimumHeight(32)
        self.theme_button.setToolTip("Toggle between dark and light themes")
        status_layout.addWidget(self.theme_button)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        status_layout.addWidget(separator)

        self.status_label = QLabel("🟢 ACTIVE")
        self.status_label.setObjectName("statusIndicator")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        self.status_label.setMinimumHeight(30)
        self.status_label.setToolTip("Current voice recognition status")
        status_layout.addWidget(self.status_label)

        timer_grid = QGridLayout()
        timer_grid.setSpacing(6)
        
        session_icon = QLabel("⏱️")
        session_icon.setObjectName("timerIcon")
        session_icon.setMinimumWidth(20)
        timer_grid.addWidget(session_icon, 0, 0)
        
        session_title = QLabel("Session Time")
        session_title.setObjectName("timerTitle")
        session_title.setFont(QFont("Segoe UI", 10))
        session_title.setToolTip("Time since application started")
        timer_grid.addWidget(session_title, 0, 1)
        
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerValue")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.timer_label.setFont(QFont("Segoe UI", 10))
        timer_grid.addWidget(self.timer_label, 0, 2)

        pause_icon = QLabel("⏸️")
        pause_icon.setObjectName("timerIcon")
        pause_icon.setMinimumWidth(20)
        timer_grid.addWidget(pause_icon, 1, 0)
        
        pause_title = QLabel("Pause Time")
        pause_title.setObjectName("timerTitle")
        pause_title.setFont(QFont("Segoe UI", 10))
        pause_title.setToolTip("Total time voice recognition was paused")
        timer_grid.addWidget(pause_title, 1, 1)
        
        self.pause_timer_label = QLabel("00:00:00")
        self.pause_timer_label.setObjectName("timerValue")
        self.pause_timer_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pause_timer_label.setFont(QFont("Segoe UI", 10))
        timer_grid.addWidget(self.pause_timer_label, 1, 2)

        countdown_icon = QLabel("⏲️")
        countdown_icon.setObjectName("timerIcon")
        countdown_icon.setMinimumWidth(20)
        timer_grid.addWidget(countdown_icon, 2, 0)
        
        countdown_title = QLabel("Countdown")
        countdown_title.setObjectName("timerTitle")
        countdown_title.setFont(QFont("Segoe UI", 10))
        countdown_title.setToolTip("Remaining time for timed pause")
        timer_grid.addWidget(countdown_title, 2, 1)
        
        self.countdown_label = QLabel("N/A")
        self.countdown_label.setObjectName("timerValue")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.countdown_label.setFont(QFont("Segoe UI", 10))
        timer_grid.addWidget(self.countdown_label, 2, 2)

        last_action_icon = QLabel("ℹ️")
        last_action_icon.setObjectName("timerIcon")
        last_action_icon.setMinimumWidth(20)
        timer_grid.addWidget(last_action_icon, 3, 0)
        
        last_action_title = QLabel("Last Action")
        last_action_title.setObjectName("timerTitle")
        last_action_title.setFont(QFont("Segoe UI", 10))
        last_action_title.setToolTip("Timestamp of last pause/resume")
        timer_grid.addWidget(last_action_title, 3, 1)
        
        self.last_action_label = QLabel("N/A")
        self.last_action_label.setObjectName("timerValue")
        self.last_action_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.last_action_label.setFont(QFont("Segoe UI", 10))
        timer_grid.addWidget(self.last_action_label, 3, 2)

        timer_grid.setColumnStretch(1, 1)
        status_layout.addLayout(timer_grid)
        status_layout.addStretch()

        # Right panel: Controls
        self.controls_panel = QFrame()
        self.controls_panel.setObjectName("controlsPanel")
        controls_layout = QVBoxLayout(self.controls_panel)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(10)

        self.main_button = QPushButton("PAUSE VOICE RECOGNITION")
        self.main_button.setObjectName("mainButton")
        self.main_button.clicked.connect(self.toggle_pause)
        self.main_button.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        self.main_button.setMinimumHeight(44)
        self.main_button.setMinimumWidth(160)
        self.main_button.setToolTip("Pause or resume voice recognition (Ctrl+Shift+P)")
        controls_layout.addWidget(self.main_button)

        quick_actions_label = QLabel("Quick Actions")
        quick_actions_label.setObjectName("sectionLabel")
        quick_actions_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        quick_actions_label.setMinimumHeight(20)
        quick_actions_label.setToolTip("Timed pause options")
        controls_layout.addWidget(quick_actions_label)
        
        quick_button_layout = QHBoxLayout()
        quick_button_layout.setSpacing(8)
        
        self.pause_15min_button = QPushButton("15min Pause")
        self.pause_15min_button.setObjectName("pause15MinButton")
        self.pause_15min_button.clicked.connect(lambda: self.timed_pause(15))
        self.pause_15min_button.setFont(QFont("Segoe UI", 10))
        self.pause_15min_button.setMinimumHeight(40)
        self.pause_15min_button.setMinimumWidth(90)
        self.pause_15min_button.setToolTip("Pause for 15 minutes (Ctrl+Shift+1)")
        quick_button_layout.addWidget(self.pause_15min_button)

        self.pause_1hr_button = QPushButton("1hr Pause")
        self.pause_1hr_button.setObjectName("pause1HrButton")
        self.pause_1hr_button.clicked.connect(lambda: self.timed_pause(60))
        self.pause_1hr_button.setFont(QFont("Segoe UI", 10))
        self.pause_1hr_button.setMinimumHeight(40)
        self.pause_1hr_button.setMinimumWidth(90)
        self.pause_1hr_button.setToolTip("Pause for 1 hour (Ctrl+Shift+2)")
        quick_button_layout.addWidget(self.pause_1hr_button)

        controls_layout.addLayout(quick_button_layout)

        settings_label = QLabel("Settings")
        settings_label.setObjectName("sectionLabel")
        settings_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        settings_label.setMinimumHeight(20)
        settings_label.setToolTip("Application settings")
        controls_layout.addWidget(settings_label)

        self.use_groq_cb = QCheckBox("Use Groq API (fallback)")
        self.use_groq_cb.setObjectName("settingsCheckbox")
        self.use_groq_cb.setFont(QFont("Segoe UI", 10))
        self.use_groq_cb.setToolTip("Use Groq API for transcription when enabled")
        self.use_groq_cb.stateChanged.connect(self.save_transcription_settings)
        controls_layout.addWidget(self.use_groq_cb)

        self.use_gpu_cb = QCheckBox("Use local GPU model")
        self.use_gpu_cb.setObjectName("settingsCheckbox")
        self.use_gpu_cb.setFont(QFont("Segoe UI", 10))
        self.use_gpu_cb.setToolTip("Use local GPU model when available")
        self.use_gpu_cb.stateChanged.connect(self.save_transcription_settings)
        controls_layout.addWidget(self.use_gpu_cb)

        self.use_cpu_cb = QCheckBox("Use local CPU fallback")
        self.use_cpu_cb.setObjectName("settingsCheckbox")
        self.use_cpu_cb.setFont(QFont("Segoe UI", 10))
        self.use_cpu_cb.setToolTip("Allow CPU fallback when GPU is unavailable")
        self.use_cpu_cb.stateChanged.connect(self.save_transcription_settings)
        controls_layout.addWidget(self.use_cpu_cb)

        self.max_retries_input = QLineEdit()
        self.max_retries_input.setObjectName("settingsInput")
        self.max_retries_input.setPlaceholderText("Groq max retries")
        self.max_retries_input.setFont(QFont("Segoe UI", 10))
        self.max_retries_input.setToolTip("Number of retries for Groq transcription")
        self.max_retries_input.editingFinished.connect(self.save_transcription_settings)
        controls_layout.addWidget(self.max_retries_input)

        self.run_faster_whisper_btn = QPushButton("Run Faster Whisper")
        self.run_faster_whisper_btn.setObjectName("fasterWhisperButton")
        self.run_faster_whisper_btn.setAccessibleName("runFasterWhisperBtn")
        self.run_faster_whisper_btn.clicked.connect(self.run_faster_whisper)
        self.run_faster_whisper_btn.setFont(QFont("Segoe UI", 10))
        self.run_faster_whisper_btn.setMinimumHeight(40)
        self.run_faster_whisper_btn.setMinimumWidth(140)
        self.run_faster_whisper_btn.setToolTip("Launch Faster Whisper script")
        controls_layout.addWidget(self.run_faster_whisper_btn)

        # Add test VB Matrix button
        self.test_voicemeeter_button = QPushButton("Test VB Matrix Restart")
        self.test_voicemeeter_button.setObjectName("testButton")
        self.test_voicemeeter_button.clicked.connect(self.restart_voicemeeter)
        self.test_voicemeeter_button.setFont(QFont("Segoe UI", 10))
        self.test_voicemeeter_button.setMinimumHeight(40)
        self.test_voicemeeter_button.setToolTip("Manually test VB Matrix restart")
        controls_layout.addWidget(self.test_voicemeeter_button)

        self.auto_unpause_check = QCheckBox("Auto-unpause after timed pause")
        self.auto_unpause_check.setObjectName("settingsCheckbox")
        self.auto_unpause_check.setChecked(True)
        self.auto_unpause_check.setFont(QFont("Segoe UI", 10))
        self.auto_unpause_check.setToolTip("Automatically resume after timed pause")
        self.auto_unpause_check.stateChanged.connect(self.save_config)
        controls_layout.addWidget(self.auto_unpause_check)

        self.minimize_to_tray_check = QCheckBox("Minimize to system tray")
        self.minimize_to_tray_check.setObjectName("settingsCheckbox")
        self.minimize_to_tray_check.setFont(QFont("Segoe UI", 10))
        self.minimize_to_tray_check.setToolTip("Minimize to tray instead of closing")
        self.minimize_to_tray_check.stateChanged.connect(self.save_config)
        controls_layout.addWidget(self.minimize_to_tray_check)


        hotkey_label = QLabel("Hotkeys: Ctrl+Shift+P (Toggle), Ctrl+Shift+1 (15min), Ctrl+Shift+2 (1hr)")
        hotkey_label.setObjectName("hotkeyLabel")
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_label.setFont(QFont("Segoe UI", 9))
        hotkey_label.setMinimumHeight(20)
        hotkey_label.setToolTip("Keyboard shortcuts for quick actions")
        controls_layout.addWidget(hotkey_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setFont(QFont("Segoe UI", 9))
        self.error_label.setMinimumHeight(20)
        self.error_label.setWordWrap(True)
        controls_layout.addWidget(self.error_label)

        controls_layout.addStretch()

        # Initially add panels to horizontal layout
        self.content_layout.addWidget(self.status_panel, 1)
        self.content_layout.addWidget(self.controls_panel, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() < 500:
            if isinstance(self.content_layout, QHBoxLayout):
                self.content_layout.removeWidget(self.status_panel)
                self.content_layout.removeWidget(self.controls_panel)
                self.content_layout = QVBoxLayout()
                self.content_layout.setSpacing(12)
                self.content_layout.addWidget(self.status_panel)
                self.content_layout.addWidget(self.controls_panel)
                self.main_layout.replaceWidget(self.main_layout.itemAt(1).widget(), QWidget())
                self.main_layout.insertLayout(1, self.content_layout)
        else:
            if isinstance(self.content_layout, QVBoxLayout):
                self.content_layout.removeWidget(self.status_panel)
                self.content_layout.removeWidget(self.controls_panel)
                self.content_layout = QHBoxLayout()
                self.content_layout.setSpacing(12)
                self.content_layout.addWidget(self.status_panel, 1)
                self.content_layout.addWidget(self.controls_panel, 1)
                self.main_layout.replaceWidget(self.main_layout.itemAt(1).widget(), QWidget())
                self.main_layout.insertLayout(1, self.content_layout)

    def update_countdown(self):
        if self.timed_pause_end and self.is_paused:
            remaining = self.timed_pause_end - datetime.now()
            if remaining.total_seconds() > 0:
                self.countdown_label.setText(str(timedelta(seconds=int(remaining.total_seconds()))).split('.')[0])
            else:
                self.countdown_label.setText("N/A")
                self.timed_pause_end = None
        else:
            self.countdown_label.setText("N/A")

    def load_theme(self):
        theme_file = "dark_theme.qss" if self.is_dark_theme else "light_theme.qss"
        try:
            if os.path.exists(theme_file):
                with open(theme_file, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                    self.setStyleSheet(stylesheet)
                    print(f"Loaded theme: {theme_file}")
            else:
                print(f"Theme file {theme_file} not found.")
                self.setStyleSheet("")
        except Exception as e:
            print(f"Error loading theme file {theme_file}: {e}")
            self.setStyleSheet("")

    def update_status_colors(self):
        if self.is_paused:
            self.status_label.setText("🔴 PAUSED")
        else:
            self.status_label.setText("🟢 ACTIVE")

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.theme_button.setText("Switch to Light Theme" if self.is_dark_theme else "Switch to Dark Theme")
        self.load_theme()
        self.save_config()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        toggle_action = QAction("Toggle Pause", self)
        toggle_action.triggered.connect(self.toggle_pause)
        tray_menu.addAction(toggle_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setIcon(QIcon.fromTheme("audio-headset"))
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_application(self):
        self.save_config()
        self.tray_icon.hide()
        QApplication.quit()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.total_pause_time = config.get('total_pause_time', 0)
                    self.is_dark_theme = config.get('is_dark_theme', True)
                    self.auto_unpause_check.setChecked(config.get('auto_unpause', True))
                    self.minimize_to_tray_check.setChecked(config.get('minimize_to_tray', False))
                print("Config loaded successfully")
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        try:
            config = {
                'total_pause_time': self.total_pause_time,
                'last_session': datetime.now().isoformat(),
                'is_dark_theme': self.is_dark_theme,
                'auto_unpause': self.auto_unpause_check.isChecked(),
                'minimize_to_tray': self.minimize_to_tray_check.isChecked()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            print("Config saved successfully")
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_transcription_settings(self):
        try:
            self._loading_transcription_settings = True
            config = settings_load(
                self.transcription_config_file, TRANSCRIPTION_DEFAULTS
            )
            self.use_gpu_cb.setChecked(config.get("use_local_gpu", True))
            self.use_cpu_cb.setChecked(config.get("use_local_cpu", True))
            self.use_groq_cb.setChecked(config.get("fallback_to_groq", True))
            self.max_retries_input.setText(str(config.get("max_retries", 3)))
        except Exception as e:
            print(f"Error loading transcription settings: {e}")
        finally:
            self._loading_transcription_settings = False

    def save_transcription_settings(self):
        if self._loading_transcription_settings:
            return
        try:
            max_retries_text = self.max_retries_input.text().strip()
            try:
                max_retries = max(1, int(max_retries_text)) if max_retries_text else 3
            except Exception:
                max_retries = 3
                self.max_retries_input.setText(str(max_retries))

            config = {
                "use_local_gpu": self.use_gpu_cb.isChecked(),
                "use_local_cpu": self.use_cpu_cb.isChecked(),
                "fallback_to_groq": self.use_groq_cb.isChecked(),
                "max_retries": max_retries,
            }
            settings_save(self.transcription_config_file, config)
        except Exception as e:
            print(f"Error saving transcription settings: {e}")

    def toggle_pause(self):
        if self.is_paused:
            self.unpause_voice_recognition()
        else:
            self.pause_voice_recognition()

    def pause_voice_recognition(self):
        try:
            self.set_global_pause_flag(True)
            self.is_paused = True
            self.pause_start_time = time.time()
            self.update_status_colors()
            self.main_button.setText("RESUME VOICE RECOGNITION")
            self.last_action = f"Paused at {datetime.now().strftime('%H:%M:%S')}"
            self.last_action_label.setText(self.last_action)
            self.error_label.setText("")
            print("Voice recognition PAUSED")
        except Exception as e:
            self.error_label.setText(f"Error pausing: {str(e)}")
            print(f"Error pausing voice recognition: {e}")

    def unpause_voice_recognition(self):
        try:
            self.set_global_pause_flag(False)
            if self.pause_start_time:
                pause_duration = time.time() - self.pause_start_time
                self.total_pause_time += pause_duration
                self.pause_start_time = None
            self.is_paused = False
            self.timed_pause_end = None
            self.update_status_colors()
            self.main_button.setText("PAUSE VOICE RECOGNITION")
            self.last_action = f"Resumed at {datetime.now().strftime('%H:%M:%S')}"
            self.last_action_label.setText(self.last_action)
            self.error_label.setText("")
            print("Voice recognition RESUMED")
        except Exception as e:
            self.error_label.setText(f"Error resuming: {str(e)}")
            print(f"Error unpausing voice recognition: {e}")

    def timed_pause(self, minutes):
        try:
            self.pause_voice_recognition()
            self.timed_pause_end = datetime.now() + timedelta(minutes=minutes)
            if self.auto_unpause_check.isChecked():
                def auto_unpause():
                    time.sleep(minutes * 60)
                    if self.is_paused and self.timed_pause_end and datetime.now() >= self.timed_pause_end:
                        self.unpause_voice_recognition()
                threading.Thread(target=auto_unpause, daemon=True).start()
                print(f"Auto-unpause scheduled for {minutes} minutes")
        except Exception as e:
            self.error_label.setText(f"Error setting timed pause: {str(e)}")
            print(f"Error in timed pause: {e}")

    def set_global_pause_flag(self, paused):
        try:
            with open("voice_pause_flag.txt", "w") as f:
                f.write("PAUSED" if paused else "ACTIVE")
        except Exception as e:
            self.error_label.setText(f"Error setting flag: {str(e)}")
            print(f"Error setting pause flag: {e}")

    def restart_voicemeeter(self):
        try:
            # Get current volume before restarting
            
            # Restart VB Matrix
            vb_matrix_path = r"C:\Program Files (x86)\VB\Voicemeeter\VBAudioMatrix_x64.exe"
            subprocess.Popen([vb_matrix_path, "-r"], 
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            
            # Wait for VB Matrix to restart
            time.sleep(3)
            
            # Restore volume
            return True
        except Exception as e:
            error_msg = f"Error in restart_voicemeeter: {str(e)}"
            print(error_msg)
            self.error_label.setText(error_msg)
            return False
    
    def start_status_thread(self):
        def update_status():
            while True:
                try:
                    session_time = datetime.now() - self.session_start_time
                    session_str = str(session_time).split('.')[0]
                    self.timer_label.setText(f"{session_str}")

                    current_pause_time = self.total_pause_time
                    if self.is_paused and self.pause_start_time:
                        current_pause_time += time.time() - self.pause_start_time
                    pause_str = time.strftime('%H:%M:%S', time.gmtime(current_pause_time))
                    self.pause_timer_label.setText(f"{pause_str}")
                    
                    current_time = datetime.now()
                    time_difference = current_time - self.last_time_check

                    if time_difference > self.time_jump_threshold:
                        print(f"Detected time jump of {time_difference}. Processing wake-up actions...")
                        
                        # Restart VB Matrix when time jump is detected
                        voicemeeter_success = self.restart_voicemeeter()
                        
                        # Resume voice recognition if it was paused
                        if self.is_paused:
                            print("Resuming voice recognition after time jump")
                            self.unpause_voice_recognition()
                            self.session_start_time = current_time
                        
                        # Update status message based on success
                        if voicemeeter_success:
                            status_msg = f"Wake detected - All systems restarted at {datetime.now().strftime('%H:%M:%S')}"
                        else:
                            status_msg = f"Wake detected - Voice resumed (VB Matrix issue) at {datetime.now().strftime('%H:%M:%S')}"
                        
                        self.last_action = status_msg
                        self.last_action_label.setText(status_msg)

                    self.last_time_check = current_time
                    time.sleep(1)
                except Exception as e:
                    self.error_label.setText(f"Status update error: {str(e)}")
                    print(f"Error updating status: {e}")
                    time.sleep(5)

        threading.Thread(target=update_status, daemon=True).start()

    # Optional: Add a manual test button to your GUI setup
    def add_test_button_to_gui(self):
        """Add this to your setup_gui method if you want a manual test button"""
        self.test_voicemeeter_button = QPushButton("Test VB Matrix Restart")
        self.test_voicemeeter_button.setObjectName("testButton")
        self.test_voicemeeter_button.clicked.connect(self.restart_voicemeeter)
        self.test_voicemeeter_button.setFont(QFont("Segoe UI", 10))
        self.test_voicemeeter_button.setMinimumHeight(40)
        self.test_voicemeeter_button.setToolTip("Manually test VB Matrix restart")
        # Add this to your controls_layout where appropriate
        # controls_layout.addWidget(self.test_voicemeeter_button)
        
    def run_faster_whisper(self):
        try:
            python_path = "c:/Windows_software/openai whisper/openai/Scripts/python.exe"
            script_path = "c:/Windows_software/openai whisper/whisper-keyboard/wkey/faster_whisper_Mother_of_all_wkey.py"
            os.chdir(os.path.dirname(script_path))
            subprocess.Popen([python_path, script_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.error_label.setText("Faster Whisper started")
            print(f"Started Faster Whisper at {script_path}")
        except Exception as e:
            self.error_label.setText(f"Error starting Faster Whisper: {str(e)}")
            print(f"Error starting Faster Whisper: {e}")

    def setup_hotkeys(self):
        if keyboard:
            keyboard.add_hotkey('ctrl+shift+p', self.toggle_pause)
        else:
            print("keyboard library not installed. Hotkey functionality disabled.")
            self.error_label.setText("Hotkey support disabled: keyboard library missing")

    def closeEvent(self, event):
        if self.minimize_to_tray_check.isChecked():
            event.ignore()
            self.hide()
        else:
            self.save_config()
            self.tray_icon.hide()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoicePauseController()
    window.show()
    sys.exit(app.exec())
