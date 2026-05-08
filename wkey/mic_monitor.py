"""Microphone availability monitoring and PyAudio lifecycle management."""

import logging
import time

import pyaudio
import sounddevice as sd

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

# Injected dependencies
_touch_heartbeat = None
_maybe_handle_resume = None
_is_recovery_active = None
_request_recovery = None
_request_listener_restart = None
_handle_resume_event = None
_close_wake_stream = None
_initialize_wake_stream = None
_is_wake_stream_active = None
_pyaudio_ref = {"instance": None}
_wake_stream_lock = None


def init_mic_monitor(
    *,
    touch_heartbeat,
    maybe_handle_resume,
    is_recovery_active,
    request_recovery,
    request_listener_restart,
    handle_resume_event,
    close_wake_stream,
    initialize_wake_stream,
    is_wake_stream_active,
    pyaudio_ref,
    wake_stream_lock,
):
    """Wire up dependencies before starting the microphone monitor thread."""
    global (
        _touch_heartbeat,
        _maybe_handle_resume,
        _is_recovery_active,
        _request_recovery,
        _request_listener_restart,
        _handle_resume_event,
        _close_wake_stream,
        _initialize_wake_stream,
        _is_wake_stream_active,
        _pyaudio_ref,
        _wake_stream_lock,
    )
    _touch_heartbeat = touch_heartbeat
    _maybe_handle_resume = maybe_handle_resume
    _is_recovery_active = is_recovery_active
    _request_recovery = request_recovery
    _request_listener_restart = request_listener_restart
    _handle_resume_event = handle_resume_event
    _close_wake_stream = close_wake_stream
    _initialize_wake_stream = initialize_wake_stream
    _is_wake_stream_active = is_wake_stream_active
    _pyaudio_ref = pyaudio_ref
    _wake_stream_lock = wake_stream_lock


def check_microphone():
    try:
        devices = sd.query_devices()
        for device in devices:
            if device["max_input_channels"] > 0:
                return True
        return False
    except Exception as e:
        logging.error(f"Error in check_microphone: {e}", exc_info=True)
        return False


def wait_for_microphone(poll_interval=5):
    while not check_microphone():
        logging.info(f"{RED}No microphone detected. Waiting for microphone...{RESET}")
        time.sleep(poll_interval)


def reinitialize_pyaudio():
    try:
        with _wake_stream_lock:
            if _pyaudio_ref["instance"] is not None:
                _pyaudio_ref["instance"].terminate()
            _pyaudio_ref["instance"] = pyaudio.PyAudio()
    except Exception as e:
        logging.error(f"Error in reinitialize_pyaudio: {e}", exc_info=True)


def monitor_microphone_availability():
    try:
        was_missing = False
        recovery_wait_logged = False
        while True:
            _touch_heartbeat("microphone monitor")
            _maybe_handle_resume("microphone monitor")

            if _is_recovery_active():
                if not recovery_wait_logged:
                    logging.info(
                        f"{YELLOW}Microphone monitor waiting for active audio recovery to finish{RESET}"
                    )
                    recovery_wait_logged = True
                time.sleep(1)
                continue
            recovery_wait_logged = False

            if not check_microphone():
                logging.info(
                    f"{RED}No microphone detected. Pausing wake word detection...{RESET}"
                )
                _close_wake_stream()
                was_missing = True
            else:
                if was_missing:
                    logging.info(
                        f"{GREEN}Microphone detected after outage. Scheduling audio recovery...{RESET}"
                    )
                    _request_listener_restart("microphone restore")
                    _handle_resume_event("microphone restore")
                    _request_recovery("microphone restore")
                    was_missing = False
                elif not _is_wake_stream_active():
                    logging.info(
                        f"{GREEN}Microphone detected. Resuming wake word detection...{RESET}"
                    )
                    if not _initialize_wake_stream():
                        reinitialize_pyaudio()
                        _initialize_wake_stream()

            time.sleep(10)
    except Exception as e:
        logging.error(f"Error in monitor_microphone_availability: {e}", exc_info=True)
