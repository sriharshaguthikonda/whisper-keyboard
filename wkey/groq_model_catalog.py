import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_USER_AGENT = "whisper-keyboard-groq-model-catalog/1.0"
CACHE_PATH = Path(__file__).with_name("groq_model_catalog_cache.json")

MODEL_ALIASES = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama-3.3-70b": "llama-3.3-70b-versatile",
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "gpt-oss-120b": "openai/gpt-oss-120b",
}

DEFAULT_TOOL_USE_PREFERRED_MODELS = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
)

DEFAULT_AUDIO_STT_PREFERRED_MODELS = (
    "whisper-large-v3-turbo",
    "whisper-large-v3",
)

KNOWN_TOOL_USE_MODELS = frozenset(DEFAULT_TOOL_USE_PREFERRED_MODELS)


@dataclass(frozen=True)
class ModelCatalogResult:
    models: tuple[str, ...]
    source: str
    error: str | None = None
    tool_use_models: tuple[str, ...] = ()
    audio_stt_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelErrorClassification:
    is_model_error: bool
    reason: str
    is_rate_limit: bool = False


def normalize_model_name(model: str) -> str:
    value = (model or "").strip()
    return MODEL_ALIASES.get(value, value)


def _clean_models(models: Iterable[str]) -> tuple[str, ...]:
    cleaned = []
    seen = set()
    for model in models:
        normalized = normalize_model_name(str(model))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return tuple(cleaned)


def _rank_available_models(
    models: Iterable[str],
    preferred_models: tuple[str, ...],
    predicate,
    *,
    include_unranked: bool,
) -> tuple[str, ...]:
    available = set(_clean_models(models))
    selected = []

    for preferred in preferred_models:
        normalized = normalize_model_name(preferred)
        if normalized in available and predicate(normalized):
            selected.append(normalized)

    if include_unranked:
        for model in _clean_models(models):
            if predicate(model) and model not in selected:
                selected.append(model)

    return tuple(selected)


