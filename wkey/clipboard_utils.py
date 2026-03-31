import ctypes
import logging
import os
import subprocess
import time
import win32clipboard


PASTE_BEEP = (1060, 100)
COPYQ_PATH = os.getenv(
    "COPYQ_PATH",
    r"C:\Users\deletable\AppData\Local\Programs\CopyQ\copyq.exe",
)


def set_clipboard_content(text: str) -> None:
    """Place ``text`` onto the Windows clipboard."""
    try:
        success = False
        while not success:
            try:
                win32clipboard.OpenClipboard(0)
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text)
                win32clipboard.CloseClipboard()
                success = True
            except win32clipboard.error:
                logging.info(
                    "Failed to open the clipboard. Retrying in 1 second..."
                )
                time.sleep(0.5)
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in set_clipboard_content: %s", exc, exc_info=True)


def get_clipboard_content() -> str:
    """Return the current string content from the Windows clipboard."""
    try:
        win32clipboard.OpenClipboard(0)
        data = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return data
    except win32clipboard.error:
        logging.info(
            "Failed to open the clipboard. Returning an empty string."
        )
        return ""
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in get_clipboard_content: %s", exc, exc_info=True)
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
        result = subprocess.run(
            [COPYQ_PATH, "tab", "clipboard", "insert", "1", "-"],
            input=text,
            text=True,
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
    """
    try:
        if not transcript and "text" in kwargs:
            transcript = kwargs.get("text", "")
        cleaned = transcript.lstrip()
        if not cleaned:
            return

        had_clipboard_text = _clipboard_has_unicode_text()
        previous_clipboard_text = (
            get_clipboard_content() if had_clipboard_text else None
        )

        set_clipboard_content(cleaned)
        pasted = _copyq_paste()
        if not pasted:
            _send_ctrl_v()
            pasted = True

        # Best-effort policy:
        # - If paste path ran and we had previous clipboard text, restore it as top item.
        # - Then push transcript as second history item in CopyQ.
        if pasted and had_clipboard_text and previous_clipboard_text is not None:
            set_clipboard_content(previous_clipboard_text)
            if _copyq_insert_second_item(cleaned):
                logging.info("Paste triggered; transcript saved to CopyQ row 1")
            else:
                logging.warning(
                    "Paste triggered; failed to mirror transcript to CopyQ row 1"
                )
        elif pasted:
            logging.info(
                "Paste triggered; transcript kept as current clipboard item"
            )

        if beep_func:
            beep_func(PASTE_BEEP)
        if not pasted:
            logging.info("Paste failed; transcript stored as current clipboard item")
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
