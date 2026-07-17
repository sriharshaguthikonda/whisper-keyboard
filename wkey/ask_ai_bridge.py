import glob
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone

try:
    import winsound
except Exception:  # pragma: no cover - non-Windows test environments
    winsound = None

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = lambda *args, **kwargs: None

try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None

try:
    from . import clipboard_utils, overlay_notify
    from .ask_ai_providers import complete_ask_ai
    from .settings_manager import DEFAULT_SETTINGS, load_settings
except ImportError:  # pragma: no cover - script-style imports
    import clipboard_utils
    import overlay_notify
    from ask_ai_providers import complete_ask_ai
    from settings_manager import DEFAULT_SETTINGS, load_settings

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")
DEFAULT_PROMPT_JOBS_DIR = r"C:\Windows_software\openai whisper\prompt_jobs"
SUCCESS_BEEP = (1060, 100)
ERROR_BEEP = (440, 180)
JOB_MAX_AGE_SECONDS = 10 * 60

# Injected by the runtime (faster_whisper_Mother_of_all_wkey) at startup: a callable
# tts_speaker(text) that queues text for playback on the existing TTS stack. Stays
# None (no-op) when the runtime hasn't wired it up yet, e.g. in isolated tests.
tts_speaker = None

_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_ITALIC_RE = re.compile(r"\*([^*]+)\*|_([^_]+)_")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_END_RE = re.compile(r"[.!?]")

_CHATGPT_VARIANTS = (
    re.compile(r"\bchat\s*g\s*p\s*t\b", re.IGNORECASE),
    re.compile(r"\bchat\s*g(?:b|p)t\b", re.IGNORECASE),
    re.compile(r"\bchad\s*g\s*p\s*t\b", re.IGNORECASE),
    re.compile(r"\brgpt\b", re.IGNORECASE),
)
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_QUESTION_STRIP_CHARS = " \t\r\n,."
_DROPPED_QUESTION_CONNECTORS = {"that", "to"}
_QUESTION_STARTERS = {
    "if",
    "whether",
    "what",
    "when",
    "where",
    "why",
    "how",
    "is",
    "are",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "has",
    "have",
    "had",
}
_AI_CONTEXT_HINTS = {
    "ask",
    "ai",
    "chatgpt",
    "guideline",
    "guidelines",
    "nice",
    "changed",
    "changes",
    "current",
    "latest",
    "recent",
    "months",
    "cancer",
    "referral",
    "question",
}


def normalize_ai_triggers(transcript):
    text = "" if transcript is None else str(transcript)
    for pattern in _CHATGPT_VARIANTS:
        text = pattern.sub("chatgpt", text)
    return text


def _tokenize(text):
    return [(match.group(0).lower(), match.start(), match.end()) for match in _WORD_RE.finditer(text)]


def _looks_like_ai_question_after(tokens, index):
    if index >= len(tokens):
        return False
    if tokens[index][0] in _QUESTION_STARTERS:
        return True
    window = [token for token, _, _ in tokens[index : index + 8]]
    return bool(set(window) & _AI_CONTEXT_HINTS) and any(
        token in _QUESTION_STARTERS or token in {"changed", "changes", "latest", "current"}
        for token in window
    )


def _match_chatgpt_trigger(tokens, index, allow_rgpd=False):
    if index >= len(tokens):
        return None

    token = tokens[index][0]
    if token in {"chatgpt", "chatgbt", "rgpt"}:
        return index + 1

    if token == "chat" and index + 1 < len(tokens):
        next_token = tokens[index + 1][0]
        if next_token in {"gpt", "gbt"}:
            return index + 2
        if (
            next_token == "g"
            and index + 3 < len(tokens)
            and tokens[index + 2][0] == "p"
            and tokens[index + 3][0] == "t"
        ):
            return index + 4

    if token == "chad" and index + 1 < len(tokens):
        next_token = tokens[index + 1][0]
        if next_token == "gpt":
            return index + 2
        if (
            next_token == "g"
            and index + 3 < len(tokens)
            and tokens[index + 2][0] == "p"
            and tokens[index + 3][0] == "t"
        ):
            return index + 4

    if token == "rgpd" and allow_rgpd and _looks_like_ai_question_after(tokens, index + 1):
        return index + 1

    return None


