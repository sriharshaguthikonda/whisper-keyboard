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
import subprocess
import psutil

from groq import Groq
import ollama
from dotenv import load_dotenv
import json

import io
import edge_tts
import pyttsx4

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


from pydub import AudioSegment
from pydub.playback import play
import queue
import logging

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
    global api_key, Groq_client
    if api_key is None:
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
    else:
        pass
    Groq_client = Groq(api_key=api_key)
    return Groq_client


# Define models
ROUTING_MODEL = "llama3-70b-8192"
# ROUTING_MODEL = "llama-3.2-1b-preview"
# TOOL_USE_MODEL = "llama3-groq-8b-8192-tool-use-preview"
# TOOL_USE_MODEL = "llama3-groq-70b-8192-tool-use-preview"
TOOL_USE_MODEL = "llama-3.1-8b-instant"

GENERAL_MODEL = "llama3-70b-8192"
ollama_model = "llama3.2:latest"


# Path to your Edge WebDriver
webdriver_path = r"C:\Users\deletable\Downloads\edgedriver_win64\msedgedriver.exe"

# Set up Edge options
options = Options()
options.add_argument(
    r"user-data-dir=C:\\Users\\YourUsername\\AppData\\Local\\Microsoft\\Edge\\User Data"
)  # Adjust this to your user data directory
options.add_argument(r"profile-directory=Profile 1")  # Adjust this to your profile name

# Add remote allow origins
options.add_argument("--remote-allow-origins=*")

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
    global driver, driver_pid, session_id, executor_url

    try:
        logging.info("Starting WebDriver...")
        driver = webdriver.Edge(service=service, options=options)
        time.sleep(6)
        driver.get("https://open.spotify.com/collection/tracks")
        # driver.execute_script("window.focus();")
        time.sleep(5)  # Wait for the page to load
        driver_pid = driver.service.process.pid
        session_id = driver.session_id
        executor_url = driver.command_executor._url
        logging.info("WebDriver started successfully.")
    except Exception as e:
        logging.error(f"Error starting WebDriver: {e}", exc_info=True)


"""
https://chatgpt.com/c/66e49b09-cca4-8013-a443-6793c6073c2f
"""


