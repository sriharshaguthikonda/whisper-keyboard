# voice_commands.py
import os
import gc
import pyautogui
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from ctypes import cast, POINTER


import re
import string
from fuzzywuzzy import process
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options

# from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By


import time
import re
import subprocess
import psutil

from groq import Groq
import ollama
from dotenv import load_dotenv
import json

import io
import math
import tempfile
import edge_tts
import pyttsx4
from clipboard_utils import (
    paste_transcript, 
    set_clipboard_content,
    )

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


from pydub import AudioSegment
from pydub.playback import play
import queue
import logging


from commands_and_tools import (
    COMMAND_MAPPINGS,
    ACTIONS,
    tools,
    ASK_AI_TOOLS,
    extra_tools,
    tool_function_registry,
    launch_application,
    stop_spotify,
)
try:
    from model_rotation import (
        next_tool_use_model,
        note_tool_use_model_failure,
        note_tool_use_rate_limit,
        refresh_groq_model_rotators,
    )
    from groq_model_catalog import classify_groq_model_error
except ModuleNotFoundError:
    from wkey.model_rotation import (
        next_tool_use_model,
        note_tool_use_model_failure,
        note_tool_use_rate_limit,
        refresh_groq_model_rotators,
    )
    from wkey.groq_model_catalog import classify_groq_model_error
try:
    from settings_manager import (
        load_settings as settings_load,
        DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
    )
except ModuleNotFoundError:
    from wkey.settings_manager import (
        load_settings as settings_load,
        DEFAULT_SETTINGS as SETTINGS_DEFAULTS,
    )

# Temporarily disable browser/media tools from LLM tool selection
DISABLED_TOOL_NAMES = {
    "play_music",
    "pause_song",
    "stop_media",
    "next_track",
    "previous_track",
    "restart_media",
    "open_browser",
    "open_website",
    "search_google",
}

def _filtered_tools_for_llm():
    filtered = []
    all_tools = list(tools)
    try:
        from wkey.ask_ai_bridge import is_ask_ai_enabled
    except ImportError:
        from ask_ai_bridge import is_ask_ai_enabled
    if is_ask_ai_enabled():
        all_tools.extend(ASK_AI_TOOLS)
    for tool in all_tools:
        if tool.get("type") == "function":
            name = tool.get("function", {}).get("name")
            if name in DISABLED_TOOL_NAMES:
                continue
        filtered.append(tool)
    return filtered


# ANSI Color codes
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Additional ANSI Color codes
ORANGE = "\033[38;5;214m"
PINK = "\033[38;5;198m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("voice_commands.log"),
        logging.StreamHandler(),  # This will also print to console
    ],
)

load_dotenv()
global api_key
api_key = os.getenv("GROQ_API_KEY")
global Groq_client
Groq_client = Groq(api_key=api_key)


def _parse_csv_env(name: str, default_csv: str):
    raw = os.getenv(name, default_csv)
    return [item.strip() for item in raw.split(",") if item and item.strip()]


def _parse_positive_float_env(name: str, default_value: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default_value)
    try:
        value = float(raw.strip())
        if value > 0:
            return value
    except Exception:
        pass
    logging.warning(
        "Invalid %s value %r, using default %.1f", name, raw, float(default_value)
    )
    return float(default_value)


TOOL_EXECUTION_TIMEOUT_SECONDS = _parse_positive_float_env(
    "WKEY_TOOL_EXEC_TIMEOUT_SECONDS", 20.0
)


# TTS preferences: Ava first, then Edge voice backups, then local fallback.
DEFAULT_EDGE_VOICE = os.getenv("EDGE_TTS_PRIMARY_VOICE", "en-US-AvaNeural")
EDGE_TTS_FALLBACK_VOICES = _parse_csv_env(
    "EDGE_TTS_FALLBACK_VOICES",
    "en-US-JennyNeural,en-US-AriaNeural",
)
KOKORO_FALLBACK_VOICES = _parse_csv_env(
    "KOKORO_FALLBACK_VOICES",
    "af_jessica,af_sky",
)
DEFAULT_TTS_SPEED = float(os.getenv("TTS_DEFAULT_SPEED", "1.3"))
ENABLE_PYTTS_FALLBACK = os.getenv("ENABLE_PYTTS_FALLBACK", "0").strip().lower() not in (
    "0",
    "false",
    "no",
)


def initialize_groq_client():
    try:
        global api_key, Groq_client
        if api_key is None:
            load_dotenv()
            api_key = os.getenv("GROQ_API_KEY")
        else:
            pass
        Groq_client = Groq(api_key=api_key)
        logging.info(f"{GREEN}Groq client initialized successfully.{RESET}")
        return Groq_client
    except Exception as e:
        logging.error(f"{RED}Error initializing Groq client: {e}{RESET}", exc_info=True)


# Define models
ROUTING_MODEL = "llama3-70b-8192"
# ROUTING_MODEL = "llama-3.2-1b-preview"
GENERAL_MODEL = "llama3-70b-8192"
ollama_model = "llama3.2:latest"


# Path to your Edge WebDriver (optional override; default uses Selenium Manager)
# webdriver_path = os.path.join(os.path.dirname(__file__), "drivers", "msedgedriver.exe")

# Set up Edge options (use dedicated profile to avoid collisions/crashes)
EDGE_PROFILE_DIR = r"C:\Users\deletable\AppData\Local\Microsoft\Edge\User Data\Profile_wkey_selenium"
os.makedirs(EDGE_PROFILE_DIR, exist_ok=True)

options = Options()
options.add_argument(f"user-data-dir={EDGE_PROFILE_DIR}")
options.add_argument("profile-directory=Profile_wkey_selenium")

# Add stability flags to reduce DevToolsActivePort/lock issues
options.add_argument("--remote-allow-origins=*")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")
options.add_argument("--disable-features=msEdgeReporting")  # reduce telemetry side-effects
options.add_argument("--remote-debugging-port=0")  # allow dynamic debug port

# Start minimized
# options.add_argument("--start-minimized")

# Optional: Run in headless mode (no GUI)
# options.add_argument("--headless")
# options.add_argument("--disable-gpu")


# Initialize the WebDriver (use Selenium Manager by default)
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "transcription_config.json")

driver = None
driver_pid = None
session_id = None
executor_url = None
_driver_control_lock = threading.RLock()


def _load_edge_selenium_setting():
    try:
        config = settings_load(SETTINGS_PATH, SETTINGS_DEFAULTS)
        return bool(config.get("enable_edge_selenium", True))
    except Exception as e:
        logging.warning(
            f"{YELLOW}Failed to load enable_edge_selenium setting ({e}); defaulting to enabled.{RESET}"
        )
        return True


_edge_selenium_enabled = _load_edge_selenium_setting()


def _set_driver_reference(driver_instance):
    try:
        from commands_and_tools import set_driver_reference

        set_driver_reference(driver_instance)
    except ImportError:
        pass


def is_selenium_enabled():
    with _driver_control_lock:
        return _edge_selenium_enabled


def stop_driver(reason="manual stop"):
    global driver, driver_pid, session_id, executor_url
    with _driver_control_lock:
        current_driver = driver
        driver = None
        driver_pid = None
        session_id = None
        executor_url = None
    _set_driver_reference(None)
    if current_driver is not None:
        try:
            current_driver.quit()
            logging.info(
                f"{YELLOW}WebDriver stopped ({reason}).{RESET}"
            )
        except Exception as e:
            logging.warning(
                f"{YELLOW}WebDriver stop encountered an error ({reason}): {e}{RESET}"
            )


