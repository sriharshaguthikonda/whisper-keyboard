"""Cursor-adjacent feedback toast for whisper-keyboard.

Shows a small, topmost, auto-fading tkinter window near the mouse cursor so the
user gets quick visual confirmation of what the dictation/ask-AI pipeline just
did ("Listening - dictation", "Pasted: ...", errors, ...).

THREADING INVARIANT: exactly one lazily-started daemon thread ("the overlay
thread") owns the withdrawn tk.Tk() root and every Toplevel it creates. All
tkinter calls happen on that thread ONLY, via a queue.Queue that notify() (safe
to call from any thread) pushes onto. Never touch a tkinter object from outside
the overlay thread.

FOCUS SAFETY (critical for a keyboard tool): the toast must never steal
keyboard focus from whatever window the user is dictating into. It is created
with overrideredirect + topmost, and on Windows we additionally strip its
ex-styles to WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED |
WS_EX_TRANSPARENT and show it with SWP_NOACTIVATE so it can never receive
activation. All pywin32 use is best-effort (try/except) so the toast still
works, just less bulletproof, when pywin32 isn't available.

# ponytail: plain tkinter Toplevel + win32 ex-style bolt-on. Upgrade path if this
# ever needs animation/richer layout: a real layered-window renderer (GDI+/Direct2D).
"""

import logging
import queue
import threading

try:
    import tkinter as tk
    _TK_AVAILABLE = True
except Exception:  # pragma: no cover - headless/CI environments
    tk = None
    _TK_AVAILABLE = False

try:
    import win32api
    import win32con
    import win32gui
    _WIN32_AVAILABLE = True
except Exception:  # pragma: no cover - non-Windows / pywin32 missing
    win32api = None
    win32con = None
    win32gui = None
    _WIN32_AVAILABLE = False

try:
    from .settings_manager import DEFAULT_SETTINGS, load_settings
except ImportError:  # pragma: no cover - script-style imports
    from settings_manager import DEFAULT_SETTINGS, load_settings

import os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")
logger = logging.getLogger(__name__)

_ERROR_BG = "#4a1c1c"
_INFO_BG = "#1c1c1c"
_FG = "#f2f2f2"

_state_lock = threading.Lock()
_thread = None
_cmd_queue = None


def _format(text, max_len=80):
    """Collapse to a single line and truncate with an ellipsis if needed."""
    single_line = " ".join(str(text or "").split())
    if len(single_line) > max_len:
        return single_line[: max_len - 1].rstrip() + "…"
    return single_line


def _gate(settings):
    """True when the overlay is allowed to show, per settings."""
    return bool((settings or {}).get("overlay_enabled", True))


def _apply_no_activate(toplevel):
    """Best-effort: make the toast un-activatable on Windows so it never steals focus."""
    if not _WIN32_AVAILABLE:
        return
    try:
        hwnd = toplevel.winfo_id()
        parent = win32gui.GetParent(hwnd) or hwnd
        style = win32gui.GetWindowLong(parent, win32con.GWL_EXSTYLE)
        style |= (
            win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
        )
        win32gui.SetWindowLong(parent, win32con.GWL_EXSTYLE, style)
        win32gui.SetWindowPos(
            parent,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOACTIVATE
            | win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOOWNERZORDER,
        )
    except Exception:
        logger.debug("overlay_notify: win32 no-activate styling failed", exc_info=True)


def _monitor_work_area(x, y):
    """Work area (l, t, r, b) of the monitor containing point (x, y), or None.

    Multi-monitor setups have secondary screens at offset/negative virtual
    coordinates; clamping to the primary screen would drag the toast off the
    monitor the cursor is actually on.
    """
    if not _WIN32_AVAILABLE:
        return None
    try:
        hmon = win32api.MonitorFromPoint((int(x), int(y)), win32con.MONITOR_DEFAULTTONEAREST)
        return win32api.GetMonitorInfo(hmon)["Work"]
    except Exception:
        return None


