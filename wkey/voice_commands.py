# voice_commands.py
import os
import pyautogui
import re
import string
from fuzzywuzzy import process
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import time


# Path to your Edge WebDriver
webdriver_path = r"C:\Users\deletable\Downloads\edgedriver_win64\msedgedriver.exe"

# Set up Edge options
options = Options()
options.add_argument(
    r"user-data-dir=C:\\Users\\YourUsername\\AppData\\Local\\Microsoft\\Edge\\User Data"
)  # Adjust this to your user data directory
options.add_argument(r"profile-directory=Profile 1")  # Adjust this to your profile name
options.add_argument("--headless")
# options.add_argument("--disable-gpu")  # Optional: Disable GPU acceleration

# Initialize the WebDriver
service = Service(webdriver_path)

driver = None
driver_pid = None


def start_driver():
    global driver
    global driver_pid

    try:
        driver = webdriver.Edge(service=service, options=options)
        time.sleep(6)
        driver.get("https://open.spotify.com/collection/tracks")
        driver.execute_script("window.focus();")
        time.sleep(5)  # Wait for the page to load
        driver_pid = driver.service.process.pid
    except Exception as e:
        print(f"Error terminating WebDriver process: {e}")


# Start the WebDriver in a separate thread
# Allow time to log in (if not using a persistent session)
# time.sleep(60)  # Uncomment if you need time to log in manually


# Control playback
def play_song():
    try:
        play_button = driver.find_element("xpath", "//button[@aria-label='Play']")
        ActionChains(driver).move_to_element(play_button).click(play_button).perform()
        print("Playback started.")
    except Exception as e:
        print(f"Error while trying to play: {e}")


def pause_song():
    try:
        pause_button = driver.find_element("xpath", "//button[@aria-label='Pause']")
        pause_button.click()
        print("Playback paused.")
    except Exception as e:
        print(f"Error while trying to pause: {e}")


def next_track():
    try:
        next_button = driver.find_element("xpath", "//button[@aria-label='Next']")
        next_button.click()
        print("Next track.")
    except Exception as e:
        print(f"Error while trying to skip to next track: {e}")


