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
    from model_rotation import next_audio_stt_model
except ModuleNotFoundError:
    from wkey.model_rotation import next_audio_stt_model
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
    from clipboard_utils import paste_transcript
except ModuleNotFoundError:
    from wkey.clipboard_utils import paste_transcript
import webrtcvad
try:
    from voice_activity_detection import VoiceDetector
except ModuleNotFoundError:
    from wkey.voice_activity_detection import VoiceDetector
import traceback
from queue import Empty as QueueEmpty
from contextlib import contextmanager
try:
    from faster_whisper_Mother_of_all_wkey_status_display import make_status_display
except ModuleNotFoundError:
    from wkey.faster_whisper_Mother_of_all_wkey_status_display import make_status_display
try:
    from settings_manager import (
        load_settings,
        watch_settings,
        DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
    )
except ModuleNotFoundError:
    from wkey.settings_manager import (
        load_settings,
        watch_settings,
        DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
    )
try:
    from keyboard_shortcuts import KeyboardShortcutHandler
except ModuleNotFoundError:
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler
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

# Set up driver reference for commands_and_tools
try:
    from commands_and_tools import set_driver_reference
    set_driver_reference(driver)
except ImportError:
    pass

# Add global variables for pause functionality
FLAG_PATH = os.path.join(os.path.dirname(__file__), "voice_pause_flag.txt")
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

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("whisper_keyboard.log", encoding="utf-8"),
        logging.StreamHandler(_safe_console_stream()),
    ],
)

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

# Initialize VoiceDetector
vad_detector = VoiceDetector()

load_dotenv()

# Load transcription settings
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")
SETTINGS = load_settings(SETTINGS_PATH, SETTINGS_DEFAULTS)

# Get the key labels from environment variables, default to 'f24' if not set
key_label = os.environ.get("WKEY", "f24").lower()
# Support both 'f24' and 'ctrl_r' as valid keys
if key_label not in ['f24', 'ctrl_r']:
    print(f"Warning: WKEY '{key_label}' is not supported. Defaulting to 'f24'")
    key_label = 'f24'

# Store both possible record keys
RECORD_KEYS = {
    'f24': Key.f24,
    'ctrl_r': Key.ctrl_r
}

def map_key_to_keyword_index(key):
    """Return keyword index for a given manual trigger key."""
    if key == RECORD_KEYS['f24']:
        return 0  # Route directly to execute_command_run_with_tool
    return None  # Default manual (paste) pathway

keyboard_controller = KeyboardController()
recording = False
stream = None
audio_buffer = np.array([], dtype="float32")
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

settings_watch_handle = None

def apply_settings(new_settings):
    global SETTINGS, gpu_available, model, model_device, cpu_model_initialized
    SETTINGS = new_settings

    want_gpu = SETTINGS.get("use_local_gpu", True)
    want_cpu = SETTINGS.get("use_local_cpu", True)

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
General_gorq_system_prompt = "when outputting numbers, no spaces, no commas, no hyphens, just numbers like for example:84567945"

api_key = os.getenv("GROQ_API_KEY")
global Groq_client
Groq_client = Groq(api_key=api_key)

# Reusable HTTP session for Groq API calls
groq_session_holder = {"session": None}

p = pyaudio.PyAudio()
wake_stream = None
wakeword_listener = None
transcription_pipeline = None

# Define beep sounds
START_BEEP = (2080, 100)
STOP_BEEP = (440, 100)

# Locks for synchronization
recording_lock = threading.Lock()
audio_data_lock = threading.Lock()

# Wake-word validation synchronization
keyword_validation_event = threading.Event()
keyword_validation_result = None
KEYWORD_VALIDATION_TIMEOUT = 1.5

# Resource throttling state
RESOURCE_RELAX_SECONDS_ON_OVERFLOW = 2.0
resource_relax_until = 0.0

def bump_resource_relax(seconds=RESOURCE_RELAX_SECONDS_ON_OVERFLOW):
    """Extend relax window when the audio callback reports overload."""
    global resource_relax_until
    relax_until = time.time() + seconds
    if relax_until > resource_relax_until:
        resource_relax_until = relax_until

