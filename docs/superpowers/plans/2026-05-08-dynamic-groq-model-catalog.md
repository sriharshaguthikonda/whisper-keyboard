# Dynamic Groq Model Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop F24/tool-use and Groq STT from failing repeatedly when a hardcoded Groq model is removed, renamed, or unavailable.

**Architecture:** Add a Groq model catalog module that reads `/openai/v1/models`, caches model IDs without secrets, filters task-specific model lists, and quarantines failing models for a cooldown. Keep `voice_commands.py` and `transcription_utils.py` as callers; move model availability logic into `model_rotation.py` plus the new catalog module.

**Tech Stack:** Python stdlib (`urllib.request`, `json`, `pathlib`, `time`, `threading`), existing `aiohttp`, existing `pytest`, existing Groq OpenAI-compatible endpoints.

---

## Start Gate

- [ ] Run this from the repo root:

```powershell
Set-Location 'C:\Windows_software\openai whisper\whisper-keyboard'
git status --short --branch
```

Expected: branch is `refactor/clean-architecture`. Worktree may include this plan file if it was not committed yet. Do not revert unrelated local changes.

- [ ] Confirm the failure being addressed is the tool-use model path:

```powershell
Select-String -Path 'wkey\voice_commands.py' -Pattern 'next_tool_use_model|chat/completions|execute_command_run_with_tool' -CaseSensitive:$false -Context 2,4
```

Expected: `execute_command_run_with_tool()` calls `next_tool_use_model()` and posts to `https://api.groq.com/openai/v1/chat/completions`.

- [ ] Confirm the current static rotator:

```powershell
Get-Content -Path 'wkey\model_rotation.py'
```

Expected: hardcoded `TOOL_USE_MODELS` and `AUDIO_STT_MODELS`.

## Files

- Create: `wkey/groq_model_catalog.py`
- Modify: `wkey/model_rotation.py`
- Modify: `wkey/voice_commands.py`
- Modify: `wkey/transcription_utils.py`
- Modify: `wkey/faster_whisper_Mother_of_all_wkey.py`
- Modify: `.gitignore`
- Modify: `README.md`
- Create: `tests/test_groq_model_catalog.py`
- Create: `tests/test_model_rotation.py`
- Modify or create: `tests/test_transcription_utils.py`

## Design Rules

- Do not send user transcripts, commands, prompts, audio, or secrets to any new endpoint.
- The only discovery call is `GET https://api.groq.com/openai/v1/models` with the existing `GROQ_API_KEY`.
- Cache only public model IDs, timestamp, base URL, and error string.
- Never cache API keys.
- A model-specific 400 or 404 should quarantine only that model and immediately try another model.
- A `/models` discovery failure should fall back to the last cache, then the configured list.
- If every model is quarantined, use the configured first model once and log that all models are quarantined. This prevents a permanent silent dead end.
- Keep network discovery optional and bounded with short timeouts.
- Do not add new third-party dependencies.

## Patient Avatar Pattern To Reuse

Use these local files as the known-good pattern source:

- `C:\Windows_software\Patient_Avatar\services\agent\src\agent_groq_key_pool.py`
- `C:\Windows_software\Patient_Avatar\services\agent\src\agent_config.py`
- `C:\Windows_software\Patient_Avatar\services\agent\src\agent_model_fallbacks.py`

The relevant pattern is:

- call `GET {base_url}/models`;
- parse `payload["data"][].id`;
- sort and deduplicate model IDs;
- if the catalog is known, drop configured models that are not available;
- choose task-specific fallbacks by predicate when the requested model is unavailable;
- log model-resolution notes without logging secrets.

## Task 1: Add Pure Groq Catalog Tests

**Files:**
- Create: `tests/test_groq_model_catalog.py`
- Create: `wkey/groq_model_catalog.py`

- [ ] Add this failing test file:

```python
import json
import urllib.error

import pytest

from wkey.groq_model_catalog import (
    ModelCatalogResult,
    classify_groq_model_error,
    filter_audio_stt_models,
    filter_tool_use_models,
    list_groq_models,
    normalize_model_name,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_list_groq_models_parses_sorted_unique_ids(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout, request.headers))
        return FakeResponse(
            {
                "data": [
                    {"id": "whisper-large-v3"},
                    {"id": "openai/gpt-oss-120b"},
                    {"id": "openai/gpt-oss-120b"},
                    {"id": ""},
                    {"not_id": "ignored"},
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    models = list_groq_models("gsk-test", timeout_seconds=3.0)

    assert models == ("openai/gpt-oss-120b", "whisper-large-v3")
    assert calls[0][0] == "https://api.groq.com/openai/v1/models"
    assert calls[0][1] == 3.0
    assert calls[0][2]["Authorization"] == "Bearer gsk-test"


def test_list_groq_models_raises_runtime_error_for_http_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="http_401"):
        list_groq_models("bad-key")


def test_filter_tool_use_models_prefers_configured_available_models():
    catalog = ModelCatalogResult(
        models=(
            "llama-3.3-70b-versatile",
            "openai/gpt-oss-120b",
            "whisper-large-v3",
        ),
        source="live",
        error=None,
    )

    resolved = filter_tool_use_models(
        configured_models=(
            "decommissioned-model",
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
        ),
        catalog=catalog,
    )

    assert resolved == ("openai/gpt-oss-120b", "llama-3.3-70b-versatile")


def test_filter_tool_use_models_uses_catalog_fallback_when_configured_are_missing():
    catalog = ModelCatalogResult(
        models=(
            "prompt-guard-86m",
            "whisper-large-v3",
            "qwen/qwen3-32b",
            "openai/gpt-oss-20b",
        ),
        source="live",
        error=None,
    )

    resolved = filter_tool_use_models(
        configured_models=("decommissioned-model",),
        catalog=catalog,
    )

    assert resolved == ("openai/gpt-oss-20b", "qwen/qwen3-32b")


def test_filter_audio_stt_models_keeps_only_whisper_models():
    catalog = ModelCatalogResult(
        models=("openai/gpt-oss-120b", "whisper-large-v3", "whisper-large-v3-turbo"),
        source="live",
        error=None,
    )

    resolved = filter_audio_stt_models(
        configured_models=("old-whisper", "whisper-large-v3"),
        catalog=catalog,
    )

    assert resolved == ("whisper-large-v3", "whisper-large-v3-turbo")


def test_filter_models_falls_back_to_configured_when_catalog_unknown():
    catalog = ModelCatalogResult(models=(), source="configured", error="timeout")

    assert filter_tool_use_models(
        configured_models=("model-a", "model-b"),
        catalog=catalog,
    ) == ("model-a", "model-b")


def test_normalize_model_name_maps_legacy_aliases():
    assert normalize_model_name("llama3-70b-8192") == "llama-3.3-70b-versatile"
    assert normalize_model_name(" gpt-oss-120b ") == "openai/gpt-oss-120b"


def test_classify_groq_model_error_detects_removed_model_body():
    body = '{"error":{"message":"The model moonshotai/kimi-k2-instruct-0905 does not exist"}}'

    result = classify_groq_model_error(404, body)

    assert result.is_model_error is True
    assert "model" in result.reason


def test_classify_groq_model_error_does_not_hide_auth_errors():
    result = classify_groq_model_error(401, '{"error":{"message":"invalid api key"}}')

    assert result.is_model_error is False
```

- [ ] Run the new tests and confirm they fail because the module is missing:

```powershell
python -m pytest tests\test_groq_model_catalog.py -q
```

Expected: import failure for `wkey.groq_model_catalog`.

## Task 2: Implement `wkey/groq_model_catalog.py`

**Files:**
- Create: `wkey/groq_model_catalog.py`

- [ ] Add this module:

```python
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
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
)

DEFAULT_AUDIO_STT_PREFERRED_MODELS = (
    "whisper-large-v3-turbo",
    "whisper-large-v3",
)


@dataclass(frozen=True)
class ModelCatalogResult:
    models: tuple[str, ...]
    source: str
    error: str | None = None


@dataclass(frozen=True)
class ModelErrorClassification:
    is_model_error: bool
    reason: str


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
                if isinstance(item, dict) and isinstance(item.get("id"), str)
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
        return ModelCatalogResult(models=(), source="missing_cache", error="missing_cache")
    except Exception as error:
        return ModelCatalogResult(models=(), source="bad_cache", error=str(error))

    saved_at = float(payload.get("saved_at", 0))
    models = _clean_models(payload.get("models", ()))
    if not models:
        return ModelCatalogResult(models=(), source="bad_cache", error="empty_cache")
    if now - saved_at > max_age_seconds:
        return ModelCatalogResult(models=(), source="expired_cache", error="expired_cache")
    return ModelCatalogResult(models=models, source="cache", error=None)


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
        return ModelCatalogResult(models=models, source="live", error=None)
    except Exception as error:
        stale = load_cached_catalog(
            cache_path=cache_path,
            max_age_seconds=315360000,
        )
        if stale.models:
            return ModelCatalogResult(
                models=stale.models,
                source="stale_cache",
                error=str(error),
            )
        return ModelCatalogResult(models=(), source="configured", error=str(error))


def _is_tool_use_candidate(model: str) -> bool:
    lowered = model.lower()
    blocked = ("whisper", "tts", "audio", "speech", "guard", "safeguard")
    return not any(token in lowered for token in blocked)


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

    available = set(catalog.models)
    selected = [model for model in configured if model in available]

    for preferred in preferred_models:
        normalized = normalize_model_name(preferred)
        if normalized in available and normalized not in selected:
            selected.append(normalized)

    for model in catalog.models:
        if predicate(model) and model not in selected:
            selected.append(model)

    return tuple(selected) or configured


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
```