def set_selenium_enabled(enabled, start_if_needed=False):
    global _edge_selenium_enabled
    enabled = bool(enabled)
    should_start_driver = False
    with _driver_control_lock:
        previous = _edge_selenium_enabled
        _edge_selenium_enabled = enabled
        should_start_driver = enabled and start_if_needed and driver is None
    if previous != enabled:
        state = "enabled" if enabled else "disabled"
        logging.info(f"{CYAN}Edge/Selenium automation {state} via settings.{RESET}")
    if not enabled:
        stop_driver(reason="disabled in settings")
    elif should_start_driver:
        threading.Thread(target=start_driver, daemon=True, name="EdgeSeleniumStartup").start()


def _ensure_selenium_enabled(action_name):
    if not is_selenium_enabled():
        logging.info(
            f"{YELLOW}Skipping Selenium action '{action_name}' because enable_edge_selenium is off.{RESET}"
        )
        return False
    return True

def _get_executor_url(driver_instance):
    try:
        executor = driver_instance.command_executor
    except Exception:
        return None
    for attr in ("remote_url", "remote_server_addr", "_url", "url"):
        value = getattr(executor, attr, None)
        if value:
            return value
    return None


def start_driver():
    global driver, driver_pid, session_id, executor_url
    if not _ensure_selenium_enabled("start_driver"):
        return False
    try:
        with _driver_control_lock:
            if driver is not None:
                logging.info(f"{CYAN}WebDriver already initialized. Skipping startup.{RESET}")
                return True

        logging.info(f"{CYAN}Starting driver...{RESET}")
        new_driver = webdriver.Edge(service=Service(), options=options)
        time.sleep(6)
        new_driver.get("https://open.spotify.com/collection/tracks")
        time.sleep(5)  # Wait for the page to load
        new_executor_url = _get_executor_url(new_driver)
        if not new_executor_url:
            logging.warning(f"{YELLOW}Could not determine executor_url for WebDriver session.{RESET}")

        with _driver_control_lock:
            if not _edge_selenium_enabled:
                try:
                    new_driver.quit()
                except Exception:
                    pass
                logging.info(
                    f"{YELLOW}WebDriver startup aborted because Selenium automation was disabled mid-start.{RESET}"
                )
                return False
            driver = new_driver
            driver_pid = new_driver.service.process.pid if new_driver.service and new_driver.service.process else None
            session_id = new_driver.session_id
            executor_url = new_executor_url
        _set_driver_reference(driver)
        logging.info(f"{GREEN}WebDriver started successfully.{RESET}")
        return True
    except Exception as e:
        logging.error(f"{RED}Error starting driver: {e}{RESET}", exc_info=True)
        with _driver_control_lock:
            driver = None
            driver_pid = None
            session_id = None
            executor_url = None
        _set_driver_reference(None)
        return False


"""
https://chatgpt.com/c/66e49b09-cca4-8013-a443-6793c6073c2f
"""


def reconnect_driver():
    global driver, session_id, executor_url, options
    if not _ensure_selenium_enabled("reconnect_driver"):
        return False
    try:
        logging.info(f"{CYAN}Reconnecting to WebDriver session...{RESET}")
        if session_id and executor_url:
            new_driver = webdriver.Remote(command_executor=executor_url, options=options)
            new_driver.session_id = session_id

            with _driver_control_lock:
                if not _edge_selenium_enabled:
                    try:
                        new_driver.quit()
                    except Exception:
                        pass
                    logging.info(
                        f"{YELLOW}Skipping reconnect completion because Selenium automation is disabled.{RESET}"
                    )
                    return False
                driver = new_driver

            logging.info(f"{GREEN}Reconnected to the existing session.{RESET}")
            _set_driver_reference(driver)
            return True
    except (SessionNotCreatedException, WebDriverException) as e:
        logging.error(
            f"{RED}Failed to reconnect to the session: {str(e)}{RESET}", exc_info=True
        )
    except Exception as e:
        logging.error(f"{RED}Unexpected reconnect error: {e}{RESET}", exc_info=True)

    logging.info(f"{CYAN}Attempting to start a new WebDriver session...{RESET}")
    return start_driver()


# Start the WebDriver in a separate thread
# Allow time to log in (if not using a persistent session)
# time.sleep(60)  # Uncomment if you need time to log in manually

"""
 ######  ########   #######  ######## #### ######## ##    ## 
##    ## ##     ## ##     ##    ##     ##  ##        ##  ##  
##       ##     ## ##     ##    ##     ##  ##         ####   
 ######  ########  ##     ##    ##     ##  ######      ##    
      ## ##        ##     ##    ##     ##  ##          ##    
##    ## ##        ##     ##    ##     ##  ##          ##    
 ######  ##         #######     ##    #### ##          ##    
"""


def change_device():
    if not _ensure_selenium_enabled("change_device"):
        return False
    local_driver = driver
    if local_driver is None:
        logging.warning(f"{YELLOW}change_device requested but WebDriver is not available.{RESET}")
        return False
    try:
        logging.info("Changing playback device...")
        devices_button = local_driver.find_element(
            By.XPATH, "//button[@aria-label='Connect to a device']"
        )
        # Click the button
        devices_button.click()
        logging.info("Playback started.")
        # Locate the element containing "This web browser"
        # Wait for the panel to appear
        # wait = WebDriverWait(driver, 10)
        time.sleep(2)
        try:
            local_driver.find_element(By.XPATH, '//*[@id="device-picker"]').click()
        except Exception as e:
            logging.error(
                f"Error while trying to play after reconnection: {e}", exc_info=True
            )
        time.sleep(2)
        local_driver.find_element(
            # By.XPATH, '//*[text()="Web Player (Microsoft Edge)"]'
            By.XPATH,
            '//*[text()="This web browser"]',
        ).click()
        # Click the panel
        return True
    except Exception as e:
        logging.error(
            f"Error while trying to play after reconnection: {e}", exc_info=True
        )
        return False


# Control playback
def play_music():
    if not _ensure_selenium_enabled("play_music"):
        return False
    try:
        if driver is None:
            logging.warning(f"{YELLOW}play_music requested but WebDriver is not available.{RESET}")
            return False
        play_button = driver.find_element(By.XPATH, "//button[@aria-label='Play']")
        play_button.click()
        change_device()
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                play_button = driver.find_element(
                    By.XPATH, "//button[@aria-label='Play']"
                )
                play_button.click()
                print("Playback started after reconnection.")
                return True
            except Exception as e:
                print(f"Error while trying to play after reconnection: {e}")

        elif "target window already closed" in error_message:
            if driver is not None:
                driver.quit()
            start_driver()
            try:
                play_button = driver.find_element(
                    By.XPATH, "//button[@aria-label='Play']"
                )
                play_button.click()
                print("Playback started after reconnection.")
                return True
            except Exception as e:
                print(f"Error while trying to play after reconnection: {e}")

        else:
            print(f"Error while trying to play: {e}")
        return False


def pause_song():
    if not _ensure_selenium_enabled("pause_song"):
        return False
    try:
        if driver is None:
            logging.warning(f"{YELLOW}pause_song requested but WebDriver is not available.{RESET}")
            return False
        pause_button = driver.find_element("xpath", "//button[@aria-label='Pause']")
        pause_button.click()
        print("Playback paused.")
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                pause_button = driver.find_element(
                    "xpath", "//button[@aria-label='Pause']"
                )
                pause_button.click()
                print("Playback paused after reconnection.")
                return True
            except Exception as e:
                print(f"Error while trying to pause after reconnection: {e}")
        else:
            print(f"Error while trying to pause: {e}")
        return False


