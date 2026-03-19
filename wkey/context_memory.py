import threading
import time
from collections import deque


_LOCK = threading.Lock()
_MEMORY = deque(maxlen=64)


def add_recent_transcript(text: str, source: str = "unknown") -> None:
    cleaned = (text or "").strip()
    if len(cleaned) < 2:
        return
    with _LOCK:
        _MEMORY.append(
            {
                "text": cleaned.replace("\n", " "),
                "source": source,
                "ts": time.time(),
            }
        )


def clear_recent_transcripts() -> None:
    with _LOCK:
        _MEMORY.clear()


def _collect_recent(
    *,
    max_items: int,
    max_chars: int,
    max_age_seconds: int,
    exclude_text: str = "",
):
    now = time.time()
    exclude_clean = (exclude_text or "").strip()
    selected = []
    total_chars = 0

    with _LOCK:
        for item in reversed(_MEMORY):
            if now - float(item.get("ts", 0.0)) > max_age_seconds:
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            if exclude_clean and text == exclude_clean:
                continue
            if total_chars + len(text) > max_chars:
                remaining = max_chars - total_chars
                if remaining < 20:
                    continue
                text = text[:remaining]
            selected.append(text)
            total_chars += len(text)
            if len(selected) >= max_items or total_chars >= max_chars:
                break

    selected.reverse()
    return selected


def build_stt_prompt(
    base_prompt: str,
    *,
    max_items: int = 2,
    max_chars: int = 180,
    max_age_seconds: int = 120,
):
    recent = _collect_recent(
        max_items=max_items,
        max_chars=max_chars,
        max_age_seconds=max_age_seconds,
    )
    if not recent:
        return base_prompt
    joined = " | ".join(recent)
    return (
        f"{base_prompt}\n"
        f"Recent context (for disambiguation only): {joined}\n"
        "Do not copy context unless it is actually heard in the current audio."
    )


def get_router_context(
    *,
    current_query: str = "",
    max_items: int = 3,
    max_chars: int = 320,
    max_age_seconds: int = 180,
):
    recent = _collect_recent(
        max_items=max_items,
        max_chars=max_chars,
        max_age_seconds=max_age_seconds,
        exclude_text=current_query,
    )
    if not recent:
        return ""
    return "Recent utterances (oldest to newest):\n" + "\n".join(
        f"- {line}" for line in recent
    )

