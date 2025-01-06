# voice_commands.py
import os
import pyautogui
import re
import string
from fuzzywuzzy import process
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
import logging

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


import tkinter as tk


from commands_and_tools import (
    COMMAND_MAPPINGS,
    ACTIONS,
    tools,
    extra_tools,
)


load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Define models
ROUTING_MODEL = "llama3-70b-8192"
# ROUTING_MODEL = "llama-3.2-1b-preview"
TOOL_USE_MODEL = "llama3-groq-8b-8192-tool-use-preview"
GENERAL_MODEL = "llama3-70b-8192"


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

# Additional ANSI Color codes
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"


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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler("voice_commands_errors.log"),  # Also log to file
    ],
)


def start_driver():
    global driver, driver_pid, session_id, executor_url

    logging.debug("Initializing web driver")
    try:
        driver = webdriver.Edge(service=service, options=options)
        time.sleep(6)
        logging.debug("Loading Spotify web player")
        driver.get("https://open.spotify.com/collection/tracks")
        time.sleep(5)
        driver_pid = driver.service.process.pid
        session_id = driver.session_id
        executor_url = driver.command_executor._url
        logging.debug(f"Driver initialized with PID: {driver_pid}")
        logging.info(
            f"{BRIGHT_GREEN}Spotify web player initialized successfully{RESET}"
        )
    except Exception as e:
        logging.error(f"Failed to initialize web driver: {str(e)}", exc_info=True)
        logging.info(f"{RED}Error initializing web driver: {e}{RESET}")


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
        logging.error(f"Failed to reconnect to session: {str(e)}", exc_info=True)
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
            logging.error(
                f"Failed to create new session: {str(new_session_error)}", exc_info=True
            )
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
def play_music():
    logging.debug("Attempting to play music")
    try:
        play_button = driver.find_element(By.XPATH, "//button[@aria-label='Play']")
        play_button.click()
        logging.debug("Play button clicked")
        change_device()
        logging.info(f"{CYAN}Music playback started{RESET}")
    except Exception as e:
        error_message = str(e)
        logging.error(f"Play music error: {error_message}", exc_info=True)
        if "disconnected" in error_message:
            logging.debug("DevTools disconnection detected")
            logging.info(
                f"{YELLOW}Attempting to reconnect due to DevTools disconnection...{RESET}"
            )
            reconnect_driver()
            try:
                play_button = driver.find_element(
                    By.XPATH, "//button[@aria-label='Play']"
                )
                play_button.click()
                logging.info(f"{GREEN}Playback started after reconnection{RESET}")
            except Exception as e:
                logging.info(
                    f"{RED}Error while trying to play after reconnection: {e}{RESET}"
                )

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


"""
   ###     ######  ######## ####  #######  ##    ##  ######  
  ## ##   ##    ##    ##     ##  ##     ## ###   ## ##    ## 
 ##   ##  ##          ##     ##  ##     ## ####  ## ##       
##     ## ##          ##     ##  ##     ## ## ## ##  ######  
######### ##          ##     ##  ##     ## ##  ####       ## 
##     ## ##    ##    ##     ##  ##     ## ##   ### ##    ## 
##     ##  ######     ##    ####  #######  ##    ##  ######  
"""


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
def process_TTS_queue(TTS_queue):
    while True:
        sentence = TTS_queue.get()
        if sentence is None:  # Sentinel value to stop the worker
            break
        asyncio.run(text_to_speech(sentence, speed=1.5))
        TTS_queue.task_done()


threading.Thread(target=process_TTS_queue, args=(TTS_queue,), daemon=True).start()


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
            raise ValueError("No audio received. verify that your params are correct.")

        audio_fp = io.BytesIO(audio_bytes)
        audio_fp.seek(0)

        TTS_Audio_play_queue.put(audio_fp)

    except Exception as e:
        print(f"Error occurred during playback: {e}")


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


def execute_command_run_with_tool(query):
    try:
        logging.debug(f"Processing command: {query}")
        route = route_query(query)  # Step 1: Determine if a tool is needed

        logging.debug(f"Route decision: {route}")
        # Step 2: Handle the result of routing
        if route == "NO TOOL":
            # Use the general model if no tools are needed
            run_general(query)
        else:
            # Step 3: Handle tool usage
            tools_messages = [
                {
                    "role": "system",
                    "content": """
                    1. you are a tool selection assistant. pick the best possible tool among tools for the given query. 
                    2. if there is "and" in the query, then you will have to select two functions
                    """,
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
                            # visual_feedback(function_name, result)
                        except Exception as e:
                            print(f"Error executing function {function_name}: {e}")
                    else:
                        print(f"Function {function_name} not found in globals.")
            else:
                print("No tool calls were made by the model.")

        return True  # Function executed successfully
    except Exception as e:
        logging.error(f"Command execution error: {str(e)}", exc_info=True)
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
