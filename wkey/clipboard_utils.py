import ctypes
import logging
import os
import subprocess
import threading
import time
import unicodedata
import win32clipboard


PASTE_BEEP = (1060, 100)
COPYQ_PATH = os.getenv(
    "COPYQ_PATH",
    r"C:\Users\deletable\AppData\Local\Programs\CopyQ\copyq.exe",
)


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


CLIPBOARD_MAX_RETRIES = _env_int("WKEY_CLIPBOARD_MAX_RETRIES", 8)
CLIPBOARD_RETRY_DELAY_SECONDS = _env_float(
    "WKEY_CLIPBOARD_RETRY_DELAY_SECONDS", 0.08
)
CLIPBOARD_RETRY_MAX_SECONDS = _env_float(
    "WKEY_CLIPBOARD_RETRY_MAX_SECONDS", 0.60
)
CLIPBOARD_LOCK = threading.Lock()


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text.replace("\x00", ""))
    return normalized.encode("utf-8", errors="replace").decode("utf-8")


def _retry_sleep_seconds(attempt: int) -> float:
    if CLIPBOARD_RETRY_DELAY_SECONDS <= 0:
        return 0.0
    return min(CLIPBOARD_RETRY_DELAY_SECONDS * attempt, CLIPBOARD_RETRY_MAX_SECONDS)


def set_clipboard_content(text: str) -> None:
    """Place ``text`` onto the Windows clipboard."""
    safe_text = _normalize_text(text)
    with CLIPBOARD_LOCK:
        for attempt in range(1, CLIPBOARD_MAX_RETRIES + 1):
            opened = False
            try:
                win32clipboard.OpenClipboard(0)
                opened = True
                win32clipboard.EmptyClipboard()
                # Force Unicode clipboard format to avoid MBCS encoding failures.
                win32clipboard.SetClipboardText(
                    safe_text,
                    win32clipboard.CF_UNICODETEXT,
                )
                return
            except win32clipboard.error as exc:
                if attempt == CLIPBOARD_MAX_RETRIES:
                    logging.error(
                        "Error in set_clipboard_content after %s retries: %s",
                        CLIPBOARD_MAX_RETRIES,
                        exc,
                        exc_info=True,
                    )
                    return
                wait_seconds = _retry_sleep_seconds(attempt)
                logging.info(
                    "Clipboard busy. Retrying in %.2fs (%s/%s)",
                    wait_seconds,
                    attempt,
                    CLIPBOARD_MAX_RETRIES,
                )
                if wait_seconds:
                    time.sleep(wait_seconds)
            except Exception as exc:  # pragma: no cover - just logging
                logging.error("Error in set_clipboard_content: %s", exc, exc_info=True)
                return
            finally:
                if opened:
                    try:
                        win32clipboard.CloseClipboard()
                    except win32clipboard.error:
                        pass


def get_clipboard_content() -> str:
    """Return the current string content from the Windows clipboard."""
    with CLIPBOARD_LOCK:
        for attempt in range(1, CLIPBOARD_MAX_RETRIES + 1):
            opened = False
            try:
                win32clipboard.OpenClipboard(0)
                opened = True
                if _clipboard_has_unicode_text():
                    return win32clipboard.GetClipboardData(
                        win32clipboard.CF_UNICODETEXT
                    )

                data = win32clipboard.GetClipboardData()
                if isinstance(data, str):
                    return data
                if isinstance(data, bytes):
                    return data.decode("utf-8", errors="replace")
                return str(data)
            except win32clipboard.error as exc:
                if attempt == CLIPBOARD_MAX_RETRIES:
                    logging.info(
                        "Failed to read clipboard after %s retries: %s",
                        CLIPBOARD_MAX_RETRIES,
                        exc,
                    )
                    return ""
                wait_seconds = _retry_sleep_seconds(attempt)
                if wait_seconds:
                    time.sleep(wait_seconds)
            except Exception as exc:  # pragma: no cover - just logging
                logging.error("Error in get_clipboard_content: %s", exc, exc_info=True)
                return ""
            finally:
                if opened:
                    try:
                        win32clipboard.CloseClipboard()
                    except win32clipboard.error:
                        pass
    return ""


