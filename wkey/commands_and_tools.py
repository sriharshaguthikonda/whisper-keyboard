import pyautogui
import subprocess
import os
import logging
import re
import asyncio
from fuzzywuzzy import process
import threading
import time
from selenium.webdriver.common.by import By

# Global variable to hold driver reference
_driver_ref = None

def set_driver_reference(driver):
    """Set the global driver reference"""
    global _driver_ref
    _driver_ref = driver

def get_driver():
    """Get the driver reference, importing if necessary"""
    global _driver_ref
    if _driver_ref is None:
        try:
            # Late import to avoid circular dependency
            import voice_commands
            _driver_ref = voice_commands.driver
        except (ImportError, AttributeError):
            _driver_ref = None
    return _driver_ref

def _set_alarm_wrapper(minutes, message):
    """Wrapper function for set_alarm to avoid circular import"""
    try:
        import voice_commands
        return voice_commands.set_alarm(minutes, message)
    except (ImportError, AttributeError):
        print("set_alarm function not available")
        return False

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


"""TODO: donot touch these functions"""

"""TODO: they exist in the voice_commands.py file and if you have to change change them there"""

"""TODO: donot touch these functions"""


# Control playback
def play_music():
    try:
        driver = get_driver()
        if driver is None:
            print("Driver not available - cannot play music")
            return False
            
        play_button = driver.find_element(By.XPATH, "//button[@aria-label='Play']")
        play_button.click()
        
        # Late import to avoid circular dependency
        try:
            import voice_commands
            voice_commands.change_device()
        except (ImportError, AttributeError):
            print("change_device function not available")
            
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            try:
                import voice_commands
                voice_commands.reconnect_driver()
                driver = get_driver()
                if driver is not None:
                    play_button = driver.find_element(
                        By.XPATH, "//button[@aria-label='Play']"
                    )
                    play_button.click()
                    print("Playback started after reconnection.")
                    return True
            except Exception as e:
                print(f"Error while trying to play after reconnection: {e}")

        elif "target window already closed" in error_message:
            driver = get_driver()
            if driver is not None:
                driver.quit()
            try:
                import voice_commands
                voice_commands.start_driver()
                driver = get_driver()
                if driver is not None:
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
    try:
        driver = get_driver()
        if driver is None:
            print("Driver not available - cannot pause song")
            return False
            
        pause_button = driver.find_element("xpath", "//button[@aria-label='Pause']")
        pause_button.click()
        print("Playback paused.")
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            try:
                import voice_commands
                voice_commands.reconnect_driver()
                driver = get_driver()
                if driver is not None:
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
    try:
        driver = get_driver()
        if driver is None:
            print("Driver not available - cannot skip track")
            return False
            
        next_button = driver.find_element("xpath", "//button[@aria-label='Next']")
        next_button.click()
        print("Next track.")
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            try:
                import voice_commands
                voice_commands.reconnect_driver()
                driver = get_driver()
                if driver is not None:
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
    try:
        driver = get_driver()
        if driver is None:
            print("Driver not available - cannot go to previous track")
            return False
            
        prev_button = driver.find_element("xpath", "//button[@aria-label='Previous']")
        prev_button.click()
        print("Previous track.")
        return True
    except Exception as e:
        error_message = str(e)
        if "disconnected: not connected to DevTools" in error_message:
            print("Attempting to reconnect due to DevTools disconnection...")
            try:
                import voice_commands
                voice_commands.reconnect_driver()
                driver = get_driver()
                if driver is not None:
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


def execute_system_command(command):
    try:
        os.system(command)
    except Exception as e:
        logging.error(f"Error executing {command}: {e}", exc_info=True)

