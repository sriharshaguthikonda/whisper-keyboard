"""Audio stream recovery, resume detection, and resource throttling."""

import logging
import threading
import time
from collections import deque

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Overflow / gap detection helpers (replaces faster_whisper_..._recovery.py)
# ---------------------------------------------------------------------------

class OverflowBurstTracker:
    def __init__(self, *, window_seconds=8.0, threshold=6):
        self.window_seconds = float(window_seconds)
        self.threshold = int(threshold)
        self._events = deque()
        self._lock = threading.Lock()

    def note_overflow(self):
        now = time.monotonic()
        with self._lock:
            self._events.append(now)
            cutoff = now - self.window_seconds
            while self._events and self._events[0] < cutoff:
                self._events.popleft()
            count = len(self._events)
            return count >= self.threshold, count

    def reset(self):
        with self._lock:
            self._events.clear()


class ResumeGapDetector:
    def __init__(self, *, gap_seconds=20.0):
        self.gap_seconds = float(gap_seconds)
        self._last_tick = time.monotonic()
        self._lock = threading.Lock()

    def check(self):
        now = time.monotonic()
        with self._lock:
            gap = now - self._last_tick
            self._last_tick = now
        return gap >= self.gap_seconds, gap

    def mark_now(self):
        with self._lock:
            self._last_tick = time.monotonic()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUDIO_RECOVERY_MIN_INTERVAL_SECONDS = 8.0
RESUME_DETECTION_SUPPRESSION_SECONDS = 30.0
LISTENER_RESTART_DELAY_SECONDS = 0.25
RESOURCE_RELAX_SECONDS_ON_OVERFLOW = 2.0
RESUME_COOLDOWN_SECONDS = 5.0
RESUME_GAP_SECONDS = 20.0
OVERFLOW_BURST_WINDOW_SECONDS = 8.0
OVERFLOW_BURST_THRESHOLD = 6

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

resource_relax_until = 0.0
resume_cooldown_until = 0.0
resume_detection_suppressed_until = 0.0
last_audio_recovery_ts = 0.0
audio_recovery_in_progress = False

audio_recovery_event = threading.Event()
audio_recovery_reasons: set = set()
audio_recovery_reasons_lock = threading.Lock()
audio_recovery_state_lock = threading.Lock()
audio_recovery_execution_lock = threading.Lock()
input_stream_lock = threading.RLock()
wake_stream_lock = threading.RLock()
keyboard_listener_lock = threading.Lock()
keyboard_listener_restart_requested = threading.Event()

overflow_burst_tracker = OverflowBurstTracker(
    window_seconds=OVERFLOW_BURST_WINDOW_SECONDS,
    threshold=OVERFLOW_BURST_THRESHOLD,
)
resume_gap_detector = ResumeGapDetector(gap_seconds=RESUME_GAP_SECONDS)

# Mutable references — populated by init_audio_recovery()
_stream_ref = {"value": None}
_wake_stream_ref = {"value": None}
_keyboard_listener_ref = {"value": None}
_keyboard_handler_ref = {"value": None}

# Injected callables
_initialize_input_stream = None
_initialize_wake_stream = None
_reinitialize_pyaudio = None
_set_pause_state = None
_reset_recording_state = None   # main provides: resets buffers/queues/recording flag
_clear_transcripts = None


def init_audio_recovery(
    *,
    stream_ref,
    wake_stream_ref,
    keyboard_listener_ref,
    keyboard_handler_ref,
    initialize_input_stream,
    initialize_wake_stream,
    reinitialize_pyaudio,
    set_pause_state,
    reset_recording_state,
    clear_transcripts,
):
    """Wire up external dependencies. Call once at startup before any recording."""
    global (
        _stream_ref,
        _wake_stream_ref,
        _keyboard_listener_ref,
        _keyboard_handler_ref,
        _initialize_input_stream,
        _initialize_wake_stream,
        _reinitialize_pyaudio,
        _set_pause_state,
        _reset_recording_state,
        _clear_transcripts,
    )
    _stream_ref = stream_ref
    _wake_stream_ref = wake_stream_ref
    _keyboard_listener_ref = keyboard_listener_ref
    _keyboard_handler_ref = keyboard_handler_ref
    _initialize_input_stream = initialize_input_stream
    _initialize_wake_stream = initialize_wake_stream
    _reinitialize_pyaudio = reinitialize_pyaudio
    _set_pause_state = set_pause_state
    _reset_recording_state = reset_recording_state
    _clear_transcripts = clear_transcripts