def next_track():
    if not _ensure_selenium_enabled("next_track"):
        return False
    try:
        if driver is None:
            logging.warning(f"{YELLOW}next_track requested but WebDriver is not available.{RESET}")
            return False
        next_button = driver.find_element("xpath", "//button[@aria-label='Next']")
        next_button.click()
        print("Next track.")
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                next_button = driver.find_element(
                    "xpath", "//button[@aria-label='Next']"
                )
                next_button.click()
                print("Next track after reconnection.")
                return True
            except Exception as e:
                print(
                    f"Error while trying to skip to next track after reconnection: {e}"
                )
        else:
            print(f"Error while trying to skip to next track: {e}")
        return False


def previous_track():
    if not _ensure_selenium_enabled("previous_track"):
        return False
    try:
        if driver is None:
            logging.warning(f"{YELLOW}previous_track requested but WebDriver is not available.{RESET}")
            return False
        prev_button = driver.find_element("xpath", "//button[@aria-label='Previous']")
        prev_button.click()
        print("Previous track.")
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                prev_button = driver.find_element(
                    "xpath", "//button[@aria-label='Previous']"
                )
                prev_button.click()
                print("Previous track after reconnection.")
                return True
            except Exception as e:
                print(
                    f"Error while trying to go to previous track after reconnection: {e}"
                )
        else:
            print(f"Error while trying to go to previous track: {e}")
        return False


"""
######## ##     ## ##    ##  ######  ######## ####  #######  ##    ##  ######  
##       ##     ## ###   ## ##    ##    ##     ##  ##     ## ###   ## ##    ## 
##       ##     ## ####  ## ##          ##     ##  ##     ## ####  ## ##       
######   ##     ## ## ## ## ##          ##     ##  ##     ## ## ## ##  ######  
##       ##     ## ##  #### ##          ##     ##  ##     ## ##  ####       ## 
##       ##     ## ##   ### ##    ##    ##     ##  ##     ## ##   ### ##    ## 
##        #######  ##    ##  ######     ##    ####  #######  ##    ##  ######  
"""


def search_everything(query: str = ""):
    try:
        everything_path = r"C:\Program Files\Everything 1.5a\Everything64.exe"
        cmd = [everything_path]
        if query:
            cleaned = re.sub(r"[^\w\s]", " ", query)
            cleaned = " ".join(cleaned.split())
            cmd.extend(["-search", cleaned])
        subprocess.run(cmd)
    except Exception as e:
        logging.error(f"Error executing search_everything: {e}", exc_info=True)


def show_desktop():
    try:
        pyautogui.hotkey("win", "d")
    except Exception as e:
        logging.error(f"Error executing show_desktop: {e}", exc_info=True)


def open_settings():
    try:
        pyautogui.hotkey("win", "i")
    except Exception as e:
        logging.error(f"Error executing open_settings: {e}", exc_info=True)


def lock_screen():
    try:
        pyautogui.hotkey("win", "l")
    except Exception as e:
        logging.error(f"Error executing lock_screen: {e}", exc_info=True)


def take_screenshot():
    try:
        pyautogui.hotkey("win", "prtsc")
    except Exception as e:
        logging.error(f"Error executing take_screenshot: {e}", exc_info=True)


def open_file_explorer():
    try:
        pyautogui.hotkey("win", "e")
    except Exception as e:
        logging.error(f"Error executing open_file_explorer: {e}", exc_info=True)


def windows_search():
    try:
        pyautogui.hotkey("win", "s")
    except Exception as e:
        logging.error(f"Error executing windows_search: {e}", exc_info=True)


def open_run_dialog():
    try:
        pyautogui.hotkey("win", "r")
    except Exception as e:
        logging.error(f"Error executing open_run_dialog: {e}", exc_info=True)


def open_task_manager():
    try:
        pyautogui.hotkey("ctrl", "shift", "esc")
    except Exception as e:
        logging.error(f"Error executing open_task_manager: {e}", exc_info=True)


def minimize_all_windows():
    try:
        pyautogui.hotkey("win", "m")
    except Exception as e:
        logging.error(f"Error executing minimize_all_windows: {e}", exc_info=True)


def restore_windows():
    try:
        pyautogui.hotkey("win", "shift", "m")
    except Exception as e:
        logging.error(f"Error executing restore_windows: {e}", exc_info=True)


def open_task_scheduler():
    try:
        os.system("taskschd.msc")
        logging.info(f"{GREEN}Opening Task Scheduler...{RESET}")
    except Exception as e:
        logging.error(
            f"{RED}Error executing open_task_scheduler: {e}{RESET}", exc_info=True
        )


# Volume controls
def open_sound_control_panel():
    try:
        os.system("control mmsys.cpl")
    except Exception as e:
        logging.error(f"Error executing open_sound_control_panel: {e}", exc_info=True)


def kill_process_by_name(process_name):
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] == process_name:
                proc.kill()
                print(
                    f"Process {process_name} with PID {proc.info['pid']} has been killed."
                )
                return
        print(f"No process named {process_name} found.")
    except Exception as e:
        logging.error(f"Error executing kill_process_by_name: {e}", exc_info=True)


VOLUME_REQUEST_TIMEOUT = 2.0
VOLUME_WORKER_RESTART_BACKOFF_SECONDS = 1.0
_volume_timeout_callbacks = []
_volume_timeout_callbacks_lock = threading.Lock()


def register_volume_timeout_callback(callback):
    if not callable(callback):
        return
    with _volume_timeout_callbacks_lock:
        _volume_timeout_callbacks.append(callback)


def _run_volume_timeout_callback(callback, timeout_seconds):
    try:
        callback(timeout_seconds)
    except Exception as e:
        logging.error(
            f"{RED}Volume timeout callback failed: {e}{RESET}", exc_info=True
        )


def _notify_volume_timeout_callbacks(timeout_seconds, async_dispatch=False):
    with _volume_timeout_callbacks_lock:
        callbacks = list(_volume_timeout_callbacks)
    if async_dispatch:
        for index, callback in enumerate(callbacks, start=1):
            threading.Thread(
                target=_run_volume_timeout_callback,
                args=(callback, timeout_seconds),
                daemon=True,
                name=f"VolumeTimeoutCallback-{index}",
            ).start()
        return
    for callback in callbacks:
        _run_volume_timeout_callback(callback, timeout_seconds)


