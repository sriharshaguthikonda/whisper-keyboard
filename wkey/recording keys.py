from pynput.keyboard import Key, Listener, Controller
import time

# Global variables to store recorded keystrokes
recorded_keys = []
is_recording = False

# Keyboard controller for replaying keystrokes
keyboard = Controller()

def on_press(key):
    global is_recording
    global recorded_keys

    # Start recording when F12 key is pressed
    if key == Key.f12:
        is_recording = True
        print("Recording keystrokes...")
    elif is_recording:
        recorded_keys.append(key)
        print(f"Key pressed: {key}")

def on_release(key):
    global is_recording
    global recorded_keys

    # Stop recording when F11 key is pressed
    if key == Key.f11:
        is_recording = False
        print("Recording stopped.")
    elif key == Key.f10:
        # Replay recorded keystrokes when F10 key is pressed
        print("Replaying keystrokes...")
        for recorded_key in recorded_keys:
            keyboard.press(recorded_key)
            keyboard.release(recorded_key)
            time.sleep(0.1)
        print("Replay complete.")
        recorded_keys.clear()

    # Stop listener if ESC key is pressed
    if key == Key.esc:
        return False

# Start the listener
with Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()


