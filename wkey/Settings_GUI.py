import os
from settings_manager import (
    load_settings as settings_load,
    save_settings as settings_save,
    DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
)
from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QLineEdit,
    QPushButton,
)
from qtpy.QtCore import Qt

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Keyboard Settings")
        self.layout = QVBoxLayout(self)

        self.use_local_cb = QCheckBox("Use local GPU model when available")
        self.use_cpu_cb = QCheckBox("Use local CPU fallback")
        self.use_api_cb = QCheckBox("Fallback to Groq API")
        self.precheck_cb = QCheckBox("Enable pre-recording keyword check")
        self.max_retries_edit = QLineEdit()
        self.max_retries_edit.setPlaceholderText("Max retries (Groq)")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("GROQ_API_KEY")

        self.layout.addWidget(self.use_local_cb)
        self.layout.addWidget(self.use_cpu_cb)
        self.layout.addWidget(self.use_api_cb)
        self.layout.addWidget(self.precheck_cb)
        self.layout.addWidget(QLabel("Max Retries:"))
        self.layout.addWidget(self.max_retries_edit)
        self.layout.addWidget(QLabel("Groq API Key:"))
        self.layout.addWidget(self.api_key_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        self.layout.addLayout(btn_layout)

        self.load_settings()

    def load_settings(self):
        config = settings_load(SETTINGS_PATH, SETTINGS_DEFAULTS)
        self.use_local_cb.setChecked(config.get("use_local_gpu", True))
        self.use_cpu_cb.setChecked(config.get("use_local_cpu", True))
        self.use_api_cb.setChecked(config.get("fallback_to_groq", True))
        self.precheck_cb.setChecked(
            config.get("enable_pre_recording_keyword_check", False)
        )
        self.max_retries_edit.setText(str(config.get("max_retries", 3)))
        self.api_key_edit.setText(os.environ.get("GROQ_API_KEY", ""))

    def save_settings(self):
        config = settings_load(SETTINGS_PATH, SETTINGS_DEFAULTS)
        config["use_local_gpu"] = self.use_local_cb.isChecked()
        config["use_local_cpu"] = self.use_cpu_cb.isChecked()
        config["fallback_to_groq"] = self.use_api_cb.isChecked()
        config["enable_pre_recording_keyword_check"] = self.precheck_cb.isChecked()
        try:
            max_retries = int(self.max_retries_edit.text().strip())
            config["max_retries"] = max(1, max_retries)
        except Exception:
            pass
        settings_save(SETTINGS_PATH, config)
        if self.api_key_edit.text().strip():
            os.environ["GROQ_API_KEY"] = self.api_key_edit.text().strip()
        self.close()


def main():
    app = QApplication([])
    window = SettingsWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
