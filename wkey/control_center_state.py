"""UI-independent state helpers for the Qt control center."""

from __future__ import annotations

import copy
import os
from typing import Mapping

try:
    from .settings_manager import (
        ASK_HOTKEY_PROVIDERS,
        DEFAULT_SETTINGS,
        SPEAKER_FILTER_MODES,
        normalize_hotkey_profiles,
        normalize_record_keys,
        record_key_display_text,
        record_keys_from_hotkey_profiles,
        runtime_mode_for_settings,
    )
except ImportError:
    from settings_manager import (
        ASK_HOTKEY_PROVIDERS,
        DEFAULT_SETTINGS,
        SPEAKER_FILTER_MODES,
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
    "ask_ai_enabled",
    "ask_chatgpt_fallback_to_ai",
)

SPEAKER_FILTER_PATH_FIELDS = (
    "speaker_filter_profile_path",
    "speaker_filter_enrollment_dir",
    "speaker_filter_negative_dir",
)

INTEGER_SETTING_LIMITS = {
    "max_retries": (1, 20),
    "stt_context_items": (1, 8),
    "stt_context_chars": (40, 800),
    "router_context_items": (1, 8),
    "router_context_chars": (80, 1200),
    "context_max_age_seconds": (15, 3600),
    "max_recording_seconds": (1, 600),
    "ask_chatgpt_claim_timeout_sec": (1, 60),
}

FLOAT_SETTING_LIMITS = {
    "google_wake_volume_hold_seconds": (0.0, 30.0),
    "manual_pre_recording_seconds": (0.0, 5.0),
    "wake_pre_recording_seconds": (0.0, 10.0),
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


def _normalize_speaker_filter_mode(value):
    mode = str(value or "analysis").strip().lower()
    return mode if mode in SPEAKER_FILTER_MODES else "analysis"


def _normalize_ask_hotkey_provider(value):
    provider = str(value or "chatgpt").strip().lower()
    return provider if provider in ASK_HOTKEY_PROVIDERS else "chatgpt"


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


def _normalize_path(value, default):
    text = str(value or "").strip()
    return text or default


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

    if "speaker_filter_enabled" in values:
        updated["speaker_filter_enabled"] = _coerce_bool(
            values["speaker_filter_enabled"]
        )

    if "speaker_filter_mode" in values:
        updated["speaker_filter_mode"] = _normalize_speaker_filter_mode(
            values["speaker_filter_mode"]
        )

    if "speaker_filter_threshold" in values:
        updated["speaker_filter_threshold"] = _clamp_float(
            values["speaker_filter_threshold"], 0.0, 1.0
        )

    for key in SPEAKER_FILTER_PATH_FIELDS:
        if key in values:
            updated[key] = _normalize_path(values[key], DEFAULT_SETTINGS[key])

    if "speaker_filter_apply_to" in values:
        updated["speaker_filter_apply_to"] = "dictation"

    if "ask_hotkey_provider" in values:
        updated["ask_hotkey_provider"] = _normalize_ask_hotkey_provider(
            values["ask_hotkey_provider"]
        )

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
        "speaker_filter": {
            "enabled": normalized["speaker_filter_enabled"],
            "mode": normalized["speaker_filter_mode"],
            "threshold": normalized["speaker_filter_threshold"],
            "profile_path": normalized["speaker_filter_profile_path"],
            "enrollment_dir": normalized["speaker_filter_enrollment_dir"],
            "negative_dir": normalized["speaker_filter_negative_dir"],
            "apply_to": normalized["speaker_filter_apply_to"],
        },
    }
