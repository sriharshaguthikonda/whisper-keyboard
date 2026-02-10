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

DEFAULT_SETTINGS = {
    "use_local_gpu": True,
    "use_local_cpu": True,
    "fallback_to_groq": True,
    "max_retries": 3,
}


def _validate_settings(settings, defaults):
    merged = defaults.copy()
    if not isinstance(settings, dict):
        return merged

    for key, value in settings.items():
        if key in ("use_local_gpu", "use_local_cpu", "fallback_to_groq"):
            merged[key] = bool(value)
        elif key == "max_retries":
            try:
                merged[key] = max(1, int(value))
            except Exception:
                pass
        else:
            merged[key] = value
    return merged


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

