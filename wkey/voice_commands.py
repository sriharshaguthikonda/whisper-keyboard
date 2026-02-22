# voice_commands.py
import os
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
    extra_tools,
    launch_application,
    stop_spotify,
)
from model_rotation import next_tool_use_model


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


# Path to your Edge WebDriver
webdriver_path = r"C:\Users\deletable\Downloads\edgedriver_win64\msedgedriver.exe"

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


# Initialize the WebDriver
service = Service(webdriver_path)

driver = None
driver_pid = None
session_id = None
executor_url = None


def start_driver():
    try:
        global driver, driver_pid, session_id, executor_url

        logging.info(f"{CYAN}Starting driver...{RESET}")
        driver = webdriver.Edge(service=service, options=options)
        time.sleep(6)
        driver.get("https://open.spotify.com/collection/tracks")
        # driver.execute_script("window.focus();")
        time.sleep(5)  # Wait for the page to load
        driver_pid = driver.service.process.pid
        session_id = driver.session_id
        executor_url = driver.command_executor.remote_url
        logging.info(f"{GREEN}WebDriver started successfully.{RESET}")
        
        # Update driver reference in commands_and_tools
        try:
            from commands_and_tools import set_driver_reference
            set_driver_reference(driver)
        except ImportError:
            pass
            
    except Exception as e:
        logging.error(f"{RED}Error starting driver: {e}{RESET}", exc_info=True)


"""
https://chatgpt.com/c/66e49b09-cca4-8013-a443-6793c6073c2f
"""