def reconnect_driver():
    global driver, session_id, executor_url, options

    try:
        logging.info("Reconnecting to WebDriver session...")
        if session_id and executor_url:
            driver = webdriver.Remote(command_executor=executor_url, options=options)
            driver.session_id = session_id
            logging.info("Reconnected to the existing session.")
    except (SessionNotCreatedException, WebDriverException) as e:
        logging.error(f"Failed to reconnect to the session: {str(e)}", exc_info=True)

        # Attempt to start a new session
        try:
            logging.info("Attempting to start a new WebDriver session...")
            # options = webdriver.EdgeOptions()
            # options.binary_location = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"  # Correct Edge binary path

            driver = webdriver.Edge(
                options=options,
                service_log_path="C:/Users/deletable/Downloads/edgedriver_win64/msedgedriver.log",
            )
            time.sleep(3)
            driver.get("https://open.spotify.com/collection/tracks")
            time.sleep(3)
            logging.info("Started a new session.")
        except Exception as new_session_error:
            logging.error(
                f"Failed to start a new session: {new_session_error}", exc_info=True
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
        if "disconnected" in error_message or "NoneType" in error_message:
            logging.info("Attempting to reconnect due to disconnection...")
            reconnect_driver()
            try:
                driver.execute_script(
                    "document.querySelector('button[aria-label=\"Play\"]').click()"
                )
                logging.info("Playback started after reconnection.")
                change_device()
            except Exception as e:
                logging.error(
                    f"Error while trying to play after reconnection: {e}", exc_info=True
                )
        else:
            logging.error(f"Error while trying to play: {e}", exc_info=True)


def pause_song():
    try:
        logging.info("Pausing playback...")
        driver.execute_script(
            "document.querySelector('button[aria-label=\"Pause\"]').click()"
        )
        logging.info("Playback paused.")
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            logging.info("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                driver.execute_script(
                    "document.querySelector('button[aria-label=\"Pause\"]').click()"
                )
                logging.info("Playback paused after reconnection.")
            except Exception as e:
                logging.error(
                    f"Error while trying to pause after reconnection: {e}",
                    exc_info=True,
                )
        else:
            logging.error(f"Error while trying to pause: {e}", exc_info=True)


def next_track():
    try:
        logging.info("Skipping to next track...")
        driver.execute_script(
            "document.querySelector('button[aria-label=\"Next\"]').click()"
        )
        logging.info("Next track.")
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            logging.info("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                driver.execute_script(
                    "document.querySelector('button[aria-label=\"Next\"]').click()"
                )
                logging.info("Next track after reconnection.")
            except Exception as e:
                logging.error(
                    f"Error while trying to skip to next track after reconnection: {e}",
                    exc_info=True,
                )
        else:
            logging.error(
                f"Error while trying to skip to next track: {e}", exc_info=True
            )


def previous_track():
    try:
        logging.info("Skipping to previous track...")
        driver.execute_script(
            "document.querySelector('button[aria-label=\"Previous\"]').click()"
        )
        logging.info("Previous track.")
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            logging.info("Attempting to reconnect due to DevTools disconnection...")
            reconnect_driver()
            try:
                driver.execute_script(
                    "document.querySelector('button[aria-label=\"Previous\"]').click()"
                )
                logging.info("Previous track after reconnection.")
            except Exception as e:
                logging.error(
                    f"Error while trying to go to previous track after reconnection: {e}",
                    exc_info=True,
                )
        else:
            logging.error(
                f"Error while trying to go to previous track: {e}", exc_info=True
            )


"""
 ######   #######  ##     ## ##     ##    ###    ##    ## ########  
##    ## ##     ## ###   ### ###   ###   ## ##   ###   ## ##     ## 
##       ##     ## #### #### #### ####  ##   ##  ####  ## ##     ## 
##       ##     ## ## ### ## ## ### ## ##     ## ## ## ## ##     ## 
##       ##     ## ##     ## ##     ## ######### ##  #### ##     ## 
##    ## ##     ## ##     ## ##     ## ##     ## ##   ### ##     ## 
 ######   #######  ##     ## ##     ## ##     ## ##    ## ########  
"""

COMMAND_MAPPINGS = {
    # System Commands
    "search windows": [
        "open start menu",
        "show start menu",
        "Windows search",
    ],
    "show desktop": ["show desktop", "minimize everything"],
    "open settings": ["open settings", "settings"],
    "lock screen": ["lock screen", "lock the computer"],
    "take screenshot": ["take screenshot", "capture screen"],
    "open file explorer": [
        "open file explorer",
        "explore files",
    ],
    "windows search": ["open search", "search"],
    "open run dialog": ["open run dialog", "run command"],
    "open task manager": [
        "open task manager",
        "task manager",
    ],
    "minimize all windows": [
        "minimize all windows",
        "minimize windows",
    ],
    "restore windows": [
        "restore windows",
        "restore all windows",
    ],
    #    "shutdown system": ["shutdown system", "turn off computer"],
    #    "restart system": ["restart system", "reboot computer"],
    #    "log off": ["log off", "sign out"],
    # Application Commands
    #     "open control panel": [
    #         "open control panel",
    #         "control panel",
    #     ],
    "open calculator": ["open calculator", "calculator"],
    "open notepad": ["open notepad", "notepad"],
    "open word": ["open word", "start word"],
    "open excel": ["open excel", "start excel"],
    "open powerpoint": [
        "open powerpoint",
        "start powerpoint",
    ],
    "open outlook": ["open outlook", "start outlook"],
    "open paint": ["open paint", "start paint"],
    "open command prompt": [
        "open command prompt",
        "open console",
        "command prompt",
        "Open command drop",
    ],
    "open powershell": ["open powershell", "powershell"],
    "open edge": ["open edge", "start edge"],
    "open chrome": ["open chrome", "start chrome"],
    "open firefox": ["open firefox", "start firefox"],
    # Volume Controls
    "open sound control panel": [
        "open sound control panel",
        "open audio settings",
    ],
    "volume up": ["volume up", "increase volume"],
    "volume down": ["volume down", "decrease volume"],
    # "mute volume": ["mute volume", "mute sound"],
    # Media Controls
    "play media": [
        "play media",
        "play",
        "play music",
    ],
    "stop media": [
        "stop media",
        "stop",
        "stop music",
    ],
    "next track": [
        "next track",
        "next song",
        "skip",
        "play next song",
    ],
    "previous track": [
        "previous track",
        "previous song",
        "replay",
        "play previous song",
    ],
    # Custom or Complex Operations
    "open device manager": [
        "open device manager",
        "device manager",
    ],
    "open disk management": [
        "open disk management",
        "disk management",
        "format disk",
        "hard disk",
    ],
    "open network connections": [
        "open network connections",
        "network connections",
    ],
    "open system properties": [
        "open system properties",
        "system properties",
    ],
    "open date and time": [
        "open date and time",
        "date and time",
    ],
    # System Commands
    "ping google": [
        "ping google",
        "check internet connection",
    ],
    "flush dns": ["flush dns", "reset dns cache"],
    # Add more as needed Play, pause, media.
    "restart voicemeeter": [
        "restart voice meter",
        "set voice meter",
    ],
    "load display fusion profile": [
        "display fusion",
        "a computer start display fusion",
        "load monitor profile",
        "set monitor profile",
    ],
    # Add more as needed Play, pause, media.
    "open negative screen": [
        "open negative screen",
        "invert screen",
    ],
}


"""
   ###     ######  ######## ####  #######  ##    ##  ######  
  ## ##   ##    ##    ##     ##  ##     ## ###   ## ##    ## 
 ##   ##  ##          ##     ##  ##     ## ####  ## ##       
##     ## ##          ##     ##  ##     ## ## ## ##  ######  
######### ##          ##     ##  ##     ## ##  ####       ## 
##     ## ##    ##    ##     ##  ##     ## ##   ### ##    ## 
##     ##  ######     ##    ####  #######  ##    ##  ######  
"""

# Define actions for commands
ACTIONS = {
    # System Commands
    "search windows": lambda: pyautogui.press("win"),
    "show desktop": lambda: pyautogui.hotkey("win", "d"),
    "open settings": lambda: pyautogui.hotkey("win", "i"),
    "lock screen": lambda: pyautogui.hotkey("win", "l"),
    "take screenshot": lambda: pyautogui.hotkey("win", "prtsc"),
    "open file explorer": lambda: pyautogui.hotkey("win", "e"),
    "windows search": lambda: pyautogui.hotkey("win", "s"),
    "open run dialog": lambda: pyautogui.hotkey("win", "r"),
    "open task manager": lambda: pyautogui.hotkey("ctrl", "shift", "esc"),
    "minimize all windows": lambda: pyautogui.hotkey("win", "m"),
    "restore windows": lambda: pyautogui.hotkey("win", "shift", "m"),
    #    "shutdown system": lambda: os.system('shutdown /s /t 0'),
    #    "restart system": lambda: os.system('shutdown /r /t 0'),
    # "log off": lambda: os.system('shutdown /l'),
    # Application Commands
    "open control panel": lambda: os.system("control"),
    "open calculator": lambda: os.system("calc"),
    "open notepad": lambda: os.system("notepad"),
    "open word": lambda: os.system("start winword"),
    "open excel": lambda: os.system("start excel"),
    "open powerpoint": lambda: os.system("start powerpnt"),
    "open outlook": lambda: os.system("start outlook"),
    "open paint": lambda: os.system("start mspaint"),
    "open command prompt": lambda: os.system("start cmd"),
    "open powershell": lambda: os.system("start powershell"),
    "open edge": lambda: os.system("start msedge"),
    "open chrome": lambda: os.system("start chrome"),
    "open firefox": lambda: os.system("start firefox"),
    # Volume Controls
    "open sound control panel": lambda: os.system("control mmsys.cpl"),
    "volume up": lambda: pyautogui.press("volumeup"),
    "volume down": lambda: pyautogui.press("volumedown"),
    "mute volume": lambda: pyautogui.press("volumemute"),
    # Media Controls
    "play media": play_music,
    "stop media": pause_song,
    "next track": next_track,
    "previous track": previous_track,
    # Custom or Complex Operations
    "open device manager": lambda: os.system("devmgmt.msc"),
    "open disk management": lambda: os.system("diskmgmt.msc"),
    "open network connections": lambda: os.system("ncpa.cpl"),
    "open system properties": lambda: os.system("sysdm.cpl"),
    "open date and time": lambda: os.system("timedate.cpl"),
    # System Commands
    "ping google": lambda: os.system("ping www.google.com"),
    "flush dns": lambda: os.system("ipconfig /flushdns"),
    # Voicemeeter Commands
    "restart voicemeeter": lambda: subprocess.run(
        ["C:\\Program Files (x86)\\VB\\Voicemeeter\\voicemeeter8x64.exe", "-r"]
    ),
    # DisplayFusion Commands
    "load display fusion profile": lambda: subprocess.run(
        [
            "C:\\Program Files (x86)\\DisplayFusion\\DisplayFusionCommand.exe",
            "-monitorloadprofile",
            "Triple monitor medrivision bluegriffon textcrawler",
        ]
    ),
    # Add more as needed
    "open negative screen": lambda: subprocess.Popen(
        ["C:\\Program Files\\Negative screen\\NegativeScreen-custom-multi-monitor.exe"]
    ),
}


"""
######## ##     ## ##    ##  ######  ######## ####  #######  ##    ##  ######  
##       ##     ## ###   ## ##    ##    ##     ##  ##     ## ###   ## ##    ## 
##       ##     ## ####  ## ##          ##     ##  ##     ## ####  ## ##       
######   ##     ## ## ## ## ##          ##     ##  ##     ## ## ## ##  ######  
##       ##     ## ##  #### ##          ##     ##  ##     ## ##  ####       ## 
##       ##     ## ##   ### ##    ##    ##     ##  ##     ## ##   ### ##    ## 
##        #######  ##    ##  ######     ##    ####  #######  ##    ##  ######  
"""


# Define action functions
def search_windows():
    pyautogui.press("win")


def show_desktop():
    pyautogui.hotkey("win", "d")


def open_settings():
    pyautogui.hotkey("win", "i")


def lock_screen():
    pyautogui.hotkey("win", "l")


def take_screenshot():
    pyautogui.hotkey("win", "prtsc")


def open_file_explorer():
    pyautogui.hotkey("win", "e")


def windows_search():
    pyautogui.hotkey("win", "s")


def open_run_dialog():
    pyautogui.hotkey("win", "r")


def open_task_manager():
    pyautogui.hotkey("ctrl", "shift", "esc")


def minimize_all_windows():
    pyautogui.hotkey("win", "m")


def restore_windows():
    pyautogui.hotkey("win", "shift", "m")


# Application commands
def open_control_panel():
    os.system("control")


def open_calculator():
    os.system("calc")


def open_notepad():
    os.system("notepad")


def open_word():
    os.system("start winword")


def open_excel():
    os.system("start excel")


def open_powerpoint():
    os.system("start powerpnt")


def open_outlook():
    os.system("start outlook")


def open_paint():
    os.system("start mspaint")


def open_command_prompt():
    os.system("start cmd")


def open_powershell():
    os.system("start powershell")


def open_edge():
    os.system("start msedge")


def open_chrome():
    os.system("start chrome")


def open_firefox():
    os.system("start firefox")


# Volume controls
def open_sound_control_panel():
    os.system("control mmsys.cpl")


def kill_process_by_name(process_name):
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] == process_name:
            proc.kill()
            print(
                f"Process {process_name} with PID {proc.info['pid']} has been killed."
            )
            return
    print(f"No process named {process_name} found.")


