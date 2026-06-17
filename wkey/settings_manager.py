import json
import logging
import os
import threading
import time

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    _WATCHDOG_AVAILABLE = True
except Exception:
    FileSystemEventHandler = object
    Observer = None
    _WATCHDOG_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_RECORD_KEYS = "f24,ctrl_l"
SUPPORTED_RECORD_KEY_LABELS = ("f24", "ctrl_l")
RECORD_KEY_DISPLAY_NAMES = {
    "f24": "F24",
    "ctrl_l": "Left Ctrl",
}
RECORD_KEY_ALIASES = {
    "f24": "f24",
    "left ctrl": "ctrl_l",
    "left control": "ctrl_l",
    "lctrl": "ctrl_l",
    "ctrl_l": "ctrl_l",
    "left_ctrl": "ctrl_l",
    "right ctrl": "ctrl_l",
    "right control": "ctrl_l",
    "rctrl": "ctrl_l",
    "ctrl_r": "ctrl_l",
    "right_ctrl": "ctrl_l",
}

DEFAULT_SETTINGS = {
    "use_local_gpu": True,
    "use_local_cpu": True,
    "fallback_to_groq": True,
    "enable_edge_selenium": True,
    "enable_wakeword_detection": False,
    "max_retries": 3,
    "enable_pre_recording_keyword_check": False,
    "enable_transcript_context_memory": True,
    "stt_context_items": 2,
    "stt_context_chars": 180,
    "router_context_items": 3,
    "router_context_chars": 320,
    "context_max_age_seconds": 180,
    "max_recording_seconds": 45,
    "google_wake_volume_hold_seconds": 2.5,
    "record_keys": DEFAULT_RECORD_KEYS,
}


def normalize_record_key_label(label):
    if label is None:
        return None
    normalized = str(label).strip().lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    return RECORD_KEY_ALIASES.get(normalized) or RECORD_KEY_ALIASES.get(
        normalized.replace(" ", "_")
    )


def normalize_record_keys(value, default=DEFAULT_RECORD_KEYS, allow_empty=False):
    if value is None:
        pieces = str(default).split(",")
    elif isinstance(value, (list, tuple, set)):
        pieces = value
    else:
        pieces = str(value).split(",")

    selected = set()
    for piece in pieces:
        label = normalize_record_key_label(piece)
        if label in SUPPORTED_RECORD_KEY_LABELS:
            selected.add(label)

    if not selected:
        if allow_empty:
            return ""
        if default in (None, value):
            return DEFAULT_RECORD_KEYS
        return normalize_record_keys(default, default=DEFAULT_RECORD_KEYS)

    return ",".join(label for label in SUPPORTED_RECORD_KEY_LABELS if label in selected)


def record_key_display_text(record_keys):
    normalized = normalize_record_keys(record_keys)
    names = [
        RECORD_KEY_DISPLAY_NAMES[label]
        for label in normalized.split(",")
        if label in RECORD_KEY_DISPLAY_NAMES
    ]
    return " or ".join(names) if names else "None"


def _validate_settings(settings, defaults):
    merged = defaults.copy()
    if not isinstance(settings, dict):
        return merged

    for key, value in settings.items():
        if key in (
            "use_local_gpu",
            "use_local_cpu",
            "fallback_to_groq",
            "enable_edge_selenium",
            "enable_wakeword_detection",
            "enable_pre_recording_keyword_check",
            "enable_transcript_context_memory",
        ):
            merged[key] = bool(value)
        elif key in (
            "max_retries",
            "stt_context_items",
            "stt_context_chars",
            "router_context_items",
            "router_context_chars",
            "context_max_age_seconds",
            "max_recording_seconds",
        ):
            try:
                merged[key] = max(1, int(value))
            except Exception:
                pass
        elif key == "google_wake_volume_hold_seconds":
            try:
                merged[key] = max(0.0, float(value))
            except Exception:
                pass
        elif key == "record_keys":
            merged[key] = normalize_record_keys(value)
        else:
            merged[key] = value
    return merged


def runtime_mode_for_settings(settings):
    return "combined" if settings.get("enable_wakeword_detection", False) else "keyboard"


def build_backend_environment(settings, base_env=None):
    env = dict(os.environ if base_env is None else base_env)
    env["WKEY_RECORD_KEYS"] = normalize_record_keys(
        settings.get("record_keys", DEFAULT_RECORD_KEYS)
    )
    env["WKEY_RUNTIME_MODE"] = runtime_mode_for_settings(settings)
    return env


def load_settings(path, defaults=None):
    if defaults is None:
        defaults = DEFAULT_SETTINGS
    config = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f) or {}
        except Exception as e:
            logger.warning("Failed to read settings %s: %s", path, e)
    return _validate_settings(config, defaults)


def save_settings(path, settings):
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.warning("Failed to write settings %s: %s", path, e)
        return False


def watch_settings(path, defaults, on_change, poll_interval=0.5, debounce_seconds=0.25):
    settings_path = os.path.abspath(path)
    settings_dir = os.path.dirname(settings_path) or "."
    last_event_time = 0.0

    def _trigger():
        nonlocal last_event_time
        now = time.time()
        if now - last_event_time < debounce_seconds:
            return
        last_event_time = now
        try:
            new_settings = load_settings(settings_path, defaults)
            on_change(new_settings)
        except Exception as e:
            logger.warning("Settings reload failed: %s", e)

    if _WATCHDOG_AVAILABLE:
        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if os.path.abspath(event.src_path) == settings_path:
                    _trigger()

            def on_created(self, event):
                if os.path.abspath(event.src_path) == settings_path:
                    _trigger()

        observer = Observer()
        observer.schedule(_Handler(), settings_dir, recursive=False)
        observer.start()
        return observer

    def _poll():
        last_mtime = None
        while True:
            try:
                if os.path.exists(settings_path):
                    mtime = os.path.getmtime(settings_path)
                    if last_mtime is None:
                        last_mtime = mtime
                    elif mtime != last_mtime:
                        last_mtime = mtime
                        _trigger()
                time.sleep(poll_interval)
            except Exception:
                time.sleep(poll_interval)

    thread = threading.Thread(target=_poll, daemon=True)
    thread.start()
    return thread