def _clamp_position(root, x, y, width, height):
    work = _monitor_work_area(x, y)
    if work is not None:
        left, top, right, bottom = work
    else:
        # Fallback: primary screen only (tkinter can't see other monitors).
        left, top = 0, 0
        right = root.winfo_screenwidth()
        bottom = root.winfo_screenheight()
    x = max(left, min(x, right - width))
    y = max(top, min(y, bottom - height))
    return x, y


def _overlay_loop(cmd_queue):
    root = tk.Tk()
    root.withdraw()
    current = {"toplevel": None}

    def _destroy_current():
        toplevel = current["toplevel"]
        if toplevel is not None:
            try:
                toplevel.destroy()
            except Exception:
                pass
        current["toplevel"] = None

    def _show(text, kind, duration_ms, opacity, font_size, offset_px):
        _destroy_current()
        toplevel = tk.Toplevel(root)
        current["toplevel"] = toplevel
        # Keep hidden until the no-activate ex-styles are applied so the toast
        # can never grab focus even for one frame (worst bug in a keyboard tool).
        toplevel.withdraw()
        toplevel.overrideredirect(True)
        toplevel.attributes("-topmost", True)
        try:
            toplevel.attributes("-alpha", opacity)
        except Exception:
            pass
        bg = _ERROR_BG if kind == "error" else _INFO_BG
        label = tk.Label(
            toplevel,
            text=text,
            bg=bg,
            fg=_FG,
            font=("Segoe UI", font_size),
            padx=10,
            pady=6,
        )
        label.pack()
        toplevel.update_idletasks()
        width = toplevel.winfo_width()
        height = toplevel.winfo_height()
        x = root.winfo_pointerx() + offset_px
        y = root.winfo_pointery() + offset_px
        x, y = _clamp_position(root, x, y, width, height)
        toplevel.geometry(f"+{x}+{y}")
        _apply_no_activate(toplevel)
        toplevel.deiconify()

        steps = 10

        def _fade(step):
            if current["toplevel"] is not toplevel:
                return  # replaced by a newer toast
            if step >= steps:
                _destroy_current()
                return
            try:
                toplevel.attributes("-alpha", opacity * (1 - step / steps))
            except Exception:
                pass
            toplevel.after(30, _fade, step + 1)

        toplevel.after(max(0, duration_ms), lambda: _fade(0))

    def _pump():
        try:
            while True:
                text, kind, duration_ms, opacity, font_size, offset_px = cmd_queue.get_nowait()
                _show(text, kind, duration_ms, opacity, font_size, offset_px)
        except queue.Empty:
            pass
        root.after(50, _pump)

    root.after(50, _pump)
    root.mainloop()


def _ensure_thread():
    global _thread, _cmd_queue
    with _state_lock:
        if _thread is None or not _thread.is_alive():
            _cmd_queue = queue.Queue()
            _thread = threading.Thread(
                target=_overlay_loop, args=(_cmd_queue,), daemon=True, name="OverlayNotify"
            )
            _thread.start()
        return _cmd_queue


def notify(text: str, kind: str = "info"):
    """Show a cursor-adjacent feedback toast. Thread-safe, non-blocking, never raises."""
    if not _TK_AVAILABLE:
        return
    try:
        settings = load_settings(SETTINGS_PATH, DEFAULT_SETTINGS)
        if not _gate(settings):
            return
        message = _format(text)
        if not message:
            return
        cmd_queue = _ensure_thread()
        cmd_queue.put(
            (
                message,
                kind,
                int(settings.get("overlay_duration_ms", 1500)),
                float(settings.get("overlay_opacity", 0.85)),
                int(settings.get("overlay_font_size", 11)),
                int(settings.get("overlay_offset_px", 24)),
            )
        )
    except Exception:
        logger.debug("overlay_notify.notify failed", exc_info=True)