def should_relax_resources():
    return time.time() < resource_relax_until

"""
 ######  ######## ########  ########    ###    ##     ## 
##    ##    ##    ##     ## ##         ## ##   ###   ### 
##          ##    ##     ## ##        ##   ##  #### #### 
 ######     ##    ########  ######   ##     ## ## ### ## 
      ##    ##    ##   ##   ##       ######### ##     ## 
##    ##    ##    ##    ##  ##       ##     ## ##     ## 
 ######     ##    ##     ## ######## ##     ## ##     ## 
"""

PRE_RECORDING_DURATION = 3
BUFFER_SIZE = PRE_RECORDING_DURATION * sample_rate
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
)

# Add a context manager for audio operations
@contextmanager
def audio_operation_guard():
    try:
        yield
    except Exception as e:
        logging.error(f"{RED}Audio operation failed: {e}{RESET}", exc_info=True)
        reset_state()

# Modify the audio callback for better error handling
def audio_callback(indata, frames, time, status):
    try:
        with audio_operation_guard():
            global buffer_index, audio_buffer
            if status:
                bump_resource_relax()
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
    success, stream = initialize_input_stream_impl(
        stream=stream,
        audio_callback=audio_callback,
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
        current_volume = get_volume()
        if initial_volume is None or current_volume != initial_volume:
            initial_volume = current_volume
        print(f"Decreasing volume from {initial_volume * 100}% to 10%")
        set_volume(0.1)
    except Exception as e:
        logging.error(f"Error in decrease_volume_all: {e}", exc_info=True)

def restore_volume_all():
    global initial_volume
    try:
        if initial_volume is not None:
            set_volume(initial_volume)
            time.sleep(0.5)
            initial_volume = None
    except Exception as e:
        logging.error(f"Error in restore_volume_all: {e}", exc_info=True)

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
    global True_positve_audio, recording, keyword_validation_result
    try:
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
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        elif keyword_index == 2 and "lama" not in pre_recording_transcript.lower():
            True_positve_audio = False
            keyword_validation_result = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            with recording_lock:
                recording = False
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        elif keyword_index == 3 and "google" not in pre_recording_transcript.lower():
            True_positve_audio = False
            keyword_validation_result = False
            logging.info(
                f"{RED}No relevant keyword found in pre-recording. Stopping recording.{RESET}"
            )
            with recording_lock:
                recording = False
            threading.Thread(target=stop_recording, args=(keyword_index,)).start()
        else:
            keyword_validation_result = True

    except Exception as e:
        logging.error(f"Error in check_keywords_in_transcription: {e}", exc_info=True)
        keyword_validation_result = None
    finally:
        keyword_validation_event.set()

def start_recording(keyword_index=None):
    """Start recording audio.
    
    Args:
        keyword_index: Index of the wake word that triggered recording, or None if triggered by F24 key
    """
    try:
        # Only check pause status if this was triggered by a wake word (not manual keys)
        if keyword_index not in (None, 0) and check_pause_status():
            logging.info(f"{YELLOW}Voice recognition is paused. Ignoring wake word recording request.{RESET}")
            return
            
        global stream, recording, play_pause_pressed, something_is_playing, True_positve_audio, keyword_validation_result

        with recording_lock:
            if recording:
                logging.info(f"{YELLOW}Recording is already in progress.{RESET}")
                return

            True_positve_audio = True
            keyword_validation_event.clear()
            keyword_validation_result = None
            recording = True

        logging.info(f"{GREEN}Starting recording...{RESET}")
        decrease_volume_all()

        if not initialize_input_stream():
            logging.info(f"{RED}No microphone detected. Recording canceled.{RESET}")
            with recording_lock:
                recording = False
            return

        if something_is_playing:
            logging.info(f"{ORANGE}Something is playing, decreasing volume.{RESET}")
            decrease_volume_all()
            play_pause_pressed = True

        beep(START_BEEP)
        logging.info(f"{CYAN}Listening...{RESET}")

        if keyword_index not in (None, 0) and keyword_index not in RECORD_KEYS.values():
            if pre_recording_buffer is not None and pre_recording_buffer.size > 0:
                pre_recording_data = np.roll(
                    pre_recording_buffer, -buffer_index, axis=0
                ).flatten()

                threading.Thread(
                    target=check_keywords_in_transcription,
                    args=(pre_recording_data, keyword_index),
                ).start()

    except Exception as e:
        logging.error(f"{RED}Error in start_recording: {e}{RESET}", exc_info=True)

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
    try:
        global stream, recording, play_pause_pressed, audio_buffer, sample_rate, recording_start_time, True_positve_audio, vad_detector, keyword_validation_result

        if not recording:
            if initial_volume is not None:
                threading.Thread(target=restore_volume_all).start()
            play_pause_pressed = False
            beep(STOP_BEEP)
            return

        if keyword_index in (1, 2, 3) and not keyword_validation_event.is_set():
            keyword_validation_event.wait(timeout=KEYWORD_VALIDATION_TIMEOUT)

        if keyword_index in (1, 2, 3) and keyword_validation_result is False:
            if initial_volume is not None:
                threading.Thread(target=restore_volume_all).start()
            play_pause_pressed = False
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            logging.info(
                f"{MAGENTA}Wake-word validation failed. Dropping recording.{RESET}"
            )
            True_positve_audio = True
            return

        if not True_positve_audio:
            if initial_volume is not None:
                threading.Thread(target=restore_volume_all).start()
            play_pause_pressed = False
            beep(STOP_BEEP)
            with recording_lock:
                recording = False
            logging.info(
                f"{MAGENTA}True_positve_audio...is {True_positve_audio}{RESET}"
            )
            True_positve_audio = True
            return

        logging.info(f"{GREEN}Stopping recording...{RESET}")
        hard_stop_limit = 5
        recording_start_time = time.time()

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
            pre_recording_data = np.roll(
                pre_recording_buffer_f24, -buffer_index, axis=0
            ).flatten()
            audio_buffer = np.concatenate([pre_recording_data, audio_buffer], axis=0)
            save_manual_recording_if_configured(
                audio_buffer, keyword_index, sample_rate=sample_rate
            )
            audio_buffer_queue.put((audio_buffer, keyword_index))

            threading.Thread(target=restore_volume_all).start()
            audio_buffer = np.array([], dtype="float32")

            if play_pause_pressed:
                threading.Thread(target=restore_volume_all).start()
                play_pause_pressed = False

            beep(STOP_BEEP)
            with recording_lock:
                recording = False
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
        audio_buffer_queue.put((audio_buffer.copy(), keyword_index))
        audio_buffer = np.array([], dtype="float32")

        threading.Thread(target=restore_volume_all).start()
        audio_buffer = np.array([], dtype="float32")

        if play_pause_pressed:
            threading.Thread(target=restore_volume_all).start()
            play_pause_pressed = False

        beep(STOP_BEEP)
        with recording_lock:
            recording = False
        logging.info(f"{MAGENTA}Recording stopped. Processing audio...{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error in stop_recording: {e}{RESET}", exc_info=True)
        reset_state()

keyboard_handler = None

def _start_recording_async(keyword_index):
    threading.Thread(target=start_recording, args=(keyword_index,)).start()

def _stop_recording_async(keyword_index):
    threading.Thread(target=stop_recording, args=(keyword_index,)).start()

def init_keyboard_handler():
    global keyboard_handler
    keyboard_handler = KeyboardShortcutHandler(
        record_keys=RECORD_KEYS.values(),
        map_key_to_keyword_index=map_key_to_keyword_index,
        start_recording=_start_recording_async,
        stop_recording=_stop_recording_async,
        toggle_pause=toggle_pause_state,
        debounce_time=0.5,
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
            return
        if not os.path.isdir(target_dir):
            return

        key_label_local = "f24" if keyword_index == 0 else "ctrl_r"
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
    except Exception as e:
        logging.error(f"Error saving manual recording: {e}", exc_info=True)

"""
 #######  ##      ## ##      ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
##     ## ##  ##  ## ##  ##  ## 
 #######   ###  ###   ###  ###  
"""

def _get_pause_flag_path():
    cwd_flag = os.path.join(os.getcwd(), os.path.basename(FLAG_PATH))
    if os.path.abspath(cwd_flag) != os.path.abspath(FLAG_PATH):
        return cwd_flag
    return FLAG_PATH

def check_pause_status():
    """Check if voice recognition should be paused"""
    global global_pause_active, last_pause_check
    flag_path = _get_pause_flag_path()
    global_pause_active, last_pause_check, paused = pause_check_impl(
        flag_path, last_pause_check, global_pause_active
    )
    return paused

def set_pause_state(paused: bool):
    global global_pause_active, last_pause_check
    pause_set_impl(_get_pause_flag_path(), paused)
    global_pause_active = paused
    last_pause_check = time.time()

def toggle_pause_state():
    global global_pause_active, last_pause_check
    global_pause_active = pause_toggle_impl(_get_pause_flag_path(), global_pause_active)
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
        p.terminate()
        p = pyaudio.PyAudio()
    except Exception as e:
        logging.error(f"Error in reinitialize_pyaudio: {e}", exc_info=True)

def monitor_microphone_availability():
    try:
        global wake_stream, p
        while True:
            if not check_microphone():
                logging.info(
                    f"{RED}No microphone detected. Pausing wake word detection...{RESET}"
                )
                if wake_stream:
                    try:
                        wake_stream.stop_stream()
                        wake_stream.close()
                    except OSError as e:
                        logging.info(f"Error stopping stream: {e}")
                    finally:
                        wake_stream = None
            else:
                if (wake_stream is None) or (not wake_stream.is_active()):
                    logging.info(
                        f"{GREEN}Microphone detected. Resuming wake word detection...{RESET}"
                    )
                    if not initialize_wake_stream():
                        reinitialize_pyaudio()

            time.sleep(10)
    except Exception as e:
        logging.error(f"Error in monitor_microphone_availability: {e}", exc_info=True)

def set_wake_stream(value):
    global wake_stream
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
    listener = init_wakeword_listener()
    listener.listen(
        get_wake_stream=lambda: wake_stream,
        set_wake_stream=set_wake_stream,
        check_pause_status=check_pause_status,
        is_recording=lambda: recording,
        start_recording_async=_start_recording_async,
        stop_recording_async=_stop_recording_async,
        decrease_volume_all=decrease_volume_all,
        restore_volume_all=restore_volume_all,
        should_relax=should_relax_resources,
        log=print,
    )

def cleanup():
    try:
        global wake_stream
        if wake_stream:
            try:
                if wake_stream.is_active():
                    wake_stream.stop_stream()
                wake_stream.close()
            except OSError as e:
                logging.info(f"Error during cleanup: {e}")
            wake_stream = None
        p.terminate()
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
        Groq_client,
        transcribe_pre_recording_buffer_prompt,
        get_groq_audio_model,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )


async def transcribe_with_groq_async(byte_io, keyword_index, max_retries=3):
    return await transcribe_with_groq_async_util(
        byte_io,
        keyword_index,
        api_key,
        get_groq_audio_model,
        General_gorq_system_prompt,
        groq_session_holder,
        max_retries=max_retries,
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
        )
    return transcription_pipeline

async def process_audio_async():
    pipeline = init_transcription_pipeline()
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
    try:
        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        logging.info("Ctrl+C pressed. Exiting...")
    except Exception as e:
        logging.error(f"Error in start_listener: {e}", exc_info=True)

def beep(sound):
    try:
        frequency, duration = sound
        winsound.Beep(frequency, duration)
    except Exception as e:
        logging.error(f"Error in beep: {e}", exc_info=True)

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
        global recording, play_pause_pressed, audio_buffer
        recording = False
        play_pause_pressed = False
        audio_buffer = np.array([], dtype="float32")
        threading.Thread(target=restore_volume_all).start()
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
                transcript, keyword_index = transcript_queue.get()
                logging.error(f"Transcript received in clean_transcript: {transcript}")
                if keyword_index in (0, 1):
                    logging.error(
                        f"Transcript sent for execute_command_run_with_tool: {transcript}"
                    )
                    await execute_command_run_with_tool(transcript)
                elif keyword_index == 2:
                    pass
                elif keyword_index == 3:
                    logging.error(f"google assistant command: {transcript}")
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

def display_pause_status(start: bool = True):
    """Start/stop the pause-status spinner."""
    global _spinner, _spinner_thread

    if start:
        if _spinner_thread and _spinner_thread.is_alive():
            return  # already running

        _spinner = make_status_display(
            check_pause_status=check_pause_status,
            active_message=f"{GREEN}Voice recognition active - Say 'Hey computer' or wake word... (Ctrl+Alt+Shift+ScrollLock to pause){RESET}",
            paused_message=f"{RED}VOICE RECOGNITION PAUSED - Press Ctrl+Alt+Shift+ScrollLock to resume{RESET}",
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
}

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
        global recording, play_pause_pressed, audio_buffer, stream, wake_stream

        with recording_lock:
            recording = False

        play_pause_pressed = False
        audio_buffer = np.array([], dtype="float32")

        while not audio_buffer_queue.empty():
            try:
                audio_buffer_queue.get_nowait()
            except QueueEmpty:
                break

        while not transcript_queue.empty():
            try:
                transcript_queue.get_nowait()
            except QueueEmpty:
                break

        if stream and stream.active:
            try:
                stream.stop()
                stream.close()
            except:
                pass

        if not initialize_input_stream():
            stream = None

        if wake_stream:
            try:
                wake_stream.stop_stream()
                wake_stream.close()
            except:
                pass
            wake_stream = None

        initialize_wake_stream()

        global_state["consecutive_failures"] = 0
        global_state["last_successful_operation"] = time.time()
        global_state["is_processing"] = False

        threading.Thread(target=restore_volume_all).start()
        logging.info(f"{GREEN}All states reset successfully{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error in reset_all_states: {e}{RESET}", exc_info=True)

def main():
    global stream
    global driver
    global driver_pid

    logging.info(
        f"{CYAN}wkey is active. Hold down {BOLD}{key_label.upper()}{RESET}{CYAN} to start dictating.{RESET}"
    )
    logging.info(
        f"{CYAN}Press Ctrl+Alt+Shift+Scroll Lock to pause/resume voice recognition.{RESET}"
    )

    def exception_handler(exc_type, exc_value, exc_traceback):
        logging.error(
            f"{RED}Unhandled exception:{RESET}",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = exception_handler

    try:
        init_keyboard_handler()
        start_settings_watch()
        init_wakeword_listener()
        start_thread(listen_for_wake_word, "WakeWordListener")
        start_thread(monitor_microphone_availability, "MicrophoneMonitor")
        loop2 = asyncio.new_event_loop()
        start_thread(
            lambda: run_asyncio_in_thread(loop2, clean_transcript()), "CleanTranscript"
        )
        loop = asyncio.new_event_loop()
        start_thread(
            lambda: run_asyncio_in_thread(loop, process_audio_async()), "ProcessAudio"
        )
        threading.Thread(target=start_driver, daemon=True).start()
        threading.Thread(target=display_pause_status, daemon=True).start()

        while True:
            wait_for_microphone()
            if not initialize_input_stream():
                time.sleep(5)
                continue

            try:
                start_listener()
            except Exception as e:
                logging.error(
                    f"{RED}Input stream error: {str(e)}{RESET}", exc_info=True
                )
            finally:
                if stream:
                    try:
                        if stream.active:
                            stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
            time.sleep(2)

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
            threading.Thread(target=restore_volume_all).start()
            logging.info(f"{YELLOW}Cleanup completed. Exiting...{RESET}")
            if driver:
                driver.quit()
        except Exception as e:
            logging.error(
                f"{RED}Error during cleanup: {str(e)}\n{traceback.format_exc()}{RESET}"
            )

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(
                f"{RED}Fatal error: {str(e)}\n{traceback.format_exc()}{RESET}"
            )
            time.sleep(5)
