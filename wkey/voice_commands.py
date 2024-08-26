# voice_commands.py
import os
import pyautogui
import re
from fuzzywuzzy import process


COMMAND_MAPPINGS = {
    # System Commands
    "search windows": ["open start menu", "show start menu", "Windows search"],
    "show desktop": ["show desktop", "minimize everything"],
    "open settings": ["open settings", "settings"],
    "lock screen": ["lock screen", "lock the computer"],
    "take screenshot": ["take screenshot", "capture screen"],
    "open file explorer": ["open file explorer", "explore files"],
    "windows search": ["open search", "search"],
    "open run dialog": ["open run dialog", "run command"],
    "open task manager": ["open task manager", "task manager"],
    "minimize all windows": ["minimize all windows", "minimize windows"],
    "restore windows": ["restore windows", "restore all windows"],
#    "shutdown system": ["shutdown system", "turn off computer"],
#    "restart system": ["restart system", "reboot computer"],
#    "log off": ["log off", "sign out"],

    # Application Commands
    "open control panel": ["open control panel", "control panel"],
    "open calculator": ["open calculator", "calculator"],
    "open notepad": ["open notepad", "notepad"],
    "open word": ["open word", "start word"],
    "open excel": ["open excel", "start excel"],
    "open powerpoint": ["open powerpoint", "start powerpoint"],
    "open outlook": ["open outlook", "start outlook"],
    "open paint": ["open paint", "start paint"],
    "open command prompt": ["open command prompt","open console", "command prompt"," Open command drop"],
    "open powershell": ["open powershell", "powershell"],
    "open edge": ["open edge", "start edge"],
    "open chrome": ["open chrome", "start chrome"],
    "open firefox": ["open firefox", "start firefox"],

    # Volume Controls
    "volume up": ["volume up", "increase volume"],
    "volume down": ["volume down", "decrease volume"],
    "mute volume": ["mute volume", "mute sound"],

    # Media Controls
    "play pause media": ["play pause media", "toggle media play pause","Play, pause, media.", "pause everything"],
    "next track": ["next track", "next song"],
    "previous track": ["previous track", "previous song"],

    # Custom or Complex Operations
    "open device manager": ["open device manager", "device manager"],
    "open disk management": ["open disk management", "disk management", "format disk", "hard disk"],
    "open network connections": ["open network connections", "network connections"],
    "open system properties": ["open system properties", "system properties"],
    "open date and time": ["open date and time", "date and time"],


    # System Commands
    "ping google": ["ping google", "check internet connection"],
    "flush dns": ["flush dns", "reset dns cache"],

    # Add more as needed Play, pause, media.
}


# Define actions for commands
ACTIONS = {
    # System Commands
    "search windows": lambda: pyautogui.press('win'),
    "show desktop": lambda: pyautogui.hotkey('win', 'd'),
    "open settings": lambda: pyautogui.hotkey('win', 'i'),
    "lock screen": lambda: pyautogui.hotkey('win', 'l'),
    "take screenshot": lambda: pyautogui.hotkey('win', 'prtsc'),
    "open file explorer": lambda: pyautogui.hotkey('win', 'e'),
    "windows search": lambda: pyautogui.hotkey('win', 's'),
    "open run dialog": lambda: pyautogui.hotkey('win', 'r'),
    "open task manager": lambda: pyautogui.hotkey('ctrl', 'shift', 'esc'),
    "minimize all windows": lambda: pyautogui.hotkey('win', 'm'),
    "restore windows": lambda: pyautogui.hotkey('win', 'shift', 'm'),
#    "shutdown system": lambda: os.system('shutdown /s /t 0'),
#    "restart system": lambda: os.system('shutdown /r /t 0'),
    #"log off": lambda: os.system('shutdown /l'),

    # Application Commands
    "open control panel": lambda: os.system('control'),
    "open calculator": lambda: os.system('calc'),
    "open notepad": lambda: os.system('notepad'),
    "open word": lambda: os.system('start winword'),
    "open excel": lambda: os.system('start excel'),
    "open powerpoint": lambda: os.system('start powerpnt'),
    "open outlook": lambda: os.system('start outlook'),
    "open paint": lambda: os.system('start mspaint'),
    "open command prompt": lambda: os.system('start cmd'),
    "open powershell": lambda: os.system('start powershell'),
    "open edge": lambda: os.system('start msedge'),
    "open chrome": lambda: os.system('start chrome'),
    "open firefox": lambda: os.system('start firefox'),

    # Volume Controls
    "volume up": lambda: pyautogui.press('volumeup'),
    "volume down": lambda: pyautogui.press('volumedown'),
    "mute volume": lambda: pyautogui.press('volumemute'),

    # Media Controls
    "play pause media": lambda: pyautogui.press('playpause'),
    "next track": lambda: pyautogui.press('nexttrack'),
    "previous track": lambda: pyautogui.press('prevtrack'),

    # Custom or Complex Operations
    "open device manager": lambda: os.system('devmgmt.msc'),
    "open disk management": lambda: os.system('diskmgmt.msc'),
    "open network connections": lambda: os.system('ncpa.cpl'),
    "open system properties": lambda: os.system('sysdm.cpl'),
    "open date and time": lambda: os.system('timedate.cpl'),

    # System Commands
    "ping google": lambda: os.system('ping -c 4 google.com'),
    "flush dns": lambda: os.system('ipconfig /flushdns'),
    # Add more as needed
}


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