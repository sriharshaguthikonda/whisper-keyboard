import copy
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

DEFAULT_RECORD_KEYS = "f24,ctrl_r"
SUPPORTED_RECORD_KEY_LABELS = ("f24", "f23", "ctrl_l", "ctrl_r")
TRIGGER_MODIFIER_LABELS = {
    "ctrl",
    "ctrl_l",
    "ctrl_r",
    "shift",
    "shift_l",
    "shift_r",
    "alt",
    "alt_l",
    "alt_r",
}
SPEAKER_FILTER_MODES = ("analysis", "conservative", "balanced", "permissive", "custom")
DEFAULT_SPEAKER_FILTER_PROFILE_PATH = "wkey/speaker_filter_profile.json"
DEFAULT_SPEAKER_FILTER_ENROLLMENT_DIR = r"I:\Record_only_by_harsha"
DEFAULT_SPEAKER_FILTER_NEGATIVE_DIR = r"I:\Record_others_16k_wav"
RECORD_KEY_DISPLAY_NAMES = {
    "f24": "F24",
    "f23": "F23",
    "ctrl_l": "Left Ctrl",
    "ctrl_r": "Right Ctrl",
}
RECORD_KEY_ALIASES = {
    "f24": "f24",
    "f23": "f23",
    "left ctrl": "ctrl_r",
    "left control": "ctrl_r",
    "lctrl": "ctrl_r",
    "ctrl_l": "ctrl_r",
    "left_ctrl": "ctrl_r",
    "right ctrl": "ctrl_r",
    "right control": "ctrl_r",
    "rctrl": "ctrl_r",
    "ctrl_r": "ctrl_r",
    "right_ctrl": "ctrl_r",
}
TRIGGER_ALIASES = {
    **RECORD_KEY_ALIASES,
    "control": "ctrl_r",
    "ctrl": "ctrl_r",
    "left shift": "shift_l",
    "leftshift": "shift_l",
    "lshift": "shift_l",
    "shift_l": "shift_l",
    "right shift": "shift_r",
    "rightshift": "shift_r",
    "rshift": "shift_r",
    "shift_r": "shift_r",
    "shift": "shift",
    "left alt": "alt_l",
    "leftalt": "alt_l",
    "lalt": "alt_l",
    "alt_l": "alt_l",
    "right alt": "alt_r",
    "rightalt": "alt_r",
    "ralt": "alt_r",
    "alt_r": "alt_r",
    "alt": "alt",
}

