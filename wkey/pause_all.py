import time
import sounddevice as sd
import numpy as np
import ctypes

from pycaw.pycaw import AudioUtilities
from collections import deque

# Initialize deques with a maximum length of 50
Background_max_volumes = deque(maxlen=50)
Background_min_volumes = deque(maxlen=50)
recent_volumes = deque(maxlen=2)

# Limit the size of the lists to store recent volumes, background maximum volumes, and background minimum volumes
MAX_LIST_SIZE = 50

# Initialize a list to store the recent volume values
recent_volumes = []

diff_to_max = 0
diff_to_min = 0

volume_norm = 0

pause_all_audio_buffer = np.array([], dtype='float32')


def is_sound_playing_windows_processing(something_is_playing):
    global recent_volumes
    Background_max = 0
    Background_min = 0
    global diff_to_max
    global diff_to_min
    global volume_norm

    duration = 0.5  # Duration for recording audio in seconds
    sample_rate = 44000  # Sample rate in Hz

    # Callback function for audio stream
    def pause_all_callback(indata, frames, time, status):
        global volume_norm
        volume_norm = np.linalg.norm(indata) * 1000000

    try:
        with sd.InputStream(callback=pause_all_callback):
            sd.sleep(1000)

        print(volume_norm)

        sessions = None
        try:
            sessions = AudioUtilities.GetAllSessions()
#            print(sessions)
        except ctypes.COMError as e:
            print(f"Error getting audio sessions: {e}")

        for session in sessions:
            if session.State == 1:  # Check if session is active
                session_state = True
                Background_max_volumes.append(volume_norm)
                Background_max = np.percentile(Background_max_volumes, 15)  # 75th percentile
            elif session.State == 0:  # Check if session is inactive Can you hear me now?
                session_state = False
                Background_min_volumes.append(volume_norm)
                Background_min = np.min(Background_min_volumes)

            # Calculate the absolute differences between the moving average and background max/min
            diff_to_max = abs(volume_norm - Background_max)
            diff_to_min = abs(volume_norm - Background_min)

            if diff_to_max < diff_to_min and session_state:
                print(something_is_playing)
                something_is_playing = True
                return something_is_playing
                # Moving average is closer to background max
                # print("Moving average is closer to background max.")
            elif diff_to_min < diff_to_max and session_state:
                something_is_playing = False
                print(something_is_playing)
                return something_is_playing
        
        # Determine if sound is playing based on the moving average volume
        # print(moving_average)

    except sd.PortAudioError as e:
        something_is_playing = None
        return something_is_playing
        print("Failed to connect to input device:", e)
        time.sleep(1)


def get_threshold(current_volume):
    # Adjust this function to dynamically calculate the threshold based on current volume or other factors
    # For example, you can use a moving average of recent volume levels
    # Here, we simply return a fixed threshold of 3000
    return 10000


def get_applications_playing_audio():
    while True:
        # Check if sound is actively playing
        if is_sound_playing_windows():
            print("Sound is actively playing.")

            # Add your code here to retrieve the list of applications playing audio
            # This could involve using pycaw or other methods to get the list of active audio sessions

        else:
            print("No sound is actively playing.")

        # Wait for a brief interval before checking again
        # time.sleep(1)  # Adjust the interval as needed


if __name__ == "__main__":
    get_applications_playing_audio()
