import sys
import os
import time
import threading
import json
import platform
from pathlib import Path
import traceback
from typing import Optional

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, 
    QLabel, QMessageBox, QSystemTrayIcon, QMenu, QHBoxLayout, 
    QCheckBox, QFrame, QTextEdit, QTabWidget,
    QGroupBox, QGridLayout, QSlider, QSpinBox, QComboBox
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRect, QSettings, QStandardPaths
)
from PyQt6.QtGui import (
    QIcon, QFont, QPixmap, QPainter, QColor, QAction, QPalette
)

# Windows-specific imports
try:
    import win32gui
    import win32con
    import win32api
    import win32process
    import psutil
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    print("Windows-specific modules not available. Some features may be limited.")

# Import the main functionality
try:
    from faster_whisper_Mother_of_all_wkey import main as whisper_main, cleanup, reset_all_states
except ImportError:
    print("Whisper module not found. Using mock functions for demo.")
    def whisper_main(): pass
    def cleanup(): pass
    def reset_all_states(): pass

class StatusIndicator(QLabel):
    """Simple status indicator"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._status = "stopped"
        
    def set_status(self, status: str):
        self._status = status
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self._status == "running":
            color = QColor(34, 197, 94)  # Green
        elif self._status == "error":
            color = QColor(239, 68, 68)  # Red
        else:
            color = QColor(100, 116, 139)  # Gray
            
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 12, 12)

class LogWidget(QTextEdit):
    """Simple log display widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(1000)
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.setFont(font)
        
    def add_log(self, message: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        self.append(f"[{timestamp}] {message}")
        self.ensureCursorVisible()

class SettingsWidget(QWidget):
    """Settings panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        startup_group = QGroupBox("Startup Settings")
        startup_layout = QVBoxLayout(startup_group)
        
        self.auto_start_cb = QCheckBox("Start automatically on system startup")
        self.auto_start_cb.toggled.connect(self.toggle_auto_start)
        self.start_minimized_cb = QCheckBox("Start minimized to system tray")
        
        startup_layout.addWidget(self.auto_start_cb)
        startup_layout.addWidget(self.start_minimized_cb)
        
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QGridLayout(perf_group)
        
        perf_layout.addWidget(QLabel("Idle timeout (minutes):"), 0, 0)
        self.idle_timeout_spin = QSpinBox()
        self.idle_timeout_spin.setRange(1, 480)
        self.idle_timeout_spin.setValue(120)
        perf_layout.addWidget(self.idle_timeout_spin, 0, 1)
        
        perf_layout.addWidget(QLabel("CPU Priority:"), 1, 0)
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Normal", "High", "Real-time"])
        self.priority_combo.setCurrentText("Normal")
        perf_layout.addWidget(self.priority_combo, 1, 1)
        
        audio_group = QGroupBox("Audio Settings")
        audio_layout = QGridLayout(audio_group)
        
        audio_layout.addWidget(QLabel("Input Sensitivity:"), 0, 0)
        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(1, 100)
        self.sensitivity_slider.setValue(50)
        audio_layout.addWidget(self.sensitivity_slider, 0, 1)
        
        layout.addWidget(startup_group)
        layout.addWidget(perf_group)
        layout.addWidget(audio_group)
        layout.addStretch()
        
    def check_auto_start(self):
        try:
            import winreg as reg
            key = reg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "WhisperKeyboard"
            
            with reg.OpenKey(key, key_path, 0, reg.KEY_READ | reg.KEY_WOW64_64KEY) as registry_key:
                try:
                    reg.QueryValueEx(registry_key, app_name)
                    auto_start = True
                except WindowsError:
                    auto_start = False
            
            self.auto_start_cb.setChecked(auto_start)
            start_minimized = '--minimized' in ' '.join(sys.argv[1:])
            self.start_minimized_cb.setChecked(start_minimized)
            
            main_window = self.window()
            if not isinstance(main_window, WhisperApp):
                return
                
            if auto_start and not main_window.is_running:
                main_window.log_widget.add_log("Auto-starting...", "info")
                QTimer.singleShot(2000, main_window.start_whisper)
                if start_minimized:
                    QTimer.singleShot(2500, main_window.showMinimized)
                    
        except Exception as e:
            main_window = self.window()
            if isinstance(main_window, WhisperApp):
                main_window.log_widget.add_log(f"Error checking auto-start: {str(e)}", "error")
            
    def toggle_auto_start(self, state):
        try:
            import winreg as reg
            app_path = sys.executable if getattr(sys, 'frozen', False) else f'"{os.path.join(os.path.dirname(sys.executable), "pythonw.exe")}" "{os.path.abspath(sys.argv[0])}" --minimized'
            key = reg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "WhisperKeyboard"
            
            with reg.OpenKey(key, key_path, 0, reg.KEY_SET_VALUE | reg.KEY_WOW64_64KEY) as registry_key:
                if state:
                    reg.SetValueEx(registry_key, app_name, 0, reg.REG_SZ, app_path)
                    self.window().log_widget.add_log("Auto-start enabled", "success")
                else:
                    try:
                        reg.DeleteValue(registry_key, app_name)
                        self.window().log_widget.add_log("Auto-start disabled", "info")
                    except WindowsError:
                        pass
        except Exception as e:
            self.window().log_widget.add_log(f"Error setting auto-start: {str(e)}", "error")

class WhisperApp(QMainWindow):
    """Whisper Keyboard Controller with light/dark mode toggle"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("WhisperKeyboard", "Settings")
        self.is_running = False
        self.main_thread = None
        self.stop_event = threading.Event()
        self.dark_mode = self.get_system_theme() == "dark"
        
        self.init_ui()
        self.setup_tray()
        self.setup_monitoring()
        self.load_settings()
        self.apply_theme()
        
    def get_system_theme(self) -> str:
        """Detect system theme preference"""
        if platform.system() == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value else "dark"
            except Exception:
                pass
        return "dark"  # Default to dark

    def apply_theme(self):
        """Apply system-appropriate theme with minimal custom styling"""
        # Use system palette as base
        palette = QPalette()
        
        if self.dark_mode:
            # Dark theme
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            
            # Minimal dark theme styling
            self.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #3a3a3a;
                    margin: 0px;
                    padding: 5px;
                }
                QTabBar::tab {
                    padding: 5px 10px;
                }
                QTabBar::tab:selected {
                    border-bottom: 2px solid #2a82da;
                }
            """)
        else:
            # Light theme - use system defaults with minimal overrides
            self.setStyleSheet("""
                QTabBar::tab:selected {
                    border-bottom: 2px solid #2a82da;
                }
            """)
            
        self.setPalette(palette)

    def toggle_theme(self):
        """Toggle between dark and light themes"""
        self.dark_mode = not self.dark_mode
        self.theme_btn.setText("🌙" if not self.dark_mode else "☀️")
        self.apply_theme()
        self.settings.setValue("dark_mode", self.dark_mode)
        self.log_widget.add_log(f"Switched to {'dark' if self.dark_mode else 'light'} theme", "info")
        
    def init_ui(self):
        self.setWindowTitle('Whisper Keyboard Controller')
        self.setMinimumSize(480, 600)
        self.resize(600, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        header_widget = self.create_header()
        main_layout.addWidget(header_widget)
        
        self.tab_widget = QTabWidget()
        control_tab = self.create_control_tab()
        self.tab_widget.addTab(control_tab, "Control")
        self.settings_widget = SettingsWidget(self)
        self.tab_widget.addTab(self.settings_widget, "Settings")
        self.log_widget = LogWidget()
        self.tab_widget.addTab(self.log_widget, "Logs")
        
        main_layout.addWidget(self.tab_widget)
        self.log_widget.add_log("Application started", "info")
        self.settings_widget.check_auto_start()
        
    def create_header(self) -> QWidget:
        """Create header with title, status, and theme toggle"""
        header = QWidget()
        header.setFixedHeight(80)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        title_layout = QVBoxLayout()
        title_label = QLabel('Whisper Keyboard')
        title_label.setFont(QFont("", 18, QFont.Weight.Bold))
        subtitle_label = QLabel('AI-Powered Voice Control')
        subtitle_label.setFont(QFont("", 10))
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()
        
        controls_layout = QHBoxLayout()
        self.status_indicator = StatusIndicator()
        self.status_label = QLabel('Stopped')
        self.status_label.setFont(QFont("", 12))
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        self.theme_btn = QPushButton("🌙" if not self.dark_mode else "☀️")
        self.theme_btn.setFixedSize(40, 40)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setToolTip("Toggle theme")
        
        controls_layout.addLayout(status_layout)
        controls_layout.addWidget(self.theme_btn)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        layout.addLayout(controls_layout)
        return header
        
    def create_control_tab(self) -> QWidget:
        """Create the main control interface"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(30)
        
        self.toggle_btn = QPushButton('Start Listening')
        self.toggle_btn.setMinimumHeight(50)
        self.toggle_btn.clicked.connect(self.toggle_whisper)
        
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.Shape.Box)
        stats_layout = QGridLayout(stats_frame)
        
        stats_layout.addWidget(QLabel("Session Time:"), 0, 0)
        self.session_time_label = QLabel("00:00:00")
        stats_layout.addWidget(self.session_time_label, 0, 1)
        stats_layout.addWidget(QLabel("Commands:"), 1, 0)
        self.commands_count_label = QLabel("0")
        stats_layout.addWidget(self.commands_count_label, 1, 1)
        stats_layout.addWidget(QLabel("Status:"), 2, 0)
        self.detailed_status_label = QLabel("Ready")
        stats_layout.addWidget(self.detailed_status_label, 2, 1)
        
        layout.addWidget(self.toggle_btn)
        layout.addSpacing(20)
        layout.addWidget(stats_frame)
        layout.addStretch()
        return widget
        
    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.log_widget.add_log("System tray not available", "warning")
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.create_app_icon()
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)
        
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_normal)
        tray_menu.addAction(show_action)
        self.toggle_action = QAction("Start", self)
        self.toggle_action.triggered.connect(self.toggle_whisper)
        tray_menu.addAction(self.toggle_action)
        tray_menu.addSeparator()
        theme_action = QAction("Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        tray_menu.addAction(theme_action)
        tray_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.cleanup_and_exit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
    def create_app_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(59, 130, 246))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(24, 12, 16, 28, 8, 8)
        painter.drawRect(30, 40, 4, 8)
        painter.drawRect(22, 46, 20, 4)
        painter.end()
        return QIcon(pixmap)
        
    def setup_monitoring(self):
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self.update_session_time)
        self.session_start_time = None
        
        if WINDOWS_AVAILABLE:
            self.idle_timer = QTimer()
            self.idle_timer.timeout.connect(self.check_idle_time)
            self.idle_timer.start(60000)
            
        self.sleep_timer = QTimer()
        self.sleep_timer.timeout.connect(self.check_sleep_state)
        self.sleep_timer.start(10000)
        self.last_check = time.time()
        
    def toggle_whisper(self):
        if self.is_running:
            self.stop_whisper()
        else:
            self.start_whisper()
            
    def start_whisper(self):
        if not self.is_running:
            self.is_running = True
            self.session_start_time = time.time()
            self.session_timer.start(1000)
            self.status_indicator.set_status("running")
            self.status_label.setText('Running')
            self.toggle_btn.setText('Stop Listening')
            self.toggle_action.setText('Stop')
            self.detailed_status_label.setText('Listening for voice commands...')
            self.stop_event.clear()
            self.main_thread = threading.Thread(target=self.run_whisper, daemon=True)
            self.main_thread.start()
            self.log_widget.add_log("Started listening for voice commands", "success")
            
    def stop_whisper(self):
        if self.is_running:
            self.is_running = False
            self.session_timer.stop()
            self.status_indicator.set_status("stopped")
            self.status_label.setText('Stopped')
            self.toggle_btn.setText('Start Listening')
            self.toggle_action.setText('Start')
            self.detailed_status_label.setText('Ready to start')
            self.stop_event.set()
            try:
                cleanup()
                reset_all_states()
            except Exception as e:
                self.log_widget.add_log(f"Cleanup error: {str(e)}", "error")
            self.log_widget.add_log("Stopped listening", "info")
            
    def run_whisper(self):
        try:
            whisper_main()
        except Exception as e:
            self.log_widget.add_log(f"Whisper error: {str(e)}", "error")
            self.status_indicator.set_status("error")
            
    def update_session_time(self):
        if self.session_start_time:
            elapsed = int(time.time() - self.session_start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.session_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
    def check_idle_time(self):
        if not WINDOWS_AVAILABLE:
            return
        try:
            last_input = win32api.GetLastInputInfo()
            current_time = win32api.GetTickCount()
            idle_time = (current_time - last_input) / 1000.0
            idle_threshold = self.settings_widget.idle_timeout_spin.value() * 60
            if idle_time > idle_threshold and self.is_running:
                self.log_widget.add_log(f"System idle for {idle_time/60:.1f} minutes", "warning")
        except Exception as e:
            self.log_widget.add_log(f"Idle check error: {str(e)}", "error")
            
    def check_sleep_state(self):
        current_time = time.time()
        time_diff = current_time - self.last_check
        if time_diff > 30 and self.is_running:
            self.log_widget.add_log("System resumed from sleep, restarting...", "info")
            self.restart_after_sleep()
        self.last_check = current_time
        
    def restart_after_sleep(self):
        if self.is_running:
            self.detailed_status_label.setText('Restarting after sleep...')
            self.stop_whisper()
            QTimer.singleShot(2000, self.start_whisper)
            
    def show_normal(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()
        
    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isHidden() or self.windowState() & Qt.WindowState.WindowMinimized:
                self.show_normal()
            else:
                self.hide()
                
    def load_settings(self):
        self.dark_mode = self.settings.value("dark_mode", self.get_system_theme() == "dark", type=bool)
        self.settings_widget.auto_start_cb.setChecked(
            self.settings.value("auto_start", False, type=bool))
        self.settings_widget.start_minimized_cb.setChecked(
            self.settings.value("start_minimized", False, type=bool))
        self.settings_widget.idle_timeout_spin.setValue(
            self.settings.value("idle_timeout", 120, type=int))
        self.settings_widget.priority_combo.setCurrentText(
            self.settings.value("cpu_priority", "Normal", type=str))
        self.settings_widget.sensitivity_slider.setValue(
            self.settings.value("sensitivity", 50, type=int))
        
        self.settings_widget.auto_start_cb.toggled.connect(self.save_settings)
        self.settings_widget.start_minimized_cb.toggled.connect(self.save_settings)
        self.settings_widget.idle_timeout_spin.valueChanged.connect(self.save_settings)
        self.settings_widget.priority_combo.currentTextChanged.connect(self.save_settings)
        self.settings_widget.sensitivity_slider.valueChanged.connect(self.save_settings)
        
    def save_settings(self):
        self.settings.setValue("dark_mode", self.dark_mode)
        self.settings.setValue("auto_start", self.settings_widget.auto_start_cb.isChecked())
        self.settings.setValue("start_minimized", self.settings_widget.start_minimized_cb.isChecked())
        self.settings.setValue("idle_timeout", self.settings_widget.idle_timeout_spin.value())
        self.settings.setValue("cpu_priority", self.settings_widget.priority_combo.currentText())
        self.settings.setValue("sensitivity", self.settings_widget.sensitivity_slider.value())
        
    def closeEvent(self, event):
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.log_widget.add_log("Application minimized to system tray", "info")
            self.hide()
            event.ignore()
        else:
            self.cleanup_and_exit()
            
    def cleanup_and_exit(self):
        try:
            self.log_widget.add_log("Shutting down application...", "info")
            if self.is_running:
                self.stop_whisper()
            self.save_settings()
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            QApplication.quit()
        except Exception as e:
            print(f"Error during exit: {e}")
            os._exit(1)

def setup_application():
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Whisper Keyboard Controller")
    app.setApplicationDisplayName("Whisper Keyboard")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("WhisperKeyboard")
    app.setOrganizationDomain("whisperkeyboard.app")
    return app

def main():
    app = setup_application()
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 65432))
    except OSError:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Whisper Keyboard Controller")
        msg.setText("Another instance of Whisper Keyboard Controller is already running.")
        msg.exec()
        sys.exit(1)
    
    window = WhisperApp()
    if '--minimized' in sys.argv or window.settings_widget.start_minimized_cb.isChecked():
        window.hide()
        if hasattr(window, 'tray_icon') and window.tray_icon.isVisible():
            window.tray_icon.showMessage(
                "Whisper Keyboard Controller",
                "Application started and minimized to system tray",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
    else:
        window.show()
    
    if window.settings_widget.auto_start_cb.isChecked():
        QTimer.singleShot(1000, window.start_whisper)
    
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        window.cleanup_and_exit()

if __name__ == '__main__':
    main()