import winsound

START_BEEP = (880, 100)  # Frequency in Hz, Duration in ms
STOP_BEEP = (440, 100)   # Lower frequency for stop
PASTE_BEEP = (660, 100)  # Intermediate frequency for paste


def beep(sound):
    frequency, duration = sound
    winsound.Beep(frequency, duration)