def previous_track():
    try:
        prev_button = driver.find_element("xpath", "//button[@aria-label='Previous']")
        prev_button.click()
        print("Previous track.")
    except Exception as e:
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
        "Hey computer open start menu",
        "Hey computer show start menu",
        "Hey computer Windows search",
    ],
    "show desktop": ["Hey computer show desktop", "Hey computer minimize everything"],
    "open settings": ["Hey computer open settings", "Hey computer settings"],
    "lock screen": ["Hey computer lock screen", "Hey computer lock the computer"],
    "take screenshot": ["Hey computer take screenshot", "Hey computer capture screen"],
    "open file explorer": [
        "Hey computer open file explorer",
        "Hey computer explore files",
    ],
    "windows search": ["Hey computer open search", "Hey computer search"],
    "open run dialog": ["Hey computer open run dialog", "Hey computer run command"],
    "open task manager": [
        "Hey computer open task manager",
        "Hey computer task manager",
    ],
    "minimize all windows": [
        "Hey computer minimize all windows",
        "Hey computer minimize windows",
    ],
    "restore windows": [
        "Hey computer restore windows",
        "Hey computer restore all windows",
    ],
    #    "shutdown system": ["Hey computer shutdown system", "Hey computer turn off computer"],
    #    "restart system": ["Hey computer restart system", "Hey computer reboot computer"],
    #    "log off": ["Hey computer log off", "Hey computer sign out"],
    # Application Commands
    "open control panel": [
        "Hey computer open control panel",
        "Hey computer control panel",
    ],
    "open calculator": ["Hey computer open calculator", "Hey computer calculator"],
    "open notepad": ["Hey computer open notepad", "Hey computer notepad"],
    "open word": ["Hey computer open word", "Hey computer start word"],
    "open excel": ["Hey computer open excel", "Hey computer start excel"],
    "open powerpoint": [
        "Hey computer open powerpoint",
        "Hey computer start powerpoint",
    ],
    "open outlook": ["Hey computer open outlook", "Hey computer start outlook"],
    "open paint": ["Hey computer open paint", "Hey computer start paint"],
    "open command prompt": [
        "Hey computer open command prompt",
        "Hey computer open console",
        "Hey computer command prompt",
        "Hey computer Open command drop",
    ],
    "open powershell": ["Hey computer open powershell", "Hey computer powershell"],
    "open edge": ["Hey computer open edge", "Hey computer start edge"],
    "open chrome": ["Hey computer open chrome", "Hey computer start chrome"],
    "open firefox": ["Hey computer open firefox", "Hey computer start firefox"],
    # Volume Controls
    "open sound control panel": [
        "Hey computer open sound control panel",
        "Hey computer open audio settings",
    ],
    "volume up": ["Hey computer volume up", "Hey computer increase volume"],
    "volume down": ["Hey computer volume down", "Hey computer decrease volume"],
    # "mute volume": ["Hey computer mute volume", "Hey computer mute sound"],
    # Media Controls
    "play media": [
        "Hey computer play media",
        "Hey computer play",
        "Hey computer play music",
    ],
    "stop media": [
        "Hey computer stop media",
        "Hey computer stop",
        "Hey computer stop music",
    ],
    "next track": [
        "Hey computer next track",
        "Hey computer next song",
        "Hey computer skip",
        "Hey computer play next song",
    ],
    "previous track": [
        "Hey computer previous track",
        "Hey computer previous song",
        "Hey computer replay",
        "Hey computer play previous song",
    ],
    # Custom or Complex Operations
    "open device manager": [
        "Hey computer open device manager",
        "Hey computer device manager",
    ],
    "open disk management": [
        "Hey computer open disk management",
        "Hey computer disk management",
        "Hey computer format disk",
        "Hey computer hard disk",
    ],
    "open network connections": [
        "Hey computer open network connections",
        "Hey computer network connections",
    ],
    "open system properties": [
        "Hey computer open system properties",
        "Hey computer system properties",
    ],
    "open date and time": [
        "Hey computer open date and time",
        "Hey computer date and time",
    ],
    # System Commands
    "ping google": [
        "Hey computer ping google",
        "Hey computer check internet connection",
    ],
    "flush dns": ["Hey computer flush dns", "Hey computer reset dns cache"],
    # Add more as needed Play, pause, media.
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
    # Add more as needed
}


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


def execute_command(transcript):
    # Normalize the transcript
    command = normalize_transcript(transcript)

    # Attempt to find a direct match
    action = PHRASE_TO_ACTION.get(command)

    # If no direct match is found, use fuzzy matching
    if not action:
        # Find the best fuzzy match (with a threshold of 80 for confidence)
        best_match, match_score = process.extractOne(command, PHRASE_TO_ACTION.keys())
        if (
            match_score >= 80 and "computer" in transcript
        ):  # Adjust the threshold as needed
            action = PHRASE_TO_ACTION.get(best_match)

    if action:
        action()  # Execute the corresponding action
        print(f"command for: {action}")
        return True
    else:
        print(f"No matching command found for: {transcript}")
        return transcript


"""
# Invert COMMAND_MAPPINGS to map each phrase to its action
PHRASE_TO_ACTION = {}
for action_key, phrases in COMMAND_MAPPINGS.items():
    for phrase in phrases:
        PHRASE_TO_ACTION[phrase] = ACTIONS[action_key]


def execute_command(transcript):
    # Trim leading and trailing spaces
    trimmed_transcript = transcript.strip().lower()
    
    # Convert the transcript to lowercase for command matching
    command = re.sub(r'[^a-zA-Z0-9\s]', '', trimmed_transcript)

    action = PHRASE_TO_ACTION.get(command)
    if action:
        action()  # Execute the corresponding action
        return True
    else:
        return transcript

"""
