import pyHook
import pythoncom

def on_keyboard_event(event):
    if event.event_type == 'key down':
        print(f'Key {event.Key} pressed')
    elif event.event_type == 'key up':
        print(f'Key {event.Key} released')
    return True

# Create a hook manager
hm = pyHook.HookManager()

# Define the keyboard event handler
hm.KeyDown = on_keyboard_event
hm.KeyUp = on_keyboard_event

# Set the hook
hm.HookKeyboard()

# Start the event loop
pythoncom.PumpMessages()
