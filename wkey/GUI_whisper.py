import sys
import os
import time
import threading
from datetime import datetime
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QSystemTrayIcon, QMenu, QFrame, QGridLayout, QSizePolicy,
    QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction

try:
    import keyboard
except ImportError:
    keyboard = None

class VoicePauseController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Recognition Control")
        self.setMinimumSize(450, 400)
        self.resize(450, 400)
        
        # State variables
        self.is_paused = False
        self.pause_start_time = None
        self.total_pause_time = 0
        self.session_start_time = datetime.now()
        self.is_dark_theme = True  # Default to dark theme

        # Configuration file
        self.config_file = "voice_pause_config.json"
        self.load_config()

        # Setup GUI
        self.setup_gui()

        # Setup system tray
        self.setup_tray()

        # Setup hotkeys
        self.setup_hotkeys()

        # Load theme
        self.load_theme()

        # Start status update thread
        self.start_status_thread()

    def setup_gui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Header section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        
        # Title
        title_label = QLabel("Voice Recognition Control")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Manage your voice recognition system")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle_label)
        
        main_layout.addLayout(header_layout)

        # Status card
        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 20, 20, 20)
        status_layout.setSpacing(12)

        # Status indicator
        self.status_label = QLabel("🟢 ACTIVE")
        self.status_label.setObjectName("statusIndicator")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)

        # Timer grid
        timer_grid = QGridLayout()
        timer_grid.setSpacing(16)
        
        # Session time
        session_icon = QLabel("⏱️")
        session_icon.setObjectName("timerIcon")
        timer_grid.addWidget(session_icon, 0, 0)
        
        session_title = QLabel("Session Time")
        session_title.setObjectName("timerTitle")
        timer_grid.addWidget(session_title, 0, 1)
        
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerValue")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        timer_grid.addWidget(self.timer_label, 0, 2)

        # Pause time
        pause_icon = QLabel("⏸️")
        pause_icon.setObjectName("timerIcon")
        timer_grid.addWidget(pause_icon, 1, 0)
        
        pause_title = QLabel("Pause Time")
        pause_title.setObjectName("timerTitle")
        timer_grid.addWidget(pause_title, 1, 1)
        
        self.pause_timer_label = QLabel("00:00:00")
        self.pause_timer_label.setObjectName("timerValue")
        self.pause_timer_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        timer_grid.addWidget(self.pause_timer_label, 1, 2)

        # Set column stretch
        timer_grid.setColumnStretch(1, 1)
        
        status_layout.addLayout(timer_grid)
        main_layout.addWidget(status_card)

        # Controls section
        controls_frame = QFrame()
        controls_frame.setObjectName("controlsFrame")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(20, 20, 20, 20)
        controls_layout.setSpacing(16)

        # Main control button
        self.main_button = QPushButton("PAUSE VOICE RECOGNITION")
        self.main_button.setObjectName("primaryButton")
        self.main_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.main_button.setMinimumHeight(48)
        self.main_button.clicked.connect(self.toggle_pause)
        controls_layout.addWidget(self.main_button)

        # Quick actions
        quick_actions_label = QLabel("Quick Actions")
        quick_actions_label.setObjectName("sectionLabel")
        controls_layout.addWidget(quick_actions_label)
        
        quick_button_layout = QHBoxLayout()
        quick_button_layout.setSpacing(12)
        
        self.pause_15min_button = QPushButton("Pause 15min")
        self.pause_15min_button.setObjectName("secondaryButton")
        self.pause_15min_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pause_15min_button.setMinimumHeight(36)
        self.pause_15min_button.clicked.connect(lambda: self.timed_pause(15))
        quick_button_layout.addWidget(self.pause_15min_button)

        self.pause_1hr_button = QPushButton("Pause 1hr")
        self.pause_1hr_button.setObjectName("secondaryButton")
        self.pause_1hr_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pause_1hr_button.setMinimumHeight(36)
        self.pause_1hr_button.clicked.connect(lambda: self.timed_pause(60))
        quick_button_layout.addWidget(self.pause_1hr_button)

        controls_layout.addLayout(quick_button_layout)
        main_layout.addWidget(controls_frame)

        # Settings section
        settings_frame = QFrame()
        settings_frame.setObjectName("settingsFrame")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(16)

        settings_label = QLabel("Settings")
        settings_label.setObjectName("sectionLabel")
        settings_layout.addWidget(settings_label)

        # Settings checkboxes
        self.auto_unpause_check = QCheckBox("Auto-unpause after timed pause")
        self.auto_unpause_check.setObjectName("settingsCheckbox")
        self.auto_unpause_check.setChecked(True)
        settings_layout.addWidget(self.auto_unpause_check)

        self.minimize_to_tray_check = QCheckBox("Minimize to system tray")
        self.minimize_to_tray_check.setObjectName("settingsCheckbox")
        self.minimize_to_tray_check.setChecked(False)
        settings_layout.addWidget(self.minimize_to_tray_check)

        # Theme and hotkey section
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)
        
        self.theme_button = QPushButton("Switch to Light Theme")
        self.theme_button.setObjectName("tertiaryButton")
        self.theme_button.setMinimumHeight(32)
        self.theme_button.clicked.connect(self.toggle_theme)
        bottom_layout.addWidget(self.theme_button)
        
        # Add spacer
        bottom_layout.addItem(QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        settings_layout.addLayout(bottom_layout)

        # Hotkey info
        hotkey_label = QLabel("Hotkey: Ctrl+Shift+P")
        hotkey_label.setObjectName("hotkeyLabel")
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(hotkey_label)

        main_layout.addWidget(settings_frame)
        
        # Add stretch to push everything up
        main_layout.addStretch()

    def load_theme(self):
        """Load theme from QSS file"""
        theme_file = "dark_theme.qss" if self.is_dark_theme else "light_theme.qss"
        
        try:
            if os.path.exists(theme_file):
                with open(theme_file, 'r', encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
            else:
                # Fallback to basic theme if QSS file doesn't exist
                self.apply_fallback_theme()
        except Exception as e:
            print(f"Error loading theme file {theme_file}: {e}")
            self.apply_fallback_theme()
    
    def apply_fallback_theme(self):
        """Fallback theme if QSS files are not available"""
        if self.is_dark_theme:
            stylesheet = """
                QMainWindow {
                    background-color: #1E1E1E;
                    color: #CCCCCC;
                }
                
                #titleLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #FFFFFF;
                    margin: 0;
                }
                
                #subtitleLabel {
                    font-size: 12px;
                    color: #808080;
                    margin: 0;
                }
                
                #statusCard, #controlsFrame, #settingsFrame {
                    background-color: #252526;
                    border: 1px solid #3E3E42;
                    border-radius: 8px;
                }
                
                #statusIndicator {
                    font-size: 16px;
                    font-weight: bold;
                    color: #4EC9B0;
                }
                
                #primaryButton {
                    background-color: #0E639C;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 13px;
                }
                
                #primaryButton:hover {
                    background-color: #1177BB;
                }
                
                #primaryButton:pressed {
                    background-color: #0D5A8A;
                }
                
                #secondaryButton, #tertiaryButton {
                    background-color: #3C3C3C;
                    color: #CCCCCC;
                    border: 1px solid #5A5A5A;
                    border-radius: 4px;
                    font-size: 12px;
                }
                
                #secondaryButton:hover, #tertiaryButton:hover {
                    background-color: #464647;
                }
                
                #sectionLabel {
                    font-weight: bold;
                    font-size: 13px;
                    color: #CCCCCC;
                }
                
                #settingsCheckbox {
                    color: #CCCCCC;
                    font-size: 12px;
                }
                
                #hotkeyLabel {
                    color: #808080;
                    font-size: 11px;
                }
                
                #timerTitle {
                    color: #CCCCCC;
                    font-size: 12px;
                }
                
                #timerValue {
                    color: #4EC9B0;
                    font-size: 12px;
                    font-weight: bold;
                }
                
                #timerIcon {
                    font-size: 14px;
                }
            """
        else:
            stylesheet = """
                QMainWindow {
                    background-color: #FFFFFF;
                    color: #1E1E1E;
                }
                
                #titleLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #1E1E1E;
                    margin: 0;
                }
                
                #subtitleLabel {
                    font-size: 12px;
                    color: #6A6A6A;
                    margin: 0;
                }
                
                #statusCard, #controlsFrame, #settingsFrame {
                    background-color: #F8F8F8;
                    border: 1px solid #D1D1D1;
                    border-radius: 8px;
                }
                
                #statusIndicator {
                    font-size: 16px;
                    font-weight: bold;
                    color: #107C10;
                }
                
                #primaryButton {
                    background-color: #0078D4;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 13px;
                }
                
                #primaryButton:hover {
                    background-color: #106EBE;
                }
                
                #primaryButton:pressed {
                    background-color: #005A9E;
                }
                
                #secondaryButton, #tertiaryButton {
                    background-color: #FFFFFF;
                    color: #323130;
                    border: 1px solid #8A8886;
                    border-radius: 4px;
                    font-size: 12px;
                }
                
                #secondaryButton:hover, #tertiaryButton:hover {
                    background-color: #F3F2F1;
                }
                
                #sectionLabel {
                    font-weight: bold;
                    font-size: 13px;
                    color: #323130;
                }
                
                #settingsCheckbox {
                    color: #323130;
                    font-size: 12px;
                }
                
                #hotkeyLabel {
                    color: #6A6A6A;
                    font-size: 11px;
                }
                
                #timerTitle {
                    color: #323130;
                    font-size: 12px;
                }
                
                #timerValue {
                    color: #0078D4;
                    font-size: 12px;
                    font-weight: bold;
                }
                
                #timerIcon {
                    font-size: 14px;
                }
            """
        
        self.setStyleSheet(stylesheet)
        self.update_status_colors()

    def update_status_colors(self):
        """Update status indicator colors based on current state"""
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
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        try:
            config = {
                'total_pause_time': self.total_pause_time,
                'last_session': datetime.now().isoformat(),
                'is_dark_theme': self.is_dark_theme
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Error saving config: {e}")

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
            print("Voice recognition PAUSED")
        except Exception as e:
            print(f"Error pausing voice recognition: {e}")

    def unpause_voice_recognition(self):
        try:
            self.set_global_pause_flag(False)
            if self.pause_start_time:
                pause_duration = time.time() - self.pause_start_time
                self.total_pause_time += pause_duration
                self.pause_start_time = None
            self.is_paused = False
            self.update_status_colors()
            self.main_button.setText("PAUSE VOICE RECOGNITION")
            print("Voice recognition RESUMED")
        except Exception as e:
            print(f"Error unpausing voice recognition: {e}")

    def timed_pause(self, minutes):
        self.pause_voice_recognition()
        if self.auto_unpause_check.isChecked():
            def auto_unpause():
                time.sleep(minutes * 60)
                if self.is_paused:
                    self.unpause_voice_recognition()
            threading.Thread(target=auto_unpause, daemon=True).start()
            print(f"Auto-unpause scheduled for {minutes} minutes")

    def set_global_pause_flag(self, paused):
        try:
            with open("voice_pause_flag.txt", "w") as f:
                f.write("PAUSED" if paused else "ACTIVE")
        except Exception as e:
            print(f"Error setting pause flag: {e}")

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
                    time.sleep(1)
                except Exception as e:
                    print(f"Error updating status: {e}")
                    time.sleep(5)

        threading.Thread(target=update_status, daemon=True).start()

    def setup_hotkeys(self):
        if keyboard:
            keyboard.add_hotkey('ctrl+shift+p', self.toggle_pause)
            print("Hotkey Ctrl+Shift+P registered")
        else:
            print("keyboard library not installed. Hotkey functionality disabled.")

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