- [ ] Run the catalog tests:

```powershell
python -m pytest tests\test_groq_model_catalog.py -q
```

Expected: all tests pass.

## Task 3: Upgrade `model_rotation.py` To Dynamic Catalog And Quarantine

**Files:**
- Modify: `wkey/model_rotation.py`
- Create: `tests/test_model_rotation.py`

- [ ] Add this failing test file:

```python
import time

from wkey.model_rotation import ModelRotator, refresh_groq_model_rotators


def test_model_rotator_skips_quarantined_model_until_cooldown_expires():
    now = [100.0]
    rotator = ModelRotator("tool_use", ["bad-model", "good-model"], clock=lambda: now[0])

    assert rotator.next() == "bad-model"

    rotator.mark_unavailable("bad-model", "model_unavailable_http_404", cooldown_seconds=60)

    assert rotator.next() == "good-model"

    now[0] = 161.0

    assert rotator.next() == "bad-model"


def test_model_rotator_falls_back_when_all_models_are_quarantined():
    rotator = ModelRotator("tool_use", ["model-a"], clock=lambda: 10.0)
    rotator.mark_unavailable("model-a", "model_unavailable_http_404", cooldown_seconds=60)

    assert rotator.next() == "model-a"


def test_refresh_groq_model_rotators_filters_catalog(monkeypatch):
    from wkey import model_rotation
    from wkey.groq_model_catalog import ModelCatalogResult

    monkeypatch.setattr(
        model_rotation,
        "get_groq_model_catalog",
        lambda api_key, force_refresh=False: ModelCatalogResult(
            models=("openai/gpt-oss-120b", "whisper-large-v3"),
            source="live",
            error=None,
        ),
    )

    result = refresh_groq_model_rotators("gsk-test", force_refresh=True)

    assert result.source == "live"
    assert model_rotation.next_tool_use_model() == "openai/gpt-oss-120b"
    assert model_rotation.next_audio_stt_model() == "whisper-large-v3"
```

- [ ] Run the tests and confirm they fail because `mark_unavailable` and `refresh_groq_model_rotators` do not exist:

```powershell
python -m pytest tests\test_model_rotation.py -q
```

Expected: failures for missing behavior.

- [ ] Replace `wkey/model_rotation.py` with this implementation:

```python
import itertools
import logging
import os
import threading
import time
from typing import Callable, Iterable, List

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
        self._lock = threading.Lock()
        self._clock = clock
        self._quarantined_until: dict[str, float] = {}
        self.update_models(list(models))

    def update_models(self, models: List[str]):
        cleaned = [m for m in models if m]
        if not cleaned:
            raise ValueError(f"Model list for {self.name} must not be empty")
        with self._lock:
            self.models = cleaned
            self._cycle = itertools.cycle(self.models)
            self._quarantined_until = {
                model: expires_at
                for model, expires_at in self._quarantined_until.items()
                if model in self.models and expires_at > self._clock()
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
            model = self.models[0]
        logging.warning(
            "[ModelRotator] All %s models are quarantined; using first configured model once: %s",
            self.name,
            model,
        )
        return model


TOOL_USE_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

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
```

- [ ] Run:

```powershell
python -m pytest tests\test_model_rotation.py tests\test_groq_model_catalog.py -q
```

Expected: all tests pass.

## Task 4: Wire Tool-Use Chat Failover In `voice_commands.py`

**Files:**
- Modify: `wkey/voice_commands.py`
- Create or modify: `tests/test_voice_commands_model_errors.py`