def _clipboard_has_unicode_text() -> bool:
    try:
        return bool(
            win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT)
        )
    except Exception:
        return False


def _send_ctrl_v() -> None:
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)


def _copyq_paste() -> bool:
    """Use CopyQ to trigger paste from current clipboard."""
    try:
        if not os.path.exists(COPYQ_PATH):
            return False
        result = subprocess.run(
            [COPYQ_PATH, "paste"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            return True
        logging.warning(
            "CopyQ paste failed (rc=%s): %s",
            result.returncode,
            (result.stderr or "").strip(),
        )
        return False
    except Exception as exc:
        logging.warning("CopyQ paste exception: %s", exc)
        return False


def _copyq_insert_second_item(text: str) -> bool:
    """Insert transcript as the second item (row 1) in CopyQ clipboard tab."""
    try:
        if not os.path.exists(COPYQ_PATH):
            logging.warning("CopyQ not found at path: %s", COPYQ_PATH)
            return False
        safe_text = _normalize_text(text)
        result = subprocess.run(
            [COPYQ_PATH, "tab", "clipboard", "insert", "1", "-"],
            input=safe_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            logging.warning(
                "CopyQ insert failed (rc=%s): %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return False
        return True
    except Exception as exc:  # pragma: no cover - just logging
        logging.warning("CopyQ insert exception: %s", exc)
        return False


def paste_transcript(transcript: str = "", beep_func=None, **kwargs) -> None:
    """Paste text to the active window and optionally beep.

    Supports legacy keyword ``text`` for compatibility with tool calls.
    Leading whitespace is trimmed to avoid unwanted spaces when inserting.
    
    This function preserves the original clipboard content by:
    1. Saving current clipboard content
    2. Pasting the transcript
    3. Adding transcript to CopyQ history
    4. Restoring the original clipboard content
    """
    try:
        if not transcript and "text" in kwargs:
            transcript = kwargs.get("text", "")
        cleaned = _normalize_text(transcript).lstrip()
        if not cleaned:
            return

        # Save original clipboard content
        original_clipboard = get_clipboard_content()
        
        # Set transcript to clipboard and paste using CopyQ if available
        set_clipboard_content(cleaned)
        
        # Try to use CopyQ paste first, fallback to Ctrl+V
        if not _copyq_paste():
            _send_ctrl_v()
        
        # Add transcript to CopyQ history (as second item so it's accessible but not active)
        if original_clipboard:
            set_clipboard_content(original_clipboard)
            _copyq_insert_second_item(cleaned)
            logging.info("Voice transcript pasted, original clipboard restored, transcript saved to CopyQ")
        else:
            # If clipboard was empty, just add transcript to CopyQ history
            _copyq_insert_second_item(cleaned)
            logging.info("Voice transcript pasted and saved to CopyQ")
        
        if beep_func:
            beep_func(PASTE_BEEP)
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in paste_transcript: %s", exc, exc_info=True)


def run_command_with_retry(transcript: str, max_retries: int = 3) -> None:
    """Attempt to execute ``transcript`` as a command, retrying on failure."""
    try:
        from voice_commands import execute_command_run_with_tool  # local import to avoid circular dependency
        for _ in range(max_retries):
            try:
                if execute_command_run_with_tool(transcript):
                    return
            except Exception as exc:  # pragma: no cover - just logging
                logging.error(
                    "Error in execute_command_run_with_tool: %s", exc, exc_info=True
                )
            time.sleep(2)
        logging.error(
            "Failed to execute command after %s attempts", max_retries
        )
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in run_command_with_retry: %s", exc, exc_info=True)
