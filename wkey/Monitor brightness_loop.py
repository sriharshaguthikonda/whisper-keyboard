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
        for proc in psutil.process_iter(["name"]):
            if program_name.lower() in proc.info["name"].lower():
                print(program_name, "is running")
                return True
        print(program_name, "is not running")
        return False
    except Exception as e:
        print(f"Error in is_program_running: {e}")
        return False


def start_program():
    global process, screen_inverted
    try:
        if not is_program_running(
            "NegativeScreen-custom-multi-monitor.exe"
        ):  # Only start if not already inverted
            process = subprocess.Popen([program_path], shell=True)
            print(f"Started {program_path} with PID {process.pid}")
        else:
            print(f"{program_path} is already running")
    except Exception as e:
        print(f"Error in start_program: {e}")


def kill_program():
    global process, screen_inverted
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"].lower() == "negativescreen-custom-multi-monitor.exe":
                proc.terminate()
                proc.wait(timeout=5)  # Wait for the process to terminate
                print(
                    f"Killed NegativeScreen-custom-multi-monitor.exe with PID {proc.info['pid']}"
                )
                return  # Exit after terminating the process
        print("NegativeScreen-custom-multi-monitor.exe not found.")
    except psutil.NoSuchProcess:
        print("The process does not exist.")
    except psutil.AccessDenied:
        print("Access denied when trying to terminate the process.")
    except psutil.TimeoutExpired:
        print("Timeout expired while waiting for the process to terminate.")
    except Exception as e:
        print(f"Error in kill_program: {e}")


def monitor():
    global process, screen_inverted
    last_focused_window = None
    while True:
        try:
            # Get the currently focused window
            focused_window = gw.getActiveWindow()
            if focused_window:
                window_title = focused_window.title

                # Check if the focused window has changed
                if last_focused_window != window_title:
                    last_focused_window = window_title
                    print(f"Window changed: {window_title}")

                    # Get the average brightness of the focused window
                    brightness = get_window_brightness(window_title)
                    print(f"Average brightness: {brightness}")

                    screen_inverted = is_program_running(
                        "NegativeScreen-custom-multi-monitor.exe"
                    )
                    print("screen_inverted : ", screen_inverted)

                    if (
                        brightness > brightness_threshold and not screen_inverted
                    ):  # Only start if not already inverted:
                        start_program()
                    elif (
                        brightness > brightness_threshold and screen_inverted
                    ):  # Prevent multiple kills/starts
                        kill_program()
                    elif brightness <= brightness_threshold and screen_inverted:
                        kill_program()

            time.sleep(1)
        except Exception as e:
            print(f"Error in monitor loop: {e}")


if __name__ == "__main__":
    try:
        monitor()
    except Exception as e:
        print(f"Error in main: {e}")
