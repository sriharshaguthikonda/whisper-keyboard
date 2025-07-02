import ctypes
import logging
import time
import win32clipboard

from voice_commands import execute_command_run_with_tool

PASTE_BEEP = (1060, 100)


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
            except win32clipboard.Error:
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
    except win32clipboard.Error:
        logging.info(
            "Failed to open the clipboard. Returning an empty string."
        )
        return ""
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in get_clipboard_content: %s", exc, exc_info=True)
        return ""


def send_input(text: str) -> None:
    """Simulate keyboard input of ``text``."""
    try:
        for char in text:
            ctypes.windll.user32.keybd_event(ord(char.upper()), 0, 0, 0)
            ctypes.windll.user32.keybd_event(ord(char.upper()), 0, 2, 0)
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in send_input: %s", exc, exc_info=True)


def paste_transcript(transcript: str, beep_func=None) -> None:
    """Paste ``transcript`` to the active window and optionally beep."""
    try:
        set_clipboard_content(transcript)
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
        if beep_func:
            beep_func(PASTE_BEEP)
        logging.info("Transcript pasted")
    except Exception as exc:  # pragma: no cover - just logging
        logging.error("Error in paste_transcript: %s", exc, exc_info=True)


def run_command_with_retry(transcript: str, max_retries: int = 3) -> None:
    """Attempt to execute ``transcript`` as a command, retrying on failure."""
    try:
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