# ---------------------------------------------------------------------------
# Resource throttling
# ---------------------------------------------------------------------------

def bump_resource_relax(seconds=RESOURCE_RELAX_SECONDS_ON_OVERFLOW):
    global resource_relax_until
    relax_until = time.time() + seconds
    if relax_until > resource_relax_until:
        resource_relax_until = relax_until


def should_relax_resources():
    return time.time() < resource_relax_until


# ---------------------------------------------------------------------------
# Recovery state
# ---------------------------------------------------------------------------

def is_audio_recovery_in_progress():
    with audio_recovery_state_lock:
        return audio_recovery_in_progress


def _set_audio_recovery_in_progress(value):
    global audio_recovery_in_progress
    with audio_recovery_state_lock:
        audio_recovery_in_progress = bool(value)


# ---------------------------------------------------------------------------
# Resume detection suppression
# ---------------------------------------------------------------------------

def suppress_resume_detection(seconds, reason):
    global resume_detection_suppressed_until
    duration = max(0.0, float(seconds))
    with audio_recovery_state_lock:
        until = time.monotonic() + duration
        if until > resume_detection_suppressed_until:
            resume_detection_suppressed_until = until
    logging.info(
        f"{YELLOW}Resume detection suppressed for {duration:.1f}s ({reason}){RESET}"
    )


def _resume_detection_remaining_seconds():
    with audio_recovery_state_lock:
        remaining = resume_detection_suppressed_until - time.monotonic()
    return max(0.0, remaining)


# ---------------------------------------------------------------------------
# Keyboard listener restart
# ---------------------------------------------------------------------------

def reset_keyboard_handler_state(reason):
    handler = _keyboard_handler_ref.get("value")
    if handler is None:
        return
    try:
        handler.reset_state()
        logging.info(f"{YELLOW}Keyboard shortcut state reset ({reason}){RESET}")
    except Exception as e:
        logging.error(
            f"{RED}Failed to reset keyboard shortcut state ({reason}): {e}{RESET}",
            exc_info=True,
        )


