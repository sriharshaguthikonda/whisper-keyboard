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


# Path to your Edge WebDriver
webdriver_path = r"C:\Users\deletable\Downloads\edgedriver_win64\msedgedriver.exe"

# Set up Edge options
options = Options()
options.add_argument(
    r"user-data-dir=C:\\Users\\YourUsername\\AppData\\Local\\Microsoft\\Edge\\User Data"
)  # Adjust this to your user data directory
options.add_argument(r"profile-directory=Profile 1")
# Adjust this to your profile name
# options.add_argument("--headless")
# options.add_argument("--disable-gpu")  # Optional: Disable GPU acceleration

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
            options = webdriver.EdgeOptions()
            options.binary_location = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"  # Correct Edge binary path

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
        driver.find_element(By.XPATH, '//*[@id="device-picker"]').click()
        time.sleep(2)
        driver.find_element(By.XPATH, '//*[text()="DESKTOP-6RQKD76"]').click()
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
        "restart voicemeter",
        " hey computer reset voicemeter",
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
                match_score >= 70 and "computer" in transcript
            ):  # Adjust the threshold as needed
                action = PHRASE_TO_ACTION.get(best_match)

        if action:
            action()  # Execute the corresponding action
            print(f"Executing command: {cmd}")
        else:
            print(f"No matching command found for: {cmd}")

    return True


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