def get_volume():
    volume_interface = get_volume_interface()
    current_volume = volume_interface.GetMasterVolumeLevelScalar()
    return round(current_volume, 2)


def volume_up(steps=1):
    volume_interface = get_volume_interface()
    current_volume = volume_interface.GetMasterVolumeLevelScalar()
    new_volume = min(current_volume + steps * 0.05, 1.0)  # Increase by 5% per step
    volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
    print(f"Volume increased to {new_volume * 100:.0f}%")


def volume_down(steps=1):
    volume_interface = get_volume_interface()
    current_volume = volume_interface.GetMasterVolumeLevelScalar()
    new_volume = max(current_volume - steps * 0.05, 0.0)  # Decrease by 5% per step
    volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
    print(f"Volume decreased to {new_volume * 100:.0f}%")


def set_volume(level):
    if 0.0 <= level <= 1.0:
        volume_interface = get_volume_interface()
        volume_interface.SetMasterVolumeLevelScalar(level, None)
        print(f"Volume set to {level * 100:.0f}%")
    else:
        print("Volume level must be between 0.0 and 1.0")


def get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
    return volume_interface


def mute_volume():
    pyautogui.press("volumemute")


# Media controls (assumes these are defined elsewhere)
def play_media(song=None):
    # Logic to play song if provided
    if song:
        print(f"Playing {song}")
    else:
        print("Playing default media")


