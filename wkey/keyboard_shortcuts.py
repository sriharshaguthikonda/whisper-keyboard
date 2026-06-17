import logging
import time
from pynput.keyboard import Key


class KeyboardShortcutHandler:
    def __init__(
        self,
        record_keys,
        map_key_to_keyword_index,
        start_recording,
        stop_recording,
        toggle_pause,
        cancel_recording=None,
        cancel_on_chord_keys=None,
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=time.time,
        log=None,
    ):
        self.record_keys = set(record_keys)
        self.map_key_to_keyword_index = map_key_to_keyword_index
        self.start_recording = start_recording
        self.stop_recording = stop_recording
        self.toggle_pause = toggle_pause
        self.cancel_recording = cancel_recording or (lambda keyword_index, reason: None)
        self.cancel_on_chord_keys = set(cancel_on_chord_keys or ())
        self.debounce_time = debounce_time
        self.record_rearm_delay = record_rearm_delay
        self.clock = clock
        self.log = log or logging.getLogger(__name__)
        self._pressed = set()
        self._last_record_press_time = 0.0
        self._last_record_release_time = float("-inf")
        self._last_pause_toggle_time = 0.0
        self._active_record_keys = set()
        self._canceled_record_keys = set()
        self._pause_toggle_armed = True
        self._record_suppressed_until = float("-inf")
        self._record_suppression_reason = ""

    def on_press(self, key, recording):
        now = self.clock()
        is_record_key = key in self.record_keys
        already_pressed = key in self._pressed
        if is_record_key or key == Key.scroll_lock:
            self._pressed.add(key)

        if self._cancel_chord_if_needed(key, recording, now):
            return

        if is_record_key and already_pressed:
            action = (
                "press_ignored_active"
                if key in self._active_record_keys
                else "press_ignored_repeat"
            )
            self._log_record_key_event(action, key, recording, now)
            return

        if is_record_key and self._record_suppression_remaining(now) > 0:
            self._log_record_key_event("press_ignored_suppressed", key, recording, now)
            return

        if self._pause_combo_active():
            if (
                self._pause_toggle_armed
                and now - self._last_pause_toggle_time > self.debounce_time
            ):
                self._last_pause_toggle_time = now
                self._pause_toggle_armed = False
                self.toggle_pause()
            return

        if is_record_key and not recording:
            if key in self._active_record_keys:
                self._log_record_key_event("press_ignored_active", key, recording, now)
                return
            if (
                now - self._last_record_press_time > self.debounce_time
                and now - self._last_record_release_time > self.record_rearm_delay
            ):
                self._last_record_press_time = now
                self._active_record_keys.add(key)
                self._canceled_record_keys.discard(key)
                keyword_index = self.map_key_to_keyword_index(key)
                self._log_record_key_event("press_start", key, recording, now)
                self.start_recording(keyword_index)
            else:
                self._log_record_key_event("press_ignored_rearm", key, recording, now)

    def on_release(self, key, recording):
        now = self.clock()
        was_active_record_key = key in self._active_record_keys
        if key in self._pressed:
            self._pressed.remove(key)

        if not self._pause_combo_active():
            self._pause_toggle_armed = True

        if key in self._canceled_record_keys:
            self._canceled_record_keys.discard(key)
            self._last_record_release_time = now
            self._log_record_key_event("release_ignored_canceled", key, recording, now)
            return

        if (
            key in self.record_keys
            and self._record_suppression_remaining(now) > 0
            and not recording
        ):
            self._active_record_keys.discard(key)
            self._last_record_release_time = now
            self._log_record_key_event("release_ignored_suppressed", key, recording, now)
            return

        if key in self.record_keys and (was_active_record_key or recording):
            self._active_record_keys.discard(key)
            self._last_record_release_time = now
            keyword_index = self.map_key_to_keyword_index(key)
            self._log_record_key_event("release_stop", key, recording, now)
            self.stop_recording(keyword_index)

    def _pause_combo_active(self):
        return Key.scroll_lock in self._pressed

    def _cancel_chord_if_needed(self, key, recording, now):
        cancelable_keys = self._active_record_keys & self.cancel_on_chord_keys
        if not cancelable_keys:
            return False
        if key in cancelable_keys:
            return False

        for active_key in list(cancelable_keys):
            self._active_record_keys.discard(active_key)
            self._canceled_record_keys.add(active_key)
            self._last_record_release_time = now
            keyword_index = self.map_key_to_keyword_index(active_key)
            reason = f"chord:{self._key_reason(key)}"
            self._log_record_key_event("press_cancel_chord", key, recording, now)
            self.cancel_recording(keyword_index, reason)
        return True

    def _key_reason(self, key):
        if isinstance(key, str):
            return key
        char = getattr(key, "char", None)
        if char:
            return char
        return str(key)

    def suppress_record_keys(self, seconds, reason):
        now = self.clock()
        duration = max(0.0, float(seconds or 0.0))
        until = now + duration
        if until > self._record_suppressed_until:
            self._record_suppressed_until = until
            self._record_suppression_reason = str(reason)
        self._log_record_key_event("suppression_set", None, False, now)

    def _record_suppression_remaining(self, now=None):
        if now is None:
            now = self.clock()
        return max(0.0, self._record_suppressed_until - now)

    def _log_record_key_event(self, action, key, recording, now):
        try:
            self.log.info(
                "record_key_event action=%s key=%s recording=%s "
                "suppressed_remaining=%.3f suppression_reason=%s "
                "active_keys=%s pressed_keys=%s",
                action,
                str(key) if key is not None else "none",
                bool(recording),
                self._record_suppression_remaining(now),
                self._record_suppression_reason,
                ",".join(sorted(str(item) for item in self._active_record_keys)) or "none",
                ",".join(sorted(str(item) for item in self._pressed)) or "none",
            )
        except Exception:
            pass

    def reset_state(self, preserve_rearm=False):
        last_press_time = self._last_record_press_time if preserve_rearm else 0.0
        last_release_time = (
            self._last_record_release_time if preserve_rearm else float("-inf")
        )
        suppressed_until = (
            self._record_suppressed_until if preserve_rearm else float("-inf")
        )
        suppression_reason = self._record_suppression_reason if preserve_rearm else ""
        self._pressed.clear()
        self._active_record_keys.clear()
        self._canceled_record_keys.clear()
        self._pause_toggle_armed = True
        self._last_record_press_time = last_press_time
        self._last_record_release_time = last_release_time
        self._last_pause_toggle_time = 0.0
        self._record_suppressed_until = suppressed_until
        self._record_suppression_reason = suppression_reason
