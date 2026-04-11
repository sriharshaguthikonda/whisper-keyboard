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
        debounce_time=0.5,
    ):
        self.record_keys = set(record_keys)
        self.map_key_to_keyword_index = map_key_to_keyword_index
        self.start_recording = start_recording
        self.stop_recording = stop_recording
        self.toggle_pause = toggle_pause
        self.debounce_time = debounce_time
        self._pressed = set()
        self._last_action_time = 0.0
        self._pause_toggle_armed = True

    def on_press(self, key, recording):
        now = time.time()
        self._pressed.add(key)

        if self._pause_combo_active():
            if self._pause_toggle_armed and now - self._last_action_time > self.debounce_time:
                self._last_action_time = now
                self._pause_toggle_armed = False
                self.toggle_pause()
            return

        if key in self.record_keys and not recording:
            if now - self._last_action_time > self.debounce_time:
                self._last_action_time = now
                keyword_index = self.map_key_to_keyword_index(key)
                self.start_recording(keyword_index)

    def on_release(self, key, recording):
        if key in self._pressed:
            self._pressed.remove(key)

        if not self._pause_combo_active():
            self._pause_toggle_armed = True

        now = time.time()
        if key in self.record_keys and recording:
            if now - self._last_action_time > self.debounce_time:
                self._last_action_time = now
                keyword_index = self.map_key_to_keyword_index(key)
                self.stop_recording(keyword_index)

    def _pause_combo_active(self):
        return Key.scroll_lock in self._pressed

    def reset_state(self):
        self._pressed.clear()
        self._pause_toggle_armed = True
        self._last_action_time = 0.0