def _match_ai_trigger(tokens, index):
    if index >= len(tokens):
        return None
    if tokens[index][0] == "ai":
        return index + 1
    if (
        tokens[index][0] == "the"
        and index + 1 < len(tokens)
        and tokens[index + 1][0] == "ai"
    ):
        return index + 2
    return None


def _question_after_trigger(text, tokens, index):
    if index < len(tokens) and tokens[index][0] in _DROPPED_QUESTION_CONNECTORS:
        index += 1
    if index >= len(tokens):
        return ""
    return text[tokens[index][1] :].strip(_QUESTION_STRIP_CHARS)


def classify_direct_ask_ai_transcript(transcript):
    text = "" if transcript is None else str(transcript)
    tokens = _tokenize(text)
    if not tokens:
        return None, ""

    index = 1 if tokens[0][0] == "please" else 0
    if index >= len(tokens):
        return None, ""

    if tokens[index][0] == "ask":
        trigger_index = index + 1
        chatgpt_end = _match_chatgpt_trigger(tokens, trigger_index, allow_rgpd=False)
        if chatgpt_end is not None:
            return "ask_chatgpt", _question_after_trigger(text, tokens, chatgpt_end)

        ai_end = _match_ai_trigger(tokens, trigger_index)
        if ai_end is not None:
            return "ask_ai", _question_after_trigger(text, tokens, ai_end)

        return None, ""

    if tokens[index][0] == "search":
        trigger_index = index + 1
        chatgpt_end = _match_chatgpt_trigger(tokens, trigger_index, allow_rgpd=True)
        if chatgpt_end is not None and _looks_like_ai_question_after(tokens, chatgpt_end):
            return "ask_chatgpt", _question_after_trigger(text, tokens, chatgpt_end)
        return None, ""

    chatgpt_end = _match_chatgpt_trigger(tokens, index, allow_rgpd=True)
    if chatgpt_end is not None and _looks_like_ai_question_after(tokens, chatgpt_end):
        return "ask_chatgpt", _question_after_trigger(text, tokens, chatgpt_end)

    return None, ""


def extract_question_from_transcript(transcript):
    _, question = classify_direct_ask_ai_transcript(transcript)
    return question


def _load_ask_ai_settings():
    return load_settings(SETTINGS_PATH, DEFAULT_SETTINGS)


def is_ask_ai_enabled():
    try:
        return bool(_load_ask_ai_settings().get("ask_ai_enabled", False))
    except Exception as exc:
        logging.warning("Failed to load Ask-AI setting: %s", exc)
        return False


def _beep(pattern):
    if winsound is None:
        return
    try:
        winsound.Beep(*pattern)
    except Exception:
        logging.debug("Ask-AI beep failed", exc_info=True)


def _ask_ai_config():
    settings = _load_ask_ai_settings()
    timeout = settings.get("ask_chatgpt_claim_timeout_sec", 12)
    try:
        timeout = max(1, min(60, int(timeout)))
    except Exception:
        timeout = 12
    jobs_dir = str(settings.get("prompt_jobs_dir") or DEFAULT_PROMPT_JOBS_DIR)
    model = str(settings.get("ask_ai_model") or "auto").strip()
    fallback_to_ai = bool(settings.get("ask_chatgpt_fallback_to_ai", False))
    return settings, model, timeout, jobs_dir, fallback_to_ai


def _cleanup_old_jobs(jobs_dir, now=None):
    now = time.time() if now is None else now
    patterns = ("job_*.json", "*.claimed.*", "*.error.json")
    for pattern in patterns:
        for path in glob.glob(os.path.join(jobs_dir, pattern)):
            try:
                if now - os.path.getmtime(path) > JOB_MAX_AGE_SECONDS:
                    os.remove(path)
            except (FileNotFoundError, PermissionError):
                pass
            except Exception as exc:
                logging.warning("Failed to cleanup Ask-AI job file %s: %s", path, exc)


def _new_job_id():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}_{secrets.token_hex(4)}"