DEFAULT_HOTKEY_PROFILES = {
    "dictation": {
        "label": "Dictation / Paste",
        "trigger": "ctrl_r",
        "triggers": ["ctrl_r"],
        "action": "dictation",
        "enabled": True,
        "diagnostic": False,
    },
    "command": {
        "label": "Command / Tool-use",
        "trigger": "f24",
        "triggers": ["f24"],
        "action": "command",
        "enabled": True,
        "diagnostic": False,
    },
    "pause_resume": {
        "label": "Pause / Resume",
        "trigger": "ctrl+shift+p",
        "triggers": ["ctrl_r+shift+p"],
        "action": "pause_resume",
        "enabled": True,
        "diagnostic": False,
    },
    "pause_15m": {
        "label": "Timed Pause 15m",
        "trigger": "ctrl+shift+1",
        "triggers": ["ctrl_r+shift+1"],
        "action": "timed_pause",
        "duration_minutes": 15,
        "enabled": True,
        "diagnostic": False,
    },
    "pause_60m": {
        "label": "Timed Pause 60m",
        "trigger": "ctrl+shift+2",
        "triggers": ["ctrl_r+shift+2"],
        "action": "timed_pause",
        "duration_minutes": 60,
        "enabled": True,
        "diagnostic": False,
    },
    "wake_mode_toggle": {
        "label": "Wake Mode Toggle",
        "trigger": "",
        "triggers": [],
        "action": "wake_mode_toggle",
        "enabled": False,
        "diagnostic": False,
    },
    "restart_backend": {
        "label": "Restart Backend",
        "trigger": "",
        "triggers": [],
        "action": "restart_backend",
        "enabled": False,
        "diagnostic": False,
    },
    "df_diagnostic": {
        "label": "D+F Diagnostic",
        "trigger": "d+f",
        "triggers": ["d+f"],
        "action": "diagnostic",
        "enabled": False,
        "diagnostic": True,
    },
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
    "manual_pre_recording_seconds": 2.0,
    "wake_pre_recording_seconds": 2.0,
    "google_wake_volume_hold_seconds": 2.5,
    "record_keys": DEFAULT_RECORD_KEYS,
    "hotkey_profiles": copy.deepcopy(DEFAULT_HOTKEY_PROFILES),
    "ui_theme": "system",
    "minimize_to_tray": True,
    "speaker_filter_enabled": False,
    "speaker_filter_mode": "analysis",
    "speaker_filter_threshold": 0.72,
    "speaker_filter_profile_path": DEFAULT_SPEAKER_FILTER_PROFILE_PATH,
    "speaker_filter_enrollment_dir": DEFAULT_SPEAKER_FILTER_ENROLLMENT_DIR,
    "speaker_filter_negative_dir": DEFAULT_SPEAKER_FILTER_NEGATIVE_DIR,
    "speaker_filter_apply_to": "dictation",
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


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _normalize_profile_trigger(trigger):
    triggers = normalize_profile_triggers([trigger])
    return triggers[0] if triggers else ""


def _normalize_trigger_part(part):
    value = str(part or "").strip().lower().replace("-", " ").replace("_", " ")
    value = " ".join(value.split())
    if not value:
        return None
    alias = TRIGGER_ALIASES.get(value) or TRIGGER_ALIASES.get(value.replace(" ", "_"))
    if alias:
        return alias
    compact = value.replace(" ", "")
    if compact.startswith("f") and compact[1:].isdigit():
        number = int(compact[1:])
        if 1 <= number <= 24:
            return f"f{number}"
    if len(compact) == 1 and compact.isalnum():
        return compact
    return None


def normalize_profile_trigger(trigger):
    if trigger is None:
        return ""
    parts = [
        _normalize_trigger_part(part)
        for part in str(trigger).replace(" ", "").split("+")
    ]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    seen = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    has_non_modifier = any(part not in TRIGGER_MODIFIER_LABELS for part in seen)
    if not has_non_modifier:
        return seen[0] if len(seen) == 1 and seen[0] in SUPPORTED_RECORD_KEY_LABELS else ""
    if len(seen) == 1 and seen[0].isalnum() and len(seen[0]) == 1:
        return ""
    modifier_order = {
        "ctrl_l": 0,
        "ctrl_r": 0,
        "ctrl": 0,
        "shift_l": 1,
        "shift_r": 1,
        "shift": 1,
        "alt_l": 2,
        "alt_r": 2,
        "alt": 2,
    }
    seen.sort(key=lambda item: (modifier_order.get(item, 10), item))
    return "+".join(seen)


def normalize_profile_triggers(value):
    if value is None:
        pieces = []
    elif isinstance(value, (list, tuple, set)):
        pieces = value
    else:
        pieces = str(value).split(",")

    normalized = []
    for piece in pieces:
        trigger = normalize_profile_trigger(piece)
        if trigger and trigger not in normalized:
            normalized.append(trigger)
    return normalized


def _first_trigger(triggers):
    return triggers[0] if triggers else ""


def _normalize_speaker_filter_mode(value):
    mode = str(value or "analysis").strip().lower()
    return mode if mode in SPEAKER_FILTER_MODES else "analysis"


def _normalize_speaker_filter_threshold(value):
    try:
        threshold = float(value)
    except Exception:
        threshold = DEFAULT_SETTINGS["speaker_filter_threshold"]
    return max(0.0, min(1.0, threshold))


def _normalize_nonempty_path(value, default):
    text = str(value or "").strip()
    return text or default


def _normalize_speaker_filter_apply_to(value):
    _ = value
    return "dictation"


def normalize_hotkey_profiles(value, record_keys=None):
    profiles = copy.deepcopy(DEFAULT_HOTKEY_PROFILES)

    if record_keys is not None:
        record_labels = normalize_record_keys(record_keys, allow_empty=True).split(",")
        selected = {label for label in record_labels if label}
        profiles["command"]["enabled"] = "f24" in selected
        dictation_labels = [
            label
            for label in SUPPORTED_RECORD_KEY_LABELS
            if label != "f24" and label in selected
        ]
        profiles["dictation"]["enabled"] = bool(dictation_labels)
        if dictation_labels:
            profiles["dictation"]["triggers"] = [dictation_labels[0]]
            profiles["dictation"]["trigger"] = dictation_labels[0]

    if not isinstance(value, dict):
        return profiles

    for profile_id, profile_data in value.items():
        if profile_id not in profiles or not isinstance(profile_data, dict):
            continue
        merged = profiles[profile_id]
        if "label" in profile_data and str(profile_data["label"]).strip():
            merged["label"] = str(profile_data["label"]).strip()
        if "action" in profile_data and str(profile_data["action"]).strip():
            merged["action"] = str(profile_data["action"]).strip()
        if "triggers" in profile_data:
            triggers = normalize_profile_triggers(profile_data["triggers"])
            merged["triggers"] = triggers
            merged["trigger"] = _first_trigger(triggers)
        elif "trigger" in profile_data:
            triggers = normalize_profile_triggers([profile_data["trigger"]])
            merged["triggers"] = triggers
            merged["trigger"] = _first_trigger(triggers)
        if "enabled" in profile_data:
            merged["enabled"] = _coerce_bool(profile_data["enabled"], merged["enabled"])
        if "diagnostic" in profile_data:
            merged["diagnostic"] = _coerce_bool(
                profile_data["diagnostic"], merged["diagnostic"]
            )
        if "duration_minutes" in profile_data:
            try:
                merged["duration_minutes"] = max(1, int(profile_data["duration_minutes"]))
            except Exception:
                pass

    profiles["df_diagnostic"]["enabled"] = False
    profiles["df_diagnostic"]["diagnostic"] = True
    profiles["df_diagnostic"]["trigger"] = "d+f"
    profiles["df_diagnostic"]["triggers"] = ["d+f"]
    return profiles


def record_keys_from_hotkey_profiles(profiles, fallback=DEFAULT_RECORD_KEYS):
    normalized_profiles = normalize_hotkey_profiles(profiles)
    selected = []

    command = normalized_profiles.get("command", {})
    if command.get("enabled", False):
        for trigger_value in command.get("triggers", [command.get("trigger")]):
            trigger = normalize_record_key_label(trigger_value)
            if trigger in SUPPORTED_RECORD_KEY_LABELS and trigger not in selected:
                selected.append(trigger)

    dictation = normalized_profiles.get("dictation", {})
    if dictation.get("enabled", False):
        for trigger_value in dictation.get("triggers", [dictation.get("trigger")]):
            trigger = normalize_record_key_label(trigger_value)
            if trigger in SUPPORTED_RECORD_KEY_LABELS and trigger not in selected:
                selected.append(trigger)

    if not selected:
        return normalize_record_keys(fallback)
    return normalize_record_keys(selected)


def hotkey_profiles_for_environment(profiles):
    return json.dumps(normalize_hotkey_profiles(profiles), separators=(",", ":"), sort_keys=True)


def trigger_routes_from_hotkey_profiles(profiles):
    normalized_profiles = normalize_hotkey_profiles(profiles)
    routes = {}
    for profile_id in ("dictation", "command"):
        profile = normalized_profiles.get(profile_id, {})
        if not profile.get("enabled", False):
            continue
        route = "command" if profile.get("action") == "command" else "dictation"
        for trigger in profile.get("triggers", [profile.get("trigger")]):
            normalized = normalize_profile_trigger(trigger)
            if normalized and normalized not in routes:
                routes[normalized] = route
    return routes


def record_key_display_text(record_keys):
    normalized = normalize_record_keys(record_keys)
    names = [
        RECORD_KEY_DISPLAY_NAMES[label]
        for label in normalized.split(",")
        if label in RECORD_KEY_DISPLAY_NAMES
    ]
    return " or ".join(names) if names else "None"


def _validate_settings(settings, defaults):
    merged = copy.deepcopy(defaults)
    if not isinstance(settings, dict):
        merged["record_keys"] = normalize_record_keys(merged.get("record_keys"))
        merged["hotkey_profiles"] = normalize_hotkey_profiles(
            merged.get("hotkey_profiles"), merged.get("record_keys")
        )
        return merged

    source_has_hotkey_profiles = False
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
        elif key == "manual_pre_recording_seconds":
            try:
                merged[key] = max(0.0, min(5.0, float(value)))
            except Exception:
                pass
        elif key == "wake_pre_recording_seconds":
            try:
                merged[key] = max(0.0, min(10.0, float(value)))
            except Exception:
                pass
        elif key == "record_keys":
            merged[key] = normalize_record_keys(value)
        elif key == "hotkey_profiles":
            source_has_hotkey_profiles = True
            merged[key] = normalize_hotkey_profiles(
                value, record_keys=merged.get("record_keys", DEFAULT_RECORD_KEYS)
            )
        elif key == "ui_theme":
            normalized_theme = str(value).strip().lower()
            merged[key] = (
                normalized_theme if normalized_theme in {"system", "dark", "light"} else "system"
            )
        elif key == "minimize_to_tray":
            merged[key] = _coerce_bool(value, True)
        elif key == "speaker_filter_enabled":
            merged[key] = _coerce_bool(value, False)
        elif key == "speaker_filter_mode":
            merged[key] = _normalize_speaker_filter_mode(value)
        elif key == "speaker_filter_threshold":
            merged[key] = _normalize_speaker_filter_threshold(value)
        elif key == "speaker_filter_profile_path":
            merged[key] = _normalize_nonempty_path(
                value, DEFAULT_SPEAKER_FILTER_PROFILE_PATH
            )
        elif key == "speaker_filter_enrollment_dir":
            merged[key] = _normalize_nonempty_path(
                value, DEFAULT_SPEAKER_FILTER_ENROLLMENT_DIR
            )
        elif key == "speaker_filter_negative_dir":
            merged[key] = _normalize_nonempty_path(
                value, DEFAULT_SPEAKER_FILTER_NEGATIVE_DIR
            )
        elif key == "speaker_filter_apply_to":
            merged[key] = _normalize_speaker_filter_apply_to(value)
        else:
            merged[key] = value

    if source_has_hotkey_profiles:
        merged["record_keys"] = record_keys_from_hotkey_profiles(
            merged.get("hotkey_profiles"), fallback=merged.get("record_keys")
        )
    else:
        merged["hotkey_profiles"] = normalize_hotkey_profiles(
            None, record_keys=merged.get("record_keys", DEFAULT_RECORD_KEYS)
        )
    return merged


def runtime_mode_for_settings(settings):
    return "combined" if settings.get("enable_wakeword_detection", False) else "keyboard"


def build_backend_environment(settings, base_env=None):
    env = dict(os.environ if base_env is None else base_env)
    record_keys = settings.get("record_keys", DEFAULT_RECORD_KEYS)
    if "hotkey_profiles" in settings:
        record_keys = record_keys_from_hotkey_profiles(
            settings.get("hotkey_profiles"), fallback=record_keys
        )
    env["WKEY_RECORD_KEYS"] = normalize_record_keys(
        record_keys
    )
    env["WKEY_HOTKEY_PROFILES"] = hotkey_profiles_for_environment(
        settings.get("hotkey_profiles")
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
