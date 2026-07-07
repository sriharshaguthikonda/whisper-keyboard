"""Provider routing for Ask-AI requests.

The design follows the Patient_Avatar provider chain: discover configured
provider models, rank them, prefer non-Groq providers for non-realtime answers,
and fall back without SDK-level hidden retries.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Iterable

try:
    from .runtime_paths import ensure_runtime_dir, runtime_path
except ImportError:  # pragma: no cover - script-style imports
    from runtime_paths import ensure_runtime_dir, runtime_path


logger = logging.getLogger(__name__)

CATALOG_CACHE_SECONDS = 10 * 60
MODEL_CATALOG_CACHE_FILE = "ask_ai_model_catalog.json"
DEFAULT_TIMEOUT_SECONDS = 18
DEFAULT_MAX_TOKENS = 768
COMPOUND_MODELS = {"groq/compound", "groq/compound-mini"}


@dataclass(frozen=True)
class ModelCandidate:
    provider: str
    model: str
    power_score: int = 0
    context_length: int = 0


@dataclass(frozen=True)
class CompletionResult:
    answer: str
    provider: str
    model: str


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: str
    api_key: str
    default_models: tuple[str, ...]
    models_url: str | None = None
    extra_headers: tuple[tuple[str, str], ...] = ()


class ProviderRequestError(RuntimeError):
    pass


KNOWN_SCORES: dict[str, int] = {
    "deepseek/deepseek-r1": 1000,
    "deepseek/deepseek-r1:free": 1000,
    "qwen-3-235b-a22b-instruct-2507": 960,
    "qwen/qwen3-235b-a22b-instruct": 960,
    "gpt-oss-120b": 940,
    "openai/gpt-oss-120b": 940,
    "@cf/openai/gpt-oss-120b": 940,
    "deepseek/deepseek-v3": 860,
    "deepseek/deepseek-v3:free": 860,
    "Llama-4-Maverick-17B-128E-Instruct": 845,
    "meta-llama/llama-4-maverick": 845,
    "meta-llama/llama-4-maverick:free": 845,
    "@cf/meta/llama-4-maverick-17b-128e-instruct-fp8-fast": 845,
    "llama-3.3-70b-versatile": 800,
    "Meta-Llama-3.3-70B-Instruct": 800,
    "meta-llama/llama-3.3-70b-instruct": 800,
    "meta-llama/llama-3.3-70b-instruct:free": 800,
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": 800,
    "meta-llama/llama-4-scout": 650,
    "meta-llama/llama-4-scout:free": 650,
    "openai/gpt-oss-20b": 610,
    "gpt-oss-20b": 610,
    "@cf/openai/gpt-oss-20b": 610,
    "qwen/qwen3-32b": 580,
    "qwen/qwen3-32b:free": 580,
    "@cf/qwen/qwen3-30b-a3b-fp8": 560,
    "google/gemma-3-12b-it": 420,
    "google/gemma-3-12b-it:free": 420,
    "llama-3.1-8b-instant": 220,
    "meta-llama/llama-3.1-8b-instruct": 200,
    "meta-llama/llama-3.1-8b-instruct:free": 200,
}

PROVIDER_PRIORITY = {
    "cerebras": 0,
    "sambanova": 1,
    "openrouter": 2,
    "cloudflare": 3,
    "ollama-cloud": 4,
    "groq": 5,
}


def _first_csv(value: str) -> str:
    for item in str(value or "").split(","):
        item = item.strip()
        if item:
            return item
    return ""


def _headers(spec: ProviderSpec) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {spec.api_key}",
        "Content-Type": "application/json",
    }
    headers.update(dict(spec.extra_headers))
    return headers


def _provider_specs() -> list[ProviderSpec]:
    specs: list[ProviderSpec] = []

    cerebras_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    if cerebras_key:
        specs.append(
            ProviderSpec(
                "cerebras",
                "https://api.cerebras.ai/v1",
                cerebras_key,
                ("qwen-3-235b-a22b-instruct-2507", "llama-3.3-70b"),
            )
        )

    sambanova_key = os.getenv("SAMBANOVA_API_KEY", "").strip()
    if sambanova_key:
        specs.append(
            ProviderSpec(
                "sambanova",
                "https://api.sambanova.ai/v1",
                sambanova_key,
                (
                    "Llama-4-Maverick-17B-128E-Instruct",
                    "Meta-Llama-3.3-70B-Instruct",
                ),
            )
        )

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        specs.append(
            ProviderSpec(
                "openrouter",
                "https://openrouter.ai/api/v1",
                openrouter_key,
                (
                    "deepseek/deepseek-r1",
                    "deepseek/deepseek-r1:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "qwen/qwen3-32b:free",
                ),
                extra_headers=(
                    ("HTTP-Referer", "https://whisper-keyboard.local"),
                    ("X-Title", "WhisperKeyboard"),
                ),
            )
        )

    cloudflare_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cloudflare_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if cloudflare_account and cloudflare_token:
        specs.append(
            ProviderSpec(
                "cloudflare",
                f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_account}/ai/v1",
                cloudflare_token,
                (
                    "@cf/openai/gpt-oss-120b",
                    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
                    "@cf/qwen/qwen3-30b-a3b-fp8",
                ),
                models_url=(
                    "https://api.cloudflare.com/client/v4/accounts/"
                    f"{cloudflare_account}/ai/models/search?task=Text+Generation&per_page=50"
                ),
            )
        )

    ollama_cloud_key = os.getenv("OLLAMA_CLOUD_API_KEY", "").strip()
    if ollama_cloud_key:
        specs.append(
            ProviderSpec(
                "ollama-cloud",
                "https://ollama.com/v1",
                ollama_cloud_key,
                ("llama3.3:70b", "gpt-oss:120b-cloud"),
            )
        )

    groq_key = (
        _first_csv(os.getenv("GROQ_API_KEYS", ""))
        or os.getenv("GROQ_API_KEY_2", "").strip()
        or os.getenv("GROQ_API_KEY", "").strip()
    )
    if groq_key:
        specs.append(
            ProviderSpec(
                "groq",
                "https://api.groq.com/openai/v1",
                groq_key,
                (
                    "llama-3.1-8b-instant",
                    "llama-3.3-70b-versatile",
                    "openai/gpt-oss-20b",
                    "qwen/qwen3-32b",
                ),
            )
        )

    return specs


def _score_model(model_id: str, context_length: int = 0) -> int:
    normalized = model_id.strip()
    if normalized in KNOWN_SCORES:
        return KNOWN_SCORES[normalized]
    lowered = normalized.lower()
    for key, score in KNOWN_SCORES.items():
        key_lower = key.lower()
        if lowered in key_lower or key_lower in lowered:
            return score
    match = re.search(r"(\d+(?:\.\d+)?)b(?:[^a-z]|$)", lowered)
    params = float(match.group(1)) if match else 0.0
    return min(int(params * 5 + min(context_length / 1000, 100)), 900)


def _is_groq_chat_model(model_id: str) -> bool:
    return not re.search(r"whisper|guard|orpheus|tts|playai|audio", model_id, re.I)


def _parse_openai_models(payload: bytes | str, provider: str) -> list[ModelCandidate]:
    raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    data = json.loads(raw)
    items = data.get("data", [])
    candidates: list[ModelCandidate] = []
    for item in items:
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        if provider == "groq" and not _is_groq_chat_model(model_id):
            continue
        context = int(
            item.get("context_length")
            or item.get("context_window")
            or item.get("max_context_length")
            or 0
        )
        candidates.append(
            ModelCandidate(
                provider=provider,
                model=model_id,
                power_score=_score_model(model_id, context),
                context_length=context,
            )
        )
    return sorted(candidates, key=lambda item: (-item.power_score, -item.context_length))


def _parse_cloudflare_models(payload: bytes | str) -> list[ModelCandidate]:
    raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    data = json.loads(raw)
    now_ms = time.time() * 1000
    candidates: list[ModelCandidate] = []
    for item in data.get("result", []):
        model_id = str(item.get("name") or "").strip()
        if not model_id:
            continue
        props = item.get("properties") or []
        dep = next(
            (p.get("value") for p in props if p.get("property_id") == "planned_deprecation_date"),
            "",
        )
        if dep:
            try:
                if time.mktime(time.strptime(dep[:10], "%Y-%m-%d")) * 1000 < now_ms:
                    continue
            except Exception:
                pass
        context_raw = next(
            (p.get("value") for p in props if p.get("property_id") == "context_window"),
            0,
        )
        try:
            context = int(context_raw)
        except Exception:
            context = 0
        candidates.append(
            ModelCandidate(
                provider="cloudflare",
                model=model_id,
                power_score=_score_model(model_id, context),
                context_length=context,
            )
        )
    return sorted(candidates, key=lambda item: (-item.power_score, -item.context_length))


def _fetch_provider_models(spec: ProviderSpec) -> list[ModelCandidate]:
    url = spec.models_url or f"{spec.base_url.rstrip('/')}/models"
    request = urllib.request.Request(url, headers=_headers(spec), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise ProviderRequestError(f"{spec.name} models HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        raise ProviderRequestError(f"{spec.name} models failed: {exc}") from exc

    if spec.name == "cloudflare":
        return _parse_cloudflare_models(payload)
    return _parse_openai_models(payload, spec.name)


def _default_candidates(spec: ProviderSpec) -> list[ModelCandidate]:
    return [
        ModelCandidate(
            provider=spec.name,
            model=model,
            power_score=_score_model(model),
            context_length=0,
        )
        for model in spec.default_models
        if model not in COMPOUND_MODELS
    ]


def _catalog_cache_path():
    ensure_runtime_dir()
    return runtime_path(MODEL_CATALOG_CACHE_FILE)


def _read_cached_catalog() -> list[ModelCandidate]:
    path = _catalog_cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(payload.get("saved_at", 0)) > CATALOG_CACHE_SECONDS:
            return []
        return [
            ModelCandidate(
                provider=str(item["provider"]),
                model=str(item["model"]),
                power_score=int(item.get("power_score", 0)),
                context_length=int(item.get("context_length", 0)),
            )
            for item in payload.get("models", [])
        ]
    except Exception:
        return []


def _write_cached_catalog(models: Iterable[ModelCandidate], errors: dict[str, str]) -> None:
    path = _catalog_cache_path()
    payload = {
        "saved_at": time.time(),
        "models": [asdict(item) for item in models],
        "errors": errors,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        logger.debug("Ask-AI model catalog cache write failed", exc_info=True)


def _dedupe_candidates(candidates: Iterable[ModelCandidate]) -> list[ModelCandidate]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ModelCandidate] = []
    for candidate in candidates:
        key = (candidate.provider, candidate.model)
        if key in seen or candidate.model in COMPOUND_MODELS:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate_models(refresh: bool = False) -> list[ModelCandidate]:
    if not refresh:
        cached = _read_cached_catalog()
        if cached:
            return cached

    specs = _provider_specs()
    candidates: list[ModelCandidate] = []
    errors: dict[str, str] = {}
    for spec in specs:
        try:
            fetched = _fetch_provider_models(spec)
            candidates.extend(fetched or _default_candidates(spec))
        except ProviderRequestError as exc:
            errors[spec.name] = str(exc)
            candidates.extend(_default_candidates(spec))

    candidates = _dedupe_candidates(candidates)
    if candidates:
        _write_cached_catalog(candidates, errors)
    return candidates


def classify_question_complexity(question: str) -> str:
    text = str(question or "").strip()
    lowered = text.lower()
    if len(text) > 500 or any(
        token in lowered
        for token in (
            "architecture",
            "architect",
            "audit",
            "benchmark",
            "compliance",
            "debug",
            "diagnose",
            "failure handling",
            "guideline",
            "guidelines",
            "compare",
            "differential",
            "diagnosis",
            "analyze",
            "investigate",
            "migration",
            "multi-provider",
            "multi provider",
            "multi-step",
            "policy",
            "refactor",
            "research",
            "latest",
            "recent",
            "evidence",
            "plan",
            "robust",
            "root cause",
            "security",
            "strategy",
            "tradeoff",
            "tradeoffs",
            "troubleshoot",
        )
    ):
        return "complex"
    if len(text) > 180 or any(
        token in lowered
        for token in (
            "configure",
            "explain",
            "how",
            "recommend",
            "summarize",
            "steps",
            "why",
        )
    ):
        return "standard"
    if len(text) < 180:
        return "simple"
    return "standard"


def _normalize_configured_model(configured_model: str | None) -> str:
    value = str(configured_model or "auto").strip()
    if not value or value.lower() in {"auto", "default"}:
        return "auto"
    if value.lower() in COMPOUND_MODELS:
        logger.warning("Ask-AI model %s is deprecated for voice use; routing via auto", value)
        return "auto"
    return value


def _explicit_candidate(
    configured_model: str, candidates: list[ModelCandidate]
) -> ModelCandidate | None:
    provider_names = set(PROVIDER_PRIORITY)
    provider = None
    model = configured_model
    for name in provider_names:
        prefix = f"{name}:"
        if configured_model.lower().startswith(prefix):
            provider = name
            model = configured_model[len(prefix) :]
            break
    for candidate in candidates:
        if provider and candidate.provider != provider:
            continue
        if candidate.model == model:
            return candidate
    if provider:
        return ModelCandidate(provider=provider, model=model, power_score=_score_model(model))
    return None


def select_model_for_question(
    question: str,
    candidates: list[ModelCandidate],
    configured_model: str = "auto",
) -> ModelCandidate:
    if not candidates:
        raise ProviderRequestError("no Ask-AI providers configured")

    configured_model = _normalize_configured_model(configured_model)
    if configured_model != "auto":
        explicit = _explicit_candidate(configured_model, candidates)
        if explicit:
            return explicit

    complexity = classify_question_complexity(question)
    clean = [item for item in candidates if item.model not in COMPOUND_MODELS]
    if not clean:
        raise ProviderRequestError("no compatible Ask-AI models configured")

    if complexity == "complex":
        return sorted(
            clean,
            key=lambda item: (
                -item.power_score,
                PROVIDER_PRIORITY.get(item.provider, 99),
                -item.context_length,
            ),
        )[0]

    if complexity == "simple":
        def simple_rank(item: ModelCandidate) -> tuple[int, int, int]:
            lowered = item.model.lower()
            fast_bucket = 0 if re.search(r"8b|instant|small|20b", lowered) else 1
            return (
                PROVIDER_PRIORITY.get(item.provider, 99),
                fast_bucket,
                item.power_score,
            )

        return sorted(clean, key=simple_rank)[0]

    return sorted(
        clean,
        key=lambda item: (
            PROVIDER_PRIORITY.get(item.provider, 99),
            -item.power_score,
            -item.context_length,
        ),
    )[0]


def _ordered_fallbacks(
    selected: ModelCandidate, candidates: list[ModelCandidate]
) -> list[ModelCandidate]:
    remaining = [
        item
        for item in candidates
        if (item.provider, item.model) != (selected.provider, selected.model)
    ]
    remaining = sorted(
        remaining,
        key=lambda item: (
            PROVIDER_PRIORITY.get(item.provider, 99),
            -item.power_score,
            -item.context_length,
        ),
    )
    return [selected] + remaining


def _provider_by_name(name: str) -> ProviderSpec | None:
    for spec in _provider_specs():
        if spec.name == name:
            return spec
    return None


def _post_chat_completion(
    candidate: ModelCandidate,
    question: str,
    timeout_seconds: int,
    max_tokens: int,
) -> str:
    spec = _provider_by_name(candidate.provider)
    if spec is None or not spec.api_key:
        raise ProviderRequestError(f"{candidate.provider} key unavailable")

    payload = {
        "model": candidate.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer concisely. Prefer practical steps. If current facts are "
                    "needed and you cannot browse, say what cannot be verified."
                ),
            },
            {"role": "user", "content": str(question)},
        ],
        "temperature": 0.2,
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    request = urllib.request.Request(
        f"{spec.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(spec),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise ProviderRequestError(
            f"{candidate.provider}/{candidate.model} HTTP {exc.code}: {body}"
        ) from exc
    except Exception as exc:
        raise ProviderRequestError(
            f"{candidate.provider}/{candidate.model} failed: {exc}"
        ) from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ProviderRequestError(
            f"{candidate.provider}/{candidate.model} returned invalid response"
        ) from exc
    return str(content or "").strip()


def complete_ask_ai(
    question: str,
    *,
    configured_model: str = "auto",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> CompletionResult:
    candidates = _candidate_models(refresh=False)
    configured_model = _normalize_configured_model(configured_model)
    selected = select_model_for_question(question, candidates, configured_model)
    last_error: Exception | None = None

    for candidate in _ordered_fallbacks(selected, candidates):
        try:
            logger.info(
                "Ask-AI provider request provider=%s model=%s max_tokens=%d",
                candidate.provider,
                candidate.model,
                max_tokens,
            )
            answer = _post_chat_completion(
                candidate,
                question,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
            if answer:
                return CompletionResult(
                    answer=answer,
                    provider=candidate.provider,
                    model=candidate.model,
                )
            last_error = ProviderRequestError("empty answer")
        except ProviderRequestError as exc:
            logger.warning("Ask-AI provider failed: %s", exc)
            last_error = exc

    raise ProviderRequestError(f"all Ask-AI providers failed: {last_error}") from last_error
