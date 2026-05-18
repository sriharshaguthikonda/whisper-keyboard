import itertools
import logging
import os
import threading
import time
from typing import Callable, Iterable

try:
    from groq_model_catalog import (
        ModelCatalogResult,
        filter_audio_stt_models,
        filter_tool_use_models,
        get_groq_model_catalog,
    )
except ModuleNotFoundError:
    from wkey.groq_model_catalog import (
        ModelCatalogResult,
        filter_audio_stt_models,
        filter_tool_use_models,
        get_groq_model_catalog,
    )


DEFAULT_BAD_MODEL_COOLDOWN_SECONDS = int(
    os.getenv("GROQ_BAD_MODEL_COOLDOWN_SECONDS", "3600")
)


class ModelRotator:
    def __init__(
        self,
        name: str,
        models: Iterable[str],
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.name = name
        self._clock = clock
        self._lock = threading.Lock()
        self._quarantined_until = {}
        self.update_models(list(models))

    def update_models(self, models):
        cleaned = [model for model in models if model]
        if not cleaned:
            raise ValueError(f"Model list for {self.name} must not be empty")

        with self._lock:
            self.models = cleaned
            self._cycle = itertools.cycle(self.models)
            now = self._clock()
            self._quarantined_until = {
                model: expires_at
                for model, expires_at in self._quarantined_until.items()
                if model in self.models and expires_at > now
            }

    def mark_unavailable(
        self,
        model: str,
        reason: str,
        *,
        cooldown_seconds: int = DEFAULT_BAD_MODEL_COOLDOWN_SECONDS,
    ) -> None:
        if not model:
            return
        expires_at = self._clock() + max(1, int(cooldown_seconds))
        with self._lock:
            self._quarantined_until[model] = expires_at

        logging.warning(
            "[ModelRotator] Quarantined %s model %s for %ss: %s",
            self.name,
            model,
            cooldown_seconds,
            reason,
        )

    def _is_quarantined_locked(self, model: str, now: float) -> bool:
        expires_at = self._quarantined_until.get(model)
        if expires_at is None:
            return False
        if expires_at <= now:
            self._quarantined_until.pop(model, None)
            return False
        return True

    def next(self) -> str:
        with self._lock:
            now = self._clock()
            for _ in range(len(self.models)):
                model = next(self._cycle)
                if not self._is_quarantined_locked(model, now):
                    logging.info("[ModelRotator] Using %s model: %s", self.name, model)
                    return model
            fallback_model = self.models[0]

        logging.warning(
            "[ModelRotator] All %s models are quarantined; using first configured model once: %s",
            self.name,
            fallback_model,
        )
        return fallback_model


# Tool-use models (as configured in voice_commands)
TOOL_USE_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

# Audio/STT models for Groq whisper endpoint
AUDIO_STT_MODELS = [
    "whisper-large-v3",
]

tool_use_rotator = ModelRotator("tool_use", TOOL_USE_MODELS)
audio_stt_rotator = ModelRotator("audio_transcription", AUDIO_STT_MODELS)
_catalog_lock = threading.Lock()
_last_catalog_result = ModelCatalogResult(models=(), source="configured", error=None)


def refresh_groq_model_rotators(
    api_key: str | None,
    *,
    force_refresh: bool = False,
) -> ModelCatalogResult:
    global _last_catalog_result
    with _catalog_lock:
        catalog = get_groq_model_catalog(api_key, force_refresh=force_refresh)
        tool_models = filter_tool_use_models(
            configured_models=TOOL_USE_MODELS,
            catalog=catalog,
        )
        audio_models = filter_audio_stt_models(
            configured_models=AUDIO_STT_MODELS,
            catalog=catalog,
        )
        tool_use_rotator.update_models(list(tool_models))
        audio_stt_rotator.update_models(list(audio_models))
        _last_catalog_result = catalog

        if catalog.error:
            logging.warning(
                "[ModelRotator] Groq model catalog source=%s error=%s",
                catalog.source,
                catalog.error,
            )
        else:
            logging.info(
                "[ModelRotator] Groq model catalog source=%s models=%d",
                catalog.source,
                len(catalog.models),
            )
        return catalog


def note_tool_use_model_failure(model: str, reason: str) -> None:
    tool_use_rotator.mark_unavailable(model, reason)


def note_audio_stt_model_failure(model: str, reason: str) -> None:
    audio_stt_rotator.mark_unavailable(model, reason)


def next_tool_use_model() -> str:
    return tool_use_rotator.next()


def next_audio_stt_model() -> str:
    return audio_stt_rotator.next()
