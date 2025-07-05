import pyautogui
import subprocess
import os
import logging
import re
import asyncio
from fuzzywuzzy import process
import threading
import time

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


def start_whisper():
    try:
        batch_path = r"C:\Users\deletable\OneDrive\Windows_software\openai whisper\whisper_keyboard.bat"
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
    "open control panel": lambda: open_application("control panel"),
    "open calculator": lambda: open_application("calculator"),
    "open notepad": lambda: open_application("notepad"),
    "open word": lambda: open_application("word"),
    "open excel": lambda: open_application("excel"),
    "open powerpoint": lambda: open_application("powerpoint"),
    "open outlook": lambda: open_application("outlook"),
    "open paint": lambda: open_application("paint"),
    "open command prompt": lambda: open_application("command prompt"),
    "open powershell": lambda: open_application("powershell"),
    "open edge": lambda: open_application("edge"),
    "open chrome": lambda: open_application("chrome"),
    "open firefox": lambda: open_application("firefox"),
    # Volume Controls
    "open sound control panel": lambda: open_system_utility("sound_control_panel"),
    "volume up": lambda: execute_pyautogui_press("volumeup"),
    "volume down": lambda: execute_pyautogui_press("volumedown"),
    "mute volume": lambda: execute_pyautogui_press("volumemute"),
    # Media Controls
    "play media": play_music,
    "stop media": pause_song,
    "next track": next_track,
    "previous track": previous_track,
    # Custom or Complex Operations
    "open device manager": lambda: open_system_utility("device_manager"),
    "open disk management": lambda: open_system_utility("disk_management"),
    "open network connections": lambda: open_system_utility("network_connections"),
    "open system properties": lambda: open_system_utility("system_properties"),
    "open date and time": lambda: open_system_utility("date_and_time"),
    # System Commands
    "ping google": lambda: execute_system_command("ping www.google.com"),
    "flush dns": lambda: execute_system_command("ipconfig /flushdns"),
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
    "open_task_scheduler": lambda: execute_system_command("taskschd.msc"),
    "open_startup_folder": lambda: execute_system_command("shell:startup"),
    "manage_services": lambda: execute_system_command("services.msc"),
    "start_whisper": start_whisper,
    "start_grok": start_grok,
    "set alarm": lambda minutes, message: set_alarm(minutes, message),
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
            "name": "open_application",
            "description": "Open an application by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "Name of the application to open"}
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_system_utility",
            "description": "Open a Windows system utility by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "utility": {"type": "string", "description": "Name of the utility to open"}
                },
                "required": ["utility"],
            },
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
