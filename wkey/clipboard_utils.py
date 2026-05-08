import ctypes
from dataclasses import dataclass
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
COPYQ_RESTART_LOCK = threading.Lock()
COPYQ_RESTART_COOLDOWN_SECONDS = 5.0
COPYQ_RETRY_WAIT_SECONDS = 1.0
COPYQ_SERVER_DOWN_TEXT = "cannot connect to server"
_last_copyq_restart_started = 0.0


@dataclass
class CopyQCommandResult:
    success: bool
    returncode: int | None = None
    stderr: str = ""
    server_unavailable: bool = False
    retry_attempted: bool = False
    restart_attempted: bool = False
    restart_succeeded: bool = False


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


def _emit_status(status_callback, message: str) -> None:
    try:
        if status_callback:
            status_callback(message)
    except Exception as exc:  # pragma: no cover - best effort UI feedback
        logging.debug("Status callback failed: %s", exc)


def _start_copyq_server() -> tuple[bool, bool]:
    global _last_copyq_restart_started
    if not os.path.exists(COPYQ_PATH):
        logging.warning("CopyQ not found at path: %s", COPYQ_PATH)
        return False, False

    with COPYQ_RESTART_LOCK:
        now = time.monotonic()
        if now - _last_copyq_restart_started < COPYQ_RESTART_COOLDOWN_SECONDS:
            logging.info("CopyQ restart suppressed by cooldown")
            return True, False
        try:
            subprocess.Popen(
                [COPYQ_PATH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _last_copyq_restart_started = time.monotonic()
            logging.warning("CopyQ server unavailable. Starting CopyQ.")
            return True, True
        except Exception as exc:  # pragma: no cover - just logging
            logging.warning("CopyQ restart failed: %s", exc)
            return False, False


def _invoke_copyq_command(command, *, input_text=None, timeout=3) -> CopyQCommandResult:
    try:
        result = subprocess.run(
            [COPYQ_PATH, *command],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        stderr_text = (result.stderr or "").strip()
        return CopyQCommandResult(
            success=result.returncode == 0,
            returncode=result.returncode,
            stderr=stderr_text,
            server_unavailable=COPYQ_SERVER_DOWN_TEXT in stderr_text.lower(),
        )
    except Exception as exc:  # pragma: no cover - just logging
        return CopyQCommandResult(success=False, stderr=str(exc))


def _run_copyq_command(
    command,
    *,
    input_text=None,
    timeout=3,
    failure_prefix="CopyQ command failed",
    status_callback=None,
    restart_status_message=None,
    beep_func=None,
    recovery_beep=None,
) -> CopyQCommandResult:
    if not os.path.exists(COPYQ_PATH):
        logging.warning("CopyQ not found at path: %s", COPYQ_PATH)
        return CopyQCommandResult(success=False, stderr="CopyQ not found")

    result = _invoke_copyq_command(command, input_text=input_text, timeout=timeout)
    if result.success:
        return result

    logging.warning(
        "%s (rc=%s): %s",
        failure_prefix,
        result.returncode,
        result.stderr,
    )
    if not result.server_unavailable:
        return result

    should_retry, launched = _start_copyq_server()
    result.restart_attempted = True
    result.restart_succeeded = launched

    if not should_retry:
        return result

    time.sleep(COPYQ_RETRY_WAIT_SECONDS)
    retry_result = _invoke_copyq_command(command, input_text=input_text, timeout=timeout)
    retry_result.retry_attempted = True
    retry_result.restart_attempted = True
    retry_result.restart_succeeded = launched
    if retry_result.success:
        if launched:
            if restart_status_message:
                _emit_status(status_callback, restart_status_message)
            if beep_func and recovery_beep:
                beep_func(recovery_beep)
        return retry_result

    logging.warning(
        "%s (rc=%s): %s",
        failure_prefix,
        retry_result.returncode,
        retry_result.stderr,
    )
    return retry_result


def _copyq_paste(status_callback=None, beep_func=None, recovery_beep=None) -> CopyQCommandResult:
    """Use CopyQ to trigger paste from current clipboard."""
    return _run_copyq_command(
        ["paste"],
        timeout=3,
        failure_prefix="CopyQ paste failed",
        status_callback=status_callback,
        restart_status_message="CopyQ restarted; retrying paste",
        beep_func=beep_func,
        recovery_beep=recovery_beep,
    )


def _copyq_insert_second_item(text: str) -> CopyQCommandResult:
    """Insert transcript as the second item (row 1) in CopyQ clipboard tab."""
    safe_text = _normalize_text(text)
    return _run_copyq_command(
        ["tab", "clipboard", "insert", "1", "-"],
        input_text=safe_text,
        timeout=5,
        failure_prefix="CopyQ insert failed",
    )


def paste_transcript(
    transcript: str = "",
    beep_func=None,
    status_callback=None,
    **kwargs,
) -> None:
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
        recovery_beep = kwargs.get("copyq_recovery_beep")
        cleaned = _normalize_text(transcript).lstrip()
        if not cleaned:
            return

        # Save original clipboard content
        original_clipboard = get_clipboard_content()

        # Set transcript to clipboard and paste using CopyQ if available
        set_clipboard_content(cleaned)

        # Try to use CopyQ paste first, fallback to Ctrl+V
        paste_result = _copyq_paste(
            status_callback=status_callback,
            beep_func=beep_func,
            recovery_beep=recovery_beep,
        )
        if not paste_result.success:
            _emit_status(status_callback, "CopyQ unavailable; using standard paste")
            _send_ctrl_v()

        # Add transcript to CopyQ history (as second item so it's accessible but not active)
        if original_clipboard:
            set_clipboard_content(original_clipboard)
            history_result = _copyq_insert_second_item(cleaned)
        else:
            # If clipboard was empty, just add transcript to CopyQ history
            history_result = _copyq_insert_second_item(cleaned)

        if not paste_result.success:
            logging.info("pasted via fallback after CopyQ restart failure")
        elif history_result.success:
            logging.info("pasted and CopyQ history saved")
        else:
            logging.info("pasted but CopyQ history unavailable")

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