def build_task_model_groups(models: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    cleaned = _clean_models(models)
    return (
        _rank_available_models(
            cleaned,
            DEFAULT_TOOL_USE_PREFERRED_MODELS,
            _is_tool_use_candidate,
            include_unranked=False,
        ),
        _rank_available_models(
            cleaned,
            DEFAULT_AUDIO_STT_PREFERRED_MODELS,
            _is_audio_stt_candidate,
            include_unranked=True,
        ),
    )


def _catalog_result(
    *,
    models: Iterable[str],
    source: str,
    error: str | None = None,
) -> ModelCatalogResult:
    cleaned = _clean_models(models)
    tool_use_models, audio_stt_models = build_task_model_groups(cleaned)
    return ModelCatalogResult(
        models=cleaned,
        source=source,
        error=error,
        tool_use_models=tool_use_models,
        audio_stt_models=audio_stt_models,
    )


def list_groq_models(
    api_key: str,
    *,
    base_url: str = GROQ_BASE_URL,
    timeout_seconds: float = 10.0,
) -> tuple[str, ...]:
    if not api_key:
        raise RuntimeError("missing_api_key")

    endpoint = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": GROQ_USER_AGENT,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"http_{error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"url_error:{error.reason}") from error
    except TimeoutError as error:
        raise RuntimeError("timeout") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("invalid_json") from error

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("invalid_models_payload")

    return tuple(
        sorted(
            {
                normalize_model_name(item.get("id", ""))
                for item in data
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and item.get("id", "").strip()
            }
        )
    )


def load_cached_catalog(
    *,
    cache_path: Path = CACHE_PATH,
    max_age_seconds: int = 86400,
    now: float | None = None,
) -> ModelCatalogResult:
    if now is None:
        now = time.time()
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _catalog_result(models=(), source="missing_cache", error="missing_cache")
    except Exception as error:
        return _catalog_result(models=(), source="bad_cache", error=str(error))

    saved_at = float(payload.get("saved_at", 0))
    models = _clean_models(payload.get("models", ()))
    if not models:
        return _catalog_result(models=(), source="bad_cache", error="empty_cache")
    if now - saved_at > max_age_seconds:
        return _catalog_result(models=(), source="expired_cache", error="expired_cache")
    return _catalog_result(models=models, source="cache", error=None)


def save_cached_catalog(
    models: Iterable[str],
    *,
    cache_path: Path = CACHE_PATH,
    base_url: str = GROQ_BASE_URL,
    now: float | None = None,
) -> None:
    if now is None:
        now = time.time()
    cleaned = _clean_models(models)
    cache_path.write_text(
        json.dumps(
            {
                "saved_at": now,
                "base_url": base_url,
                "models": list(cleaned),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def get_groq_model_catalog(
    api_key: str | None,
    *,
    force_refresh: bool = False,
    cache_ttl_seconds: int | None = None,
    timeout_seconds: float = 10.0,
    cache_path: Path = CACHE_PATH,
    base_url: str = GROQ_BASE_URL,
) -> ModelCatalogResult:
    if cache_ttl_seconds is None:
        cache_ttl_seconds = int(os.getenv("GROQ_MODEL_CATALOG_TTL_SECONDS", "86400"))

    if not force_refresh:
        cached = load_cached_catalog(
            cache_path=cache_path,
            max_age_seconds=cache_ttl_seconds,
        )
        if cached.models:
            return cached

    try:
        models = list_groq_models(
            api_key or "",
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        save_cached_catalog(models, cache_path=cache_path, base_url=base_url)
        return _catalog_result(models=models, source="live", error=None)
    except Exception as error:
        stale = load_cached_catalog(
            cache_path=cache_path,
            max_age_seconds=315360000,
        )
        if stale.models:
            return _catalog_result(
                models=stale.models,
                source="stale_cache",
                error=str(error),
            )
        return _catalog_result(models=(), source="configured", error=str(error))


def _is_tool_use_candidate(model: str) -> bool:
    lowered = model.lower()
    blocked = (
        "whisper",
        "tts",
        "audio",
        "speech",
        "guard",
        "safeguard",
        "compound",
        "orpheus",
    )
    return lowered in KNOWN_TOOL_USE_MODELS and not any(token in lowered for token in blocked)


def _is_audio_stt_candidate(model: str) -> bool:
    return "whisper" in model.lower()


def _filter_models(
    *,
    configured_models: Iterable[str],
    catalog: ModelCatalogResult,
    preferred_models: tuple[str, ...],
    predicate,
) -> tuple[str, ...]:
    configured = _clean_models(configured_models)
    if not catalog.models:
        return configured

    ranked = _rank_available_models(
        catalog.models,
        preferred_models,
        predicate,
        include_unranked=predicate is _is_audio_stt_candidate,
    )
    if ranked:
        return ranked

    available = set(catalog.models)
    configured_available = [
        model for model in configured if model in available and predicate(model)
    ]
    return tuple(configured_available) or configured


def filter_tool_use_models(
    *,
    configured_models: Iterable[str],
    catalog: ModelCatalogResult,
) -> tuple[str, ...]:
    return _filter_models(
        configured_models=configured_models,
        catalog=catalog,
        preferred_models=DEFAULT_TOOL_USE_PREFERRED_MODELS,
        predicate=_is_tool_use_candidate,
    )


def filter_audio_stt_models(
    *,
    configured_models: Iterable[str],
    catalog: ModelCatalogResult,
) -> tuple[str, ...]:
    return _filter_models(
        configured_models=configured_models,
        catalog=catalog,
        preferred_models=DEFAULT_AUDIO_STT_PREFERRED_MODELS,
        predicate=_is_audio_stt_candidate,
    )


def classify_groq_model_error(status: int, response_text: str) -> ModelErrorClassification:
    lowered = (response_text or "").lower()
    if status == 429 or "rate limit" in lowered or "rate_limit" in lowered:
        return ModelErrorClassification(
            False,
            f"rate_limit_http_{status}",
            is_rate_limit=True,
        )
    if status == 400 and (
        "tool_use_failed" in lowered or "failed to call a function" in lowered
    ):
        return ModelErrorClassification(True, "tool_use_failed_http_400")
    if status in (400, 404) and any(
        token in lowered
        for token in (
            "model",
            "does not exist",
            "not found",
            "decommission",
            "not supported",
            "invalid model",
        )
    ):
        return ModelErrorClassification(True, f"model_unavailable_http_{status}")
    if status == 404 and not lowered.strip():
        return ModelErrorClassification(True, "model_or_endpoint_unavailable_http_404")
    return ModelErrorClassification(False, f"http_{status}")