- [ ] Add this test file for the pure error classifier import through `voice_commands.py`:

```python
from wkey.groq_model_catalog import classify_groq_model_error


def test_tool_use_404_model_error_is_recoverable():
    body = '{"error":{"message":"model moonshotai/kimi-k2-instruct-0905 not found"}}'

    result = classify_groq_model_error(404, body)

    assert result.is_model_error
    assert result.reason == "model_unavailable_http_404"


def test_tool_use_rate_limit_is_not_model_quarantine():
    body = '{"error":{"message":"rate limit exceeded"}}'

    result = classify_groq_model_error(429, body)

    assert result.is_model_error is False
```

- [ ] Change the import in `wkey/voice_commands.py` from:

```python
from model_rotation import next_tool_use_model
```

to:

```python
from model_rotation import (
    next_tool_use_model,
    note_tool_use_model_failure,
    refresh_groq_model_rotators,
)
from groq_model_catalog import classify_groq_model_error
```

- [ ] If package imports fail in tests, use this compatible import block instead:

```python
try:
    from model_rotation import (
        next_tool_use_model,
        note_tool_use_model_failure,
        refresh_groq_model_rotators,
    )
    from groq_model_catalog import classify_groq_model_error
except ModuleNotFoundError:
    from wkey.model_rotation import (
        next_tool_use_model,
        note_tool_use_model_failure,
        refresh_groq_model_rotators,
    )
    from wkey.groq_model_catalog import classify_groq_model_error
```

- [ ] Inside `execute_command_run_with_tool()`, just before the retry loop that starts `for attempt in range(max_retries):`, add:

```python
        try:
            refresh_groq_model_rotators(api_key)
        except Exception as e:
            logging.warning(
                "%sGroq model catalog refresh failed before tool-use request: %s%s",
                YELLOW,
                e,
                RESET,
            )
```

- [ ] In the `session.post(...) as response:` block, replace the current `if response.status == 404:` block and `response.raise_for_status()` with:

```python
                        if response.status >= 400:
                            response_text = await response.text()
                            classification = classify_groq_model_error(
                                response.status,
                                response_text,
                            )
                            logging.error(
                                "Groq tool-use API error %s %s for model %s: %s",
                                response.status,
                                response.reason,
                                tool_model,
                                response_text[:500],
                            )
                            if classification.is_model_error:
                                note_tool_use_model_failure(
                                    tool_model,
                                    classification.reason,
                                )
                                try:
                                    refresh_groq_model_rotators(api_key, force_refresh=True)
                                except Exception as refresh_error:
                                    logging.warning(
                                        "%sGroq model catalog force-refresh failed after %s: %s%s",
                                        YELLOW,
                                        classification.reason,
                                        refresh_error,
                                        RESET,
                                    )
                                if attempt < max_retries - 1:
                                    continue
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status,
                                message=response.reason,
                                headers=response.headers,
                            )
                        response_data = await response.json()
```

- [ ] Ensure the old duplicate line below the block is removed:

```python
                        response_data = await response.json()
```

- [ ] Run:

```powershell
python -m pytest tests\test_voice_commands_model_errors.py tests\test_model_rotation.py tests\test_groq_model_catalog.py -q
```

Expected: all tests pass.

## Task 5: Wire Groq STT Model Failover

**Files:**
- Modify: `wkey/transcription_utils.py`
- Modify: `wkey/faster_whisper_Mother_of_all_wkey.py`
- Create or modify: `tests/test_transcription_utils.py`

- [ ] Add or update tests in `tests/test_transcription_utils.py` with this content:

```python
import io

import pytest

from wkey.groq_model_catalog import classify_groq_model_error


def test_stt_404_model_error_is_recoverable():
    body = '{"error":{"message":"model whisper-old is not supported"}}'

    result = classify_groq_model_error(400, body)

    assert result.is_model_error
    assert result.reason == "model_unavailable_http_400"
```

- [ ] In `wkey/transcription_utils.py`, add imports near the top:

```python
try:
    from groq_model_catalog import classify_groq_model_error
except ModuleNotFoundError:
    from wkey.groq_model_catalog import classify_groq_model_error
```

- [ ] Change the signature of `transcribe_pre_recording_buffer()` to include an optional failure callback:

```python
def transcribe_pre_recording_buffer(
    pre_recording_data,
    sample_rate: int,
    api_key: str,
    prompt: str,
    get_groq_audio_model: Callable[[], str],
    max_retries: int = 3,
    retry_delay: int = 2,
    timeout_total: float = 10.0,
    report_model_failure: Optional[Callable[[str, str], None]] = None,
):
```

