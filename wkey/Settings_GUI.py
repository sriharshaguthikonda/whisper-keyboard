import os
import json
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
DEFAULT_SETTINGS = {"use_local_gpu": True, "fallback_to_groq": True}

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Keyboard Settings")
        self.layout = QVBoxLayout(self)

        self.use_local_cb = QCheckBox("Use local GPU model when available")
        self.use_api_cb = QCheckBox("Fallback to Groq API")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("GROQ_API_KEY")

        self.layout.addWidget(self.use_local_cb)
        self.layout.addWidget(self.use_api_cb)
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
        config = DEFAULT_SETTINGS.copy()
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
            except Exception:
                pass
        self.use_local_cb.setChecked(config.get("use_local_gpu", True))
        self.use_api_cb.setChecked(config.get("fallback_to_groq", True))
        self.api_key_edit.setText(os.environ.get("GROQ_API_KEY", ""))

    def save_settings(self):
        config = {
            "use_local_gpu": self.use_local_cb.isChecked(),
            "fallback_to_groq": self.use_api_cb.isChecked(),
        }
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass
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