def stop_media():
    pause_song()
    print("Stopping media")


def next_track():
    print("Next track")


def previous_track():
    print("Previous track")


# Custom or complex operations
def open_device_manager():
    os.system("devmgmt.msc")


def open_disk_management():
    os.system("diskmgmt.msc")


def open_network_connections():
    os.system("ncpa.cpl")


def open_system_properties():
    os.system("sysdm.cpl")


def open_date_and_time():
    os.system("timedate.cpl")


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
            asyncio.run(
                text_to_speech(
                    text=f"The average ping to Google was {avg_ping} milleseconds, {avg_ping} milleseconds"
                )
            )
        else:
            return "Could not determine the average ping."
    except Exception as e:
        return f"Error occurred: {str(e)}"


def flush_dns():
    os.system("ipconfig /flushdns")


# Voicemeeter commands
def restart_voicemeeter():
    initial_volume = get_volume()
    print(initial_volume)
    subprocess.run(
        ["C:\\Program Files (x86)\\VB\\Voicemeeter\\voicemeeter8x64.exe", "-r"]
    )
    time.sleep(2)
    set_volume(initial_volume)


# DisplayFusion commands
def load_display_fusion_profile(profile_name):
    subprocess.run(["taskkill", "/F", "/IM", "DisplayFusion.exe"])
    subprocess.run(
        [
            "C:\\Program Files (x86)\\DisplayFusion\\DisplayFusionCommand.exe",
            "-monitorloadprofile",
            profile_name,
        ]
    )