LAUNCH_COMMANDS = {
    "cmd": "start cmd",
    "command prompt": "start cmd",
    "powershell": "start powershell",
    "edge": "start msedge",
    "chrome": "start chrome",
    "firefox": "start firefox",
    "calculator": "calc",
    "notepad": "notepad",
    "control panel": "control",
    "word": "start winword",
    "excel": "start excel",
    "powerpoint": "start powerpnt",
    "outlook": "start outlook",
    "paint": "start mspaint",
    "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc",
    "network connections": "ncpa.cpl",
    "system properties": "sysdm.cpl",
    "date and time": "timedate.cpl",
    "display fusion": '"C:\\Program Files (x86)\\DisplayFusion\\DisplayFusion.exe"',
    "displayfusion": '"C:\\Program Files (x86)\\DisplayFusion\\DisplayFusion.exe"',
    "task scheduler": "taskschd.msc",
    "startup folder": "shell:startup",
    "services": "services.msc",
    "sound control panel": "mmsys.cpl",
    "spotify": "spotify",
}

def _launch_spotify():
    candidates = [
        os.path.expandvars(r"%APPDATA%\\Spotify\\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\\Spotify\\Spotify.exe"),
        r"C:\\Program Files\\Spotify\\Spotify.exe",
        r"C:\\Program Files (x86)\\Spotify\\Spotify.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            os.startfile(path)
            return True

    execute_system_command("start spotify:")
    return False


def launch_application(app: str):
    try:
        normalized = app.strip().lower()
        if normalized == "spotify":
            _launch_spotify()
            return
        if normalized not in LAUNCH_COMMANDS:
            # fallback to closest known app if confidence is good
            match, score = process.extractOne(normalized, list(LAUNCH_COMMANDS.keys()))
            if score < 80:
                raise ValueError(f"Unsupported application: {app}")
            normalized = match
        execute_system_command(LAUNCH_COMMANDS[normalized])
    except Exception as e:
        logging.error(f"Error executing launch_application for {app}: {e}", exc_info=True)


def execute_pyautogui_hotkey(*keys):
    try:
        pyautogui.hotkey(*keys)
    except Exception as e:
        logging.error(f"Error executing hotkey {keys}: {e}", exc_info=True)


def execute_pyautogui_press(key):
    try:
        pyautogui.press(key)
    except Exception as e:
        logging.error(f"Error executing press {key}: {e}", exc_info=True)


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
        "restart vb matrix",
        "restart vb audio matrix",
    ],
    "start display fusion": [
        "start display fusion",
        "launch display fusion",
        "open display fusion",
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
    "open_task_scheduler": [
        "open task scheduler",
        "show task scheduler",
        "launch task scheduler",
        "start task scheduler",
    ],
    "open_startup_folder": [
        "open startup folder",
        "show startup folder",
        "open startup directory",
        "show startup programs",
    ],
    "manage_services": [
        "manage services",
        "open services",
        "show services",
        "windows services",
        "service manager",
    ],
    "start_whisper": [
        "start whisper",
        "launch whisper",
        "run whisper",
        "open whisper keyboard",
    ],
    "start_grok": [
        "start grok",
        "open grok",
        "launch grok",
        "run grok",
    ],
    "set alarm": ["set alarm", "alarm in"],

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
    "search windows": lambda: execute_pyautogui_press("win"),
    "show desktop": lambda: execute_pyautogui_hotkey("win", "d"),
    "open settings": lambda: execute_pyautogui_hotkey("win", "i"),
    "lock screen": lambda: execute_pyautogui_hotkey("win", "l"),
    "take screenshot": lambda: execute_pyautogui_hotkey("win", "prtsc"),
    "open file explorer": lambda: execute_pyautogui_hotkey("win", "e"),
    "windows search": lambda: execute_pyautogui_hotkey("win", "s"),
    "open run dialog": lambda: execute_pyautogui_hotkey("win", "r"),
    "open task manager": lambda: execute_pyautogui_hotkey("ctrl", "shift", "esc"),
    "minimize all windows": lambda: execute_pyautogui_hotkey("win", "m"),
    "restore windows": lambda: execute_pyautogui_hotkey("win", "shift", "m"),
    #    "shutdown system": lambda: os.system('shutdown /s /t 0'),
    #    "restart system": lambda: os.system('shutdown /r /t 0'),
    # "log off": lambda: os.system('shutdown /l'),
    # Application Commands
    "open control panel": lambda: launch_application("control panel"),
    "open calculator": lambda: launch_application("calculator"),
    "open notepad": lambda: launch_application("notepad"),
    "open word": lambda: launch_application("word"),
    "open excel": lambda: launch_application("excel"),
    "open powerpoint": lambda: launch_application("powerpoint"),
    "open outlook": lambda: launch_application("outlook"),
    "open paint": lambda: launch_application("paint"),
    "open command prompt": lambda: launch_application("cmd"),
    "open powershell": lambda: launch_application("powershell"),
    "open edge": lambda: launch_application("edge"),
    "open chrome": lambda: launch_application("chrome"),
    "open firefox": lambda: launch_application("firefox"),
    # Volume Controls
    "open sound control panel": lambda: launch_application("sound control panel"),
    "volume up": lambda: execute_pyautogui_press("volumeup"),
    "volume down": lambda: execute_pyautogui_press("volumedown"),
    "mute volume": lambda: execute_pyautogui_press("volumemute"),
    # Media Controls
    "play media": play_music,
    "stop media": pause_song,
    "next track": next_track,
    "previous track": previous_track,
    # Custom or Complex Operations
    "open device manager": lambda: launch_application("device manager"),
    "open disk management": lambda: launch_application("disk management"),
    "open network connections": lambda: launch_application("network connections"),
    "open system properties": lambda: launch_application("system properties"),
    "open date and time": lambda: launch_application("date and time"),
    # System Commands
    "ping google": lambda: execute_system_command("ping www.google.com"),
    "flush dns": lambda: execute_system_command("ipconfig /flushdns"),
    # VB Matrix Commands
    "restart voicemeeter": lambda: subprocess.run(
        ["C:\\Program Files (x86)\\VB\\Voicemeeter\\VBAudioMatrix_x64.exe", "-r"]
    ),
    # DisplayFusion Commands
    "start display fusion": lambda: launch_application("display fusion"),
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
    "open_task_scheduler": lambda: launch_application("task scheduler"),
    "open_startup_folder": lambda: launch_application("startup folder"),
    "manage_services": lambda: launch_application("services"),
    "start_whisper": start_whisper,
    "start_grok": start_grok,
    "set alarm": lambda minutes, message: _set_alarm_wrapper(minutes, message),
}


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
            "name": "launch_application",
            "description": "Launch a supported desktop app (sound control panel, device manager, disk management, network connections, system properties, date and time, task scheduler, startup folder, services, cmd, powershell, edge, chrome, firefox, calculator, notepad, control panel, word, excel, powerpoint, outlook, paint).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "Name of the app to launch. Supported: sound control panel, device manager, disk management, network connections, system properties, date and time, task scheduler, startup folder, services, cmd, powershell, edge, chrome, firefox, calculator, notepad, control panel, word, excel, powerpoint, outlook, paint.",
                    }
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_everything",
            "description": "Search Windows files using Everything (focuses results)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search text to send to Everything. If omitted, opens Everything.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "paste_transcript",
            "description": "Paste provided text into the active window",
            "parameters": {
                "type": "object",
                "properties": {
                    "transcript": {
                        "type": "string",
                        "description": "Content that should be pasted",
                    },
                    "text": {
                        "type": "string",
                        "description": "Alias for transcript content (legacy tool calls)",
                    },
                },
                "required": [],
            },
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
            "description": "Restart VB Matrix (VB-Audio Matrix)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_display_fusion",
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
    {
        "type": "function",
        "function": {
            "name": "open_task_scheduler",
            "description": "Opens Windows Task Scheduler",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_startup_folder",
            "description": "Opens Windows startup folder where programs that run at startup are stored",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_services",
            "description": "Opens Windows Services manager to view and control system services",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_whisper",
            "description": "Starts Whisper keyboard application with administrator privileges",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_grok",
            "description": "Starts Grok application by opening the specified shortcut",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": "Set an alarm with a TTS notification",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "The number of minutes to wait before the alarm goes off",
                    },
                    "message": {
                        "type": "string",
                        "description": "The message to be spoken when the alarm goes off",
                    },
                },
                "required": ["minutes", "message"],
            },
        },
    },
]
