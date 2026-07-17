"""TODO :  the merge was not complete we need to do more testing and do a complete merge of the code with other branches too"""

"""
 ######   ##     ## #### 
##    ##  ##     ##  ##  
##        ##     ##  ##  
##   #### ##     ##  ##  
##    ##  ##     ##  ##  
##    ##  ##     ##  ##  
 ######    #######  #### 
"""

import os
import sys
import time
import queue
import threading
import asyncio
import base64
import json
import io
from datetime import datetime
import winsound
import numpy as np
import sounddevice as sd
import pythoncom
from scipy.io.wavfile import write as wav_write
import groq
from groq import Groq
try:
    from model_rotation import (
        hydrate_groq_model_rotators,
        next_audio_stt_model,
        note_audio_stt_model_failure,
        note_audio_stt_rate_limit,
    )
except ModuleNotFoundError:
    from wkey.model_rotation import (
        hydrate_groq_model_rotators,
        next_audio_stt_model,
        note_audio_stt_model_failure,
        note_audio_stt_rate_limit,
    )
import torch
import logging
import io
from pynput.keyboard import Controller as KeyboardController, Key, Listener
from dotenv import load_dotenv
from faster_whisper import WhisperModel
try:
    from voice_commands import (
        execute_command_fuzzy,
        execute_command_run_with_tool,
        start_driver,
        get_volume,
        set_volume,
        driver,
    )
except ModuleNotFoundError:
    from wkey.voice_commands import (
        execute_command_fuzzy,
        execute_command_run_with_tool,
        start_driver,
        get_volume,
        set_volume,
        driver,
    )
try:
    import voice_commands as voice_commands_module
except ModuleNotFoundError:
    from wkey import voice_commands as voice_commands_module
# from google_assistant import google_assistant
try:
    from google_assistant_stub import google_assistant
except ModuleNotFoundError:
    from wkey.google_assistant_stub import google_assistant
try:
    from pause_all import is_sound_playing_windows_processing
except ModuleNotFoundError:
    from wkey.pause_all import is_sound_playing_windows_processing
import pyaudio
from concurrent.futures import ThreadPoolExecutor
try:
    from clipboard_utils import paste_transcript as clipboard_paste_transcript
except ModuleNotFoundError:
    from wkey.clipboard_utils import paste_transcript as clipboard_paste_transcript
import webrtcvad
try:
    from voice_activity_detection import VoiceDetector
except ModuleNotFoundError:
    from wkey.voice_activity_detection import VoiceDetector
import traceback
from queue import Empty as QueueEmpty
from queue import Full as QueueFull
from contextlib import contextmanager
import faulthandler
try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None
try:
    from faster_whisper_Mother_of_all_wkey_status_display import make_status_display
except ModuleNotFoundError:
    from wkey.faster_whisper_Mother_of_all_wkey_status_display import make_status_display
try:
    from settings_manager import (
        DEFAULT_RECORD_KEYS,
        record_key_display_text,
        runtime_mode_for_settings,
        load_settings,
        normalize_record_keys,
        record_keys_from_hotkey_profiles,
        trigger_routes_from_hotkey_profiles,
        watch_settings,
        DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
    )
except ModuleNotFoundError:
    from wkey.settings_manager import (
        DEFAULT_RECORD_KEYS,
        record_key_display_text,
        runtime_mode_for_settings,
        load_settings,
        normalize_record_keys,
        record_keys_from_hotkey_profiles,
        trigger_routes_from_hotkey_profiles,
        watch_settings,
        DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
    )
try:
    from ask_ai_bridge import normalize_ai_triggers
except ModuleNotFoundError:
    from wkey.ask_ai_bridge import normalize_ai_triggers
try:
    from keyboard_shortcuts import KeyboardShortcutHandler
except ModuleNotFoundError:
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler
try:
    from broker_control import BrokerRuntimeDeps, run_control_stdio
except ModuleNotFoundError:
    from wkey.broker_control import BrokerRuntimeDeps, run_control_stdio
try:
    from wakeword import WakeWordListener
except ModuleNotFoundError:
    from wkey.wakeword import WakeWordListener
try:
    from pause_control import (
        check_pause_status as pause_check_impl,
        set_pause_state as pause_set_impl,
        toggle_pause_state as pause_toggle_impl,
    )
except ModuleNotFoundError:
    from wkey.pause_control import (
        check_pause_status as pause_check_impl,
        set_pause_state as pause_set_impl,
        toggle_pause_state as pause_toggle_impl,
    )
try:
    from transcription_utils import (
        create_wav_buffer as create_wav_buffer_util,
        get_transcript_with_retries as get_transcript_with_retries_util,
        transcribe_pre_recording_buffer as transcribe_pre_recording_buffer_util,
        transcribe_with_groq_async as transcribe_with_groq_async_util,
        transcribe_with_local_model as transcribe_with_local_model_util,
        validate_audio_buffer as validate_audio_buffer_util,
    )
except ModuleNotFoundError:
    from wkey.transcription_utils import (
        create_wav_buffer as create_wav_buffer_util,
        get_transcript_with_retries as get_transcript_with_retries_util,
        transcribe_pre_recording_buffer as transcribe_pre_recording_buffer_util,
        transcribe_with_groq_async as transcribe_with_groq_async_util,
        transcribe_with_local_model as transcribe_with_local_model_util,
        validate_audio_buffer as validate_audio_buffer_util,
    )
try:
    from transcription_pipeline import TranscriptionPipeline, run_asyncio_in_thread
except ModuleNotFoundError:
    from wkey.transcription_pipeline import TranscriptionPipeline, run_asyncio_in_thread
try:
    from speaker_filter import create_filter_from_settings
except ModuleNotFoundError:
    from wkey.speaker_filter import create_filter_from_settings
try:
    from context_memory import (
        add_recent_transcript,
        build_stt_prompt,
        clear_recent_transcripts,
        get_router_context,
    )
except ModuleNotFoundError:
    from wkey.context_memory import (
        add_recent_transcript,
        build_stt_prompt,
        clear_recent_transcripts,
        get_router_context,
    )
try:
    from audio_io import (
        create_audio_buffers,
        audio_callback as audio_callback_impl,
        initialize_input_stream as initialize_input_stream_impl,
        snapshot_audio_buffer as snapshot_audio_buffer_impl,
        wait_for_silence as wait_for_silence_impl,
    )
except ModuleNotFoundError:
    from wkey.audio_io import (
        create_audio_buffers,
        audio_callback as audio_callback_impl,
        initialize_input_stream as initialize_input_stream_impl,
        snapshot_audio_buffer as snapshot_audio_buffer_impl,
        wait_for_silence as wait_for_silence_impl,
    )
try:
    from volume_lease_manager import VolumeLeaseManager
except ModuleNotFoundError:
    from wkey.volume_lease_manager import VolumeLeaseManager
try:
    from pause_flag_path import get_pause_flag_path
except ModuleNotFoundError:
    from wkey.pause_flag_path import get_pause_flag_path
try:
    from runtime_paths import ensure_runtime_dir, runtime_path
except ModuleNotFoundError:
    from wkey.runtime_paths import ensure_runtime_dir, runtime_path
try:
    from faster_whisper_Mother_of_all_wkey_recovery import (
        OverflowBurstTracker,
        ResumeGapDetector,
    )
except ModuleNotFoundError:
    from wkey.faster_whisper_Mother_of_all_wkey_recovery import (
        OverflowBurstTracker,
        ResumeGapDetector,
    )

# Set up driver reference for commands_and_tools
try:
    from commands_and_tools import set_driver_reference
    set_driver_reference(driver)
except ImportError:
    pass

# Add global variables for pause functionality
FLAG_PATH = get_pause_flag_path(__file__)
global_pause_active = False
last_pause_check = 0

# Set up ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=6)

def _safe_console_stream():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        return sys.stdout
    except Exception:
        try:
            return io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="backslashreplace"
            )
        except Exception:
            return sys.stdout