def open_negative_screen():
    subprocess.Popen(
        ["C:\\Program Files\\Negative screen\\NegativeScreen-custom-multi-monitor.exe"]
    )


invert_screen = open_negative_screen


from datetime import datetime

# Replace 'J:\\' with the actual path to the backup directory
backup_directory = "J:\\"


def last_backup():
    # List all files in the directory
    backup_files = [f for f in os.listdir(backup_directory) if f.endswith(".mrimg")]
    if not backup_files:
        asyncio.run(text_to_speech("No backup files found."))

    # Get the most recent backup file by modification date
    latest_backup = max(
        backup_files, key=lambda f: os.path.getmtime(os.path.join(backup_directory, f))
    )
    last_modified_time = os.path.getmtime(os.path.join(backup_directory, latest_backup))
    last_backup_date = datetime.fromtimestamp(last_modified_time)

    # Calculate days since the last backup
    days_ago = (datetime.now() - last_backup_date).days
    asyncio.run(text_to_speech(f"Latest backup was {days_ago} days ago."))


def open_vscode():
    # Path to the Visual Studio Code executable
    vscode_path = (
        r"C:\Users\deletable\AppData\Local\Programs\Microsoft VS Code\Code.exe"
    )
    subprocess.Popen([vscode_path])


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
    """Routing logic to let LLM decide if tools are needed"""
    routing_prompt = f"""
    Given the following user query, determine if any tools are needed to answer it.
    If a a voice command intended to control some aspect of computer comes then, respond with 'Function'.
    If no tools are needed, respond with 'NO TOOL'.

    User query: {query}

    Response:
    """
    if not Groq_client:
        Groq_client = initialize_groq_client()
    else:
        pass

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


"""
# Function to run the general model and stream text chunks to TTS immediately
def run_general(query):
    "Stream response chunks to TTS immediately as they arrive"
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
"""


# Function to run Ollama's model and stream text chunks to TTS immediately
def run_ollama(query):
    """Stream response chunks to TTS immediately as they arrive"""

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
        if word_buffer and any(word_buffer.endswith(end) for end in sentence_endings):
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
    while True:
        sentence = TTS_queue.get()
        if sentence is None:  # Sentinel value to stop the worker
            break
        asyncio.run(text_to_speech(sentence, speed=1.3))
        TTS_queue.task_done()


threading.Thread(target=process_TTS_queue, args=(TTS_queue,), daemon=True).start()


# Function to process the queue
def process_TTS_Audio_play_queue():
    while True:
        audio_fp = TTS_Audio_play_queue.get()
        if audio_fp is None:  # Add sentinel check
            break
        audio_fp.seek(0)
        sound = AudioSegment.from_file(audio_fp, format="mp3")
        play(sound)
        TTS_Audio_play_queue.task_done()


