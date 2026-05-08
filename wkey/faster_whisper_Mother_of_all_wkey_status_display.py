"""
Console status animation for faster_whisper_Mother_of_all_wkey.
Keeps output to a single line with a spinner to avoid repeated prints.
"""

import sys
import threading
import shutil
from itertools import cycle
from typing import Callable, Iterable, Optional


def make_status_display(
    check_pause_status: Callable[[], bool],
    active_message: str,
    paused_message: str,
    override_message: Optional[Callable[[], Optional[str]]] = None,
    spinner_frames: Optional[Iterable[str]] = None,
    refresh_interval: float = 0.15,
    min_padding: int = 2,
    ellipsis: str = "…",
):
    frames = tuple(
        spinner_frames
        or ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    )
    stop_event = threading.Event()

    def _term_width() -> int:
        return shutil.get_terminal_size(fallback=(80, 20)).columns

    def _fit(text: str, width: int) -> str:
        available = max(width - min_padding, 10)
        if len(text) <= available:
            return text
        cut = max(available - len(ellipsis), 0)
        return text[:cut] + ellipsis

    def _write_line(text: str) -> None:
        width = _term_width()
        text = _fit(text, width)
        try:
            sys.stdout.write("\r" + text.ljust(width))
            sys.stdout.flush()
        except OSError:
            return
        except ValueError:
            return

    def display_loop():
        try:
            for frame in cycle(frames):
                if stop_event.is_set():
                    break

                try:
                    message_override = (
                        override_message() if override_message is not None else None
                    )
                except Exception:
                    message_override = None

                if message_override:
                    msg = message_override
                else:
                    try:
                        paused = check_pause_status()  # fast responsiveness
                    except Exception:
                        paused = False  # keep spinner going even if status check glitches

                    msg = paused_message if paused else active_message
                _write_line(f"{frame} {msg}")

                if stop_event.wait(refresh_interval):
                    break
        finally:
            width = _term_width()
            try:
                sys.stdout.write("\r" + (" " * width) + "\r")
                sys.stdout.flush()
            except OSError:
                pass
            except ValueError:
                pass

    def stop():
        stop_event.set()

    display_loop.stop = stop  # type: ignore[attr-defined]
    return display_loop
