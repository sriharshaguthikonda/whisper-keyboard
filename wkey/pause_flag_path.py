import os


def get_pause_flag_path(anchor_file):
    """Return canonical pause-flag path next to the caller file."""
    base_dir = os.path.dirname(os.path.abspath(anchor_file))
    return os.path.join(base_dir, "voice_pause_flag.txt")