def request_keyboard_listener_restart(reason):
    reset_keyboard_handler_state(reason)
    with keyboard_listener_lock:
        listener = _keyboard_listener_ref.get("value")
        can_restart = listener is not None and listener.is_alive()
        if can_restart:
            keyboard_listener_restart_requested.set()
    if not can_restart:
        logging.info(
            f"{YELLOW}Keyboard listener restart requested but no active listener found ({reason}){RESET}"
        )
        return
    logging.info(f"{YELLOW}Restarting keyboard listener ({reason}){RESET}")
    try:
        listener.stop()
    except Exception as e:
        logging.error(
            f"{RED}Failed to stop keyboard listener ({reason}): {e}{RESET}",
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Wake stream access helpers
# ---------------------------------------------------------------------------

def get_current_wake_stream():
    with wake_stream_lock:
        return _wake_stream_ref.get("value")


def is_wake_stream_active():
    with wake_stream_lock:
        current_stream = _wake_stream_ref.get("value")
        if current_stream is None:
            return False
        try:
            return current_stream.is_active()
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Resume event — resets recording state and buffers
# ---------------------------------------------------------------------------

def _drain_queue(q):
    try:
        while not q.empty():
            q.get_nowait()
    except Exception:
        pass


def handle_resume_event(reason="resume"):
    """Reset cooldown, queues, overflow tracker, and recording state after a resume."""
    global resume_cooldown_until
    resume_cooldown_until = time.time() + RESUME_COOLDOWN_SECONDS
    if _clear_transcripts:
        _clear_transcripts()
    if _reset_recording_state:
        _reset_recording_state(reason)
    overflow_burst_tracker.reset()
    logging.info(f"{YELLOW}Resume cooldown active ({reason}){RESET}")


def _status_has_overflow(status):
    if not status:
        return False
    try:
        if getattr(status, "input_overflow", False):
            return True
    except Exception:
        pass
    return "overflow" in str(status).lower()


# ---------------------------------------------------------------------------
# Stream teardown helpers
# ---------------------------------------------------------------------------

def _close_input_stream_for_recovery():
    with input_stream_lock:
        local_stream = _stream_ref.get("value")
        _stream_ref["value"] = None
    if not local_stream:
        return
    try:
        if getattr(local_stream, "active", False):
            local_stream.stop()
    except Exception as e:
        logging.info(f"{YELLOW}Input stream stop during recovery raised: {e}{RESET}")
    try:
        local_stream.close()
    except Exception as e:
        logging.info(f"{YELLOW}Input stream close during recovery raised: {e}{RESET}")


def _close_wake_stream_for_recovery():
    with wake_stream_lock:
        local_wake_stream = _wake_stream_ref.get("value")
        _wake_stream_ref["value"] = None
    if not local_wake_stream:
        return
    try:
        if local_wake_stream.is_active():
            local_wake_stream.stop_stream()
    except Exception as e:
        logging.info(f"{YELLOW}Wake stream stop during recovery raised: {e}{RESET}")
    try:
        local_wake_stream.close()
    except Exception as e:
        logging.info(f"{YELLOW}Wake stream close during recovery raised: {e}{RESET}")


# ---------------------------------------------------------------------------
# Main recovery orchestration
# ---------------------------------------------------------------------------

def request_audio_recovery(reason):
    reason = str(reason)
    if is_audio_recovery_in_progress():
        logging.info(
            f"{YELLOW}Audio recovery already running. Queuing additional reason={reason}{RESET}"
        )
    with audio_recovery_reasons_lock:
        audio_recovery_reasons.add(reason)
    audio_recovery_event.set()


def _perform_audio_recovery(reason):
    global last_audio_recovery_ts
    with audio_recovery_state_lock:
        if audio_recovery_in_progress:
            logging.info(
                f"{YELLOW}Audio recovery skipped — another recovery already running (reason={reason}){RESET}"
            )
            return
        now = time.time()
        if now - last_audio_recovery_ts < AUDIO_RECOVERY_MIN_INTERVAL_SECONDS:
            logging.info(
                f"{YELLOW}Audio recovery skipped (cooldown) reason={reason}{RESET}"
            )
            return
        last_audio_recovery_ts = now
        _set_audio_recovery_in_progress(True)

    try:
        with audio_recovery_execution_lock:
            logging.warning(f"{YELLOW}Audio recovery start: {reason}{RESET}")
            request_keyboard_listener_restart(f"recovery:{reason}")
            handle_resume_event(f"recovery:{reason}")
            _close_input_stream_for_recovery()
            _close_wake_stream_for_recovery()

            if not _initialize_input_stream():
                logging.warning(
                    f"{YELLOW}Audio recovery: input stream could not be reinitialized{RESET}"
                )
            if not _initialize_wake_stream():
                _reinitialize_pyaudio()
                _initialize_wake_stream()
            resume_gap_detector.mark_now()
            suppress_resume_detection(
                RESUME_DETECTION_SUPPRESSION_SECONDS, f"recovery:{reason}"
            )
            logging.info(f"{GREEN}Audio recovery complete: {reason}{RESET}")
    except Exception as e:
        logging.error(
            f"{RED}Audio recovery failed ({reason}): {e}{RESET}", exc_info=True
        )
    finally:
        _set_audio_recovery_in_progress(False)


def audio_recovery_worker():
    while True:
        audio_recovery_event.wait()
        audio_recovery_event.clear()
        with audio_recovery_reasons_lock:
            if not audio_recovery_reasons:
                continue
            reasons = sorted(audio_recovery_reasons)
            audio_recovery_reasons.clear()
        _perform_audio_recovery("|".join(reasons))


# ---------------------------------------------------------------------------
# System resume detection
# ---------------------------------------------------------------------------

def maybe_handle_system_resume(source):
    resumed, gap_seconds = resume_gap_detector.check()
    if not resumed:
        return
    remaining = _resume_detection_remaining_seconds()
    if remaining > 0:
        logging.info(
            f"{YELLOW}Resume detection suppressed ({remaining:.1f}s remaining) for {source}{RESET}"
        )
        return
    logging.warning(
        f"{YELLOW}Detected resume/time jump ({gap_seconds:.1f}s) from {source}{RESET}"
    )
    suppress_resume_detection(
        RESUME_DETECTION_SUPPRESSION_SECONDS, f"system resume:{source}"
    )
    try:
        if _set_pause_state:
            _set_pause_state(False)
        logging.info(f"{GREEN}Auto-resumed voice pause state after system wake{RESET}")
    except Exception as e:
        logging.error(
            f"{RED}Failed to auto-resume pause state: {e}{RESET}", exc_info=True
        )
    request_keyboard_listener_restart(f"system resume:{source}")
    handle_resume_event(f"system resume:{source}")
    request_audio_recovery(f"system resume:{source}")
