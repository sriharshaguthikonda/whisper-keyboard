"""Volume ducking helpers — decrease/restore system volume around recordings."""

import threading
import time
import logging

try:
    from voice_commands import get_volume, set_volume
except ModuleNotFoundError:
    from wkey.voice_commands import get_volume, set_volume

try:
    from volume_lease_manager import VolumeLeaseManager
except ModuleNotFoundError:
    from wkey.volume_lease_manager import VolumeLeaseManager

_volume_lease_manager = None
_settings_getter = None
initial_volume = None


def init_volume_control(volume_lease_manager, settings_getter):
    """Wire up dependencies. Call once at startup before any recording."""
    global _volume_lease_manager, _settings_getter
    _volume_lease_manager = volume_lease_manager
    _settings_getter = settings_getter


def decrease_volume_all():
    global initial_volume
    try:
        baseline_volume, lease_count = _volume_lease_manager.begin_duck(
            reason="decrease_volume_all"
        )
        if baseline_volume is None:
            baseline_volume = get_volume()
        initial_volume = baseline_volume
        logging.info(
            "decrease_volume_all: lease_count=%d baseline=%.2f duck_to=0.10",
            lease_count,
            initial_volume,
        )
    except Exception as e:
        logging.error(f"Error in decrease_volume_all: {e}", exc_info=True)


def restore_volume_all():
    global initial_volume
    try:
        target_volume, remaining_leases, did_restore = _volume_lease_manager.end_duck(
            reason="restore_volume_all"
        )
        logging.info(
            "restore_volume_all: remaining_leases=%d target=%s did_restore=%s",
            remaining_leases,
            f"{target_volume:.2f}" if target_volume is not None else "None",
            did_restore,
        )
        if did_restore:
            initial_volume = None
            return
        if remaining_leases > 0 and target_volume is not None:
            initial_volume = target_volume
            return
        if target_volume is None and initial_volume is not None:
            logging.warning(
                "restore_volume_all: lease manager returned None target; "
                "falling back to initial_volume=%.2f",
                initial_volume,
            )
            set_volume(initial_volume)
            initial_volume = None
    except Exception as e:
        logging.error(f"Error in restore_volume_all: {e}", exc_info=True)


def _restore_volume_all_async(delay_seconds=0.0):
    def _run():
        try:
            if delay_seconds and delay_seconds > 0:
                time.sleep(delay_seconds)
            restore_volume_all()
        except Exception as e:
            logging.error(f"Error in delayed restore_volume_all: {e}", exc_info=True)

    threading.Thread(target=_run, daemon=True).start()


def _get_volume_restore_delay_for_keyword(keyword_index):
    if keyword_index == 3:
        try:
            settings = _settings_getter() if callable(_settings_getter) else {}
            return max(
                0.0, float(settings.get("google_wake_volume_hold_seconds", 2.5))
            )
        except Exception:
            return 2.5
    return 0.0