def _env_flag_enabled(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


RUNTIME_DIR = ensure_runtime_dir()
RUNTIME_LOG_PATH = str(runtime_path("wkey-runtime.log"))
BACKEND_HEALTH_STATUS_PATH = str(runtime_path("backend_health_status.json"))
BACKEND_EXIT_STATUS_PATH = str(runtime_path("backend_exit_status.json"))
FAULT_LOG_PATH = str(runtime_path("faulthandler.log"))
RUNTIME_LOCK_PATH = str(runtime_path("wkey_runtime.lock"))
DUPLICATE_BACKEND_EXIT_CODE = 21
RECOVERABLE_RESTART_EXIT_CODE = 75


def configure_runtime_logging(log_path=RUNTIME_LOG_PATH):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    normalized_path = os.path.abspath(log_path)

    try:
        os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
        has_file_handler = any(
            getattr(handler, "_wkey_runtime_log_path", None) == normalized_path
            for handler in root_logger.handlers
        )
        if not has_file_handler:
            file_handler = logging.FileHandler(normalized_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler._wkey_runtime_log_path = normalized_path
            root_logger.addHandler(file_handler)
    except Exception as exc:
        root_logger.warning(
            "Runtime file logging unavailable path=%s error=%s",
            normalized_path,
            exc,
        )

    has_stream_handler = any(
        getattr(handler, "_wkey_runtime_stream_handler", False)
        for handler in root_logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler(_safe_console_stream())
        stream_handler.setFormatter(formatter)
        stream_handler._wkey_runtime_stream_handler = True
        root_logger.addHandler(stream_handler)

    return normalized_path


ACTIVE_RUNTIME_LOG_PATH = configure_runtime_logging()

# ANSI Color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
ORANGE = "\033[38;5;214m"
PINK = "\033[38;5;198m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

# Initial setup and global variables
initial_volume = None
transcript_queue = queue.Queue()
audio_buffer_queue = queue.Queue()
wake_audio_queue = queue.Queue(maxsize=8)
volume_lease_manager = VolumeLeaseManager(
    get_volume_fn=get_volume,
    set_volume_fn=set_volume,
    logger=logging,
    duck_volume=0.1,
    tolerance=0.03,
    history_window_seconds=300,
    history_max_samples=5,
    enable_endpoint_callback=_env_flag_enabled(
        "WKEY_ENABLE_VOLUME_ENDPOINT_CALLBACKS", default=False
    ),
)


def _format_volume_value(value):
    if value is None:
        return "None"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def log_volume_lease_state(context, level=logging.INFO):
    try:
        snapshot = volume_lease_manager.try_snapshot_state()
        if snapshot is None:
            logging.log(
                level,
                "volume_lease_state context=%s lock_busy=True initial_volume=%s "
                "recording=%s play_pause_pressed=%s recovery_in_progress=%s",
                context,
                _format_volume_value(globals().get("initial_volume")),
                bool(globals().get("recording", False)),
                bool(globals().get("play_pause_pressed", False)),
                is_audio_recovery_in_progress(),
            )
            return
        logging.log(
            level,
            "volume_lease_state context=%s lease_count=%d restore_pending=%s "
            "restore_target=%s initial_volume=%s recording=%s "
            "play_pause_pressed=%s recovery_in_progress=%s",
            context,
            snapshot["lease_count"],
            snapshot["restore_pending"],
            _format_volume_value(snapshot["restore_target"]),
            _format_volume_value(globals().get("initial_volume")),
            bool(globals().get("recording", False)),
            bool(globals().get("play_pause_pressed", False)),
            is_audio_recovery_in_progress(),
        )
    except Exception as e:
        logging.error(
            "Failed to log volume lease state (%s): %s", context, e, exc_info=True
        )


def _set_volume_async(target_volume, reason):
    def _run():
        try:
            set_volume(target_volume)
        except Exception as e:
            logging.error(
                "Async cached volume restore failed (%s): %s",
                reason,
                e,
                exc_info=True,
            )

    threading.Thread(
        target=_run,
        daemon=True,
        name="VolumeCachedRestore",
    ).start()


def force_release_volume_ducking(reason, level=logging.WARNING):
    global initial_volume
    cached_initial_volume = initial_volume
    (
        target_volume,
        released_leases,
        scheduled_restore,
    ) = volume_lease_manager.force_release_all(
        reason=reason,
        restore=True,
        async_restore=True,
    )

    if not scheduled_restore and cached_initial_volume is not None:
        logging.log(
            level,
            "force_release_volume_ducking fallback restore reason=%s cached_initial_volume=%s",
            reason,
            _format_volume_value(cached_initial_volume),
        )
        _set_volume_async(cached_initial_volume, reason=f"{reason}:cached_initial_volume")
        target_volume = cached_initial_volume
        scheduled_restore = True

    initial_volume = None
    log_level = (
        level
        if released_leases > 0 or scheduled_restore or cached_initial_volume is not None
        else logging.DEBUG
    )
    logging.log(
        log_level,
        "force_release_volume_ducking reason=%s released_leases=%d target=%s scheduled_restore=%s",
        reason,
        released_leases,
        _format_volume_value(target_volume),
        scheduled_restore,
    )
    log_volume_lease_state(f"force_release:{reason}", level=log_level)
    return target_volume, released_leases, scheduled_restore


# Initialize VoiceDetector
vad_detector = VoiceDetector()

load_dotenv()

# Load transcription settings
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")
SETTINGS = load_settings(SETTINGS_PATH, SETTINGS_DEFAULTS)
try:
    voice_commands_module.set_selenium_enabled(
        SETTINGS.get("enable_edge_selenium", True),
        start_if_needed=False,
    )
except AttributeError:
    pass
except Exception as e:
    logging.warning(f"{YELLOW}Failed to apply initial Selenium setting: {e}{RESET}")

# Get the key labels from environment variables, default to Right Ctrl if not set.
key_label = os.environ.get("WKEY", "ctrl_r").lower()
SUPPORTED_RECORD_KEYS = {
    'f24': Key.f24,
    'f23': Key.f23,
    'ctrl_l': Key.ctrl_l,
    'ctrl_r': Key.ctrl_r,
}
if key_label not in SUPPORTED_RECORD_KEYS:
    print(f"Warning: WKEY '{key_label}' is not supported. Defaulting to 'ctrl_r'")
    key_label = 'ctrl_r'

SUPPORTED_RUNTIME_MODES = {"combined", "keyboard", "wakeword"}


def _env_overrides_enabled():
    return os.environ.get("WKEY_ALLOW_ENV_OVERRIDES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_runtime_mode(settings, env_mode=None):
    mode = (env_mode or "").strip().lower()
    if mode and _env_overrides_enabled():
        if mode in SUPPORTED_RUNTIME_MODES:
            return mode
        print(
            f"Warning: WKEY_RUNTIME_MODE '{mode}' is not supported. "
            "Using settings-derived runtime mode."
        )
    elif mode:
        print("Ignoring WKEY_RUNTIME_MODE because WKEY_ALLOW_ENV_OVERRIDES is not enabled.")
    return runtime_mode_for_settings(settings)


runtime_mode = _resolve_runtime_mode(SETTINGS, os.environ.get("WKEY_RUNTIME_MODE"))


def _resolve_record_key_source(settings):
    if _env_overrides_enabled() and "WKEY_RECORD_KEYS" in os.environ:
        return normalize_record_keys(
            os.environ.get("WKEY_RECORD_KEYS", ""),
            allow_empty=True,
        )
    if "hotkey_profiles" in settings:
        return record_keys_from_hotkey_profiles(
            settings.get("hotkey_profiles"),
            fallback=settings.get("record_keys", DEFAULT_RECORD_KEYS),
        )
    return normalize_record_keys(settings.get("record_keys", DEFAULT_RECORD_KEYS))


def _resolve_trigger_routes(settings):
    return trigger_routes_from_hotkey_profiles(settings.get("hotkey_profiles"))


def _build_record_keys(record_key_source, mode):
    record_key_labels = [
        label.strip().lower()
        for label in record_key_source.split(",")
        if label.strip()
    ]
    keys = {
        label: SUPPORTED_RECORD_KEYS[label]
        for label in record_key_labels
        if label in SUPPORTED_RECORD_KEYS
    }
    if mode == "keyboard" and not keys:
        keys = {key_label: SUPPORTED_RECORD_KEYS[key_label]}
    return keys


record_key_source = _resolve_record_key_source(SETTINGS)
RECORD_KEYS = _build_record_keys(record_key_source, runtime_mode)
TRIGGER_ROUTES = _resolve_trigger_routes(SETTINGS)

activation_metrics_lock = threading.Lock()
activation_events = []
activation_first_audio_recorded = False
last_backend_health_write = 0.0
last_audio_overflow_status = {
    "last_overflow_count": 0,
    "overflow_burst": False,
    "external_restart_requested": False,
}


def reset_activation_metrics():
    global activation_first_audio_recorded
    with activation_metrics_lock:
        activation_events.clear()
        activation_first_audio_recorded = False


def record_activation_event(event, clock=time.perf_counter):
    timestamp = float(clock())
    with activation_metrics_lock:
        activation_events.append({"event": str(event), "timestamp": timestamp})
        del activation_events[:-32]
    return timestamp


def record_first_audio_frame(clock=time.perf_counter):
    global activation_first_audio_recorded
    with activation_metrics_lock:
        if activation_first_audio_recorded:
            return False
        activation_first_audio_recorded = True
    record_activation_event("first_audio_frame", clock=clock)
    return True


def get_activation_status():
    with activation_metrics_lock:
        events = [dict(item) for item in activation_events]
    first_by_name = {}
    for item in events:
        first_by_name.setdefault(item.get("event"), item.get("timestamp"))
    press_time = first_by_name.get("hotkey_press")

    def delta_ms(name):
        if press_time is None or name not in first_by_name:
            return None
        return round((first_by_name[name] - press_time) * 1000.0, 3)

    return {
        "latest_event": events[-1]["event"] if events else None,
        "events": events,
        "press_to_recording_true_ms": delta_ms("recording_true"),
        "press_to_stream_ready_ms": delta_ms("stream_ready"),
        "press_to_first_audio_ms": delta_ms("first_audio_frame"),
        "press_to_queued_audio_ms": delta_ms("queued_audio"),
    }


def write_backend_health_status(source="runtime", clock=time.time, force=False):
    global last_backend_health_write
    now = float(clock())
    if not force and now - last_backend_health_write < 1.0:
        return None
    last_backend_health_write = now
    payload = {
        "pid": os.getpid(),
        "source": str(source),
        "last_heartbeat": now,
        "runtime_mode": runtime_mode,
        "record_keys": list(RECORD_KEYS.keys()),
        "wakeword_enabled": is_wakeword_runtime_enabled(),
        "keyboard_runtime_enabled": is_keyboard_runtime_enabled(),
        "python_keyboard_listener_enabled": is_python_keyboard_listener_enabled(),
        "activation": get_activation_status(),
        "audio": dict(last_audio_overflow_status),
        "shutdown_reason": get_broker_control_shutdown_reason(),
    }
    last_error = None
    for attempt in range(3):
        temp_path = (
            f"{BACKEND_HEALTH_STATUS_PATH}."
            f"{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp"
        )
        try:
            status_dir = os.path.dirname(BACKEND_HEALTH_STATUS_PATH)
            if status_dir:
                os.makedirs(status_dir, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            os.replace(temp_path, BACKEND_HEALTH_STATUS_PATH)
            return payload
        except Exception as exc:
            last_error = exc
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))
    if last_error is not None:
        logging.warning("Failed to write backend health status: %s", last_error)
    return payload


def write_backend_exit_status(
    *,
    reason,
    exit_code,
    recoverable=False,
    child_pid=None,
    clock=time.time,
):
    payload = {
        "pid": os.getpid(),
        "child_pid": child_pid,
        "reason": str(reason),
        "exit_code": int(exit_code),
        "recoverable": bool(recoverable),
        "timestamp": float(clock()),
    }
    temp_path = (
        f"{BACKEND_EXIT_STATUS_PATH}."
        f"{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp"
    )
    try:
        status_dir = os.path.dirname(BACKEND_EXIT_STATUS_PATH)
        if status_dir:
            os.makedirs(status_dir, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        os.replace(temp_path, BACKEND_EXIT_STATUS_PATH)
    except Exception as exc:
        logging.warning("Failed to write backend exit status: %s", exc)
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
    return payload


def is_keyboard_runtime_enabled():
    return runtime_mode in {"combined", "keyboard"} and bool(RECORD_KEYS)


def is_broker_control_stdio_enabled():
    return os.environ.get("WKEY_BROKER_CONTROL", "").strip().lower() == "stdio"


def is_python_keyboard_listener_enabled():
    input_owner = os.environ.get("WKEY_INPUT_OWNER", "python").strip().lower()
    return is_keyboard_runtime_enabled() and input_owner != "broker"


def is_wakeword_runtime_enabled():
    return runtime_mode in {"combined", "wakeword"}


def is_ask_ai_enabled():
    return bool(SETTINGS.get("ask_ai_enabled", False))


def map_key_to_keyword_index(key):
    """Return keyword index for a given manual trigger key."""
    for label, configured_key in RECORD_KEYS.items():
        if key == configured_key:
            route = TRIGGER_ROUTES.get(label)
            if route == "command" or (route is None and label == "f24"):
                return 0  # Route directly to execute_command_run_with_tool
            return None
    return None  # Default manual (paste) pathway

keyboard_controller = KeyboardController()
recording = False
stream = None
audio_buffer = []
sample_rate = 16000

# Initialize local model based on settings and GPU availability
model = None
model_device = None
cpu_model_initialized = False
gpu_available = SETTINGS.get("use_local_gpu", True) and torch.cuda.is_available()

def initialize_local_model_cpu():
    global model, model_device, cpu_model_initialized
    if not SETTINGS.get("use_local_cpu", True):
        return False
    if cpu_model_initialized:
        return model is not None
    cpu_model_initialized = True
    try:
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        model_device = "cpu"
        logging.info(f"{YELLOW}Initialized WhisperModel on CPU{RESET}")
        return True
    except Exception as e:
        logging.error(f"{RED}Failed to initialize WhisperModel on CPU: {str(e)}{RESET}")
        model = None
        model_device = None
        return False

def initialize_local_model_gpu():
    global model, model_device, gpu_available
    if not gpu_available:
        return False
    try:
        # Set CUDA to use version 12.3 explicitly
        if os.name == 'nt':  # Windows
            cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3"
            if os.path.exists(cuda_path):
                os.environ['CUDA_HOME'] = cuda_path
                os.environ['PATH'] = fr"{cuda_path}\bin;{cuda_path}\libnvvp;{os.environ['PATH']}"
        
        logging.info(f"CUDA is available. Devices: {torch.cuda.device_count()}")
        logging.info(f"Current device: {torch.cuda.current_device()}")
        logging.info(f"Device name: {torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else 'No CUDA devices'}")
        
        # Initialize model with explicit CUDA device
        model = WhisperModel(
            "small.en",
            device="cuda",
            compute_type="float16",  # Use float16 for better performance
            num_workers=4            # Reduce workers to prevent OOM
        )
        
        # Test the model with a small tensor to verify it's working
        test_tensor = torch.zeros(1).cuda()
        logging.info(f"{GREEN}Successfully initialized WhisperModel on CUDA device: {torch.cuda.get_device_name(0)}{RESET}")
        model_device = "cuda"
        return True
        
    except Exception as e:
        logging.error(f"{RED}Failed to initialize WhisperModel on CUDA: {str(e)}{RESET}")
        gpu_available = False
        model = None
        model_device = None
        logging.info(f"{YELLOW}GPU init failed. CPU model will be initialized only after repeated Groq failures.{RESET}")
        return False

if gpu_available:
    initialize_local_model_gpu()
else:
    if SETTINGS.get("use_local_gpu", True):
        logging.info(f"{YELLOW}CUDA is not available. CPU model will be initialized only after repeated Groq failures.{RESET}")
    else:
        logging.info(f"{YELLOW}Local GPU model is disabled in settings. CPU model will be initialized only after repeated Groq failures.{RESET}")

def get_groq_audio_model():
    return next_audio_stt_model()

def _speaker_filter_cache_key(settings):
    enabled = bool(settings.get("speaker_filter_enabled", False))
    if not enabled:
        return (False,)
    return (
        True,
        str(settings.get("speaker_filter_mode", "analysis")),
        float(settings.get("speaker_filter_threshold", 0.72)),
        str(settings.get("speaker_filter_profile_path", "")),
        str(settings.get("speaker_filter_apply_to", "dictation")),
    )

def get_target_speaker_filter():
    key = _speaker_filter_cache_key(SETTINGS)
    if key == (False,):
        speaker_filter_cache["key"] = key
        speaker_filter_cache["filter"] = None
        return None
    if speaker_filter_cache.get("key") == key:
        return speaker_filter_cache.get("filter")
    speaker_filter = create_filter_from_settings(SETTINGS, logger=logging)
    speaker_filter_cache["key"] = key
    speaker_filter_cache["filter"] = speaker_filter
    return speaker_filter

def write_target_speaker_status(status):
    try:
        payload = dict(status or {})
        temp_path = f"{SPEAKER_FILTER_STATUS_PATH}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
        os.replace(temp_path, SPEAKER_FILTER_STATUS_PATH)
    except Exception as exc:
        logging.warning("Failed to write speaker filter status: %s", exc)

settings_watch_handle = None


def _setting_float(name, default, minimum, maximum):
    try:
        value = float(SETTINGS.get(name, default))
    except Exception:
        value = float(default)
    return max(float(minimum), min(float(maximum), value))


def _rebuild_prerecord_buffers_if_idle():
    global PRE_RECORDING_DURATION, PRE_RECORDING_F24_SECONDS, BUFFER_SIZE
    global pre_recording_buffer, pre_recording_buffer_f24, buffer_index, audio_buffer

    if globals().get("recording", False):
        logging.info("prerecord_buffer_rebuild_deferred recording_active=true")
        return False

    wake_seconds = _setting_float("wake_pre_recording_seconds", 2.0, 0.0, 10.0)
    manual_seconds = _setting_float("manual_pre_recording_seconds", 2.0, 0.0, 5.0)
    buffer_size = int(round(wake_seconds * sample_rate))

    lock = globals().get("audio_data_lock")
    if lock is None:
        lock = threading.RLock()

    with lock:
        (
            pre_recording_buffer,
            pre_recording_buffer_f24,
            buffer_index,
            audio_buffer,
        ) = create_audio_buffers(
            buffer_size=buffer_size,
            sample_rate=sample_rate,
            channels=channels,
            pre_recording_f24_seconds=manual_seconds,
        )
        PRE_RECORDING_DURATION = wake_seconds
        PRE_RECORDING_F24_SECONDS = manual_seconds
        BUFFER_SIZE = buffer_size
    logging.info(
        "prerecord_buffers_rebuilt wake_seconds=%.3f manual_seconds=%.3f",
        wake_seconds,
        manual_seconds,
    )
    return True


def apply_settings(new_settings):
    global SETTINGS, runtime_mode, record_key_source, RECORD_KEYS, TRIGGER_ROUTES
    global gpu_available, model, model_device, cpu_model_initialized
    wakeword_was_enabled = is_wakeword_runtime_enabled()
    SETTINGS = new_settings
    runtime_mode = _resolve_runtime_mode(SETTINGS)
    record_key_source = _resolve_record_key_source(SETTINGS)
    RECORD_KEYS = _build_record_keys(record_key_source, runtime_mode)
    TRIGGER_ROUTES = _resolve_trigger_routes(SETTINGS)
    handler = globals().get("keyboard_handler")
    if handler is not None:
        handler.record_keys = set(RECORD_KEYS.values())
    wakeword_is_enabled = is_wakeword_runtime_enabled()

    want_gpu = SETTINGS.get("use_local_gpu", True)
    want_cpu = SETTINGS.get("use_local_cpu", True)
    want_selenium = SETTINGS.get("enable_edge_selenium", True)

    _rebuild_prerecord_buffers_if_idle()

    if not want_gpu and model_device == "cuda":
        model = None
        model_device = None

    if not want_cpu and model_device == "cpu":
        model = None
        model_device = None
        cpu_model_initialized = False

    if not want_cpu:
        cpu_model_initialized = False

    gpu_available = want_gpu and torch.cuda.is_available()
    if gpu_available and model_device != "cuda":
        initialize_local_model_gpu()

    try:
        voice_commands_module.set_selenium_enabled(
            want_selenium, start_if_needed=True
        )
    except AttributeError:
        pass
    except Exception as e:
        logging.warning(f"{YELLOW}Failed to apply Selenium setting update: {e}{RESET}")

    if wakeword_was_enabled and not wakeword_is_enabled:
        logging.info(f"{YELLOW}Wake-word detection disabled in settings; closing wake stream.{RESET}")
        _close_wake_stream_for_recovery()
    elif not wakeword_was_enabled and wakeword_is_enabled:
        logging.info(f"{GREEN}Wake-word detection enabled in settings.{RESET}")
        if runtime_mode == "combined":
            logging.info("Wake-word detection will use shared input stream in combined mode.")
        else:
            initialize_wake_stream()

def start_settings_watch():
    global settings_watch_handle

    def _on_change(updated_settings):
        logging.info("Settings updated: %s", updated_settings)
        apply_settings(updated_settings)

    settings_watch_handle = watch_settings(
        SETTINGS_PATH, SETTINGS_DEFAULTS, _on_change
    )

play_pause_pressed = False
something_is_playing = False

Hey_computer_STT_prompt = None

General_gorq_system_prompt = (
    "English dictation about AI coding tools, Windows software, and programming. "
    "Preferred spellings: Claude, Claude Code, Anthropic, OpenAI, ChatGPT, Codex, "
    "GitHub, Groq, Kanata, Whisper Keyboard, AutoHotkey, PowerShell, PySide6, Qt, "
    "CUDA, and PyTorch. "
    "Voice command spellings: ask ChatGPT, ask AI. "
    "Medical spellings: NICE guidelines, two-week-wait cancer referral. "
    "Format spoken digit sequences as continuous digits, for example: 84567945."
)

COMPUTER_WAKE_GROQ_PROMPT_HINT = (
    "This audio was triggered by the wake word 'computer'. Preserve the word "
    "'computer' when it is spoken, and transcribe the wake word together with "
    "the command that follows. Do not collapse short wake-command speech into "
    "punctuation-only output."
)
COMPUTER_WAKE_CAPTURE_GRACE_SECONDS = 1.25


def _get_setting_int(name, default_value, minimum=1, maximum=10000):
    try:
        value = int(SETTINGS.get(name, default_value))
        return max(minimum, min(maximum, value))
    except Exception:
        return default_value


def _is_transcript_context_enabled():
    return bool(SETTINGS.get("enable_transcript_context_memory", True))


def _build_dynamic_stt_prompt(keyword_index=None):
    if not _is_transcript_context_enabled():
        base_prompt = General_gorq_system_prompt
    else:
        base_prompt = build_stt_prompt(
            General_gorq_system_prompt,
            max_items=_get_setting_int("stt_context_items", 2, minimum=1, maximum=8),
            max_chars=_get_setting_int(
                "stt_context_chars", 180, minimum=40, maximum=800
            ),
            max_age_seconds=_get_setting_int(
                "context_max_age_seconds", 180, minimum=15, maximum=3600
            ),
        )

    if keyword_index == 1:
        return f"{base_prompt}\n{COMPUTER_WAKE_GROQ_PROMPT_HINT}"
    return base_prompt


def _build_router_context_hint(current_query):
    if not _is_transcript_context_enabled():
        return ""
    return get_router_context(
        current_query=current_query,
        max_items=_get_setting_int("router_context_items", 3, minimum=1, maximum=8),
        max_chars=_get_setting_int(
            "router_context_chars", 320, minimum=80, maximum=1200
        ),
        max_age_seconds=_get_setting_int(
            "context_max_age_seconds", 180, minimum=15, maximum=3600
        ),
    )


def _record_recent_transcript(transcript, keyword_index):
    if not _is_transcript_context_enabled():
        return
    source_map = {
        None: "manual_dictation",
        0: "manual_router",
        1: "wake_computer",
        2: "wake_lama",
        3: "wake_google",
    }
    source = source_map.get(keyword_index, "unknown")
    add_recent_transcript(transcript, source=source)

api_key = os.getenv("GROQ_API_KEY")
global Groq_client
Groq_client = Groq(api_key=api_key)
try:
    hydrate_groq_model_rotators(api_key)
except Exception as e:
    logging.warning("Groq model catalog refresh failed during startup: %s", e)

# Reusable HTTP session for Groq API calls
groq_session_holder = {"session": None}

p = pyaudio.PyAudio()
wake_stream = None
wakeword_listener = None
transcription_pipeline = None
speaker_filter_cache = {"key": None, "filter": None}
SPEAKER_FILTER_STATUS_PATH = os.path.join(
    os.path.dirname(__file__), "speaker_filter_status.json"
)

# Define beep sounds
START_BEEP = (2080, 100)
STOP_BEEP = (440, 100)
COPYQ_RECOVERY_BEEP = (1560, 120)

# Locks for synchronization
recording_lock = threading.Lock()
audio_data_lock = threading.Lock()

# Wake-word validation synchronization
keyword_validation_event = threading.Event()
keyword_validation_result = None
KEYWORD_VALIDATION_TIMEOUT = 1.5
MIN_MANUAL_RECORDING_SECONDS = 0.25
MANUAL_RECORDING_SUPPRESSION_SECONDS = 2.0
MANUAL_RECORDING_CANCEL_PENDING_SECONDS = 1.0
manual_recording_suppressed_until = 0.0
manual_recording_suppression_reason = ""
manual_recording_cancel_pending_until = 0.0
manual_recording_cancel_pending_reason = ""
recording_start_time = 0.0
recording_session_counter = 0
active_recording_session_id = 0
recording_stop_in_progress = False
deferred_keyboard_listener_restart_reasons = set()

# Resource throttling state
RESOURCE_RELAX_SECONDS_ON_OVERFLOW = 2.0
resource_relax_until = 0.0

RESUME_RECOVERY_ENABLED = _env_flag_enabled("WKEY_RESUME_RECOVERY", default=True)
RECOVERY_POLICY = "in_app" if RESUME_RECOVERY_ENABLED else "external_restart"
AUDIO_CALLBACK_STALE_SECONDS = 10.0
AUDIO_RECOVERY_WATCHDOG_INTERVAL_SECONDS = 5.0
AUDIO_RECOVERY_RETRY_DELAYS = (1.0, 2.0, 4.0, 15.0)

OVERFLOW_BURST_WINDOW_SECONDS = 8.0
OVERFLOW_BURST_THRESHOLD = 6

overflow_burst_tracker = OverflowBurstTracker(
    window_seconds=OVERFLOW_BURST_WINDOW_SECONDS,
    threshold=OVERFLOW_BURST_THRESHOLD,
)

input_stream_lock = threading.RLock()
audio_recovery_lock = threading.Lock()
audio_recovery_requested = threading.Event()
audio_recovery_state_lock = threading.Lock()
audio_recovery_state = {
    "in_progress": False,
    "started_at": 0.0,
    "reason": "",
    "pending_reason": "",
    "stuck_reported": False,
}
audio_stream_generation = 0
LAST_AUDIO_CALLBACK_TS = time.monotonic()
resume_gap_detector = ResumeGapDetector(gap_seconds=20.0)
wake_stream_lock = threading.RLock()
keyboard_listener_lock = threading.Lock()
manual_recording_suppression_lock = threading.Lock()
manual_recording_cancel_lock = threading.Lock()
keyboard_listener_restart_requested = threading.Event()
keyboard_listener = None

_fault_log_handle = None

def bump_resource_relax(seconds=RESOURCE_RELAX_SECONDS_ON_OVERFLOW):
    """Extend relax window when the audio callback reports overload."""
    global resource_relax_until
    relax_until = time.time() + seconds
    if relax_until > resource_relax_until:
        resource_relax_until = relax_until

def should_relax_resources():
    return time.time() < resource_relax_until

def is_audio_recovery_in_progress():
    with audio_recovery_state_lock:
        return bool(audio_recovery_state["in_progress"])


def is_recording_lifecycle_active():
    with recording_lock:
        return recording or recording_stop_in_progress


def get_audio_recovery_status():
    with audio_recovery_state_lock:
        return dict(audio_recovery_state)


def suppress_manual_recording(seconds=MANUAL_RECORDING_SUPPRESSION_SECONDS, reason=""):
    global manual_recording_suppressed_until
    global manual_recording_suppression_reason

    duration = max(0.0, float(seconds or 0.0))
    until = time.time() + duration
    reason = str(reason)
    with manual_recording_suppression_lock:
        if until > manual_recording_suppressed_until:
            manual_recording_suppressed_until = until
            manual_recording_suppression_reason = reason
        remaining = max(0.0, manual_recording_suppressed_until - time.time())

    handler = globals().get("keyboard_handler")
    if handler is not None and hasattr(handler, "suppress_record_keys"):
        try:
            handler.suppress_record_keys(duration, reason)
        except Exception as e:
            logging.warning(
                f"{YELLOW}Failed to suppress keyboard record keys ({reason}): {e}{RESET}"
            )

    logging.info(
        "manual_recording_suppression_set reason=%s duration=%.2fs remaining=%.2fs",
        reason,
        duration,
        remaining,
    )


def _manual_recording_suppression_remaining():
    with manual_recording_suppression_lock:
        remaining = manual_recording_suppressed_until - time.time()
        reason = manual_recording_suppression_reason
    return max(0.0, remaining), reason


def _recovery_reason_parts(reason):
    return [part.strip().lower() for part in str(reason).split("|") if part.strip()]


def _is_volume_timeout_recovery_reason(reason):
    parts = _recovery_reason_parts(reason)
    return bool(parts) and all(part.startswith("volume timeout") for part in parts)


def reset_keyboard_handler_state(reason, preserve_rearm=False):
    if keyboard_handler is None:
        return
    try:
        keyboard_handler.reset_state(preserve_rearm=preserve_rearm)
        logging.info(
            f"{YELLOW}Keyboard shortcut state reset ({reason}, preserve_rearm={preserve_rearm}){RESET}"
        )
    except Exception as e:
        logging.error(
            f"{RED}Failed to reset keyboard shortcut state ({reason}): {e}{RESET}",
            exc_info=True,
        )


def request_keyboard_listener_restart(reason):
    logging.info(
        "keyboard_listener_restart_ignored recovery_policy=%s reason=%s",
        RECOVERY_POLICY,
        reason,
    )


def _flush_deferred_keyboard_listener_restart():
    with keyboard_listener_lock:
        deferred_keyboard_listener_restart_reasons.clear()


def get_current_wake_stream():
    with wake_stream_lock:
        return wake_stream


def is_wake_stream_active():
    with wake_stream_lock:
        current_stream = wake_stream
        if current_stream is None:
            return False
        try:
            return current_stream.is_active()
        except Exception:
            return False


def _drain_queue(q):
    try:
        while not q.empty():
            q.get_nowait()
    except Exception:
        pass

def handle_resume_event(reason="resume"):
    if RESUME_RECOVERY_ENABLED:
        reset_keyboard_handler_state(reason)
        request_audio_recovery(reason)
        return
    logging.info(
        "resume_event_ignored recovery_policy=%s reason=%s",
        RECOVERY_POLICY,
        reason,
    )


def _status_has_overflow(status):
    if not status:
        return False
    try:
        if getattr(status, "input_overflow", False):
            return True
    except Exception:
        pass
    return "overflow" in str(status).lower()


def request_audio_recovery(reason):
    reason = str(reason)
    if _is_volume_timeout_recovery_reason(reason):
        logging.warning(
            f"{YELLOW}Volume timeout recovery handled as volume-only cleanup (reason={reason}){RESET}"
        )
        suppress_manual_recording(
            MANUAL_RECORDING_SUPPRESSION_SECONDS,
            f"volume_timeout:{reason}",
        )
        force_release_volume_ducking(reason, level=logging.WARNING)
        return
    if not RESUME_RECOVERY_ENABLED:
        logging.info(
            "audio_recovery_ignored recovery_policy=%s reason=%s",
            RECOVERY_POLICY,
            reason,
        )
        return False
    with audio_recovery_state_lock:
        pending = audio_recovery_state["pending_reason"]
        if reason not in pending.split(" | "):
            audio_recovery_state["pending_reason"] = (
                f"{pending} | {reason}" if pending else reason
            )
    audio_recovery_requested.set()
    return True


def _close_input_stream_for_recovery():
    global stream
    with input_stream_lock:
        local_stream = stream
        stream = None
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
    global wake_stream
    with wake_stream_lock:
        local_wake_stream = wake_stream
        wake_stream = None
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


def _perform_audio_recovery(reason):
    if _is_volume_timeout_recovery_reason(reason):
        logging.warning(
            f"{YELLOW}Skipping audio stream recovery for volume timeout ({reason}){RESET}"
        )
        suppress_manual_recording(
            MANUAL_RECORDING_SUPPRESSION_SECONDS,
            f"volume_timeout:{reason}",
        )
        force_release_volume_ducking(reason, level=logging.WARNING)
        return True
    if not RESUME_RECOVERY_ENABLED:
        logging.info(
            "audio_recovery_perform_ignored recovery_policy=%s reason=%s",
            RECOVERY_POLICY,
            reason,
        )
        return False
    global audio_stream_generation
    with audio_recovery_lock:
        with audio_recovery_state_lock:
            audio_recovery_state.update(
                in_progress=True,
                started_at=time.monotonic(),
                reason=str(reason),
                stuck_reported=False,
            )
        try:
            audio_stream_generation += 1
            _close_input_stream_for_recovery()
            success = bool(initialize_input_stream())
            logging.log(
                logging.INFO if success else logging.ERROR,
                "audio_recovery_complete success=%s reason=%s generation=%d",
                success,
                reason,
                audio_stream_generation,
            )
            return success
        finally:
            with audio_recovery_state_lock:
                audio_recovery_state.update(in_progress=False, started_at=0.0)


def audio_recovery_worker():
    if not RESUME_RECOVERY_ENABLED:
        logging.info("audio_recovery_worker_disabled recovery_policy=%s", RECOVERY_POLICY)
        return
    failures = 0
    while True:
        audio_recovery_requested.wait()
        audio_recovery_requested.clear()
        with audio_recovery_state_lock:
            reason = audio_recovery_state["pending_reason"] or "unspecified"
            audio_recovery_state["pending_reason"] = ""
        if _perform_audio_recovery(reason):
            failures = 0
            continue
        delay = AUDIO_RECOVERY_RETRY_DELAYS[
            min(failures, len(AUDIO_RECOVERY_RETRY_DELAYS) - 1)
        ]
        failures += 1
        logging.error(
            "audio_recovery_degraded retry_in=%.1fs failures=%d reason=%s",
            delay,
            failures,
            reason,
        )
        time.sleep(delay)
        request_audio_recovery("recovery_retry")


def maybe_handle_system_resume(source):
    if not RESUME_RECOVERY_ENABLED:
        logging.info(
            "system_resume_detection_ignored recovery_policy=%s source=%s",
            RECOVERY_POLICY,
            source,
        )
        return False
    handle_resume_event(f"system_resume:{source}")
    return True


def check_resume_audio_health(now=None):
    if not RESUME_RECOVERY_ENABLED:
        return False
    resumed, gap = resume_gap_detector.check()
    if resumed:
        handle_resume_event(f"monotonic_gap {gap:.1f}s")
        return True
    current_time = time.monotonic() if now is None else float(now)
    audio_expected = bool(recording or is_wakeword_runtime_enabled())
    callback_age = current_time - LAST_AUDIO_CALLBACK_TS
    if audio_expected and callback_age > AUDIO_CALLBACK_STALE_SECONDS:
        request_audio_recovery(f"audio_callback_stale age={callback_age:.1f}s")
        return True
    return False


def audio_recovery_watchdog():
    while RESUME_RECOVERY_ENABLED:
        try:
            check_resume_audio_health()
        except Exception as exc:
            logging.error("resume_audio_watchdog_error: %s", exc, exc_info=True)
        time.sleep(AUDIO_RECOVERY_WATCHDOG_INTERVAL_SECONDS)


_volume_timeout_hook_registered = False


def register_volume_timeout_recovery_hook():
    global _volume_timeout_hook_registered
    if _volume_timeout_hook_registered:
        return
    register_callback = getattr(
        voice_commands_module, "register_volume_timeout_callback", None
    )
    if not callable(register_callback):
        logging.warning(
            f"{YELLOW}Volume timeout callback registration unavailable in voice_commands module{RESET}"
        )
        return

    def _on_timeout(timeout_seconds):
        logging.warning(
            f"{YELLOW}Volume timeout callback received ({timeout_seconds:.1f}s). Releasing volume ducking only.{RESET}"
        )
        log_volume_lease_state(
            f"volume_timeout_callback:{timeout_seconds:.1f}s", level=logging.WARNING
        )
        reason = f"volume timeout {timeout_seconds:.1f}s"
        suppress_manual_recording(
            MANUAL_RECORDING_SUPPRESSION_SECONDS,
            reason,
        )
        force_release_volume_ducking(reason, level=logging.WARNING)

    register_callback(_on_timeout)
    _volume_timeout_hook_registered = True
    logging.info(f"{GREEN}Registered volume-timeout recovery callback{RESET}")

"""
 ######  ######## ########  ########    ###    ##     ## 
##    ##    ##    ##     ## ##         ## ##   ###   ### 
##          ##    ##     ## ##        ##   ##  #### #### 
 ######     ##    ########  ######   ##     ## ## ### ## 
      ##    ##    ##   ##   ##       ######### ##     ## 
##    ##    ##    ##    ##  ##       ##     ## ##     ## 
 ######     ##    ##     ## ######## ##     ## ##     ## 
"""

PRE_RECORDING_DURATION = max(
    0.0, min(10.0, float(SETTINGS.get("wake_pre_recording_seconds", 2.0)))
)
PRE_RECORDING_F24_SECONDS = max(
    0.0, min(5.0, float(SETTINGS.get("manual_pre_recording_seconds", 2.0)))
)
BUFFER_SIZE = int(round(PRE_RECORDING_DURATION * sample_rate))
channels = 1

(
    pre_recording_buffer,
    pre_recording_buffer_f24,
    buffer_index,
    audio_buffer,
) = create_audio_buffers(
    buffer_size=BUFFER_SIZE,
    sample_rate=sample_rate,
    channels=channels,
    pre_recording_f24_seconds=PRE_RECORDING_F24_SECONDS,
)

# Add a context manager for audio operations
@contextmanager
def audio_operation_guard():
    try:
        yield
    except Exception as e:
        logging.error(f"{RED}Audio operation failed: {e}{RESET}", exc_info=True)
        reset_state()


def _enqueue_shared_wake_audio(indata, frames):
    if (
        runtime_mode != "combined"
        or not is_wakeword_runtime_enabled()
        or recording
        or not isinstance(indata, np.ndarray)
        or frames <= 0
    ):
        return
    try:
        audio = np.asarray(indata[:frames], dtype=np.float32)
        if audio.ndim > 1:
            audio = audio[:, 0]
        pcm = np.clip(audio.reshape(-1), -1.0, 1.0)
        data = (pcm * 32767.0).astype(np.int16, copy=False).tobytes()
        if not data:
            return
        try:
            wake_audio_queue.put_nowait(data)
        except QueueFull:
            try:
                wake_audio_queue.get_nowait()
            except QueueEmpty:
                pass
            try:
                wake_audio_queue.put_nowait(data)
            except QueueFull:
                pass
    except Exception as e:
        logging.debug("shared wake audio enqueue skipped: %s", e, exc_info=True)


def read_shared_wake_audio(timeout=0.05):
    try:
        return wake_audio_queue.get(timeout=timeout)
    except QueueEmpty:
        return None


# Modify the audio callback for better error handling
def audio_callback(indata, frames, time, status, callback_generation=None):
    global LAST_AUDIO_CALLBACK_TS
    if (
        callback_generation is not None
        and callback_generation != audio_stream_generation
    ):
        logging.debug(
            "stale_audio_callback_dropped callback_generation=%s current_generation=%s",
            callback_generation,
            audio_stream_generation,
        )
        return
    LAST_AUDIO_CALLBACK_TS = globals()["time"].monotonic()
    try:
        with audio_operation_guard():
            global buffer_index, audio_buffer, last_audio_overflow_status
            if status:
                bump_resource_relax()
                if _status_has_overflow(status):
                    burst, count = overflow_burst_tracker.note_overflow()
                    last_audio_overflow_status = {
                        "last_overflow_count": int(count),
                        "overflow_burst": bool(burst),
                        "external_restart_requested": bool(burst),
                    }
                    logging.warning(
                        "%sInput overflow detected; recovery_policy=%s.%s",
                        YELLOW,
                        RECOVERY_POLICY,
                        RESET,
                    )
                    if burst:
                        write_backend_health_status(
                            source="input_overflow_burst", force=True
                        )
                        if RESUME_RECOVERY_ENABLED:
                            request_audio_recovery("input_overflow_burst")
                        else:
                            request_broker_control_shutdown("input_overflow_burst")
            if recording and isinstance(indata, np.ndarray) and len(indata) > 0:
                record_first_audio_frame()
            _enqueue_shared_wake_audio(indata, frames)
            buffer_index, audio_buffer = audio_callback_impl(
                indata=indata,
                frames=frames,
                time_info=time,
                status=status,
                is_recording=lambda: recording,
                buffer_index=buffer_index,
                audio_buffer=audio_buffer,
                pre_recording_buffer=pre_recording_buffer,
                pre_recording_buffer_f24=pre_recording_buffer_f24,
                buffer_size=BUFFER_SIZE,
                max_recording_samples=_get_max_recording_seconds() * sample_rate,
                recording_lock=recording_lock,
                audio_data_lock=audio_data_lock,
                log=logging,
                warning_color_prefix=YELLOW,
                warning_color_suffix=RESET,
                error_color_prefix=RED,
                error_color_suffix=RESET,
            )

    except Exception as e:
        logging.error(f"{RED}Error in audio_callback: {e}{RESET}", exc_info=True)

stream = None

"""
##     ##  #######  ##       ##     ## ##     ## ######## 
##     ## ##     ## ##       ##     ## ###   ### ##       
##     ## ##     ## ##       ##     ## #### #### ##       
##     ## ##     ## ##       ##     ## ## ### ## ######   
 ##   ##  ##     ## ##       ##     ## ##     ## ##       
  ## ##   ##     ## ##       ##     ## ##     ## ##       
    ###     #######  ########  #######  ##     ## ######## 
"""

def initialize_input_stream():
    global stream
    with input_stream_lock:
        callback_generation = audio_stream_generation

        def generation_guarded_callback(indata, frames, time_info, status):
            return audio_callback(
                indata,
                frames,
                time_info,
                status,
                callback_generation=callback_generation,
            )

        success, stream = initialize_input_stream_impl(
            stream=stream,
            audio_callback=generation_guarded_callback,
            sample_rate=sample_rate,
            log=logging,
            success_color_prefix=GREEN,
            success_color_suffix=RESET,
            error_color_prefix=RED,
            error_color_suffix=RESET,
        )
    return success

def initialize_wake_stream():
    global wake_stream, p
    if not is_wakeword_runtime_enabled():
        logging.info(f"{YELLOW}Wake-word stream initialization skipped; wake-word detection disabled.{RESET}")
        return False
    with wake_stream_lock:
        try:
            if p is None:
                p = pyaudio.PyAudio()
            wake_stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=16000,
            )
            wake_stream.start_stream()
            logging.info(f"{GREEN}Wake-word stream initialized{RESET}")
            return True
        except Exception as e:
            logging.info(
                f"{RED}No microphone detected for wake-word stream: {e}{RESET}"
            )
            wake_stream = None
            return False

def decrease_volume_all():
    global initial_volume
    try:
        log_volume_lease_state("decrease_volume_all:before", level=logging.DEBUG)
        baseline_volume, lease_count = volume_lease_manager.begin_duck(
            reason="decrease_volume_all"
        )
        if baseline_volume is None:
            baseline_volume = get_volume()
        initial_volume = baseline_volume
        logging.info(
            "decrease_volume_all: lease_count=%d baseline=%.2f duck_to=0.10",
            lease_count, initial_volume,
        )
        if lease_count > 1:
            log_volume_lease_state(
                f"decrease_volume_all:after:nested={lease_count}",
                level=logging.WARNING,
            )
        else:
            log_volume_lease_state("decrease_volume_all:after", level=logging.DEBUG)
    except Exception as e:
        logging.error(f"Error in decrease_volume_all: {e}", exc_info=True)

def restore_volume_all():
    global initial_volume
    try:
        log_volume_lease_state("restore_volume_all:before", level=logging.DEBUG)
        target_volume, remaining_leases, did_restore = volume_lease_manager.end_duck(
            reason="restore_volume_all"
        )
        logging.info(
            "restore_volume_all: remaining_leases=%d target=%s did_restore=%s",
            remaining_leases,
            f"{target_volume:.2f}" if target_volume is not None else "None",
            did_restore,
        )
        if did_restore:
            initial_volume = None
            return
        if remaining_leases > 0 and target_volume is not None:
            initial_volume = target_volume
            log_volume_lease_state(
                f"restore_volume_all:after:remaining={remaining_leases}",
                level=logging.WARNING,
            )
            return
        if target_volume is None and initial_volume is not None:
            logging.warning(
                "restore_volume_all: lease manager returned None target; "
                "falling back to initial_volume=%.2f", initial_volume
            )
            set_volume(initial_volume)
            initial_volume = None
        log_volume_lease_state("restore_volume_all:after", level=logging.DEBUG)
    except Exception as e:
        logging.error(f"Error in restore_volume_all: {e}", exc_info=True)

def _restore_volume_all_async(delay_seconds=0.0):
    def _run():
        try:
            if delay_seconds and delay_seconds > 0:
                time.sleep(delay_seconds)
            restore_volume_all()
        except Exception as e:
            logging.error(f"Error in delayed restore_volume_all: {e}", exc_info=True)

    threading.Thread(target=_run, daemon=True).start()

def _get_volume_restore_delay_for_keyword(keyword_index):
    if keyword_index == 3:
        try:
            return max(
                0.0, float(SETTINGS.get("google_wake_volume_hold_seconds", 2.5))
            )
        except Exception:
            return 2.5
    return 0.0

def monitor_sound_processing():
    pythoncom.CoInitialize()
    global something_is_playing
    while True:
        if not recording:
            something_is_playing = is_sound_playing_windows_processing(
                something_is_playing
            )

"""
 ######  ########    ###    ########  ########    ########  ########  ######  
##    ##    ##      ## ##   ##     ##    ##       ##     ## ##       ##    ## 
##          ##     ##   ##  ##     ##    ##       ##     ## ##       ##       
 ######     ##    ##     ## ########     ##       ########  ######   ##       
      ##    ##    ######### ##   ##      ##       ##   ##   ##       ##       
##    ##    ##    ##     ## ##    ##     ##       ##    ##  ##       ##    ## 
 ######     ##    ##     ## ##     ##    ##       ##     ## ########  ######   
"""

global True_positve_audio
True_positve_audio = True

def check_keywords_in_transcription(pre_recording_data, keyword_index):
    global True_positve_audio, recording, keyword_validation_result, active_recording_session_id
    try:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass
        keyword_validation_result = None
        pre_recording_transcript = transcribe_pre_recording_buffer(pre_recording_data)

        logging.error(
            f"pre_recording_transcript: {pre_recording_transcript} keyword_index: {keyword_index}"
        )

        if keyword_index == 1 and "computer" not in pre_recording_transcript.lower():
            True_positve_audio = False
            keyword_validation_result = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        elif keyword_index == 2 and "lama" not in pre_recording_transcript.lower():
            True_positve_audio = False
            keyword_validation_result = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        elif keyword_index == 3 and "google" not in pre_recording_transcript.lower():
            True_positve_audio = False
            keyword_validation_result = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        else:
            keyword_validation_result = True

    except Exception as e:
        logging.error(f"Error in check_keywords_in_transcription: {e}", exc_info=True)
        keyword_validation_result = None
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        keyword_validation_event.set()


def is_pre_recording_keyword_check_enabled():
    return bool(SETTINGS.get("enable_pre_recording_keyword_check", False))


def should_run_pre_recording_keyword_check(keyword_index, candidate_buffer=None):
    if keyword_index not in (1, 2, 3):
        return False
    if not is_wakeword_runtime_enabled():
        return False
    if not is_pre_recording_keyword_check_enabled():
        return False
    if candidate_buffer is None:
        candidate_buffer = pre_recording_buffer
    return bool(candidate_buffer is not None and getattr(candidate_buffer, "size", 0) > 0)


def _get_max_recording_seconds():
    return _get_setting_int("max_recording_seconds", 45, minimum=5, maximum=900)

def _trim_audio_to_max_duration(audio_data):
    try:
        max_samples = _get_max_recording_seconds() * sample_rate
        if max_samples <= 0 or audio_data is None:
            return audio_data
        if len(audio_data) <= max_samples:
            return audio_data
        original_seconds = len(audio_data) / float(sample_rate)
        max_seconds = max_samples / float(sample_rate)
        logging.warning(
            f"{YELLOW}Audio buffer too long ({original_seconds:.1f}s). Trimming to {max_seconds:.1f}s.{RESET}"
        )
        return audio_data[-max_samples:]
    except Exception as e:
        logging.error(f"Error trimming audio buffer: {e}", exc_info=True)
        return audio_data

def _schedule_recording_timeout(recording_session_id, keyword_index):
    max_seconds = _get_max_recording_seconds()

    def _run():
        try:
            time.sleep(max_seconds)
            with recording_lock:
                if (not recording) or active_recording_session_id != recording_session_id:
                    return
            logging.warning(
                f"{YELLOW}Recording timeout reached ({max_seconds}s). Auto-stopping.{RESET}"
            )
            stop_recording(keyword_index)
        except Exception as e:
            logging.error(f"Error in recording timeout watchdog: {e}", exc_info=True)

    threading.Thread(target=_run, daemon=True).start()


def _cancel_recording_start_if_invalid(recording_session_id, keyword_index, context):
    global recording, active_recording_session_id, play_pause_pressed
    recovery_in_progress = is_audio_recovery_in_progress()
    with recording_lock:
        session_stale = (
            recording_session_id is None
            or not recording
            or active_recording_session_id != recording_session_id
        )
        active_session_id = active_recording_session_id

    if not recovery_in_progress and not session_stale:
        return False

    logging.warning(
        "Cancelling recording start context=%s keyword_index=%s "
        "session_id=%s active_session_id=%s recovery_in_progress=%s",
        context,
        keyword_index,
        recording_session_id,
        active_session_id,
        recovery_in_progress,
    )
    force_release_volume_ducking(
        f"start_recording_cancel:{context}",
        level=logging.WARNING,
    )
    with recording_lock:
        if active_recording_session_id == recording_session_id or not recording:
            recording = False
            active_recording_session_id = 0
    play_pause_pressed = False
    return True


def _is_recording_session_active(recording_session_id):
    with recording_lock:
        return bool(recording and active_recording_session_id == recording_session_id)


def _run_start_feedback_async(recording_session_id, keyword_index, duck_playback=False):
    def _run():
        try:
            if not _is_recording_session_active(recording_session_id):
                return
            decrease_volume_all()
            if duck_playback and _is_recording_session_active(recording_session_id):
                decrease_volume_all()
            if _is_recording_session_active(recording_session_id):
                beep(START_BEEP)
        except Exception as e:
            logging.error(
                "Error in start feedback keyword_index=%s session_id=%s: %s",
                keyword_index,
                recording_session_id,
                e,
                exc_info=True,
            )

    thread = threading.Thread(target=_run, name="StartRecordingFeedback", daemon=True)
    thread.start()
    return thread


def _is_manual_recording_keyword(keyword_index):
    return keyword_index in (None, 0)


def _mark_manual_recording_cancel_pending(reason):
    global manual_recording_cancel_pending_until
    global manual_recording_cancel_pending_reason

    with manual_recording_cancel_lock:
        manual_recording_cancel_pending_until = (
            time.time() + MANUAL_RECORDING_CANCEL_PENDING_SECONDS
        )
        manual_recording_cancel_pending_reason = str(reason)


def _clear_manual_recording_cancel_pending():
    global manual_recording_cancel_pending_until
    global manual_recording_cancel_pending_reason

    with manual_recording_cancel_lock:
        manual_recording_cancel_pending_until = 0.0
        manual_recording_cancel_pending_reason = ""


def _consume_manual_recording_cancel_pending(keyword_index):
    global manual_recording_cancel_pending_until
    global manual_recording_cancel_pending_reason

    if not _is_manual_recording_keyword(keyword_index):
        return False, ""
    with manual_recording_cancel_lock:
        remaining = manual_recording_cancel_pending_until - time.time()
        if remaining <= 0:
            return False, ""
        reason = manual_recording_cancel_pending_reason
        manual_recording_cancel_pending_until = 0.0
        manual_recording_cancel_pending_reason = ""
    return True, reason


def cancel_recording(keyword_index, reason):
    global recording, play_pause_pressed, audio_buffer, active_recording_session_id
    global recording_stop_in_progress

    if not _is_manual_recording_keyword(keyword_index):
        logging.info(
            "Ignoring cancel_recording for non-manual keyword_index=%s reason=%s",
            keyword_index,
            reason,
        )
        return

    reason = str(reason)
    with recording_lock:
        was_recording = recording
        session_id = active_recording_session_id
        if recording and not recording_stop_in_progress:
            recording = False
            active_recording_session_id = 0
            _clear_manual_recording_cancel_pending()
        else:
            _mark_manual_recording_cancel_pending(reason)

    with audio_data_lock:
        audio_buffer = []

    play_pause_pressed = False
    force_release_volume_ducking(
        f"cancel_recording:{reason}",
        level=logging.WARNING,
    )
    logging.info(
        "manual_recording_cancelled keyword_index=%s reason=%s "
        "was_recording=%s session_id=%s queued_audio=dropped",
        keyword_index,
        reason,
        was_recording,
        session_id,
    )


def start_recording(keyword_index=None):
    """Start recording audio.
    
    Args:
        keyword_index: Index of the wake word that triggered recording, or None if triggered by F24 key
    """
    try:
        if is_audio_recovery_in_progress():
            request_type = "manual" if keyword_index in (None, 0) else "wake-word"
            logging.info(
                f"{YELLOW}Audio recovery in progress. Ignoring {request_type} recording request.{RESET}"
            )
            return

        if keyword_index in (None, 0):
            cancel_pending, cancel_reason = _consume_manual_recording_cancel_pending(
                keyword_index
            )
            if cancel_pending:
                logging.info(
                    "Manual recording start canceled before activation "
                    "keyword_index=%s reason=%s",
                    keyword_index,
                    cancel_reason,
                )
                return

            remaining, suppression_reason = _manual_recording_suppression_remaining()
            if remaining > 0:
                logging.info(
                    "Manual recording request suppressed "
                    "keyword_index=%s remaining=%.2fs reason=%s",
                    keyword_index,
                    remaining,
                    suppression_reason,
                )
                return

        # Only block wake-word triggers while paused; manual keys still work
        if keyword_index not in (None, 0) and check_pause_status():
            logging.info(f"{YELLOW}Voice recognition is paused. Ignoring wake word recording request.{RESET}")
            return

        global stream
        global recording
        global play_pause_pressed
        global something_is_playing
        global True_positve_audio
        global keyword_validation_result
        global audio_buffer
        global recording_start_time
        global recording_session_counter
        global active_recording_session_id

        current_recording_session_id = None
        with recording_lock:
            if recording or recording_stop_in_progress:
                logging.info(
                    f"{YELLOW}Recording is already in progress or stopping.{RESET}"
                )
                return

            True_positve_audio = True
            keyword_validation_event.clear()
            keyword_validation_result = None
            recording = True
            record_activation_event("recording_true")
            recording_start_time = time.time()
            recording_session_counter += 1
            active_recording_session_id = recording_session_counter
            current_recording_session_id = active_recording_session_id

        with audio_data_lock:
            audio_buffer = []

        logging.info(f"{GREEN}Starting recording...{RESET}")

        if not initialize_input_stream():
            logging.info(f"{RED}No microphone detected. Recording canceled.{RESET}")
            force_release_volume_ducking(
                "start_recording:no_input_stream",
                level=logging.WARNING,
            )
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            return
        record_activation_event("stream_ready")
        if _cancel_recording_start_if_invalid(
            current_recording_session_id,
            keyword_index,
            "after_initialize_input_stream",
            ):
                return

        if something_is_playing:
            logging.info(f"{ORANGE}Something is playing, decreasing volume.{RESET}")
            play_pause_pressed = True

        _run_start_feedback_async(
            current_recording_session_id,
            keyword_index,
            duck_playback=something_is_playing,
        )
        if _cancel_recording_start_if_invalid(
            current_recording_session_id,
            keyword_index,
            "before_listening",
        ):
            return
        logging.info(f"{CYAN}Listening...{RESET}")
        if current_recording_session_id is not None:
            _schedule_recording_timeout(current_recording_session_id, keyword_index)

        if keyword_index not in (None, 0) and keyword_index not in RECORD_KEYS.values():
            if should_run_pre_recording_keyword_check(keyword_index, pre_recording_buffer):
                pre_recording_data = np.roll(
                    pre_recording_buffer, -buffer_index, axis=0
                ).flatten()

                threading.Thread(
                    target=check_keywords_in_transcription,
                    args=(pre_recording_data, keyword_index),
                ).start()
            else:
                keyword_validation_result = True
                keyword_validation_event.set()
                logging.info(
                    "Pre-recording keyword validation skipped "
                    "keyword_index=%s wakeword_enabled=%s precheck_enabled=%s buffer_available=%s",
                    keyword_index,
                    is_wakeword_runtime_enabled(),
                    is_pre_recording_keyword_check_enabled(),
                    bool(
                        pre_recording_buffer is not None
                        and getattr(pre_recording_buffer, "size", 0) > 0
                    ),
                )

    except Exception as e:
        logging.error(f"{RED}Error in start_recording: {e}{RESET}", exc_info=True)
        force_release_volume_ducking(
            "start_recording:exception",
            level=logging.WARNING,
        )
        play_pause_pressed = False
        with recording_lock:
            recording = False
            active_recording_session_id = 0

"""
 ######  ########  #######  ########     ########  ########  ######  
##    ##    ##    ##     ## ##     ##    ##     ## ##       ##    ## 
##          ##    ##     ## ##     ##    ##     ## ##       ##       
 ######     ##    ##     ## ########     ##   ##   #######  ##
      ##    ##    ##     ## ##           ##    ##  ##       ##        
##    ##    ##    ##     ## ##           ##    ##  ##       ##    ## 
 ######     ##     #######  ##           ##     ## ########  ######  
"""

def stop_recording(keyword_index):
    stop_claimed = False
    claimed_session_id = None
    try:
        global stream, recording, play_pause_pressed, audio_buffer, sample_rate, recording_start_time, True_positve_audio, vad_detector, keyword_validation_result, active_recording_session_id, recording_stop_in_progress
        restore_delay_seconds = _get_volume_restore_delay_for_keyword(keyword_index)

        with recording_lock:
            if not recording:
                if recording_stop_in_progress:
                    logging.info(
                        "duplicate_stop_ignored pid=%s session_id=%s keyword_index=%s",
                        os.getpid(),
                        active_recording_session_id,
                        keyword_index,
                    )
                    return
            else:
                recording = False
                recording_stop_in_progress = True
                claimed_session_id = active_recording_session_id
                active_recording_session_id = 0
                stop_claimed = True

        if not stop_claimed:
            snapshot = volume_lease_manager.snapshot_state()
            if (
                snapshot["lease_count"] > 0
                or snapshot["restore_pending"]
                or initial_volume is not None
            ):
                logging.warning(
                    "stop_recording called while recording=False with active volume "
                    "state keyword_index=%s lease_count=%d restore_pending=%s "
                    "restore_target=%s play_pause_pressed=%s",
                    keyword_index,
                    snapshot["lease_count"],
                    snapshot["restore_pending"],
                    _format_volume_value(snapshot["restore_target"]),
                    play_pause_pressed,
                )
                force_release_volume_ducking(
                    f"stop_recording:not_recording:{keyword_index}",
                    level=logging.WARNING,
                )
            with recording_lock:
                active_recording_session_id = 0
            play_pause_pressed = False
            beep(STOP_BEEP)
            return
        logging.info(
            "stop_recording_claimed pid=%s session_id=%s keyword_index=%s",
            os.getpid(),
            claimed_session_id,
            keyword_index,
        )

        if keyword_index in (1, 2, 3) and not keyword_validation_event.is_set():
            keyword_validation_event.wait(timeout=KEYWORD_VALIDATION_TIMEOUT)

        if keyword_index in (1, 2, 3) and keyword_validation_result is False:
            if initial_volume is not None:
                _restore_volume_all_async(delay_seconds=restore_delay_seconds)
            if play_pause_pressed:
                _restore_volume_all_async(delay_seconds=restore_delay_seconds)
            play_pause_pressed = False
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            logging.info(
                f"{MAGENTA}Wake-word validation failed. Dropping recording.{RESET}"
            )
            True_positve_audio = True
            return

        if not True_positve_audio:
            if initial_volume is not None:
                _restore_volume_all_async(delay_seconds=restore_delay_seconds)
            if play_pause_pressed:
                _restore_volume_all_async(delay_seconds=restore_delay_seconds)
            play_pause_pressed = False
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            logging.info(
                f"{MAGENTA}True_positve_audio...is {True_positve_audio}{RESET}"
            )
            True_positve_audio = True
            return

        logging.info(f"{GREEN}Stopping recording...{RESET}")
        hard_stop_limit = 5

        pre_recording_data = np.roll(
            pre_recording_buffer, -buffer_index, axis=0
        ).flatten()

        if keyword_index == 1:
            stop_delay_threshold = 0.5
        elif keyword_index == 2:
            stop_delay_threshold = 1
        elif keyword_index == 3:
            stop_delay_threshold = 1
        elif keyword_index in (None, 0):
            manual_duration_seconds = max(0.0, time.time() - recording_start_time)
            if manual_duration_seconds < MIN_MANUAL_RECORDING_SECONDS:
                logging.info(
                    "Manual recording dropped before transcription: duration=%.3fs "
                    "minimum=%.3fs; prerecord buffer not queued.",
                    manual_duration_seconds,
                    MIN_MANUAL_RECORDING_SECONDS,
                )
                _restore_volume_all_async(delay_seconds=restore_delay_seconds)
                audio_buffer = []

                if play_pause_pressed:
                    _restore_volume_all_async(delay_seconds=restore_delay_seconds)
                    play_pause_pressed = False

                beep(STOP_BEEP)
                with recording_lock:
                    recording = False
                    active_recording_session_id = 0
                return

            pre_recording_data = np.roll(
                pre_recording_buffer_f24, -buffer_index, axis=0
            ).flatten()
            local_audio_buffer = snapshot_audio_buffer_impl(
                audio_buffer, audio_data_lock
            )
            pre_samples = len(pre_recording_data)
            live_samples = len(local_audio_buffer)
            audio_buffer = np.concatenate([pre_recording_data, local_audio_buffer], axis=0)
            audio_buffer = _trim_audio_to_max_duration(audio_buffer)
            saved_path = save_manual_recording_if_configured(
                audio_buffer, keyword_index, sample_rate=sample_rate
            )
            record_activation_event("queued_audio")
            audio_buffer_queue.put((audio_buffer, keyword_index))
            try:
                queue_size = audio_buffer_queue.qsize()
            except Exception:
                queue_size = "unknown"
            logging.info(
                "manual_audio_queued keyword_index=%s samples=%d duration=%.3fs "
                "pre_samples=%d live_samples=%d saved_path=%s queue_size=%s",
                keyword_index,
                len(audio_buffer),
                len(audio_buffer) / float(sample_rate),
                pre_samples,
                live_samples,
                saved_path or "",
                queue_size,
            )

            _restore_volume_all_async(delay_seconds=restore_delay_seconds)
            audio_buffer = []

            if play_pause_pressed:
                _restore_volume_all_async(delay_seconds=restore_delay_seconds)
                play_pause_pressed = False

            beep(STOP_BEEP)
            with recording_lock:
                recording = False
                active_recording_session_id = 0
            logging.info(f"{MAGENTA}Recording stopped. Processing audio...{RESET}")
            return
        else:
            stop_delay_threshold = 2

        wait_for_silence_impl(
            stream=stream,
            audio_buffer=audio_buffer,
            audio_data_lock=audio_data_lock,
            vad_detector=vad_detector,
            sample_rate=sample_rate,
            hard_stop_limit=hard_stop_limit,
            stop_delay_threshold=stop_delay_threshold,
            log=logging,
            voice_detected_prefix=PINK,
            voice_detected_suffix=RESET,
            vad_error_prefix=RED,
            vad_error_suffix=RESET,
            hard_stop_prefix=ORANGE,
            hard_stop_suffix=RESET,
            stream_inactive_prefix=YELLOW,
            stream_inactive_suffix=RESET,
        )
        local_audio_buffer = snapshot_audio_buffer_impl(
            audio_buffer, audio_data_lock
        )
        audio_buffer = np.concatenate([pre_recording_data, local_audio_buffer], axis=0)
        audio_buffer = _trim_audio_to_max_duration(audio_buffer)
        if keyword_index == 1:
            audio_duration_seconds = len(audio_buffer) / float(sample_rate)
            logging.info(
                "Wake capture audio prepared for 'hey_computer10': %.2fs (%d samples)",
                audio_duration_seconds,
                len(audio_buffer),
            )
        record_activation_event("queued_audio")
        audio_buffer_queue.put((audio_buffer.copy(), keyword_index))
        audio_buffer = []

        _restore_volume_all_async(delay_seconds=restore_delay_seconds)
        audio_buffer = []

        if play_pause_pressed:
            _restore_volume_all_async(delay_seconds=restore_delay_seconds)
            play_pause_pressed = False

        beep(STOP_BEEP)
        with recording_lock:
            recording = False
            active_recording_session_id = 0
        logging.info(f"{MAGENTA}Recording stopped. Processing audio...{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error in stop_recording: {e}{RESET}", exc_info=True)
        reset_state()
    finally:
        if stop_claimed:
            with recording_lock:
                recording_stop_in_progress = False
            _flush_deferred_keyboard_listener_restart()

keyboard_handler = None
broker_control_shutdown_requested = threading.Event()
broker_control_shutdown_reason = None
broker_control_shutdown_reason_lock = threading.Lock()

def _start_recording_async(keyword_index):
    reset_activation_metrics()
    record_activation_event("hotkey_press")
    threading.Thread(target=start_recording, args=(keyword_index,)).start()

def _stop_recording_async(keyword_index):
    threading.Thread(target=stop_recording, args=(keyword_index,)).start()


def _cancel_recording_async(keyword_index, reason):
    threading.Thread(
        target=cancel_recording,
        args=(keyword_index, reason),
        daemon=True,
        name="ManualRecordingCancel",
    ).start()


def get_broker_control_status():
    with recording_lock:
        is_recording = recording
        stop_in_progress = recording_stop_in_progress
        session_id = active_recording_session_id
    return {
        "recording": is_recording,
        "recording_stop_in_progress": stop_in_progress,
        "active_recording_session_id": session_id,
        "runtime_mode": runtime_mode,
        "keyboard_runtime_enabled": is_keyboard_runtime_enabled(),
        "python_keyboard_listener_enabled": is_python_keyboard_listener_enabled(),
        "activation": get_activation_status(),
    }


def request_broker_control_shutdown(reason="broker_control_shutdown"):
    global broker_control_shutdown_reason
    with broker_control_shutdown_reason_lock:
        broker_control_shutdown_reason = str(reason)
    broker_control_shutdown_requested.set()


def get_broker_control_shutdown_reason():
    with broker_control_shutdown_reason_lock:
        return broker_control_shutdown_reason


def start_broker_control_stdio_thread(input_stream=None, output_stream=None):
    deps = BrokerRuntimeDeps(
        start=_start_recording_async,
        stop=_stop_recording_async,
        cancel=_cancel_recording_async,
        status=get_broker_control_status,
        shutdown=request_broker_control_shutdown,
    )
    thread = threading.Thread(
        target=run_control_stdio,
        args=(input_stream or sys.stdin, output_stream or sys.stdout, deps),
        daemon=True,
        name="BrokerControlStdio",
    )
    thread.start()
    return thread


def _capture_wake_command(keyword_index, grace_seconds=COMPUTER_WAKE_CAPTURE_GRACE_SECONDS):
    start_recording(keyword_index)
    with recording_lock:
        started = recording and active_recording_session_id != 0
    if not started:
        logging.info(
            f"{YELLOW}Wake capture worker skipped stop because recording never started for keyword_index={keyword_index}.{RESET}"
        )
        return

    logging.info(
        "Wake capture mode for 'hey_computer10': holding %.2fs before silence stop",
        grace_seconds,
    )
    time.sleep(grace_seconds)
    stop_recording(keyword_index)

def _capture_wake_command_async(keyword_index):
    threading.Thread(
        target=_capture_wake_command,
        args=(keyword_index,),
        daemon=True,
        name="WakeCommandCapture",
    ).start()

def init_keyboard_handler():
    global keyboard_handler
    keyboard_handler = KeyboardShortcutHandler(
        record_keys=RECORD_KEYS.values(),
        map_key_to_keyword_index=map_key_to_keyword_index,
        start_recording=_start_recording_async,
        stop_recording=_stop_recording_async,
        cancel_recording=_cancel_recording_async,
        cancel_on_chord_keys={key for label, key in RECORD_KEYS.items() if label != "f24"},
        toggle_pause=toggle_pause_state,
        debounce_time=0.5,
        log=logging,
    )

def on_press(key):
    """Key press handler for voice activation keys and pause shortcut."""
    try:
        global recording
        if keyboard_handler is None:
            return
        keyboard_handler.on_press(key, recording)
    except Exception as e:
        logging.error(f"Error in on_press: {e}", exc_info=True)

def on_release(key):
    """Key release handler for voice activation keys and pause shortcut."""
    try:
        global recording
        if keyboard_handler is None:
            return
        keyboard_handler.on_release(key, recording)
    except Exception as e:
        logging.error(f"Error in on_release: {e}", exc_info=True)

"""
 ######     ###    ##     ## ######## 
##    ##   ## ##   ##     ## ##       
##        ##   ##   ##     ## ##       
 ######  ##     ##  ##     ## ######   
      ## #########  ##   ##  ##       
##    ## ##     ##   ## ##   ##       
 ######  ##     ##    ###    ######## 
"""

def save_audio(
    audio_data,
    keyword_index,
    directory="J:\\Openwakeword_whisper_keyboard_training_data_hotword\\train",
    sample_rate=16000,
    type_of_audio=None,
):
    try:
        if not os.path.exists(directory):
            logging.info(f"cannot save data to {directory} because it does not exist")
            return

        base_filename = os.path.join(
            directory, f"{type_of_audio}_{keyword_index}_recording.wav"
        )
        filename = base_filename
        counter = 1

        while os.path.exists(filename):
            filename = os.path.join(
                directory, f"{type_of_audio}_{keyword_index}_recording_{counter}.wav"
            )
            counter += 1

        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val

        audio_data_int16 = np.int16(audio_data * 32767)
        wav_write(filename, sample_rate, audio_data_int16)
        logging.info(f"{GREEN}Audio saved as {filename}{RESET}")
    except Exception as e:
        logging.error(f"Error in save_audio: {e}", exc_info=True)

def save_manual_recording_if_configured(
    audio_data,
    keyword_index,
    sample_rate=16000,
    target_dir=r"I:\Record_harsha",
):
    try:
        if audio_data is None or len(audio_data) == 0:
            return None
        if not os.path.isdir(target_dir):
            return None

        key_label_local = "f24" if keyword_index == 0 else "dictation"
        duration_ms = int((len(audio_data) / sample_rate) * 1000)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        base_name = f"manual_{key_label_local}_{timestamp}_{duration_ms}ms.wav"
        filename = os.path.join(target_dir, base_name)
        counter = 1
        while os.path.exists(filename):
            filename = os.path.join(
                target_dir,
                f"manual_{key_label_local}_{timestamp}_{duration_ms}ms_{counter}.wav",
            )
            counter += 1

        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val
        audio_data_int16 = np.int16(audio_data * 32767)
        wav_write(filename, sample_rate, audio_data_int16)
        logging.info(f"{GREEN}Saved manual recording: {filename}{RESET}")
        return filename
    except Exception as e:
        logging.error(f"Error saving manual recording: {e}", exc_info=True)
        return None

"""
 #######  ##      ## ##      ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
 #######   ###  ###   ###  ###  
"""

def check_pause_status():
    """Check if voice recognition should be paused"""
    global global_pause_active, last_pause_check
    global_pause_active, last_pause_check, paused = pause_check_impl(
        FLAG_PATH, last_pause_check, global_pause_active
    )
    return paused

def set_pause_state(paused: bool):
    global global_pause_active, last_pause_check
    pause_set_impl(FLAG_PATH, paused)
    global_pause_active = paused
    last_pause_check = time.time()

def toggle_pause_state():
    global global_pause_active, last_pause_check
    global_pause_active = pause_toggle_impl(FLAG_PATH, global_pause_active)
    last_pause_check = time.time()
    if global_pause_active:
        logging.info(f"{RED}Voice recognition paused via shortcut{RESET}")
    else:
        logging.info(f"{GREEN}Voice recognition resumed via shortcut{RESET}")

def check_microphone():
    try:
        devices = sd.query_devices()
        for device in devices:
            if device["max_input_channels"] > 0:
                return True
        return False
    except Exception as e:
        logging.error(f"Error in check_microphone: {e}", exc_info=True)

def wait_for_microphone(poll_interval=5):
    while not check_microphone():
        logging.info(f"{RED}No microphone detected. Waiting for microphone...{RESET}")
        time.sleep(poll_interval)

def reinitialize_pyaudio():
    try:
        global p
        with wake_stream_lock:
            if p is not None:
                p.terminate()
            p = pyaudio.PyAudio()
    except Exception as e:
        logging.error(f"Error in reinitialize_pyaudio: {e}", exc_info=True)

def monitor_microphone_availability():
    logging.info("microphone_monitor_disabled recovery_policy=%s", RECOVERY_POLICY)

def set_wake_stream(value):
    global wake_stream
    with wake_stream_lock:
        wake_stream = value

def init_wakeword_listener():
    global wakeword_listener
    if wakeword_listener is None:
        wakeword_listener = WakeWordListener()
    return wakeword_listener

"""
##       ####  ######  ######## ######## ##    ## 
##        ##  ##    ##    ##    ##       ###   ## 
##        ##  ##          ##    ##       ####  ## 
##        ##   ######     ##    ######   ## ## ## 
##        ##        ##    ##    ##       ##  #### 
##        ##  ##    ##    ##    ##       ##   ### 
######## ####  ######     ##    ######## ##    ## 
"""

def listen_for_wake_word():
    """Wake-word loop delegated to wakeword module."""
    while not is_wakeword_runtime_enabled():
        touch_heartbeat("wakeword listener")
        time.sleep(1)
    listener = init_wakeword_listener()
    listener.listen(
        get_wake_stream=get_current_wake_stream,
        set_wake_stream=set_wake_stream,
        check_pause_status=check_pause_status,
        is_recording=lambda: recording,
        start_recording_async=_start_recording_async,
        stop_recording_async=_stop_recording_async,
        capture_wake_command_async=_capture_wake_command_async,
        decrease_volume_all=decrease_volume_all,
        restore_volume_all=restore_volume_all,
        should_relax=should_relax_resources,
        wake_stream_lock=wake_stream_lock,
        is_recovery_active=is_audio_recovery_in_progress,
        is_enabled=is_wakeword_runtime_enabled,
        shared_audio_source=read_shared_wake_audio if runtime_mode == "combined" else None,
        heartbeat=lambda: touch_heartbeat("wakeword listener"),
        log=lambda message: logging.info(message),
    )

def cleanup():
    try:
        global p
        _close_wake_stream_for_recovery()
        with wake_stream_lock:
            if p is not None:
                p.terminate()
                p = None
        if groq_session_holder.get("session") is not None:
            asyncio.get_event_loop().run_until_complete(
                groq_session_holder["session"].close()
            )
            groq_session_holder["session"] = None
        logging.info("Cleanup completed.")
    except Exception as e:
        logging.error(f"Error in cleanup: {e}", exc_info=True)

"""
 ######   ########   #######   #######  
##    ##  ##     ## ##     ## ##     ## 
##        ##     ## ##     ## ##     ## 
##   #### ########  ##     ## ##     ## 
##    ##  ##   ##   ##     ## ##  ## ## 
##    ##  ##    ##  ##     ## ##    ##  
 ######   ##     ##  #######   ##### ## 
"""

transcribe_pre_recording_buffer_prompt = (
    "you are downstream to hotword detection algorithm. check if you are able to detect "
    "the wake word 'computer' or 'lama' in the audio"
)


def transcribe_pre_recording_buffer(pre_recording_data, max_retries=3, retry_delay=2):
    return transcribe_pre_recording_buffer_util(
        pre_recording_data,
        sample_rate,
        api_key,
        transcribe_pre_recording_buffer_prompt,
        get_groq_audio_model,
        max_retries=max_retries,
        retry_delay=retry_delay,
        report_model_failure=note_audio_stt_model_failure,
        report_rate_limit=note_audio_stt_rate_limit,
    )


async def transcribe_with_groq_async(byte_io, keyword_index, max_retries=3):
    prompt = _build_dynamic_stt_prompt(keyword_index)
    return await transcribe_with_groq_async_util(
        byte_io,
        keyword_index,
        api_key,
        get_groq_audio_model,
        prompt,
        groq_session_holder,
        max_retries=max_retries,
        report_model_failure=note_audio_stt_model_failure,
        report_rate_limit=note_audio_stt_rate_limit,
    )


def transcribe_with_local_model(audio_buffer, keyword_index):
    return transcribe_with_local_model_util(
        audio_buffer, keyword_index, model, sample_rate
    )

result_queue = queue.Queue()

def init_transcription_pipeline():
    global transcription_pipeline
    if transcription_pipeline is None:
        transcription_pipeline = TranscriptionPipeline(
            audio_buffer_queue=audio_buffer_queue,
            transcript_queue=transcript_queue,
            settings_getter=lambda: SETTINGS,
            sample_rate=sample_rate,
            validate_audio_buffer=validate_audio_buffer,
            transcribe_with_groq_async=transcribe_with_groq_async,
            transcribe_with_local_model=transcribe_with_local_model,
            model_getter=lambda: model,
            gpu_available_getter=lambda: gpu_available,
            initialize_local_model_cpu=initialize_local_model_cpu,
            paste_transcript=paste_transcript,
            beep=beep,
            global_state=global_state,
            log=logging,
            error_color_prefix=RED,
            error_color_suffix=RESET,
            record_transcript_context=_record_recent_transcript,
            speaker_filter_getter=get_target_speaker_filter,
            speaker_filter_status_writer=write_target_speaker_status,
        )
    return transcription_pipeline

async def process_audio_async():
    pipeline = init_transcription_pipeline()
    global_state["last_heartbeat"] = time.time()
    await pipeline.process_audio_async()

def validate_audio_buffer(audio_buffer):
    return validate_audio_buffer_util(audio_buffer, sample_rate)


def create_wav_buffer(audio_buffer):
    return create_wav_buffer_util(audio_buffer, sample_rate)


async def get_transcript_with_retries(byte_io, keyword_index, max_retries=3):
    for attempt in range(max_retries):
        try:
            if SETTINGS.get("fallback_to_groq", True):
                transcript = await transcribe_with_groq_async(byte_io, keyword_index)
                if transcript:
                    return transcript
        except Exception as e:
            logging.error("Transcription attempt %s failed: %s", attempt + 1, e)
            if attempt == max_retries - 1:
                return transcribe_with_local_model(byte_io, keyword_index)
        await asyncio.sleep(1)
    return None

async def process_transcript(transcript, keyword_index, audio_buffer):
    try:
        if keyword_index is None:
            if len(transcript) > 3:
                paste_transcript(transcript, beep)
        elif keyword_index == 1 and "computer" in transcript:
            keyword_pos = transcript.index("computer")
            stripped = transcript[keyword_pos + len("computer") :].strip()
            if stripped:
                transcript_queue.put((stripped, keyword_index))
        elif keyword_index == 2 and "lama" in transcript:
            keyword_pos = transcript.index("lama")
            stripped = transcript[keyword_pos + len("lama") :].strip()
            if stripped:
                paste_transcript(stripped, beep)
        else:
            logging.info(f"{YELLOW}No matching keyword found in transcript{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error processing transcript: {e}{RESET}", exc_info=True)

def start_listener():
    global keyboard_listener
    listener = None
    try:
        listener = Listener(on_press=on_press, on_release=on_release)
        with keyboard_listener_lock:
            keyboard_listener = listener
        with listener:
            listener.join()
    except KeyboardInterrupt:
        logging.info("Ctrl+C pressed. Exiting...")
    except Exception as e:
        logging.error(f"Error in start_listener: {e}", exc_info=True)
    finally:
        with keyboard_listener_lock:
            if keyboard_listener is listener:
                keyboard_listener = None

def beep(sound):
    try:
        frequency, duration = sound
        winsound.Beep(frequency, duration)
    except Exception as e:
        logging.error(f"Error in beep: {e}", exc_info=True)


def paste_transcript(transcript: str = "", beep_func=None, status_callback=None, **kwargs):
    if status_callback is None:
        status_callback = set_transient_status_message
    return clipboard_paste_transcript(
        transcript=transcript,
        beep_func=beep_func,
        status_callback=status_callback,
        copyq_recovery_beep=COPYQ_RECOVERY_BEEP,
        **kwargs,
    )

"""
########  ########  ######  ######## ######## ##    ## 
##     ## ##       ##    ## ##          ##    
##     ## ##       ##       ##          ##    
########  ######    ######  ######      ##    
##   ##   ##             ## ##          ##    
##    ##  ##       ##    ## ##          ##    
##     ## ########  ######  ########    ##    
"""

def reset_state():
    try:
        global recording, play_pause_pressed, audio_buffer, active_recording_session_id
        recording = False
        active_recording_session_id = 0
        play_pause_pressed = False
        audio_buffer = []
        _clear_manual_recording_cancel_pending()
        force_release_volume_ducking("reset_state", level=logging.WARNING)
        logging.info("State reset completed")
    except Exception as e:
        logging.error(f"Error in reset_state: {e}", exc_info=True)

def monitor_state():
    try:
        while True:
            if recording and time.time() - recording_start_time > 60:
                logging.error("Recording stuck in active state")
                reset_state()
            time.sleep(60)
    except Exception as e:
        logging.error(f"Error in monitor_state: {e}", exc_info=True)

"""
 ######  ##       #### ########  ########   #######     ###    ########  ########  
##    ## ##        ##  ##     ## ##     ## ##     ##   ## ##   ##     ## ##     ## 
##       ##        ##  ##     ## ##     ## ##     ##  ##   ##  ##     ## ##     ## 
##       ##        ##  ########  ########  ##     ## ##     ## ########  ##     ## 
##       ##        ##  ##        ##     ## ##     ## ######### ##   ##   ##     ## 
##    ## ##        ##  ##        ##     ## ##     ## ##     ## ##    ##  ##     ## 
 ######  ######## #### ##        ########   #######  ##     ## ##     ## ########  
"""


async def clean_transcript():
    try:
        while True:
            try:
                global clarification_retry_used
                global_state["last_heartbeat"] = time.time()
                transcript, keyword_index = transcript_queue.get()
                logging.debug(
                    "clean_transcript received keyword_index=%s transcript_len=%d",
                    keyword_index,
                    len(transcript or ""),
                )
                if keyword_index in (0, 1):
                    if is_ask_ai_enabled():
                        transcript = normalize_ai_triggers(transcript)
                    logging.debug(
                        "clean_transcript routing to execute_command_run_with_tool "
                        "keyword_index=%s transcript_len=%d",
                        keyword_index,
                        len(transcript or ""),
                    )
                    router_context_hint = _build_router_context_hint(transcript)
                    await execute_command_run_with_tool(
                        transcript,
                        context_hint=router_context_hint,
                    )
                    if voice_commands_module.last_tool_call_found:
                        clarification_retry_used = False
                    if keyword_index == 1:
                        if (
                            not voice_commands_module.last_tool_call_found
                            and not clarification_retry_used
                        ):
                            clarification_retry_used = True
                            _schedule_clarification_retry()
                elif keyword_index == 2:
                    pass
                elif keyword_index == 3:
                    logging.debug(
                        "clean_transcript routing to google_assistant transcript_len=%d",
                        len(transcript or ""),
                    )
                    await google_assistant(transcript)
                else:
                    logging.info(f"Unknown keyword index {keyword_index}")
                logging.info(
                    f"{BRIGHT_GREEN}Say 'Hey computer' or 'rey lama' wake word...{RESET}"
                )
            except Exception as e:
                logging.error(
                    f"An error occurred in clean_transcript: {e}", exc_info=True
                )
    except Exception as e:
        logging.error(f"Error in clean_transcript: {e}", exc_info=True)

"""
##     ##    ###    #### ##    ## 
###   ###   ## ##    ##  ###   ## 
#### ####  ##   ##   ##  ####  ## 
## ### ## ##     ##  ##  ## ## ## 
##     ## #########  ##  ##  #### 
##     ## ##     ##  ##  ##   ### 
##     ## ##     ## #### ##    ## 
"""

_spinner = None
_spinner_thread = None
_status_override_lock = threading.Lock()
_status_override_message = None
_status_override_until = 0.0

clarification_retry_used = False
CLARIFICATION_MAX_SECONDS = 6.0

def _schedule_clarification_stop():
    def _run():
        try:
            time.sleep(CLARIFICATION_MAX_SECONDS)
            if recording:
                stop_recording(keyword_index=0)
        except Exception as e:
            logging.error(f"Error scheduling clarification stop: {e}", exc_info=True)
    threading.Thread(target=_run, daemon=True).start()

def _schedule_clarification_retry():
    def _run():
        try:
            voice_commands_module.fallback_offline_tts(
                "Sorry, I didn't catch that. Please say it again.", speed=1.1
            )
            time.sleep(0.4)
            # Use keyword_index=0 to bypass wake-word validation for the clarification response
            start_recording(keyword_index=0)
            _schedule_clarification_stop()
        except Exception as e:
            logging.error(f"Error scheduling clarification retry: {e}", exc_info=True)
    threading.Thread(target=_run, daemon=True).start()


def set_transient_status_message(message: str, duration: float = 3.0):
    global _status_override_message, _status_override_until
    cleaned = (message or "").strip()
    with _status_override_lock:
        if not cleaned:
            _status_override_message = None
            _status_override_until = 0.0
            return
        _status_override_message = cleaned
        _status_override_until = time.monotonic() + max(0.0, duration)


def get_transient_status_message():
    global _status_override_message, _status_override_until
    with _status_override_lock:
        if not _status_override_message:
            return None
        if time.monotonic() >= _status_override_until:
            _status_override_message = None
            _status_override_until = 0.0
            return None
        return _status_override_message

def display_pause_status(start: bool = True):
    """Start/stop the pause-status spinner."""
    global _spinner, _spinner_thread

    if start:
        if _spinner_thread and _spinner_thread.is_alive():
            return  # already running

        if is_wakeword_runtime_enabled():
            active_message = (
                f"{GREEN}Voice recognition active - Say 'Hey computer' or wake word... "
                f"(Ctrl+Alt+Shift+ScrollLock to pause){RESET}"
            )
            paused_message = (
                f"{RED}VOICE RECOGNITION PAUSED (wake words paused, manual key "
                f"dictation still allowed) - Press Ctrl+Alt+Shift+ScrollLock to "
                f"resume wake words{RESET}"
            )
        else:
            manual_keys_text = record_key_display_text(record_key_source)
            active_message = (
                f"{GREEN}Keyboard dictation active - Hold {manual_keys_text} to record. "
                f"Wake-word detection is off.{RESET}"
            )
            paused_message = (
                f"{RED}WAKE-WORD DETECTION OFF - Manual {manual_keys_text} dictation still "
                f"allowed{RESET}"
            )

        _spinner = make_status_display(
            check_pause_status=check_pause_status,
            active_message=active_message,
            paused_message=paused_message,
            override_message=get_transient_status_message,
            spinner_frames=(
                f"{RED}█{RESET}",
                f"{BLUE}▄{RESET}",
                f"{RED}█{RESET}",
                f"{YELLOW}▄{RESET}",
                f"{YELLOW}█{RESET}",
                f"{GREEN}█{RESET}",
                f"{BLUE}▄{RESET}",
            ),
            refresh_interval=0.1,
        )

        def runner():
            try:
                _spinner()
            except Exception as e:
                logging.exception("Error in display_pause_status: %s", e)

        _spinner_thread = threading.Thread(target=runner, daemon=True)
        _spinner_thread.start()
    else:
        if _spinner:
            _spinner.stop()
        if _spinner_thread:
            _spinner_thread.join(timeout=1)
        _spinner = None
        _spinner_thread = None

def start_thread(target, name):
    try:
        def run_with_restart():
            while True:
                try:
                    target()
                    global_state["last_heartbeat"] = time.time()
                except Exception as e:
                    logging.error(
                        f"Thread {name} crashed with exception: {e}", exc_info=True
                    )
                    time.sleep(5)

        thread = threading.Thread(target=run_with_restart, name=name, daemon=True)
        thread.start()
        return thread
    except Exception as e:
        logging.error(f"Error in start_thread: {e}", exc_info=True)

global_state = {
    "last_successful_operation": time.time(),
    "consecutive_failures": 0,
    "is_processing": False,
    "last_heartbeat": time.time(),
    "transcribe_inflight": False,
    "last_transcribe_activity": time.time(),
}

WATCHDOG_INTERVAL_SECONDS = 30
WATCHDOG_STALE_SECONDS = 120

def start_watchdog():
    """Dump thread stacks if no heartbeat for a while (helps catch silent hangs)."""
    global _fault_log_handle
    if _fault_log_handle is None:
        try:
            _fault_log_handle = open(FAULT_LOG_PATH, "a", buffering=1)
            faulthandler.enable(_fault_log_handle, all_threads=True)
        except Exception as e:
            logging.error(f"{RED}Failed to init faulthandler: {e}{RESET}", exc_info=True)

    def _watch():
        while True:
            try:
                now = time.time()
                if now - global_state.get("last_heartbeat", now) > WATCHDOG_STALE_SECONDS:
                    logging.error(
                        f"{RED}Watchdog: no heartbeat for {WATCHDOG_STALE_SECONDS}s. Dumping stacks...{RESET}"
                    )
                    faulthandler.dump_traceback(all_threads=True)
                    # reset heartbeat so it doesn't spam
                    global_state["last_heartbeat"] = now
                if global_state.get("transcribe_inflight"):
                    last_transcribe = global_state.get("last_transcribe_activity", now)
                    if now - last_transcribe > (WATCHDOG_STALE_SECONDS + 30):
                        logging.error(
                            f"{RED}Watchdog: transcription stuck for {int(now - last_transcribe)}s. Dumping stacks...{RESET}"
                        )
                        faulthandler.dump_traceback(all_threads=True)
                        global_state["last_transcribe_activity"] = now
            except Exception as e:
                logging.error(f"{RED}Watchdog error: {e}{RESET}", exc_info=True)
            time.sleep(WATCHDOG_INTERVAL_SECONDS)

    threading.Thread(target=_watch, name="Watchdog", daemon=True).start()

def touch_heartbeat(source="runtime"):
    global_state["last_heartbeat"] = time.time()
    write_backend_health_status(source=source)

def monitor_program_health():
    try:
        while True:
            current_time = time.time()
            if global_state["consecutive_failures"] > 5:
                logging.error(
                    f"{RED}Too many consecutive failures. Resetting state...{RESET}"
                )
                reset_all_states()

            if current_time - global_state["last_successful_operation"] > 30:
                logging.error(
                    f"{RED}No successful operations in 30 seconds. Resetting state...{RESET}"
                )
                reset_all_states()

            time.sleep(5)
    except Exception as e:
        logging.error(
            f"{RED}Error in monitor_program_health: {e}{RESET}", exc_info=True
        )

def reset_all_states():
    try:
        global recording, play_pause_pressed, audio_buffer, stream, wake_stream, active_recording_session_id, recording_stop_in_progress

        with recording_lock:
            recording = False
            active_recording_session_id = 0
            recording_stop_in_progress = False

        play_pause_pressed = False
        audio_buffer = []

        while not audio_buffer_queue.empty():
            try:
                audio_buffer_queue.get_nowait()
            except QueueEmpty:
                break

        while not wake_audio_queue.empty():
            try:
                wake_audio_queue.get_nowait()
            except QueueEmpty:
                break

        while not transcript_queue.empty():
            try:
                transcript_queue.get_nowait()
            except QueueEmpty:
                break

        _close_input_stream_for_recovery()

        if not initialize_input_stream():
            stream = None

        _close_wake_stream_for_recovery()
        if is_wakeword_runtime_enabled() and runtime_mode != "combined":
            initialize_wake_stream()
        request_keyboard_listener_restart("reset_all_states")

        global_state["consecutive_failures"] = 0
        global_state["last_successful_operation"] = time.time()
        global_state["is_processing"] = False

        force_release_volume_ducking("reset_all_states", level=logging.WARNING)
        logging.info(f"{GREEN}All states reset successfully{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error in reset_all_states: {e}{RESET}", exc_info=True)

def main():
    global stream
    global driver
    global driver_pid

    if is_keyboard_runtime_enabled():
        logging.info(
            f"{CYAN}wkey is active. Enabled manual keys: {BOLD}{','.join(RECORD_KEYS.keys()).upper()}{RESET}{CYAN}.{RESET}"
        )
    else:
        logging.info(f"{CYAN}wkey is active in wake-word-only mode.{RESET}")
    logging.info(
        "%sRuntime mode=%s enabled_record_keys=%s%s",
        CYAN,
        runtime_mode,
        ",".join(RECORD_KEYS.keys()) or "none",
        RESET,
    )
    logging.info(
        "Startup diagnostics: pid=%s runtime_mode=%s wakeword_enabled=%s "
        "precheck_enabled=%s keyboard_runtime_enabled=%s "
        "python_keyboard_listener_enabled=%s enabled_record_keys=%s "
        "env_overrides_enabled=%s recovery_policy=%s",
        os.getpid(),
        runtime_mode,
        is_wakeword_runtime_enabled(),
        is_pre_recording_keyword_check_enabled(),
        is_keyboard_runtime_enabled(),
        is_python_keyboard_listener_enabled(),
        ",".join(RECORD_KEYS.keys()) or "none",
        _env_overrides_enabled(),
        RECOVERY_POLICY,
    )
    logging.info("Runtime logging active path=%s", ACTIVE_RUNTIME_LOG_PATH)
    logging.info(
        f"{CYAN}Press Ctrl+Alt+Shift+Scroll Lock to pause/resume voice recognition.{RESET}"
    )
    logging.info(f"{CYAN}Using canonical pause flag path: {FLAG_PATH}{RESET}")

    def exception_handler(exc_type, exc_value, exc_traceback):
        logging.error(
            f"{RED}Unhandled exception:{RESET}",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = exception_handler

    try:
        register_volume_timeout_recovery_hook()
        if is_python_keyboard_listener_enabled():
            init_keyboard_handler()
        start_settings_watch()
        started_background_threads = []

        def start_runtime_thread(target, name):
            started_background_threads.append(name)
            return start_thread(target, name)

        if is_broker_control_stdio_enabled():
            start_broker_control_stdio_thread()
            started_background_threads.append("BrokerControlStdio")

        if is_wakeword_runtime_enabled():
            init_wakeword_listener()
            if runtime_mode == "combined":
                logging.info("Wake-word detection using shared input stream in combined mode.")
            else:
                initialize_wake_stream()
            start_runtime_thread(listen_for_wake_word, "WakeWordListener")
        if RESUME_RECOVERY_ENABLED:
            start_runtime_thread(audio_recovery_worker, "AudioRecovery")
            start_runtime_thread(audio_recovery_watchdog, "ResumeAudioWatchdog")
        start_watchdog()
        loop2 = asyncio.new_event_loop()
        start_runtime_thread(
            lambda: run_asyncio_in_thread(loop2, clean_transcript()), "CleanTranscript"
        )
        loop = asyncio.new_event_loop()
        start_runtime_thread(
            lambda: run_asyncio_in_thread(loop, process_audio_async()), "ProcessAudio"
        )
        logging.info(
            "Startup background threads: %s",
            ",".join(started_background_threads) or "none",
        )
        selenium_enabled = True
        try:
            selenium_enabled = bool(voice_commands_module.is_selenium_enabled())
        except AttributeError:
            selenium_enabled = True
        except Exception as e:
            logging.warning(
                f"{YELLOW}Could not read Selenium setting at startup; defaulting to enabled ({e}).{RESET}"
            )
        if selenium_enabled:
            threading.Thread(
                target=start_driver,
                daemon=True,
                name="EdgeSeleniumStartup",
            ).start()
        else:
            logging.info(
                f"{YELLOW}Edge/Selenium browser automation disabled in settings. Skipping WebDriver startup.{RESET}"
            )
        if is_broker_control_stdio_enabled():
            logging.info("Broker stdio mode active. Skipping console status display.")
        else:
            threading.Thread(target=display_pause_status, daemon=True).start()

        while not broker_control_shutdown_requested.is_set():
            touch_heartbeat("main loop")
            wait_for_microphone()
            if not initialize_input_stream():
                time.sleep(5)
                continue

            python_listener_owns_input = is_python_keyboard_listener_enabled()
            try:
                if python_listener_owns_input:
                    start_listener()
                else:
                    time.sleep(1)
            except Exception as e:
                logging.error(
                    f"{RED}Input stream error: {str(e)}{RESET}", exc_info=True
                )
            finally:
                keyboard_listener_restart_requested.clear()
                if python_listener_owns_input:
                    _close_input_stream_for_recovery()
            time.sleep(2)
        logging.info("Broker control shutdown requested. Exiting main loop.")

    except Exception as e:
        logging.error(
            f"{RED}Critical error in main: {str(e)}\n{traceback.format_exc()}{RESET}"
        )
        reset_all_states()
    finally:
        try:
            if stream and stream.active:
                stream.stop()
                stream.close()
            cleanup()
            force_release_volume_ducking("main_cleanup", level=logging.WARNING)
            logging.info(f"{YELLOW}Cleanup completed. Exiting...{RESET}")
            if driver:
                driver.quit()
        except Exception as e:
            logging.error(
                f"{RED}Error during cleanup: {str(e)}\n{traceback.format_exc()}{RESET}"
            )

_runtime_lock_handle = None


def _try_lock_runtime_file(handle):
    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    raise OSError("No runtime file lock implementation available")


def _unlock_runtime_file(handle):
    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    elif fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_runtime_lock_pid(lock_path):
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    except Exception:
        return "unknown"


def acquire_runtime_singleton(lock_path=RUNTIME_LOCK_PATH):
    global _runtime_lock_handle
    if _runtime_lock_handle is not None:
        return True

    handle = open(lock_path, "a+", encoding="utf-8")
    try:
        _try_lock_runtime_file(handle)
    except OSError:
        existing_pid = _read_runtime_lock_pid(lock_path)
        # The OS file lock is itself the liveness oracle: a truly-dead owner
        # (whatever pid it recorded, including a stale numeric pid or "unknown")
        # releases the lock within a moment, so we can reclaim it; a live owner
        # keeps holding it, so the retry keeps failing and we back off and exit.
        reclaimed = False
        for _ in range(3):
            time.sleep(0.3)
            try:
                _try_lock_runtime_file(handle)
            except OSError:
                continue
            reclaimed = True
            break
        if reclaimed:
            logging.warning(
                "%sreclaimed_stale_runtime_lock prev_pid=%s lock=%s%s",
                YELLOW,
                existing_pid,
                lock_path,
                RESET,
            )
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
            _runtime_lock_handle = handle
            return True
        handle.close()
        logging.warning(
            "%sAnother Whisper Keyboard backend is already running "
            "(pid=%s lock=%s). Exiting.%s",
            YELLOW,
            existing_pid,
            lock_path,
            RESET,
        )
        return False

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _runtime_lock_handle = handle
    return True


def release_runtime_singleton():
    global _runtime_lock_handle
    if _runtime_lock_handle is None:
        return
    handle = _runtime_lock_handle
    _runtime_lock_handle = None
    try:
        _unlock_runtime_file(handle)
    except Exception:
        pass
    try:
        handle.close()
    except Exception:
        pass


def run_backend():
    if not acquire_runtime_singleton():
        write_backend_exit_status(
            reason="duplicate_runtime_lock",
            exit_code=DUPLICATE_BACKEND_EXIT_CODE,
            recoverable=False,
        )
        return DUPLICATE_BACKEND_EXIT_CODE
    try:
        while not broker_control_shutdown_requested.is_set():
            try:
                main()
            except Exception as e:
                logging.error(
                    f"{RED}Fatal error: {str(e)}\n{traceback.format_exc()}{RESET}"
                )
                time.sleep(5)
    finally:
        release_runtime_singleton()

    reason = get_broker_control_shutdown_reason() or "normal_shutdown"
    recoverable = reason == "input_overflow_burst"
    exit_code = RECOVERABLE_RESTART_EXIT_CODE if recoverable else 0
    write_backend_exit_status(
        reason=reason,
        exit_code=exit_code,
        recoverable=recoverable,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(run_backend())
