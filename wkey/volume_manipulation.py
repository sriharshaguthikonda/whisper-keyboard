import time
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

initial_volumes = {}  # Dictionary to store initial volumes for all devices


def get_current_volume(device):
    try:
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume.GetMasterVolumeLevelScalar()
    except Exception as e:
        print(f"Failed to get volume for device: {device.FriendlyName}, Error: {e}")
        return None


def set_volume(device, volume_level):
    try:
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(volume_level, None)
    except Exception as e:
        print(f"Failed to set volume for device: {device.FriendlyName}, Error: {e}")


def decrease_volume_all():
    global initial_volumes
    devices = AudioUtilities.GetAllDevices()
    for device in devices:
        if (
            device.state == 1 and "Speakers" in device.FriendlyName
        ):  # Only consider active speaker devices
            initial_volume = get_current_volume(device)
            if initial_volume is not None:
                initial_volumes[device.FriendlyName] = initial_volume
                print(
                    f"Decreasing volume for {device.FriendlyName} from {initial_volume * 100}% to 10%"
                )
                set_volume(device, 0.1)  # Set volume to 10%


def restore_volume_all():
    global initial_volumes
    devices = AudioUtilities.GetAllDevices()
    for device in devices:
        if device.state == 1 and device.FriendlyName in initial_volumes:
            print(
                f"Restoring volume for {device.FriendlyName} to {initial_volumes[device.FriendlyName] * 100}%"
            )
            set_volume(
                device, initial_volumes[device.FriendlyName]
            )  # Restore to initial volume


if __name__ == "__main__":
    decrease_volume_all()
    time.sleep(20)  # Simulate recording time
    restore_volume_all()
