import psutil
import pygetwindow as gw
import time
import subprocess
import mss
import numpy as np

# Define threshold for average brightness (example: 150)
brightness_threshold = 150
program_path = (
    r"C:\Program Files\Negative screen\NegativeScreen-custom-multi-monitor.exe"
)
process = None  # Variable to hold the process reference
screen_inverted = False  # Variable to track screen inversion state

# Track the state of the program (whether it's running or not)
process_running = False

# Define debounce time window (in seconds)
DEBOUNCE_TIME = 0.5  # 500 milliseconds

# Last window focus change timestamp
last_focus_time = 0


def get_window_brightness(window_title, sample_fraction=0.1):
    try:
        # Define the monitor area (example: full screen)
        monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        with mss.mss() as sct:
            screenshot = np.array(sct.grab(monitor))
            # Convert to grayscale
            grayscale = np.dot(screenshot[..., :3], [0.299, 0.587, 0.114])
            # Sample a subset of pixels
            total_pixels = grayscale.size
            sample_size = int(total_pixels * sample_fraction)
            sampled_pixels = grayscale.ravel()[:sample_size]
            # Calculate average brightness
            avg_brightness = np.mean(sampled_pixels)
            return avg_brightness
    except Exception as e:
        print(f"Error in get_window_brightness: {e}")
        return 0  # Default to 0 brightness on error


def is_program_running(program_name):
    try:
        # Check the process state once and update the global state variable
        global process_running
        if process_running:
            return True  # Return early if the program is already running

        for proc in psutil.process_iter(["name"]):
            if program_name.lower() in proc.info["name"].lower():
                process_running = True  # Set process as running
                print(f"{program_name} is running")
                return True

        process_running = False  # Reset if not found
        print(f"{program_name} is not running")
        return False
    except Exception as e:
        print(f"Error in is_program_running: {e}")
        return False


def start_program():
    global process, process_running, screen_inverted
    try:
        if not screen_inverted:  # Only start if not already inverted
            process = subprocess.Popen([program_path], shell=True)
            process_running = True  # Update the state to running
            screen_inverted = True  # Update screen state to inverted
            print(f"Started {program_path} with PID {process.pid}")
        else:
            print(f"{program_path} is already running and screen is inverted")
    except Exception as e:
        print(f"Error in start_program: {e}")


def kill_program():
    global process, process_running, screen_inverted
    try:
        if screen_inverted:  # Only kill if the screen is inverted
            for proc in psutil.process_iter(["pid", "name"]):
                if (
                    proc.info["name"].lower()
                    == "negativescreen-custom-multi-monitor.exe"
                ):
                    proc.terminate()
                    proc.wait(timeout=5)  # Wait for the process to terminate
                    process_running = False  # Update the state to not running
                    screen_inverted = False  # Update screen state to not inverted
                    print(
                        f"Killed NegativeScreen-custom-multi-monitor.exe with PID {proc.info['pid']}"
                    )
                    return
            print("NegativeScreen-custom-multi-monitor.exe not found.")
        else:
            print("The screen is not inverted. No need to kill the process.")
    except psutil.NoSuchProcess:
        print("The process does not exist.")
    except psutil.AccessDenied:
        print("Access denied when trying to terminate the process.")
    except psutil.TimeoutExpired:
        print("Timeout expired while waiting for the process to terminate.")
    except Exception as e:
        print(f"Error in kill_program: {e}")


def monitor():
    global process, screen_inverted, last_focus_time
    last_focused_window = None
    while True:
        try:
            # Get the currently focused window
            focused_window = gw.getActiveWindow()
            if focused_window:
                window_title = focused_window.title

                # Ignore the "NegativeScreen" window (empty title or specific process name)
                if not window_title or "NegativeScreen" in window_title:
                    continue  # Skip further checks if the current window is the NegativeScreen process

                # Check if enough time has passed since the last focus change (debounce)
                current_time = time.time()
                if current_time - last_focus_time < DEBOUNCE_TIME:
                    # If within the debounce time, skip processing
                    continue
                last_focus_time = current_time  # Update the last focus time

                # Check if the focused window has changed
                if last_focused_window != window_title:
                    last_focused_window = window_title
                    print(f"Window changed: {window_title}")

                    # Get the average brightness of the focused window
                    brightness = get_window_brightness(window_title)
                    print(f"Average brightness: {brightness}")

                    # Check if the program is running
                    screen_inverted = is_program_running(
                        "NegativeScreen-custom-multi-monitor.exe"
                    )
                    print("screen_inverted:", screen_inverted)

                    # Only start program if brightness is above threshold and screen is not inverted
                    if brightness > brightness_threshold and not screen_inverted:
                        start_program()
                    # Only kill the program if brightness is below threshold and screen is inverted
                    elif brightness <= brightness_threshold and screen_inverted:
                        kill_program()

            # Sleep for a short interval (e.g., 100 ms) to check for window focus changes more frequently
            time.sleep(0.1)  # This will make the checking faster and more responsive

        except Exception as e:
            print(f"Error in monitor loop: {e}")


if __name__ == "__main__":
    try:
        monitor()
    except Exception as e:
        print(f"Error in main: {e}")
