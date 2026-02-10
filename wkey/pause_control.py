import logging
import os
import time
import winsound

logger = logging.getLogger(__name__)

PAUSE_BEEP_SEQUENCE = [(900, 80), (600, 80), (400, 120)]
RESUME_BEEP_SEQUENCE = [(1200, 60), (1500, 60), (1800, 80)]


def play_beep_sequence(sequence):
    try:
        for frequency, duration in sequence:
            winsound.Beep(frequency, duration)
    except Exception as e:
        logger.error("Error in play_beep_sequence: %s", e, exc_info=True)


def _read_flag(path):
    try:
        with open(path, "r") as f:
            status = f.read().strip()
            return status == "PAUSED"
    except Exception:
        return False


def read_pause_flag(flag_path):
    try:
        alt_path = os.path.join(os.getcwd(), os.path.basename(flag_path))

        has_flag = os.path.exists(flag_path)
        has_alt = alt_path != flag_path and os.path.exists(alt_path)

        if has_flag and has_alt:
            try:
                if os.path.getmtime(alt_path) >= os.path.getmtime(flag_path):
                    return _read_flag(alt_path)
            except Exception:
                pass
            return _read_flag(flag_path)

        if has_alt:
            return _read_flag(alt_path)

        if has_flag:
            return _read_flag(flag_path)
    except Exception as e:
        logger.error("Error reading pause flag: %s", e, exc_info=True)
    return False


def write_pause_flag(flag_path, paused):
    try:
        with open(flag_path, "w") as f:
            f.write("PAUSED" if paused else "ACTIVE")
        return True
    except Exception as e:
        logger.error("Error writing pause flag: %s", e, exc_info=True)
        return False


def check_pause_status(flag_path, last_pause_check, global_pause_active, min_interval=0.5):
    now = time.time()
    if now - last_pause_check < min_interval:
        return global_pause_active, last_pause_check, global_pause_active

    paused = read_pause_flag(flag_path)
    return paused, now, paused


def set_pause_state(flag_path, paused):
    write_pause_flag(flag_path, paused)
    return paused


def toggle_pause_state(flag_path, current_paused):
    new_state = not current_paused
    write_pause_flag(flag_path, new_state)
    if new_state:
        play_beep_sequence(PAUSE_BEEP_SEQUENCE)
    else:
        play_beep_sequence(RESUME_BEEP_SEQUENCE)
    return new_state
