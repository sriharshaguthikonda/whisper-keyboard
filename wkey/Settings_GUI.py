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
    QMessageBox,
    QToolButton,
    QFrame,
)
from qtpy.QtCore import Qt
from qtpy.QtGui import QIntValidator

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper Keyboard Settings")
        self.layout = QVBoxLayout(self)

        self.use_local_cb = QCheckBox("Use local GPU model when available")
        self.use_cpu_cb = QCheckBox("Use local CPU fallback")
        self.use_api_cb = QCheckBox("Fallback to Groq API")
        self.wakeword_cb = QCheckBox("Enable wake-word detection")
        self.precheck_cb = QCheckBox("Validate detected wake word before command capture")
        self.edge_selenium_cb = QCheckBox("Enable Edge/Selenium browser automation")
        self.context_memory_cb = QCheckBox("Enable transcript context memory")
        self.ask_ai_cb = QCheckBox(
            "Enable Ask-AI voice commands (ChatGPT browser + direct Ask-AI)"
        )
        self.ask_chatgpt_fallback_cb = QCheckBox(
            "Fallback to direct Ask-AI if ChatGPT tab is not claimed"
        )

        self.max_retries_edit = QLineEdit()
        self.max_retries_edit.setPlaceholderText("Max retries (Groq)")
        self.max_retries_edit.setValidator(QIntValidator(1, 20, self))

        self.stt_context_items_edit = QLineEdit()
        self.stt_context_items_edit.setPlaceholderText("1 to 8")
        self.stt_context_items_edit.setValidator(QIntValidator(1, 8, self))

        self.stt_context_chars_edit = QLineEdit()
        self.stt_context_chars_edit.setPlaceholderText("40 to 800")
        self.stt_context_chars_edit.setValidator(QIntValidator(40, 800, self))

        self.router_context_items_edit = QLineEdit()
        self.router_context_items_edit.setPlaceholderText("1 to 8")
        self.router_context_items_edit.setValidator(QIntValidator(1, 8, self))

        self.router_context_chars_edit = QLineEdit()
        self.router_context_chars_edit.setPlaceholderText("80 to 1200")
        self.router_context_chars_edit.setValidator(QIntValidator(80, 1200, self))

        self.context_max_age_edit = QLineEdit()
        self.context_max_age_edit.setPlaceholderText("15 to 3600")
        self.context_max_age_edit.setValidator(QIntValidator(15, 3600, self))

        self.ask_chatgpt_claim_timeout_edit = QLineEdit()
        self.ask_chatgpt_claim_timeout_edit.setPlaceholderText("1 to 60")
        self.ask_chatgpt_claim_timeout_edit.setValidator(QIntValidator(1, 60, self))

        self.ask_ai_model_edit = QLineEdit()
        self.ask_ai_model_edit.setPlaceholderText("auto")

        self.prompt_jobs_dir_edit = QLineEdit()
        self.prompt_jobs_dir_edit.setPlaceholderText(
            r"C:\Windows_software\openai whisper\prompt_jobs"
        )

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("GROQ_API_KEY")

        self.layout.addLayout(
            self._build_checkbox_row(
                self.use_local_cb,
                "Use local GPU Faster-Whisper model when available.",
            )
        )
        self.layout.addLayout(
            self._build_checkbox_row(
                self.use_cpu_cb,
                "Allow local CPU model fallback when network transcription fails.",
            )
        )
        self.layout.addLayout(
            self._build_checkbox_row(
                self.use_api_cb,
                "Use Groq API for transcription. If disabled, only local models are used.",
            )
        )
        self.layout.addLayout(
            self._build_checkbox_row(
                self.wakeword_cb,
                "Turns wake-word listening on or off. Manual keyboard controls still work when off.",
            )
        )
        self.layout.addLayout(
            self._build_checkbox_row(
                self.precheck_cb,
                "Checks a short pre-buffer after wake-word detection. This is not the wake-word on/off switch.",
            )
        )
        self.layout.addLayout(
            self._build_checkbox_row(
                self.edge_selenium_cb,
                "Turns Selenium-based Edge browser automation on or off globally.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Max Retries:",
                self.max_retries_edit,
                "Number of Groq retry attempts before giving up on the request.",
            )
        )

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(separator)

        context_header = QLabel("Transcript Context Memory")
        context_header.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(context_header)

        self.layout.addLayout(
            self._build_checkbox_row(
                self.context_memory_cb,
                "When enabled, recent transcripts are added as context to improve disambiguation. "
                "Turn this off if old phrases are biasing current transcription.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "STT Context Items:",
                self.stt_context_items_edit,
                "How many recent transcript entries can be included in speech-to-text prompt context.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "STT Context Chars:",
                self.stt_context_chars_edit,
                "Maximum total characters of recent context passed to speech-to-text prompt.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Router Context Items:",
                self.router_context_items_edit,
                "How many recent entries can be attached when routing a transcribed command.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Router Context Chars:",
                self.router_context_chars_edit,
                "Maximum character budget for command-router context.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Context Max Age (s):",
                self.context_max_age_edit,
                "Only context newer than this age in seconds is eligible.",
            )
        )

        ask_ai_separator = QFrame()
        ask_ai_separator.setFrameShape(QFrame.HLine)
        ask_ai_separator.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(ask_ai_separator)

        ask_ai_header = QLabel("Ask AI")
        ask_ai_header.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(ask_ai_header)

        self.layout.addLayout(
            self._build_checkbox_row(
                self.ask_ai_cb,
                "Enables voice commands that send questions to ChatGPT browser automation or direct provider Ask-AI.",
            )
        )
        self.layout.addLayout(
            self._build_checkbox_row(
                self.ask_chatgpt_fallback_cb,
                "When off, unclaimed ChatGPT jobs fail instead of making a hidden provider request.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Claim Timeout (s):",
                self.ask_chatgpt_claim_timeout_edit,
                "Seconds to wait for the browser extension to claim a ChatGPT prompt job.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Ask-AI Model:",
                self.ask_ai_model_edit,
                "Use 'auto' for provider/model auto-selection, or provider:model for an explicit provider.",
            )
        )
        self.layout.addLayout(
            self._build_labeled_edit_row(
                "Prompt Jobs Folder:",
                self.prompt_jobs_dir_edit,
                "Folder shared with the browser extension for pending ChatGPT prompt jobs.",
            )
        )

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

        self.context_memory_cb.stateChanged.connect(self._update_context_controls_enabled)
        self.load_settings()

    def _make_info_button(self, text):
        button = QToolButton()
        button.setText("?")
        button.setToolTip("Show explanation")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda: QMessageBox.information(self, "Setting Info", text)
        )
        return button

    def _build_checkbox_row(self, checkbox, info_text):
        row = QHBoxLayout()
        row.addWidget(checkbox)
        row.addStretch(1)
        row.addWidget(self._make_info_button(info_text))
        return row

    def _build_labeled_edit_row(self, label_text, edit, info_text):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(edit, 1)
        row.addWidget(self._make_info_button(info_text))
        return row

    def _update_context_controls_enabled(self):
        enabled = self.context_memory_cb.isChecked()
        self.stt_context_items_edit.setEnabled(enabled)
        self.stt_context_chars_edit.setEnabled(enabled)
        self.router_context_items_edit.setEnabled(enabled)
        self.router_context_chars_edit.setEnabled(enabled)
        self.context_max_age_edit.setEnabled(enabled)

    def _set_int_if_valid(self, config, key, edit, minimum, maximum):
        raw = edit.text().strip()
        if not raw:
            return
        try:
            value = int(raw)
            config[key] = max(minimum, min(maximum, value))
        except Exception:
            return

    def load_settings(self):
        config = settings_load(SETTINGS_PATH, SETTINGS_DEFAULTS)
        self.use_local_cb.setChecked(config.get("use_local_gpu", True))
        self.use_cpu_cb.setChecked(config.get("use_local_cpu", True))
        self.use_api_cb.setChecked(config.get("fallback_to_groq", True))
        self.precheck_cb.setChecked(
            config.get("enable_pre_recording_keyword_check", False)
        )
        self.wakeword_cb.setChecked(config.get("enable_wakeword_detection", False))
        self.edge_selenium_cb.setChecked(config.get("enable_edge_selenium", True))
        self.context_memory_cb.setChecked(
            config.get("enable_transcript_context_memory", True)
        )
        self.max_retries_edit.setText(str(config.get("max_retries", 3)))
        self.stt_context_items_edit.setText(str(config.get("stt_context_items", 2)))
        self.stt_context_chars_edit.setText(str(config.get("stt_context_chars", 180)))
        self.router_context_items_edit.setText(
            str(config.get("router_context_items", 3))
        )
        self.router_context_chars_edit.setText(
            str(config.get("router_context_chars", 320))
        )
        self.context_max_age_edit.setText(str(config.get("context_max_age_seconds", 180)))
        self.ask_ai_cb.setChecked(config.get("ask_ai_enabled", False))
        self.ask_chatgpt_claim_timeout_edit.setText(
            str(config.get("ask_chatgpt_claim_timeout_sec", 12))
        )
        self.ask_ai_model_edit.setText(config.get("ask_ai_model", "auto"))
        self.ask_chatgpt_fallback_cb.setChecked(
            config.get("ask_chatgpt_fallback_to_ai", False)
        )
        self.prompt_jobs_dir_edit.setText(
            config.get(
                "prompt_jobs_dir",
                r"C:\Windows_software\openai whisper\prompt_jobs",
            )
        )
        self.api_key_edit.setText(os.environ.get("GROQ_API_KEY", ""))
        self._update_context_controls_enabled()

    def save_settings(self):
        config = settings_load(SETTINGS_PATH, SETTINGS_DEFAULTS)
        config["use_local_gpu"] = self.use_local_cb.isChecked()
        config["use_local_cpu"] = self.use_cpu_cb.isChecked()
        config["fallback_to_groq"] = self.use_api_cb.isChecked()
        config["enable_wakeword_detection"] = self.wakeword_cb.isChecked()
        config["enable_pre_recording_keyword_check"] = self.precheck_cb.isChecked()
        config["enable_edge_selenium"] = self.edge_selenium_cb.isChecked()
        config["enable_transcript_context_memory"] = self.context_memory_cb.isChecked()
        config["ask_ai_enabled"] = self.ask_ai_cb.isChecked()
        config["ask_chatgpt_fallback_to_ai"] = (
            self.ask_chatgpt_fallback_cb.isChecked()
        )

        self._set_int_if_valid(config, "max_retries", self.max_retries_edit, 1, 20)
        self._set_int_if_valid(
            config, "stt_context_items", self.stt_context_items_edit, 1, 8
        )
        self._set_int_if_valid(
            config, "stt_context_chars", self.stt_context_chars_edit, 40, 800
        )
        self._set_int_if_valid(
            config, "router_context_items", self.router_context_items_edit, 1, 8
        )
        self._set_int_if_valid(
            config, "router_context_chars", self.router_context_chars_edit, 80, 1200
        )
        self._set_int_if_valid(
            config, "context_max_age_seconds", self.context_max_age_edit, 15, 3600
        )
        self._set_int_if_valid(
            config,
            "ask_chatgpt_claim_timeout_sec",
            self.ask_chatgpt_claim_timeout_edit,
            1,
            60,
        )
        if self.ask_ai_model_edit.text().strip():
            config["ask_ai_model"] = self.ask_ai_model_edit.text().strip()
        if self.prompt_jobs_dir_edit.text().strip():
            config["prompt_jobs_dir"] = self.prompt_jobs_dir_edit.text().strip()

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
