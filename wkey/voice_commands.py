# voice_commands.py
import os
import pyautogui
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


from groq import Groq
from dotenv import load_dotenv
import json

import io
import edge_tts
import asyncio
import threading
from pydub import AudioSegment
from pydub.playback import play
import queue


load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Define models
ROUTING_MODEL = "llama3-70b-8192"
# ROUTING_MODEL = "llama-3.2-1b-preview"
TOOL_USE_MODEL = "llama3-groq-8b-8192-tool-use-preview"
GENERAL_MODEL = "llama3-70b-8192"


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

# Optional: Add headless and disable GPU for background processing
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
        driver = webdriver.Edge(service=service, options=options)
        time.sleep(6)
        driver.get("https://open.spotify.com/collection/tracks")
        # driver.execute_script("window.focus();")
        time.sleep(5)  # Wait for the page to load
        driver_pid = driver.service.process.pid
        session_id = driver.session_id
        executor_url = driver.command_executor._url
    except Exception as e:
        print(f"Error terminating WebDriver process: {e}")


"""
https://chatgpt.com/c/66e49b09-cca4-8013-a443-6793c6073c2f
"""


def reconnect_driver():
    global driver, session_id, executor_url, options

    try:
        if session_id and executor_url:
            driver = webdriver.Remote(command_executor=executor_url, options=options)
            driver.session_id = session_id
            print("Reconnected to the existing session.")
    except (SessionNotCreatedException, WebDriverException) as e:
        print(f"Failed to reconnect to the session: {str(e)}")

        # Attempt to start a new session
        try:
            # options = webdriver.EdgeOptions()
            # options.binary_location = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"  # Correct Edge binary path

            driver = webdriver.Edge(
                options=options,
                service_log_path="C:/Users/deletable/Downloads/edgedriver_win64/msedgedriver.log",
            )
            time.sleep(3)
            driver.get("https://open.spotify.com/collection/tracks")
            time.sleep(3)
            print("Started a new session.")
        except Exception as new_session_error:
            print(f"Failed to start a new session: {new_session_error}")


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
        devices_button = driver.find_element(
            By.XPATH, "//button[@aria-label='Connect to a device']"
        )
        # Click the button
        devices_button.click()
        print("Playback started.")
        # Locate the element containing "This web browser"
        # Wait for the panel to appear
        # wait = WebDriverWait(driver, 10)
        time.sleep(2)
        try:
            driver.find_element(By.XPATH, '//*[@id="device-picker"]').click()
        except Exception as e:
            print(f"Error while trying to play after reconnection: {e}")
        time.sleep(2)
        driver.find_element(By.XPATH, '//*[text()="This web browser"]').click()
        # Click the panel
    except Exception as e:
        print(f"Error while trying to play after reconnection: {e}")


# Control playback
def play_song():
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
    "play media": play_song,
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


def volume_up():
    pyautogui.press("volumeup")


def volume_down():
    pyautogui.press("volumedown")


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
    os.system("ping www.google.com")


def flush_dns():
    os.system("ipconfig /flushdns")


# Voicemeeter commands
def restart_voicemeeter():
    subprocess.run(
        ["C:\\Program Files (x86)\\VB\\Voicemeeter\\voicemeeter8x64.exe", "-r"]
    )


# DisplayFusion commands
def load_display_fusion_profile(profile_name):
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
    response = client.chat.completions.create(
        model=GENERAL_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query},
        ],
    )
    return response.choices[0].message.content


"""
######## ########  ######  
   ##       ##    ##    ## 
   ##       ##    ##       
   ##       ##     ######  
   ##       ##          ## 
   ##       ##    ##    ## 
   ##       ##     ######  
"""


# Function to process the queue
def process_TTS_queue(TTS_queue):
    while True:
        sentence = TTS_queue.get()
        if sentence is None:  # Sentinel value to stop the worker
            break
        asyncio.run(text_to_speech(sentence, speed=1.2))
        TTS_queue.task_done()


# Function to process the queue
def process_TTS_Audio_play_queue(TTS_Audio_play_queue):
    while True:
        audio_fp = TTS_Audio_play_queue.get()
        audio_fp.seek(0)

        sound = AudioSegment.from_file(audio_fp, format="mp3")

        # Play the adjusted audio
        play(sound)
        TTS_Audio_play_queue.task_done()


# Queue for sentences
TTS_Audio_play_queue = queue.Queue()

# Start the worker thread
threading.Thread(
    target=process_TTS_Audio_play_queue, args=(TTS_Audio_play_queue,), daemon=True
).start()


# Function to convert text to speech using edge-tts and play using pydub with speed adjustment
async def text_to_speech(text, speed=1.2, volume=1, voice="en-GB-MiaNeural"):
    try:
        rate = "+" + str(int((speed - 1) * 100)) + "%"
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_bytes = b""

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if not audio_bytes:
            raise ValueError(
                "No audio was received. Please verify that your parameters are correct."
            )

        audio_fp = io.BytesIO(audio_bytes)
        audio_fp.seek(0)

        TTS_Audio_play_queue.put(audio_fp)

    except Exception as e:
        print(f"Error occurred during playback: {e}")


"""
########  #######   #######  ##        ######  
   ##    ##     ## ##     ## ##       ##    ## 
   ##    ##     ## ##     ## ##       ##       
   ##    ##     ## ##     ## ##        ######  
   ##    ##     ## ##     ## ##             ## 
   ##    ##     ## ##     ## ##       ##    ## 
   ##     #######   #######  ########  ######  
"""

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
            "name": "windows_search",
            "description": "Open the Windows search bar",
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
            "name": "minimize_all_windows",
            "description": "Minimize all windows",
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
            "description": "Increase the system volume",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_down",
            "description": "Decrease the system volume",
            "parameters": {"type": "object", "properties": {}, "required": []},
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
            "name": "play_song",
            "description": "Play media; optionally specify a song",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {
                        "type": "string",
                        "description": "The name of the song or media file to play",
                    }
                },
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
            "description": "Go to the previous track",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_song",
            "description": "Pause media playback",
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
            tools=tools,
            tool_choice="auto",  # Automatically decide which tool to use
            max_tokens=4096,
        )
        response_message = response.choices[0].message
        print(response_message)
        tool_calls = response_message.tool_calls

        # Step 5: Call the functions dynamically based on the model's tool calls
        if tool_calls:
            for tool_call in tool_calls:
                # Extract arguments and function name
                function_args = json.loads(tool_call.function.arguments)
                function_name = tool_call.function.name

                # Dynamically call the function using globals()
                if function_name in globals():
                    try:
                        # Call the function with the arguments
                        result = globals()[function_name](**function_args)
                        print(f"Executed {function_name} with result: {result}")
                    except Exception as e:
                        print(f"Error executing function {function_name}: {e}")
                else:
                    print(f"Function {function_name} not found in globals.")
        else:
            print("No tool calls were made by the model.")

    return True  # Function executed successfully


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