def reconnect_driver():
    try:
        global driver, session_id, executor_url, options

        logging.info(f"{CYAN}Reconnecting to WebDriver session...{RESET}")
        if session_id and executor_url:
            driver = webdriver.Remote(command_executor=executor_url, options=options)
            driver.session_id = session_id
            logging.info(f"{GREEN}Reconnected to the existing session.{RESET}")
            
            # Update driver reference in commands_and_tools
            try:
                from commands_and_tools import set_driver_reference
                set_driver_reference(driver)
            except ImportError:
                pass
                
    except (SessionNotCreatedException, WebDriverException) as e:
        logging.error(
            f"{RED}Failed to reconnect to the session: {str(e)}{RESET}", exc_info=True
        )

        # Attempt to start a new session
        try:
            logging.info(f"{CYAN}Attempting to start a new WebDriver session...{RESET}")
            # options = webdriver.EdgeOptions()
            # options.binary_location = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"  # Correct Edge binary path

            driver = webdriver.Edge(
                options=options,
                service_log_path="C:/Users/deletable/Downloads/edgedriver_win64/msedgedriver.log",
            )
            time.sleep(3)
            driver.get("https://open.spotify.com/collection/tracks")
            time.sleep(3)
            logging.info(f"{GREEN}Started a new session.{RESET}")
            
            # Update driver reference in commands_and_tools
            try:
                from commands_and_tools import set_driver_reference
                set_driver_reference(driver)
            except ImportError:
                pass
                
        except Exception as new_session_error:
            logging.error(
                f"{RED}Failed to start a new session: {new_session_error}{RESET}",
                exc_info=True,
            )


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
    try:
        logging.info("Changing playback device...")
        devices_button = driver.find_element(
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
            driver.find_element(By.XPATH, '//*[@id="device-picker"]').click()
        except Exception as e:
            logging.error(
                f"Error while trying to play after reconnection: {e}", exc_info=True
            )
        time.sleep(2)
        driver.find_element(
            # By.XPATH, '//*[text()="Web Player (Microsoft Edge)"]'
            By.XPATH,
            '//*[text()="This web browser"]',
        ).click()
        # Click the panel
    except Exception as e:
        logging.error(
            f"Error while trying to play after reconnection: {e}", exc_info=True
        )


# Control playback
def play_music():
    try:
        play_button = driver.find_element(By.XPATH, "//button[@aria-label='Play']")
        play_button.click()
        change_device()
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
            except Exception as e:
                print(f"Error while trying to play after reconnection: {e}")

        elif "target window already closed" in error_message:
            driver.quit()
            start_driver()
            try:
                play_button = driver.find_element(
                    By.XPATH, "//button[@aria-label='Play']"
                )
                play_button.click()
                print("Playback started after reconnection.")
            except Exception as e:
                print(f"Error while trying to play after reconnection: {e}")

        else:
            print(f"Error while trying to play: {e}")


def pause_song():
    try:
        pause_button = driver.find_element("xpath", "//button[@aria-label='Pause']")
        pause_button.click()
        print("Playback paused.")
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
            except Exception as e:
                print(f"Error while trying to pause after reconnection: {e}")
        else:
            print(f"Error while trying to pause: {e}")


def next_track():
    try:
        next_button = driver.find_element("xpath", "//button[@aria-label='Next']")
        next_button.click()
        print("Next track.")
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
            except Exception as e:
                print(
                    f"Error while trying to skip to next track after reconnection: {e}"
                )
        else:
            print(f"Error while trying to skip to next track: {e}")


def previous_track():
    try:
        prev_button = driver.find_element("xpath", "//button[@aria-label='Previous']")
        prev_button.click()
        print("Previous track.")
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
            except Exception as e:
                print(
                    f"Error while trying to go to previous track after reconnection: {e}"
                )
        else:
            print(f"Error while trying to go to previous track: {e}")


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


def get_volume():
    try:
        volume_interface = get_volume_interface()
        if volume_interface is None:
            logging.warning("get_volume: volume_interface is None")
            return 0.5  # Default fallback
        current_volume = volume_interface.GetMasterVolumeLevelScalar()
        logging.info(f"{BLUE}Getting volume...{RESET}")
        return round(current_volume, 2)
    except Exception as e:
        logging.error(f"{RED}Error executing get_volume: {e}{RESET}", exc_info=True)
        return 0.5  # Default fallback


def volume_up(steps=1):
    try:
        volume_interface = get_volume_interface()
        current_volume = volume_interface.GetMasterVolumeLevelScalar()
        new_volume = min(current_volume + steps * 0.05, 1.0)  # Increase by 5% per step
        volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
        print(f"Volume increased to {new_volume * 100:.0f}%")
    except Exception as e:
        logging.error(f"Error executing volume_up: {e}", exc_info=True)


def volume_down(steps=1):
    try:
        volume_interface = get_volume_interface()
        current_volume = volume_interface.GetMasterVolumeLevelScalar()
        new_volume = max(current_volume - steps * 0.05, 0.0)  # Decrease by 5% per step
        volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
        print(f"Volume decreased to {new_volume * 100:.0f}%")
    except Exception as e:
        logging.error(f"Error executing volume_down: {e}", exc_info=True)


def set_volume(level):
    try:
        if 0.0 <= level <= 1.0:
            volume_interface = get_volume_interface()
            if volume_interface is None:
                logging.warning("set_volume: volume_interface is None, skipping")
                return
            volume_interface.SetMasterVolumeLevelScalar(level, None)
            logging.info(f"{BLUE}Setting volume to {level * 100}%{RESET}")
            print(f"Volume set to {level * 100:.0f}%")
        else:
            print("Volume level must be between 0.0 and 1.0")
    except Exception as e:
        logging.error(f"{RED}Error setting volume: {e}{RESET}", exc_info=True)


def get_volume_interface():
    try:
        import pythoncom
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        from ctypes import cast, POINTER
        
        # Initialize COM for this thread (required for cross-thread COM access)
        pythoncom.CoInitialize()
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
        return volume_interface
    except ValueError as e:
        logging.error(
            f"{RED}ValueError in get_volume_interface: {e}{RESET}", exc_info=True
        )
    except Exception as e:
        logging.error(f"Error executing get_volume_interface: {e}", exc_info=True)


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
    try:
        initial_volume = get_volume()
        print(initial_volume)
        subprocess.run(
            '"C:\\Program Files (x86)\\VB\\VBAudioMatrix\\VBAudioMatrix_x64.exe" -r',
            shell=True
        )
        time.sleep(2)
        set_volume(initial_volume)
    except Exception as e:
        logging.error(f"Error executing restart_voicemeeter: {e}", exc_info=True)



# DisplayFusion commands
def start_display_fusion(profile_name):
    try:
        subprocess.run(["taskkill", "/F", "/IM", "DisplayFusion.exe"])
        subprocess.run(
            [
                "C:\\Program Files (x86)\\DisplayFusion\\DisplayFusionCommand.exe",
                "-monitorloadprofile",
                profile_name,
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
        while True:
            sentence = TTS_queue.get()
            if sentence is None:  # Sentinel value to stop the worker
                break
            asyncio.run(text_to_speech(sentence, speed=1.3))
            TTS_queue.task_done()
    except Exception as e:
        logging.error(f"Error processing TTS queue: {e}", exc_info=True)


threading.Thread(target=process_TTS_queue, daemon=True).start()


# Function to process the queue
def process_TTS_Audio_play_queue():
    try:
        while True:
            audio_fp = TTS_Audio_play_queue.get()
            if audio_fp is None:  # Add sentinel check
                break
            audio_fp.seek(0)
            sound = AudioSegment.from_file(audio_fp, format="mp3")
            play(sound)
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


# Function to convert text to speech using edge-tts and play using pydub with speed adjustment
async def text_to_speech(text, speed=1.2, volume=1, voice="en-GB-MiaNeural"):
    try:
        # Online TTS using edge-tts
        rate = "+" + str(int((speed - 1) * 100)) + "%"
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_bytes = b""

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if not audio_bytes:
            raise ValueError("No audio received. verify that your params are correct.")

        audio_fp = io.BytesIO(audio_bytes)
        audio_fp.seek(0)

        # Place the audio data in the playback queue
        TTS_Audio_play_queue.put(audio_fp)

    except Exception as e:
        logging.error(f"Error executing text_to_speech: {e}", exc_info=True)
        print("Falling back to offline TTS...")
        fallback_offline_tts(text, speed, volume)


# Offline TTS fallback using pyttsx4
def fallback_offline_tts(text, speed=1.2, volume=1):
    try:
        # Initialize pyttsx4 engine
        engine = pyttsx4.init()

        # Set the speed (words per minute)
        engine.setProperty("rate", int(200 * speed))

        # Set the volume (0.0 to 1.0)
        engine.setProperty("volume", volume)

        # Speak the text
        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        logging.error(f"Error executing fallback_offline_tts: {e}", exc_info=True)
        print(f"Offline TTS failed: {e}")


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


async def execute_command_run_with_tool(query, max_retries=3, retry_delay=2):
    try:
        global Groq_client
        logging.info(f"{CYAN}Executing command: {query}{RESET}")

        tools_messages = [
            {
                "role": "system",
                "content": """You are a specialized assistant for controlling computer functions. Your role is to:
                1. Carefully analyze user queries to determine the most appropriate tool/function
                2. Select the SINGLE most relevant tool from the available options
                3. Only use tools that exactly match the user's intent
                4. For system controls (volume, media, windows), be very precise in tool selection
                5. If no exact tool matches the query, do not force a tool selection
                6. For launching desktop apps, use launch_application(app=...) with a supported app name (cmd, powershell, edge, chrome, firefox, calculator, notepad, control panel, word, excel, powerpoint, outlook, paint).

                Examples:
                - "play music" → use play_song()
                - "volume up" → use volume_up()
                - "skip" → use next_track()
                - "minimize everything" → use minimize_all_windows()
                - "check internet speed" → ping_google()

                Only respond with tool calls, no conversational responses.""",
            },
            {
                "role": "user",
                "content": query,
            },
        ]

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}

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
                            "tools": tools,
                            "tool_choice": "auto",
                            "max_tokens": 4096,
                        },
                        headers=headers,
                    ) as response:
                        if response.status == 404:
                            logging.error(
                                f"Groq API endpoint not found: {response.url}"
                            )
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status,
                                message=response.reason,
                                headers=response.headers,
                            )
                        response.raise_for_status()
                        response_data = await response.json()

                response_message = response_data["choices"][0]["message"]
                logging.info(
                    f"{CYAN}Received response from Groq client: {response_message}{RESET}"
                )
                tool_calls = response_message.get("tool_calls")

                overall_success = True
                if tool_calls:
                    for tool_call in tool_calls:
                        function_args = json.loads(tool_call["function"]["arguments"])
                        function_name = tool_call["function"]["name"]

                        if function_name in globals():
                            try:
                                logging.info(
                                    f"{CYAN}Executing function: {function_name} with arguments: {function_args}{RESET}"
                                )
                                func = globals()[function_name]
                                # Get the function's parameters
                                import inspect
                                sig = inspect.signature(func)
                                
                                # Check if the function accepts any parameters
                                if not any(param.kind == param.POSITIONAL_OR_KEYWORD for param in sig.parameters.values()):
                                    # Function takes no parameters
                                    if asyncio.iscoroutinefunction(func):
                                        result = await func()
                                    else:
                                        result = func()
                                else:
                                    # Function expects parameters
                                    if asyncio.iscoroutinefunction(func):
                                        result = await func(**function_args)
                                    else:
                                        result = func(**function_args)
                                logging.info(
                                    f"{GREEN}Executed {function_name} with result: {result}{RESET}"
                                )
                                """TODO  we have removed "return True" here because to run mulltiple functions  """
                                """return True"""
                            except Exception as e:
                                logging.error(
                                    f"{RED}Error executing function {function_name}: {str(e)}{RESET}",
                                    exc_info=True,
                                )
                                overall_success = False
                                continue
                        else:
                            logging.error(
                                f"{RED}Function {function_name} not found{RESET}"
                            )
                            """TODO  we have removed return False" here because to run mulltiple functions  """
                            """return False"""
                            overall_success = False
                            continue
                else:
                    logging.error(f"{RED}No tool calls found in the response{RESET}")

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