class VolumeController:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None
        self._thread_lock = threading.Lock()
        self._worker_seq = 0
        self._last_worker_start_ts = 0.0
        self._ensure_worker(reason="startup")

    def _start_worker_locked(self, reason):
        now = time.time()
        reason_str = str(reason)
        force_restart = reason_str.startswith("timeout")
        thread_alive = self._thread is not None and self._thread.is_alive()
        if thread_alive and not force_restart:
            return
        if (
            force_restart
            and now - self._last_worker_start_ts < VOLUME_WORKER_RESTART_BACKOFF_SECONDS
        ):
            return
        self._worker_seq += 1
        worker_id = self._worker_seq
        self._last_worker_start_ts = now
        self._thread = threading.Thread(
            target=self._worker,
            args=(worker_id,),
            daemon=True,
            name=f"VolumeControllerWorker-{worker_id}",
        )
        self._thread.start()
        logging.info(
            f"{BLUE}VolumeController worker started (id={worker_id}, reason={reason}){RESET}"
        )

    def _ensure_worker(self, reason):
        with self._thread_lock:
            self._start_worker_locked(reason)

    def _restart_worker(self, reason):
        with self._thread_lock:
            logging.warning(
                f"{YELLOW}VolumeController worker restart requested (reason={reason}){RESET}"
            )
            self._start_worker_locked(reason)

    def _worker(self, worker_id):
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except Exception as e:
            logging.error(
                f"{RED}VolumeController COM init failed (worker={worker_id}): {e}{RESET}",
                exc_info=True,
            )
        while True:
            action, default, result_container, done_event = self._queue.get()
            result = default
            volume_interface = None
            interface = None
            devices = None
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
                result = action(volume_interface)
            except Exception as e:
                logging.error(
                    f"{RED}VolumeController action failed (worker={worker_id}): {e}{RESET}",
                    exc_info=True,
                )
            finally:
                try:
                    volume_interface = None
                    interface = None
                    devices = None
                except Exception:
                    pass
                try:
                    gc.collect()
                except Exception:
                    pass
                result_container["value"] = result
                done_event.set()

    def run(self, action, default=None):
        self._ensure_worker(reason="run")
        result_container = {"value": default}
        done_event = threading.Event()
        self._queue.put((action, default, result_container, done_event))
        if not done_event.wait(timeout=VOLUME_REQUEST_TIMEOUT):
            logging.error(
                f"{RED}VolumeController timeout after {VOLUME_REQUEST_TIMEOUT}s{RESET}"
            )
            self._restart_worker(reason="timeout")
            _notify_volume_timeout_callbacks(
                VOLUME_REQUEST_TIMEOUT,
                async_dispatch=True,
            )
            return default
        return result_container["value"]

volume_controller = VolumeController()

def _with_volume_interface(action, default=None):
    return volume_controller.run(action, default=default)


def get_volume():
    current_volume = _with_volume_interface(
        lambda volume_interface: volume_interface.GetMasterVolumeLevelScalar(),
        default=0.5,
    )
    logging.debug(f"{BLUE}Getting volume...{RESET}")
    return round(current_volume, 2)


def volume_up(steps=1):
    try:
        def _raise(volume_interface):
            current_volume = volume_interface.GetMasterVolumeLevelScalar()
            new_volume = min(current_volume + steps * 0.05, 1.0)  # Increase by 5% per step
            volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
            return new_volume
        new_volume = _with_volume_interface(_raise, default=None)
        if new_volume is not None:
            print(f"Volume increased to {new_volume * 100:.0f}%")
    except Exception as e:
        logging.error(f"Error executing volume_up: {e}", exc_info=True)


def volume_down(steps=1):
    try:
        def _lower(volume_interface):
            current_volume = volume_interface.GetMasterVolumeLevelScalar()
            new_volume = max(current_volume - steps * 0.05, 0.0)  # Decrease by 5% per step
            volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
            return new_volume
        new_volume = _with_volume_interface(_lower, default=None)
        if new_volume is not None:
            print(f"Volume decreased to {new_volume * 100:.0f}%")
    except Exception as e:
        logging.error(f"Error executing volume_down: {e}", exc_info=True)


def set_volume(level):
    try:
        if 0.0 <= level <= 1.0:
            def _set(volume_interface):
                volume_interface.SetMasterVolumeLevelScalar(level, None)
            result = _with_volume_interface(_set, default=False)
            if result is False:
                logging.warning("set_volume: volume_interface unavailable, skipping")
                return
            logging.info(f"{BLUE}Setting volume to {level * 100}%{RESET}")
            print(f"Volume set to {level * 100:.0f}%")
        else:
            print("Volume level must be between 0.0 and 1.0")
    except Exception as e:
        logging.error(f"{RED}Error setting volume: {e}{RESET}", exc_info=True)


def get_volume_interface():
    logging.warning("get_volume_interface is deprecated; use _with_volume_interface")
    return None

def mute_volume():
    try:
        pyautogui.press("volumemute")
    except Exception as e:
        logging.error(f"Error executing mute_volume: {e}", exc_info=True)


def stop_media():
    try:
        pause_song()
        print("Stopping media")
    except Exception as e:
        logging.error(f"Error executing stop_media: {e}", exc_info=True)