def _write_job_atomic(jobs_dir, question, job_id=None):
    os.makedirs(jobs_dir, exist_ok=True)
    job_id = job_id or _new_job_id()
    payload = {
        "id": job_id,
        "text": str(question),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    final_path = os.path.join(jobs_dir, f"job_{job_id}.json")
    tmp_path = f"{final_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp_path, final_path)
    return job_id, final_path, payload


def ask_chatgpt(question):
    if not is_ask_ai_enabled():
        return ask_ai(question)

    _, _, timeout, jobs_dir, fallback_to_ai = _ask_ai_config()
    os.makedirs(jobs_dir, exist_ok=True)
    _cleanup_old_jobs(jobs_dir)
    job_id, pending_path, _ = _write_job_atomic(jobs_dir, question)
    claim_prefix = f"job_{job_id}.claimed."
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            for name in os.listdir(jobs_dir):
                if name.startswith(claim_prefix):
                    _beep(SUCCESS_BEEP)
                    overlay_notify.notify("ChatGPT answering…")
                    return True
        except FileNotFoundError:
            os.makedirs(jobs_dir, exist_ok=True)
        time.sleep(0.5)

    try:
        if os.path.exists(pending_path):
            os.remove(pending_path)
    except Exception as exc:
        logging.warning("Failed to delete stale Ask-AI pending job %s: %s", pending_path, exc)
    if fallback_to_ai:
        logging.warning("Ask-AI ChatGPT job was not claimed; using direct provider fallback")
        overlay_notify.notify("ChatGPT unavailable — using AI provider")
        return ask_ai(question)
    logging.warning("Ask-AI ChatGPT job was not claimed; direct provider fallback is disabled")
    _beep(ERROR_BEEP)
    overlay_notify.notify("ChatGPT did not answer", kind="error")
    return False


def _prepare_speech(text, max_chars=0):
    """Convert an answer into plain speech text: strip markdown/URLs, then
    truncate to max_chars (0 = unlimited) at the last sentence boundary."""
    speech = "" if text is None else str(text)
    speech = _CODE_FENCE_RE.sub("", speech)
    speech = _INLINE_CODE_RE.sub(r"\1", speech)
    speech = _HEADING_RE.sub("", speech)
    speech = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2) or "", speech)
    # ponytail: single-star/underscore italic regex can misfire inside snake_case
    # words; acceptable for spoken-answer cleanup, tighten if it mangles real answers.
    speech = _ITALIC_RE.sub(lambda m: m.group(1) or m.group(2) or "", speech)
    speech = _URL_RE.sub("link", speech)
    speech = _WHITESPACE_RE.sub(" ", speech).strip()

    try:
        max_chars = int(max_chars)
    except Exception:
        max_chars = 0
    if max_chars > 0 and len(speech) > max_chars:
        window = speech[:max_chars]
        boundary = -1
        for match in _SENTENCE_END_RE.finditer(window):
            boundary = match.end()
        speech = (speech[:boundary] if boundary > 0 else window).strip()
        speech = f"{speech}…"
    return speech


def _maybe_speak(answer):
    try:
        settings = _load_ask_ai_settings()
        if not bool(settings.get("ask_ai_tts_enabled", True)):
            return
        if tts_speaker is None:
            return
        max_chars = settings.get("ask_ai_tts_max_chars", 400)
        try:
            max_chars = max(0, min(4000, int(max_chars)))
        except Exception:
            max_chars = 400
        speech = _prepare_speech(answer, max_chars)
        if speech:
            tts_speaker(speech)
    except Exception:
        logging.warning("Ask-AI TTS speak failed", exc_info=True)


def ask_ai(question):
    _, model, _, _, _ = _ask_ai_config()
    try:
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        result = complete_ask_ai(
            str(question),
            configured_model=model,
            timeout_seconds=18,
            max_tokens=768,
        )
        logging.info(
            "Ask-AI provider request succeeded provider=%s model=%s answer_len=%d",
            result.provider,
            result.model,
            len(result.answer),
        )
        clipboard_utils.paste_transcript(result.answer)
        overlay_notify.notify("AI answered")
        _maybe_speak(result.answer)
        return True
    except Exception as exc:
        _beep(ERROR_BEEP)
        logging.error("Ask-AI provider request failed: %s", exc, exc_info=True)
        overlay_notify.notify("AI request failed", kind="error")
        return False
