"""UI-independent state helpers for the Qt control center."""

from __future__ import annotations

import copy
import os
from typing import Mapping

try:
    from .settings_manager import (
        DEFAULT_SETTINGS,
        normalize_hotkey_profiles,
        normalize_record_keys,
        record_key_display_text,
        record_keys_from_hotkey_profiles,
        runtime_mode_for_settings,
    )
except ImportError:
    from settings_manager import (
        DEFAULT_SETTINGS,
        normalize_hotkey_profiles,
        normalize_record_keys,
        record_key_display_text,
        record_keys_from_hotkey_profiles,
        runtime_mode_for_settings,
    )


BOOLEAN_SETTING_FIELDS = (
    "use_local_gpu",
    "use_local_cpu",
    "fallback_to_groq",
    "enable_edge_selenium",
    "enable_wakeword_detection",
    "enable_pre_recording_keyword_check",
    "enable_transcript_context_memory",
)

INTEGER_SETTING_LIMITS = {
    "max_retries": (1, 20),
    "stt_context_items": (1, 8),
    "stt_context_chars": (40, 800),
    "router_context_items": (1, 8),
    "router_context_chars": (80, 1200),
    "context_max_age_seconds": (15, 3600),
    "max_recording_seconds": (1, 600),
}

FLOAT_SETTING_LIMITS = {
    "google_wake_volume_hold_seconds": (0.0, 30.0),
}

ADVANCED_SETTING_FIELDS = tuple(INTEGER_SETTING_LIMITS) + tuple(FLOAT_SETTING_LIMITS)
THEME_MODES = ("system", "dark", "light")


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_theme_mode(value):
    mode = str(value or "system").strip().lower()
    return mode if mode in THEME_MODES else "system"


def _clamp_int(value, minimum, maximum):
    try:
        parsed = int(value)
    except Exception:
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def _clamp_float(value, minimum, maximum):
    try:
        parsed = float(value)
    except Exception:
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def provider_status(env: Mapping[str, str] | None = None):
    values = os.environ if env is None else env
    return {
        "groq": "configured" if values.get("GROQ_API_KEY") else "missing",
        "local": "available",
    }


def apply_settings_values(settings: Mapping[str, object], values: Mapping[str, object]):
    updated = copy.deepcopy(DEFAULT_SETTINGS)
    updated.update(copy.deepcopy(dict(settings or {})))

    for key in BOOLEAN_SETTING_FIELDS:
        if key in values:
            updated[key] = _coerce_bool(values[key])

    for key, (minimum, maximum) in INTEGER_SETTING_LIMITS.items():
        if key in values:
            updated[key] = _clamp_int(values[key], minimum, maximum)

    for key, (minimum, maximum) in FLOAT_SETTING_LIMITS.items():
        if key in values:
            updated[key] = _clamp_float(values[key], minimum, maximum)

    if "record_keys" in values:
        updated["record_keys"] = normalize_record_keys(values["record_keys"])

    if "ui_theme" in values:
        updated["ui_theme"] = _normalize_theme_mode(values["ui_theme"])

    if "minimize_to_tray" in values:
        updated["minimize_to_tray"] = _coerce_bool(values["minimize_to_tray"])

    profile_source = values.get("hotkey_profiles", updated.get("hotkey_profiles"))
    updated["hotkey_profiles"] = normalize_hotkey_profiles(
        profile_source, record_keys=updated.get("record_keys")
    )
    updated["record_keys"] = record_keys_from_hotkey_profiles(
        updated["hotkey_profiles"], fallback=updated.get("record_keys")
    )
    return updated


def build_settings_snapshot(settings: Mapping[str, object], env=None):
    normalized = apply_settings_values({}, dict(settings or {}))
    return {
        "runtime_mode": runtime_mode_for_settings(normalized),
        "record_keys": normalized["record_keys"],
        "active_keys": record_key_display_text(normalized["record_keys"]),
        "hotkey_profiles": copy.deepcopy(normalized["hotkey_profiles"]),
        "advanced": {
            key: normalized[key]
            for key in ADVANCED_SETTING_FIELDS
            if key in normalized
        },
        "providers": provider_status(env),
    }