# Queue for sentences
TTS_Audio_play_queue = queue.Queue()
TTS_queue = queue.Queue()

# Submit tasks to the executor instead of creating threads directly
executor.submit(process_TTS_Audio_play_queue)
executor.submit(process_TTS_queue)


# Add cleanup function to be called when shutting down
def cleanup():
    # Signal the worker threads to stop
    TTS_queue.put(None)
    TTS_Audio_play_queue.put(None)

    # Shutdown the executor gracefully
    executor.shutdown(wait=True)

    # Cleanup other resources if needed
    if driver:
        driver.quit()


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
        print(f"Offline TTS failed: {e}")


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
    """Routing logic to let LLM decide if tools are needed"""
    routing_prompt = f"""
    Given the following user query, determine if any tools are needed to answer it.
    If a a voice command intended to control some aspect of computer comes then, respond with 'Function'.
    If no tools are needed, respond with 'NO TOOL'.

    User query: {query}

    Response:
    """

    response = client.chat.completions.create(
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


def run_general(query):
    """Use the general model to answer the query since no tool is needed"""
    response = ""
    try:
        stream = client.chat.completions.create(
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

        #        if any(delimiter in response for delimiter in ".;!?"):
        if any(delimiter in response for delimiter in ".:!?"):
            response = response[1:]  # Remove the first character
            sentence, response = split_sentence(response)
            TTS_queue.put(sentence)


# Define the function to split sentences with the condition
def split_sentence(response):
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
    """Routing logic to let LLM decide if tools are needed"""
    routing_prompt = f"""
    Given the following user query, determine if any tools are needed to answer it.
    If a a voice command intended to control some aspect of computer comes then, respond with 'Function'.
    If no tools are needed, respond with 'NO TOOL'.

    User query: {query}

    Response:
    """

    response = client.chat.completions.create(
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


def run_general(query):
    """Use the general model to answer the query since no tool is needed"""
    response = ""
    try:
        stream = client.chat.completions.create(
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

        #        if any(delimiter in response for delimiter in ".;!?"):
        if any(delimiter in response for delimiter in ".:!?"):
            response = response[1:]  # Remove the first character
            sentence, response = split_sentence(response)
            TTS_queue.put(sentence)


# Define the function to split sentences with the condition
def split_sentence(response):
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


"""
########  #######   #######  ##        ######  
   ##    ##     ## ##     ## ##       ##    ## 
   ##    ##     ## ##     ## ##       ##       
   ##    ##     ## ##     ## ##        ######  
   ##    ##     ## ##     ## ##             ## 
   ##    ##     ## ##     ## ##       ##    ## 
   ##     #######   #######  ########  ######  
"""

extra_tools = [
    {
        "type": "function",
        "function": {
            "name": "minimize_all_windows",
            "description": "Minimize all windows",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_windows",
            "description": "Open the Windows start menu",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_desktop",
            "description": "Minimize all open windows to show the desktop",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_settings",
            "description": "Open Windows settings",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_screen",
            "description": "Lock the computer screen",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_file_explorer",
            "description": "Open the file explorer",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_run_dialog",
            "description": "Open the Run dialog box",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_task_manager",
            "description": "Open the Task Manager",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restore_windows",
            "description": "Restore minimized windows",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_control_panel",
            "description": "Open the Control Panel",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_calculator",
            "description": "Open the Calculator application",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_notepad",
            "description": "Open Notepad",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_word",
            "description": "Open Microsoft Word",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_excel",
            "description": "Open Microsoft Excel",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_powerpoint",
            "description": "Open Microsoft PowerPoint",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_outlook",
            "description": "Open Microsoft Outlook",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_paint",
            "description": "Open Microsoft Paint",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_command_prompt",
            "description": "Open Command Prompt",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_powershell",
            "description": "Open PowerShell",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_edge",
            "description": "Open Microsoft Edge",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_chrome",
            "description": "Open Google Chrome",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_firefox",
            "description": "Open Mozilla Firefox",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_sound_control_panel",
            "description": "Open the Sound control panel",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_up",
            "description": "Increase the system volume by a specified number of steps",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "integer",
                        "description": "The number of steps to increase the volume by (each step is 5%)",
                        "default": 1,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_down",
            "description": "Decrease the system volume by a specified number of steps",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "integer",
                        "description": "The number of steps to decrease the volume by (each step is 5%)",
                        "default": 1,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the system volume to a specific level",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "number",
                        "description": "The volume level to set (between 0.0 and 1.0)",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    }
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mute_volume",
            "description": "Mute the system volume",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play media; optionally specify a song",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_media",
            "description": "Stop media playback",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "next_track",
            "description": "Skip to the next track or play next song",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "previous_track",
            "description": "play previous song or play previous music track",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_song",
            "description": "Pause media playback or pause spotify",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_media",
            "description": "Restart media playback",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_browser",
            "description": "Open a specified browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "browser": {
                        "type": "string",
                        "description": "The name of the browser to open (e.g., 'Chrome', 'Firefox')",
                    }
                },
                "required": ["browser"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a specified website",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the website to open",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_google",
            "description": "Search Google with a specified query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for Google",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_device_manager",
            "description": "Open the Device Manager",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_disk_management",
            "description": "Open Disk Management or hard disk settings",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_network_connections",
            "description": "Open Network Connections",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_system_properties",
            "description": "Open System Properties",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_date_and_time",
            "description": "Open Date and Time settings",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ping_google",
            "description": "Ping Google to check internet connectivity",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flush_dns",
            "description": "Flush the DNS resolver cache",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_voicemeeter",
            "description": "Restart Voicemeeter",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_display_fusion_profile",
            "description": "Load a DisplayFusion monitor load profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_name": {
                        "type": "string",
                        "description": "The name of the DisplayFusion profile to load",
                    }
                },
                "required": ["profile_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_negative_screen",
            "description": "Open the Negative Screen application",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "invert_screen",
            "description": "Open the Negative Screen application",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "last_backup",
            "description": "Determine how many days ago the latest backup was created.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_vscode",
            "description": "Open Visual Studio Code on the user's machine.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def execute_command_run_with_tool(query):
    route = route_query(query)  # Step 1: Determine if a tool is needed

    # Step 2: Handle the result of routing
    if route == "NO TOOL":
        # Use the general model if no tools are needed
        response = run_general(query)
        asyncio.run(
            text_to_speech(text=response)
        )  # Asynchronously call text-to-speech with the response
    else:
        # Step 3: Handle tool usage
        tools_messages = [
            {
                "role": "system",
                "content": "you are a tool selection assistant. pick the best possible tool among tools for the given query",
            },
            {
                "role": "user",
                "content": query,
            },
        ]
        # Step 4: Get the response from the model that handles tool usage
        response = client.chat.completions.create(
            model=TOOL_USE_MODEL,
            messages=tools_messages,
            stream=False,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,
        )

        response_message = response.choices[0].message
        logging.info(f"Received response from Groq client: {response_message}")
        tool_calls = response_message.tool_calls

        # Step 3: Execute tool calls
        if tool_calls:
            for tool_call in tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                function_name = tool_call.function.name

                if function_name in globals():
                    try:
                        logging.info(
                            f"Executing function: {function_name} with arguments: {function_args}"
                        )
                        result = globals()[function_name](**function_args)
                        logging.info(f"Executed {function_name} with result: {result}")
                    except Exception as e:
                        logging.error(
                            f"Error executing function {function_name}: {str(e)}",
                            exc_info=True,
                        )
                        return False
                else:
                    logging.error(f"Function {function_name} not found")
                    return False

        return True

    except Exception as e:
        logging.error(f"Groq API error occurred: {str(e)}", exc_info=True)
        # Reinitialize the Groq client in case of an error
        logging.info("Reinitializing Groq client.")

        Groq_client = initialize_groq_client()
        return False


def visual_feedback(function_name, result):
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
    # Convert to lowercase
    transcript = transcript.lower()

    # Remove punctuation
    transcript = transcript.translate(str.maketrans("", "", string.punctuation))

    # Normalize whitespace (remove extra spaces)
    transcript = re.sub(r"\s+", " ", transcript).strip()

    return transcript


def execute_command_fuzzy(transcript):
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
            best_match, match_score = process.extractOne(cmd, PHRASE_TO_ACTION.keys())
            if (
                match_score >= 60 and "computer" in transcript
            ):  # Adjust the threshold as needed
                action = PHRASE_TO_ACTION.get(best_match)

        if action:
            action()  # Execute the corresponding action
            print(f"Executing command: {cmd}")
        else:
            print(f"No matching command found for: {cmd}")

    return True
