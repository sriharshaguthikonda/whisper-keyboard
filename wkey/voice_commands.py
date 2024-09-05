# voice_commands.py
import os
import pyautogui
import re
import string
from fuzzywuzzy import process

COMMAND_MAPPINGS = {
    # System Commands
    "search windows": [
        "Hey Jarvis open start menu",
        "Hey Jarvis show start menu",
        "Hey Jarvis Windows search",
    ],
    "show desktop": ["Hey Jarvis show desktop", "Hey Jarvis minimize everything"],
    "open settings": ["Hey Jarvis open settings", "Hey Jarvis settings"],
    "lock screen": ["Hey Jarvis lock screen", "Hey Jarvis lock the computer"],
    "take screenshot": ["Hey Jarvis take screenshot", "Hey Jarvis capture screen"],
    "open file explorer": ["Hey Jarvis open file explorer", "Hey Jarvis explore files"],
    "windows search": ["Hey Jarvis open search", "Hey Jarvis search"],
    "open run dialog": ["Hey Jarvis open run dialog", "Hey Jarvis run command"],
    "open task manager": ["Hey Jarvis open task manager", "Hey Jarvis task manager"],
    "minimize all windows": [
        "Hey Jarvis minimize all windows",
        "Hey Jarvis minimize windows",
    ],
    "restore windows": ["Hey Jarvis restore windows", "Hey Jarvis restore all windows"],
    #    "shutdown system": ["Hey Jarvis shutdown system", "Hey Jarvis turn off computer"],
    #    "restart system": ["Hey Jarvis restart system", "Hey Jarvis reboot computer"],
    #    "log off": ["Hey Jarvis log off", "Hey Jarvis sign out"],
    # Application Commands
    "open control panel": ["Hey Jarvis open control panel", "Hey Jarvis control panel"],
    "open calculator": ["Hey Jarvis open calculator", "Hey Jarvis calculator"],
    "open notepad": ["Hey Jarvis open notepad", "Hey Jarvis notepad"],
    "open word": ["Hey Jarvis open word", "Hey Jarvis start word"],
    "open excel": ["Hey Jarvis open excel", "Hey Jarvis start excel"],
    "open powerpoint": ["Hey Jarvis open powerpoint", "Hey Jarvis start powerpoint"],
    "open outlook": ["Hey Jarvis open outlook", "Hey Jarvis start outlook"],
    "open paint": ["Hey Jarvis open paint", "Hey Jarvis start paint"],
    "open command prompt": [
        "Hey Jarvis open command prompt",
        "Hey Jarvis open console",
        "Hey Jarvis command prompt",
        "Hey Jarvis Open command drop",
    ],
    "open powershell": ["Hey Jarvis open powershell", "Hey Jarvis powershell"],
    "open edge": ["Hey Jarvis open edge", "Hey Jarvis start edge"],
    "open chrome": ["Hey Jarvis open chrome", "Hey Jarvis start chrome"],
    "open firefox": ["Hey Jarvis open firefox", "Hey Jarvis start firefox"],
    # Volume Controls
    "volume up": ["Hey Jarvis volume up", "Hey Jarvis increase volume"],
    "volume down": ["Hey Jarvis volume down", "Hey Jarvis decrease volume"],
    # "mute volume": ["Hey Jarvis mute volume", "Hey Jarvis mute sound"],
    # Media Controls
    "play media": ["Hey Jarvis play media", "Hey Jarvis play", "Hey Jarvis play music"],
    "stop media": ["Hey Jarvis stop media", "Hey Jarvis stop", "Hey Jarvis stop music"],
    "next track": [
        "Hey Jarvis next track",
        "Hey Jarvis next song",
        "Hey Jarvis skip",
        "Hey Jarvis play next song",
    ],
    "previous track": [
        "Hey Jarvis previous track",
        "Hey Jarvis previous song",
        "Hey Jarvis replay",
        "Hey Jarvis play previous song",
    ],
    # Custom or Complex Operations
    "open device manager": [
        "Hey Jarvis open device manager",
        "Hey Jarvis device manager",
    ],
    "open disk management": [
        "Hey Jarvis open disk management",
        "Hey Jarvis disk management",
        "Hey Jarvis format disk",
        "Hey Jarvis hard disk",
    ],
    "open network connections": [
        "Hey Jarvis open network connections",
        "Hey Jarvis network connections",
    ],
    "open system properties": [
        "Hey Jarvis open system properties",
        "Hey Jarvis system properties",
    ],
    "open date and time": ["Hey Jarvis open date and time", "Hey Jarvis date and time"],
    # System Commands
    "ping google": ["Hey Jarvis ping google", "Hey Jarvis check internet connection"],
    "flush dns": ["Hey Jarvis flush dns", "Hey Jarvis reset dns cache"],
    # Add more as needed Play, pause, media.
}


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
    "volume up": lambda: pyautogui.press("volumeup"),
    "volume down": lambda: pyautogui.press("volumedown"),
    "mute volume": lambda: pyautogui.press("volumemute"),
    # Media Controls
    "play media": lambda: pyautogui.press("playpause"),
    "stop media": lambda: pyautogui.press("stop"),
    "next track": lambda: pyautogui.press("nexttrack"),
    "previous track": lambda: pyautogui.press("prevtrack"),
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
        if match_score >= 80:  # Adjust the threshold as needed
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