- [ ] Inside `transcribe_pre_recording_buffer()` move model selection into the retry loop. Replace:

```python
        model_name = get_groq_audio_model()
```

with:

```python
        model_name = None
```

Then add this as the first line inside `for attempt in range(max_retries):`:

```python
                model_name = get_groq_audio_model()
```

- [ ] In `transcribe_pre_recording_buffer()`, replace the `if response.status >= 400:` block with:

```python
                        if response.status >= 400:
                            logging.error(
                                "Groq pre-recording API error %s %s for model %s: %s",
                                response.status,
                                response.reason,
                                model_name,
                                response_text[:500],
                            )
                            classification = classify_groq_model_error(
                                response.status,
                                response_text,
                            )
                            if classification.is_model_error and report_model_failure:
                                report_model_failure(model_name, classification.reason)
                            response.raise_for_status()
```

- [ ] Change the signature of `transcribe_with_groq_async()` to include an optional failure callback:

```python
async def transcribe_with_groq_async(
    byte_io: io.BytesIO,
    keyword_index: Optional[int],
    api_key: str,
    get_groq_audio_model: Callable[[], str],
    prompt: str,
    groq_session_holder: Dict[str, Optional[aiohttp.ClientSession]],
    max_retries: int = 3,
    report_model_failure: Optional[Callable[[str, str], None]] = None,
):
```

- [ ] In `transcribe_with_groq_async()`, replace the single model selection before the loop:

```python
    model_name = get_groq_audio_model()
    logging.info(
        "transcribe_with_groq_async: Starting with model %s (keyword_index=%s)",
        model_name,
        keyword_index,
    )
```

with:

```python
    model_name = None
    logging.info(
        "transcribe_with_groq_async: Starting Groq STT (keyword_index=%s)",
        keyword_index,
    )
```

- [ ] Inside the `for attempt in range(max_retries):` loop, before building form data, add:

```python
            model_name = get_groq_audio_model()
            logging.info(
                "transcribe_with_groq_async: Attempt %d of %d using model %s",
                attempt + 1,
                max_retries,
                model_name,
            )
```

- [ ] In `transcribe_with_groq_async()`, replace the current `if response.status == 404:` and `if response.status >= 400:` blocks with:

```python
                    if response.status >= 400:
                        logging.error(
                            "Groq STT API error %s %s for model %s: %s",
                            response.status,
                            response.reason,
                            model_name,
                            response_text[:500],
                        )
                        classification = classify_groq_model_error(
                            response.status,
                            response_text,
                        )
                        if classification.is_model_error and report_model_failure:
                            report_model_failure(model_name, classification.reason)
                        response.raise_for_status()
```

- [ ] In `wkey/faster_whisper_Mother_of_all_wkey.py`, change the model rotation import from:

```python
    from model_rotation import next_audio_stt_model
```

to:

```python
    from model_rotation import (
        next_audio_stt_model,
        note_audio_stt_model_failure,
        refresh_groq_model_rotators,
    )
```

and change the package fallback import in the same way.

- [ ] After `api_key` is loaded in `wkey/faster_whisper_Mother_of_all_wkey.py`, add:

```python
try:
    refresh_groq_model_rotators(api_key)
except Exception as e:
    logging.warning("Groq model catalog refresh failed during startup: %s", e)
```

- [ ] In `transcribe_pre_recording_buffer()` wrapper in `wkey/faster_whisper_Mother_of_all_wkey.py`, pass the failure callback:

```python
        report_model_failure=note_audio_stt_model_failure,
```

- [ ] In `transcribe_with_groq_async()` wrapper in `wkey/faster_whisper_Mother_of_all_wkey.py`, pass the failure callback:

```python
        report_model_failure=note_audio_stt_model_failure,
```

- [ ] Run:

```powershell
python -m pytest tests\test_transcription_utils.py tests\test_transcription_pipeline.py tests\test_model_rotation.py tests\test_groq_model_catalog.py -q
```

Expected: all tests pass.

## Task 6: Ignore Runtime Cache And Document Config

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] Add this line near the local config section in `.gitignore`:

```gitignore
wkey/groq_model_catalog_cache.json
```

- [ ] Add this section to `README.md` after the Settings GUI section:

```markdown
### Groq model catalog

The app discovers current Groq models from `https://api.groq.com/openai/v1/models` using `GROQ_API_KEY`.