def _run_tts_safely(text: str):
    """
    Run text_to_speech whether or not an event loop is already running.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(text_to_speech(text=text))
    except RuntimeError:
        asyncio.run(text_to_speech(text=text))


# Custom or complex operations
# System commands
def ping_google():
    try:
        # Run the ping command and capture the output
        result = subprocess.run(
            ["ping", "www.google.com", "-n", "4"], capture_output=True, text=True
        )

        # Find the line with average ping time
        match = re.search(r"Average = (\d+)ms", result.stdout)

        if match:
            avg_ping = match.group(1)
            _run_tts_safely(
                f"The average ping to Google was {avg_ping} milleseconds, {avg_ping} milleseconds"
            )
        else:
            return "Could not determine the average ping."
    except Exception as e:
        logging.error(f"Error executing ping_google: {e}", exc_info=True)
        return f"Error occurred: {str(e)}"


def flush_dns():
    try:
        os.system("ipconfig /flushdns")
    except Exception as e:
        logging.error(f"Error executing flush_dns: {e}", exc_info=True)


# VB Matrix commands
def restart_voicemeeter():
    initial_volume = None
    try:
        initial_volume = get_volume()
        logging.info(
            f"{CYAN}restart_voicemeeter: issuing restart command (timeout={TOOL_EXECUTION_TIMEOUT_SECONDS:.1f}s){RESET}"
        )
        subprocess.run(
            [
                "C:\\Program Files (x86)\\VB\\VBAudioMatrix\\VBAudioMatrix_x64.exe",
                "-r",
            ],
            check=False,
            timeout=TOOL_EXECUTION_TIMEOUT_SECONDS,
        )
        time.sleep(2)
    except subprocess.TimeoutExpired:
        logging.error(
            f"{RED}restart_voicemeeter timed out after {TOOL_EXECUTION_TIMEOUT_SECONDS:.1f}s{RESET}"
        )
    except Exception as e:
        logging.error(f"Error executing restart_voicemeeter: {e}", exc_info=True)
    finally:
        if initial_volume is not None:
            try:
                set_volume(initial_volume)
            except Exception as restore_error:
                logging.error(
                    "Failed to restore volume after restart_voicemeeter: %s",
                    restore_error,
                    exc_info=True,
                )



# DisplayFusion commands
def start_display_fusion(profile_name="Default"):
    try:
        selected_profile = (profile_name or "Default").strip() or "Default"
        logging.info(
            f"{CYAN}start_display_fusion using profile: {selected_profile}{RESET}"
        )
        subprocess.run(["taskkill", "/F", "/IM", "DisplayFusion.exe"])
        subprocess.run(
            [
                "C:\\Program Files (x86)\\DisplayFusion\\DisplayFusionCommand.exe",
                "-monitorloadprofile",
                selected_profile,
            ]
        )
    except Exception as e:
        logging.error(
            f"Error executing start_display_fusion: {e}", exc_info=True
        )


def open_negative_screen():
    try:
        subprocess.Popen(
            [
                "C:\\Program Files\\Negative screen\\NegativeScreen-custom-multi-monitor.exe"
            ]
        )
    except Exception as e:
        logging.error(f"Error executing open_negative_screen: {e}", exc_info=True)


invert_screen = open_negative_screen


from datetime import datetime

# Replace 'J:\\' with the actual path to the backup directory
backup_directory = "J:\\"


async def last_backup():
    try:
        # List all files in the directory
        backup_files = [f for f in os.listdir(backup_directory) if f.endswith(".mrimg")]
        if not backup_files:
            await text_to_speech("No backup files found.")
            return

        # Get the most recent backup file by modification date
        latest_backup = max(
            backup_files,
            key=lambda f: os.path.getmtime(os.path.join(backup_directory, f)),
        )
        last_modified_time = os.path.getmtime(
            os.path.join(backup_directory, latest_backup)
        )
        last_backup_date = datetime.fromtimestamp(last_modified_time)

        # Calculate days since the last backup
        days_ago = (datetime.now() - last_backup_date).days
        await text_to_speech(f"Latest backup was {days_ago} days ago.")
    except Exception as e:
        logging.error(f"Error executing last_backup: {e}", exc_info=True)


def open_vscode():
    try:
        # Path to the Visual Studio Code executable
        vscode_path = (
            r"C:\Users\deletable\AppData\Local\Programs\Microsoft VS Code\Code.exe"
        )
        subprocess.Popen([vscode_path])
    except Exception as e:
        logging.error(f"Error executing open_vscode: {e}", exc_info=True)


def start_whisper():
    try:
        batch_path = r"C:\Windows_software\openai whisper\whisper_keyboard.bat"
        # Use runas to run as administrator
        subprocess.run(["runas", "/user:Administrator", f'cmd /c "{batch_path}"'])
        logging.info(f"{GREEN}Starting Whisper with administrator privileges...{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error executing start_whisper: {e}{RESET}", exc_info=True)


def start_grok():
    try:
        shortcut_path = r"C:\Users\deletable\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\groq_Ollama_RAG_Chat.bat - Shortcut.lnk"
        os.startfile(shortcut_path)
        logging.info(f"{GREEN}Starting Grok...{RESET}")
    except Exception as e:
        logging.error(f"{RED}Error executing start_grok: {e}{RESET}", exc_info=True)


# Function to run the general model and stream text chunks to TTS immediately
def run_general(query):
    """Stream response chunks to TTS immediately as they arrive"""
    try:
        stream = client.chat.completions.create(
            model=GENERAL_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query},
            ],
            stream=True,
        )

        current_sentence = ""
        sentence_endings = [".", "!", "?"]  # Sentence-ending punctuation
        word_buffer = ""  # To accumulate small chunks of words

        for chunk in stream:
            # Safeguard for chunk choices
            if not chunk.choices or not chunk.choices[0].delta:
                print("Invalid chunk received, skipping...")
                continue

            chunk_text = chunk.choices[0].delta.content

            # Ensure that the chunk text is not None
            if chunk_text is None:
                print("Received NoneType chunk, skipping...")
                continue

            # Accumulate the chunk text
            word_buffer += chunk_text

            # Only process the buffer when it forms a coherent word (ends with a space or punctuation)
            if word_buffer and (
                word_buffer.endswith(" ") or word_buffer[-1] in sentence_endings
            ):
                current_sentence += word_buffer
                word_buffer = ""  # Reset buffer after processing

            # Print colored text when a sentence forms
            if (
                any(current_sentence.endswith(end) for end in sentence_endings)
                and len(current_sentence.split()) > 5
            ):
                # Strip markdown-like symbols for TTS
                stripped_text = re.sub(r"[\*_]", "", current_sentence)

                # Ensure we don't send empty or None to TTS
                if stripped_text:
                    TTS_queue.put(stripped_text)  # Send to TTS
                else:
                    print("Stripped text is empty, skipping TTS...")

                print(current_sentence)  # Print the sentence with colors
                # Reset the current sentence after sending to TTS
                current_sentence = ""
    except Exception as e:
        logging.error(f"Error in run_general: {e}", exc_info=True)


# Function to run Ollama's model and stream text chunks to TTS immediately
def run_ollama(query):
    """Stream response chunks to TTS immediately as they arrive"""
    try:
        # Initialize Ollama client for local server

        ollama_client = ollama.Client(host="http://localhost:11434")

        # Start the chat request with streaming enabled
        stream = ollama_client.chat(
            model=ollama_model,  # Replace with your preferred model
            messages=[{"role": "user", "content": query}],
            stream=True,
        )

        current_sentence = ""
        word_buffer = ""  # To accumulate small chunks of words

        for chunk in stream:
            # Safeguard for chunk content
            print(chunk["message"]["content"], end="", flush=True)
            if not chunk.get("message") or not chunk["message"].get("content"):
                continue

            chunk_text = chunk["message"]["content"].replace(
                "\n", " "
            )  # Remove unintended newlines

            # Accumulate the chunk text
            word_buffer += chunk_text

            # Process the buffer when it contains a sentence-ending punctuation
            sentence_endings = ".!? "
            if word_buffer and any(
                word_buffer.endswith(end) for end in sentence_endings
            ):
                current_sentence += word_buffer
                word_buffer = ""  # Reset buffer after processing

                # If a coherent chunk or sentence is formed, send it to TTS
                if any(current_sentence.endswith(end) for end in sentence_endings):
                    # Strip markdown-like symbols for TTS
                    stripped_text = re.sub(r"[\*_]", "", current_sentence)

                    # Send text to TTS immediately
                    if stripped_text:
                        TTS_queue.put(stripped_text)  # Send to TTS queue
                        current_sentence = ""  # Reset after sending to TTS
    except Exception as e:
        logging.error(f"Error executing run_ollama: {e}", exc_info=True)


"""

   ###    ##          ###    ########  ##     ## 
  ## ##   ##         ## ##   ##     ## ###   ### 
 ##   ##  ##        ##   ##  ##     ## #### #### 
##     ## ##       ##     ## ########  ## ### ## 
######### ##       ######### ##   ##   ##     ## 
##     ## ##       ##     ## ##    ##  ##     ## 
##     ## ######## ##     ## ##     ## ##     ## 


"""


def set_alarm(minutes, message):
    def alarm():
        time.sleep(minutes * 60)
        # Load and play the chime sound
        chime = AudioSegment.from_mp3(
            r"C:\Windows_software\openai whisper\whisper-keyboard\wkey\chime.mp3"
        )  # Replace with the path to your chime file
        play(chime)
        for _ in range(5):  # Repeat the message 5 times
            asyncio.run(text_to_speech(f" this is an alarm to {message}"))
            time.sleep(1)  # Pause between repetitions

    threading.Thread(target=alarm).start()


"""
######## ########  ######  
   ##       ##    ##    ## 
   ##       ##    ##       
   ##       ##     ######  
   ##       ##          ## 
   ##       ##    ##    ## 
   ##       ##     ######  
