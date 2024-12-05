import win32api
import win32con
import time


def check_mouse():
    print("Listening for middle mouse button. Press Ctrl+C to exit.")
    while True:
        # Get the current state of the middle mouse button
        if win32api.GetKeyState(win32con.VK_MBUTTON) < 0:
            print("Middle mouse button pressed")
            while win32api.GetKeyState(win32con.VK_MBUTTON) < 0:
                time.sleep(0.1)  # Wait until the button is released
            print("Middle mouse button released")


try:
    check_mouse()
except KeyboardInterrupt:
    print("Stopped listening.")