Runtime behavior:

- tool-use models and Groq STT models are filtered against the live catalog when available;
- the catalog is cached in `wkey/groq_model_catalog_cache.json`;
- the cache stores model IDs only, never API keys or transcripts;
- if a model returns a model-specific HTTP 400 or 404, it is quarantined and the next model is tried;
- if catalog refresh fails, the app uses the cache, then the configured defaults.

Optional environment variables:

- `GROQ_MODEL_CATALOG_TTL_SECONDS`: cache freshness window. Default: `86400`.
- `GROQ_BAD_MODEL_COOLDOWN_SECONDS`: bad-model quarantine duration. Default: `3600`.
```

- [ ] Run:

```powershell
Select-String -Path '.gitignore','README.md' -Pattern 'groq_model_catalog_cache|GROQ_MODEL_CATALOG_TTL_SECONDS|GROQ_BAD_MODEL_COOLDOWN_SECONDS'
```

Expected: all three names are present.

## Task 7: Verification

**Files:**
- No additional source edits.

- [ ] Run the focused test set:

```powershell
python -m pytest tests\test_groq_model_catalog.py tests\test_model_rotation.py tests\test_transcription_utils.py tests\test_transcription_pipeline.py -q
```

Expected: all selected tests pass.

- [ ] Run the existing full test set:

```powershell
python -m pytest tests -q
```

Expected: all tests pass. If failures are unrelated environment import failures, capture the exact failing module and traceback in the commit message body or handoff note.

- [ ] Run the primary repo script for a bounded smoke test and stop it before handoff:

```powershell
$proc = Start-Process -FilePath python -ArgumentList 'wkey/faster_whisper_Mother_of_all_wkey.py' -WorkingDirectory 'C:\Windows_software\openai whisper\whisper-keyboard' -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 20
if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force
}
Start-Sleep -Seconds 2
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*python*' } | Select-Object Id,ProcessName,Path
```

Expected: the script starts without immediate import/config errors. No test-run process from this smoke remains running.

- [ ] If `GROQ_API_KEY` is set, run this live catalog smoke:

```powershell
@'
import os
from wkey.model_rotation import refresh_groq_model_rotators, next_tool_use_model, next_audio_stt_model

result = refresh_groq_model_rotators(os.getenv("GROQ_API_KEY"), force_refresh=True)
print("source=", result.source)
print("model_count=", len(result.models))
print("tool_model=", next_tool_use_model())
print("stt_model=", next_audio_stt_model())
'@ | python -
```

Expected: `source= live` or `source= stale_cache`; selected tool and STT models are printed. No API key is printed.

- [ ] Check that the cache is not staged:

```powershell
git status --short
```

Expected: `wkey/groq_model_catalog_cache.json` is absent from staged and unstaged output.

## Task 8: Commit

**Files:**
- All files changed above.

- [ ] Review the diff:

```powershell
git diff --stat
git diff -- .gitignore README.md wkey/groq_model_catalog.py wkey/model_rotation.py wkey/voice_commands.py wkey/transcription_utils.py wkey/faster_whisper_Mother_of_all_wkey.py tests/test_groq_model_catalog.py tests/test_model_rotation.py tests/test_transcription_utils.py
```

Expected: only files listed in this plan changed.

- [ ] Stage only the implementation files:

```powershell
git add .gitignore README.md wkey/groq_model_catalog.py wkey/model_rotation.py wkey/voice_commands.py wkey/transcription_utils.py wkey/faster_whisper_Mother_of_all_wkey.py tests/test_groq_model_catalog.py tests/test_model_rotation.py tests/test_transcription_utils.py
```

- [ ] Commit:

```powershell
git commit -m "fix: refresh Groq model catalog dynamically"
```

- [ ] Push:

```powershell
git push
```

Expected: branch `refactor/clean-architecture` pushes successfully.

## Acceptance Criteria

- A stale hardcoded model returning model-specific HTTP 400 or 404 does not consume all retries with the same model.
- Tool-use commands retry with another available model in the same invocation.
- Groq STT retries with another available Whisper model when model-specific failure occurs.
- `/models` discovery works when a key is present.
- Discovery failure uses cache, then static defaults.
- No secrets, transcripts, commands, or audio are written to the model cache.
- The bounded primary script smoke is run and stopped.
- Tests cover catalog parsing, alias normalization, task filtering, quarantine, and model-error classification.