"""


# Queue for sentences
TTS_queue = queue.Queue()


# Function to process the queue
def process_TTS_queue():
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        while True:
            sentence = TTS_queue.get()
            if sentence is None:  # Sentinel value to stop the worker
                break
            asyncio.run(text_to_speech(sentence, speed=DEFAULT_TTS_SPEED))
            TTS_queue.task_done()
    except Exception as e:
        logging.error(f"Error processing TTS queue: {e}", exc_info=True)
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


threading.Thread(target=process_TTS_queue, daemon=True).start()


# Function to process the queue
def process_TTS_Audio_play_queue():
    try:
        while True:
            item = TTS_Audio_play_queue.get()
            if item is None:  # Add sentinel check
                break
            fallback_text = None
            fallback_speed = 1.2
            fallback_volume = 1.0
            if isinstance(item, tuple):
                if len(item) >= 5:
                    audio_fp, audio_format, fallback_text, fallback_speed, fallback_volume = item
                elif len(item) == 2:
                    audio_fp, audio_format = item
                else:
                    audio_fp, audio_format = item[0], "mp3"
            else:
                audio_fp, audio_format = item, "mp3"
            audio_fp.seek(0)
            try:
                sound = AudioSegment.from_file(audio_fp, format=audio_format)
                play(sound)
            except Exception as e:
                logging.error(f"Error playing TTS audio: {e}", exc_info=True)
                if fallback_text:
                    if not fallback_kokoro_tts(fallback_text, fallback_speed, fallback_volume):
                        fallback_offline_tts(fallback_text, fallback_speed, fallback_volume)
            TTS_Audio_play_queue.task_done()
    except Exception as e:
        logging.error(f"Error processing TTS audio play queue: {e}", exc_info=True)


# Queue for sentences
TTS_Audio_play_queue = queue.Queue()
TTS_queue = queue.Queue()

# Start threads instead of using executor.submit
threading.Thread(target=process_TTS_Audio_play_queue, daemon=True).start()
threading.Thread(target=process_TTS_queue, daemon=True).start()


# Add cleanup function to be called when shutting down
def cleanup():
    try:
        # Signal the worker threads to stop
        TTS_queue.put(None)
        TTS_Audio_play_queue.put(None)

        # Cleanup other resources if needed
        if driver:
            driver.quit()
    except Exception as e:
        logging.error(f"Error during cleanup: {e}", exc_info=True)


# Local Kokoro fallback
_kokoro_pipeline = None


def _get_kokoro_pipeline():
    global _kokoro_pipeline
    if _kokoro_pipeline is not None:
        return _kokoro_pipeline
    try:
        from kokoro import KPipeline
    except Exception as e:
        logging.warning(f"Kokoro not available: {e}")
        return None
    try:
        _kokoro_pipeline = KPipeline(lang_code="a")
        return _kokoro_pipeline
    except Exception as e:
        logging.error(f"Failed to initialize Kokoro pipeline: {e}", exc_info=True)
        return None


def _time_stretch_audio(audio, speed: float):
    if not speed or speed == 1.0:
        return audio
    try:
        import librosa
    except Exception as e:
        logging.warning(f"librosa not available for speed change: {e}")
        return audio
    try:
        return librosa.effects.time_stretch(audio, rate=speed)
    except Exception as e:
        logging.warning(f"Speed change failed: {e}")
        return audio


def _kokoro_speak(text: str, voice_id: str, speed: float = 1.2, volume: float = 1.0) -> bool:
    pipeline = _get_kokoro_pipeline()
    if pipeline is None:
        return False
    try:
        import numpy as np
        import soundfile as sf
    except Exception as e:
        logging.warning(f"Kokoro deps missing: {e}")
        return False

    try:
        audio_chunks = []
        for _, _, audio in pipeline(text, voice=voice_id):
            if audio is None:
                continue
            audio_chunks.append(audio)
        if not audio_chunks:
            return False
        audio = np.concatenate(audio_chunks)
        audio = _time_stretch_audio(audio, speed)
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(out_path, audio, 24000)
        try:
            sound = AudioSegment.from_file(out_path, format="wav")
            if volume and volume != 1.0:
                try:
                    sound = sound + (20 * math.log10(volume))
                except Exception:
                    pass
            play(sound)
        finally:
            try:
                os.remove(out_path)
            except Exception:
                pass
        return True
    except Exception as e:
        logging.error(f"Kokoro playback failed ({voice_id}): {e}", exc_info=True)
        return False


def fallback_kokoro_tts(text: str, speed: float = 1.2, volume: float = 1.0) -> bool:
    for voice_id in KOKORO_FALLBACK_VOICES:
        if _kokoro_speak(text, voice_id, speed, volume):
            return True
    return False


# Function to convert text to speech using edge-tts and play using pydub with speed adjustment
async def text_to_speech(text, speed=DEFAULT_TTS_SPEED, volume=1, voice=None):
    rate = "+" + str(int((speed - 1) * 100)) + "%"
    voice_candidates = []
    if voice:
        voice_candidates.append(voice)
    else:
        voice_candidates.append(DEFAULT_EDGE_VOICE)
        voice_candidates.extend(EDGE_TTS_FALLBACK_VOICES)

    # Deduplicate while preserving order.
    deduped_candidates = []
    seen = set()
    for candidate in voice_candidates:
        if candidate and candidate not in seen:
            deduped_candidates.append(candidate)
            seen.add(candidate)

    last_edge_error = None
    for selected_voice in deduped_candidates:
        try:
            communicate = edge_tts.Communicate(text, selected_voice, rate=rate)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            if not audio_bytes:
                raise ValueError("No audio received from edge-tts.")

            audio_fp = io.BytesIO(audio_bytes)
            audio_fp.seek(0)
            TTS_Audio_play_queue.put((audio_fp, "mp3", text, speed, volume))
            logging.info("Edge TTS voice selected: %s", selected_voice)
            return
        except Exception as e:
            last_edge_error = e
            logging.warning("Edge TTS failed for voice %s: %s", selected_voice, e)

    logging.error("All Edge TTS voices failed: %s", last_edge_error, exc_info=True)
    print("Falling back to local TTS...")
    if not fallback_kokoro_tts(text, speed, volume):
        if ENABLE_PYTTS_FALLBACK:
            fallback_offline_tts(text, speed, volume)
        else:
            logging.warning("pyttsx4 fallback is disabled; no local TTS fallback left.")


# Offline TTS fallback using pyttsx4
def fallback_offline_tts(text, speed=1.2, volume=1):
    try:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        # Initialize pyttsx4 engine
        engine = pyttsx4.init()

        # Set the speed (words per minute)
        engine.setProperty("rate", int(200 * speed))

        # Set the volume (0.0 to 1.0)
        engine.setProperty("volume", volume)

        # Speak the text
        engine.say(text)
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:
            pass
        engine = None
        gc.collect()

    except Exception as e:
        logging.error(f"Error executing fallback_offline_tts: {e}", exc_info=True)
        print(f"Offline TTS failed: {e}")
    finally:
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


# Define the function to split sentences with the condition
def split_sentence(response):
    try:
        delimiters = r"[.,;!?]"  # Delimiters for splitting
        # Split the response based on delimiters
        sentences = re.split(delimiters, response, maxsplit=1)

        # If we have more than one part after the split
        if len(sentences) > 1:
            sentence, remaining_response = sentences[0], sentences[1]

            # Check if the sentence has 10 words or more
            if len(sentence.split()) < 15:
                # If the sentence is too short, don't split
                sentence = sentence + remaining_response
                remaining_response = ""
        else:
            # No split happened, just return the original response
            sentence, remaining_response = sentences[0], ""

        return sentence.strip(), remaining_response.strip()
    except Exception as e:
        logging.error(f"Error executing split_sentence: {e}", exc_info=True)


"""
########   #######  ##     ## ######## ######## 
##     ## ##     ## ##     ##    ##    ##       
##     ## ##     ## ##     ##    ##    ##       
########  ##     ## ##     ##    ##    ######   
##   ##   ##     ## ##     ##    ##    ##       
##    ##  ##     ## ##     ##    ##    ##       
##     ##  #######   #######     ##    ######## 
"""


def route_query(query):
    try:
        global Groq_client

        """Routing logic to let LLM decide if tools are needed"""
        routing_prompt = f"""
        Given the following user query, determine if any tools are needed to answer it.
        If a a voice command intended to control some aspect of computer comes then, respond with 'Function'.
        If no tools are needed, respond with 'NO TOOL'.

        User query: {query}

        Response:
        """

        response = Groq_client.chat.completions.create(
            model=ROUTING_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a routing assistant. Determine if tools are needed based on the user query.",
                },
                {"role": "user", "content": routing_prompt},
            ],
            max_tokens=20,  # We only need a short response
        )

        routing_decision = response.choices[0].message.content.strip()

        if "Function" in routing_decision:
            print("function decided")
            return "Function"
        else:
            print("no function needed")
            return "NO TOOL"
    except Exception as e:
        logging.error(f"Error executing route_query: {e}", exc_info=True)


def run_general(query):
    try:
        """Use the general model to answer the query since no tool is needed"""
        response = ""
        try:
            stream = Groq_client.chat.completions.create(
                model=GENERAL_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": query},
                ],
                stream=True,
            )
        except Exception as e:
            if "Groq API limit reached" in str(e):
                stream = ollama_chat(
                    model=GENERAL_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": query},
                    ],
                    stream=True,
                )
                response = ollama_chat(
                    user_input, system_message, ollama_model, conversation_history
                )
            else:
                raise e

        for chunk in stream:
            print(chunk.choices[0].delta.content, end="")
            chunk_text = chunk.choices[0].delta.content
            response = f"{response}{chunk_text}"

            if any(delimiter in response for delimiter in ".:!?"):
                response = response[1:]  # Remove the first character
                sentence, response = split_sentence(response)
                TTS_queue.put(sentence)
    except Exception as e:
        logging.error(f"Error executing run_general: {e}", exc_info=True)


# Define the function to split sentences with the condition
def split_sentence(response):
    try:
        delimiters = r"[.,;!?]"  # Delimiters for splitting
        # Split the response based on delimiters
        sentences = re.split(delimiters, response, maxsplit=1)

        # If we have more than one part after the split
        if len(sentences) > 1:
            sentence, remaining_response = sentences[0], sentences[1]

            # Check if the sentence has 10 words or more
            if len(sentence.split()) < 15:
                # If the sentence is too short, don't split
                sentence = sentence + remaining_response
                remaining_response = ""
        else:
            # No split happened, just return the original response
            sentence, remaining_response = sentences[0], ""

        return sentence.strip(), remaining_response.strip()
    except Exception as e:
        logging.error(f"Error executing split_sentence: {e}", exc_info=True)


import aiohttp
import asyncio


last_tool_call_found = False


def _split_compound_commands(query: str):
    text = (query or "").strip()
    if not text:
        return []

    # Split on common command separators while keeping each command phrase intact.
    parts = re.split(
        r"\s*(?:,|;|\band then\b|\bthen\b|\band\b)\s*",
        text,
        flags=re.IGNORECASE,
    )
    commands = []
    for part in parts:
        cleaned = part.strip().strip(".!?")
        if cleaned:
            commands.append(cleaned)
    return commands


async def execute_command_run_with_tool(
    query,
    max_retries=3,
    retry_delay=2,
    context_hint="",
    _allow_compound_split=True,
):
    try:
        global Groq_client, last_tool_call_found
        logging.info(f"{CYAN}Executing command: {query}{RESET}")

        normalized_query = normalize_transcript(query)
        split_commands = _split_compound_commands(query)
        if _allow_compound_split and len(split_commands) > 1:
            logging.info(
                f"{YELLOW}Compound command detected; executing {len(split_commands)} sub-commands sequentially{RESET}"
            )
            sub_results = []
            for idx, cmd in enumerate(split_commands, start=1):
                logging.info(
                    f"{YELLOW}Compound sub-command {idx}/{len(split_commands)}: {cmd}{RESET}"
                )
                sub_ok = await execute_command_run_with_tool(
                    cmd,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    context_hint=context_hint,
                    _allow_compound_split=False,
                )
                sub_results.append(bool(sub_ok))
            last_tool_call_found = any(sub_results)
            if not all(sub_results):
                logging.warning(
                    f"{YELLOW}One or more sub-commands failed in compound execution: {split_commands}{RESET}"
                )
            return all(sub_results)

        if "spotify" in normalized_query:
            if any(token in normalized_query for token in ("kill", "stop", "close", "quit", "exit")):
                stop_spotify()
                last_tool_call_found = True
                return True
            if any(token in normalized_query for token in ("open", "play", "start", "launch", "spotify")):
                launch_application("spotify")
                last_tool_call_found = True
                return True

        last_tool_call_found = False
        tools_messages = [
            {
                "role": "system",
                "content": """You are a specialized assistant for controlling computer functions. Your role is to:
                1. Carefully analyze user queries to determine the most appropriate tool/function
                2. For a query with multiple independent actions, return MULTIPLE tool calls (one per action)
                3. For a query with a single action, return exactly one tool call
                4. Only use tools that exactly match the user's intent
                5. For system controls (volume, media, windows), be very precise in tool selection
                6. If no exact tool matches the query, do not force a tool selection
                7. For launching desktop apps, use launch_application(app=...) with a supported app name (sound control panel, device manager, disk management, network connections, system properties, date and time, task scheduler, startup folder, recycle bin, services, cmd, powershell, edge, chrome, firefox, calculator, notepad, control panel, word, excel, powerpoint, outlook, paint, spotify).
                8. If the user says "start/open display fusion" without a profile, call start_display_fusion(profile_name="Default").

                Examples:
                - "play music" → use play_song()
                - "volume up" → use volume_up()
                - "skip" → use next_track()
                - "minimize everything" → use minimize_all_windows()
                - "check internet speed" → ping_google()
                - "restart voicemeeter and open recycle bin" → call restart_voicemeeter() and launch_application(app="recycle bin")

                Only respond with tool calls, no conversational responses.""",
            },
            {
                "role": "user",
                "content": query,
            },
        ]
        if context_hint:
            tools_messages.insert(
                1,
                {
                    "role": "system",
                    "content": (
                        "Weak context from recent utterances (can be noisy):\n"
                        f"{context_hint}\n"
                        "Use only to disambiguate; prioritize the current query."
                    ),
                },
            )

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            refresh_groq_model_rotators(api_key)
        except Exception as e:
            logging.warning(
                "%sGroq model catalog refresh failed before tool-use request: %s%s",
                YELLOW,
                e,
                RESET,
            )

        for attempt in range(max_retries):
            try:
                tool_model = next_tool_use_model()
                logging.info(
                    f"{YELLOW}Attempt {attempt + 1} of {max_retries} using model {tool_model}{RESET}"
                )
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={
                            "model": tool_model,
                            "messages": tools_messages,
                            "stream": False,
                            "tools": _filtered_tools_for_llm(),
                            "tool_choice": "auto",
                            "max_tokens": 4096,
                        },
                        headers=headers,
                    ) as response:
                        if response.status >= 400:
                            response_text = await response.text()
                            classification = classify_groq_model_error(
                                response.status,
                                response_text,
                            )
                            logging.error(
                                "Groq tool-use API error %s %s for model %s: %s",
                                response.status,
                                response.reason,
                                tool_model,
                                response_text[:500],
                            )
                            if classification.is_model_error:
                                note_tool_use_model_failure(
                                    tool_model,
                                    classification.reason,
                                )
                                if classification.reason.startswith(
                                    ("model_", "model_or_endpoint")
                                ):
                                    try:
                                        refresh_groq_model_rotators(
                                            api_key,
                                            force_refresh=True,
                                            update_on_error=False,
                                        )
                                    except Exception as refresh_error:
                                        logging.warning(
                                            "%sGroq model catalog force-refresh failed after %s: %s%s",
                                            YELLOW,
                                            classification.reason,
                                            refresh_error,
                                            RESET,
                                        )
                                if attempt < max_retries - 1:
                                    continue
                            if classification.is_rate_limit:
                                note_tool_use_rate_limit(
                                    tool_model,
                                    classification.reason,
                                )
                                if attempt < max_retries - 1:
                                    continue
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status,
                                message=response.reason,
                                headers=response.headers,
                            )
                        response_data = await response.json()

                response_message = response_data["choices"][0]["message"]
                logging.info(
                    f"{CYAN}Received response from Groq client: {response_message}{RESET}"
                )
                tool_calls = response_message.get("tool_calls")

                overall_success = True
                if tool_calls:
                    async def _run_tool_call(tool_call):
                        try:
                            function_name = tool_call["function"]["name"]
                            raw_args = tool_call["function"].get("arguments")
                            if not raw_args or raw_args == "null":
                                function_args = {}
                            else:
                                function_args = json.loads(raw_args)
                            if function_args is None:
                                function_args = {}
                        except Exception as e:
                            logging.error(
                                f"{RED}Invalid tool call payload: {e}{RESET}",
                                exc_info=True,
                            )
                            return False

                        if (
                            function_name in {"ask_chatgpt", "ask_ai"}
                            and not str(function_args.get("question") or "").strip()
                        ):
                            try:
                                from wkey.ask_ai_bridge import extract_question_from_transcript
                            except ImportError:
                                from ask_ai_bridge import extract_question_from_transcript
                            extracted_question = extract_question_from_transcript(query)
                            if extracted_question:
                                function_args["question"] = extracted_question
                        if (
                            function_name in {"ask_chatgpt", "ask_ai"}
                            and not str(function_args.get("question") or "").strip()
                        ):
                            logging.error(
                                f"{RED}Ask-AI tool call missing question for query: {query}{RESET}"
                            )
                            return False

                        if function_name in DISABLED_TOOL_NAMES:
                            logging.info(
                                f"{YELLOW}Ignoring disabled tool call: {function_name}{RESET}"
                            )
                            return False

                        tool_registry = tool_function_registry(globals())
                        if function_name not in tool_registry:
                            logging.error(
                                f"{RED}Function {function_name} not found{RESET}"
                            )
                            return False

                        try:
                            logging.info(
                                f"{CYAN}Executing function: {function_name} with arguments: {function_args}{RESET}"
                            )
                            func = tool_registry[function_name]
                            import inspect

                            sig = inspect.signature(func)
                            accepts_named = any(
                                param.kind
                                in (
                                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                    inspect.Parameter.KEYWORD_ONLY,
                                    inspect.Parameter.VAR_KEYWORD,
                                )
                                for param in sig.parameters.values()
                            )
                            if not accepts_named:
                                if asyncio.iscoroutinefunction(func):
                                    invocation = func()
                                else:
                                    invocation = asyncio.to_thread(func)
                            else:
                                if asyncio.iscoroutinefunction(func):
                                    invocation = func(**function_args)
                                else:
                                    invocation = asyncio.to_thread(func, **function_args)
                            result = await asyncio.wait_for(
                                invocation, timeout=TOOL_EXECUTION_TIMEOUT_SECONDS
                            )
                            logging.info(
                                f"{GREEN}Executed {function_name} with result: {result}{RESET}"
                            )
                            return True
                        except asyncio.TimeoutError:
                            logging.error(
                                f"{RED}Tool execution timeout ({TOOL_EXECUTION_TIMEOUT_SECONDS:.1f}s) for {function_name}{RESET}"
                            )
                            return False
                        except Exception as e:
                            logging.error(
                                f"{RED}Error executing function {function_name}: {str(e)}{RESET}",
                                exc_info=True,
                            )
                            return False

                    tool_results = await asyncio.gather(
                        *[_run_tool_call(tc) for tc in tool_calls],
                        return_exceptions=True,
                    )
                    for result in tool_results:
                        if isinstance(result, Exception):
                            overall_success = False
                        elif result is False:
                            overall_success = False
                else:
                    logging.error(f"{RED}No tool calls found in the response{RESET}")
                    split_commands = _split_compound_commands(query)
                    if len(split_commands) > 1:
                        logging.info(
                            f"{YELLOW}Fallback: routing {len(split_commands)} sub-commands sequentially{RESET}"
                        )
                        sub_results = []
                        for cmd in split_commands:
                            sub_result = await execute_command_run_with_tool(
                                cmd,
                                max_retries=max_retries,
                                retry_delay=retry_delay,
                                context_hint=context_hint,
                                _allow_compound_split=False,
                            )
                            sub_results.append(sub_result)
                        successful = []
                        for sub in sub_results:
                            if isinstance(sub, Exception):
                                successful.append(False)
                            else:
                                successful.append(bool(sub))
                        last_tool_call_found = any(successful)
                        return all(successful)

                last_tool_call_found = bool(tool_calls)
                return overall_success

            except Exception as e:
                logging.error(
                    f"{RED}Error executing command: {str(e)}{RESET}", exc_info=True
                )
                if attempt < max_retries - 1:
                    logging.info(
                        f"{YELLOW}Retrying... ({attempt + 1}/{max_retries}){RESET}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logging.error(
                        f"{RED}Failed to execute command after {max_retries} attempts{RESET}"
                    )
                    return False

    except Exception as e:
        logging.error(
            f"{RED}Error in execute_command_run_with_tool: {str(e)}{RESET}",
            exc_info=True,
        )
        return False


def visual_feedback(function_name, result):
    try:
        # Visual feedback
        root = tk.Tk()
        root.title("Function Execution Result")

        # Set window size
        root.geometry("800x600")

        label = tk.Label(
            root,
            text=f"Executed {function_name} with result: {result}",
            font=("Helvetica", 24),
        )
        label.pack(pady=200)

        root.mainloop()
    except Exception as e:
        logging.error(f"Error executing visual_feedback: {e}", exc_info=True)


"""
######## ##     ## ########  ######  
##        ##   ##  ##       ##    ## 
##         ## ##   ##       ##       
######      ###    ######   ##       
##         ## ##   ##       ##       
##        ##   ##  ##       ##    ## 
######## ##     ## ########  ######  
"""
# Invert COMMAND_MAPPINGS to map each phrase to its action
PHRASE_TO_ACTION = {}
for action_key, phrases in COMMAND_MAPPINGS.items():
    for phrase in phrases:
        PHRASE_TO_ACTION[phrase] = ACTIONS[action_key]


def normalize_transcript(transcript):
    try:
        # Convert to lowercase
        transcript = transcript.lower()

        # Remove punctuation
        transcript = transcript.translate(str.maketrans("", "", string.punctuation))

        # Normalize whitespace (remove extra spaces)
        transcript = re.sub(r"\s+", " ", transcript).strip()

        return transcript
    except Exception as e:
        logging.error(f"Error executing normalize_transcript: {e}", exc_info=True)


def execute_command_fuzzy(transcript):
    try:
        # Normalize the transcript
        command = normalize_transcript(transcript)

        # Split the command at "and" and iterate through each part
        commands = command.split(" and ")

        for cmd in commands:
            # Strip any leading/trailing whitespace from each command
            cmd = cmd.strip()

            # Attempt to find a direct match
            action = PHRASE_TO_ACTION.get(cmd)

            # If no direct match is found, use fuzzy matching
            if not action:
                # Find the best fuzzy match (with a threshold of 80 for confidence)
                best_match, match_score = process.extractOne(
                    cmd, PHRASE_TO_ACTION.keys()
                )
                if (
                    match_score >= 60 and "computer" in transcript
                ):  # Adjust the threshold as needed
                    action = PHRASE_TO_ACTION.get(best_match)

            if action:
                action()  # Execute the corresponding action
                logging.info(f"{GREEN}Executing fuzzy command: {cmd}{RESET}")
                print(f"Executing command: {cmd}")
            else:
                print(f"No matching command found for: {cmd}")

        return True
    except Exception as e:
        logging.error(f"{RED}Error executing fuzzy command: {e}{RESET}", exc_info=True)

    return True
