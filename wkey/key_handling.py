import threading
import time
import keyboard

# Define a debounce delay in seconds
DEBOUNCE_DELAY = 0.3  # 300 milliseconds

# Initialize a variable to track the last press time
last_press_time = 0


def start_recording():
    # Implement the start recording functionality here
    pass


def stop_recording():
    # Implement the stop recording functionality here
    pass


def on_press(key):
    global last_press_time
    current_time = time.time()
    if key == "record" and (current_time - last_press_time) > DEBOUNCE_DELAY:
        threading.Thread(target=start_recording).start()
        last_press_time = current_time


def on_release(key):
    global last_press_time
    current_time = time.time()
    if key == "record" and (current_time - last_press_time) > DEBOUNCE_DELAY:
        threading.Thread(target=stop_recording).start()
        last_press_time = current_time


def start_listening():
    keyboard.on_press(on_press)
    keyboard.on_release(on_release)
    keyboard.wait()


"""
########  #######  ##        
##       ##     ## ##    ##  
##              ## ##    ##  
######    #######  ##    ##  
##       ##        ######### 
##       ##              ##  
##       #########       ##  
"""
