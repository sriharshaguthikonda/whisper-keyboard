import threading
import time
from collections import deque


class OverflowBurstTracker:
    def __init__(self, *, window_seconds=8.0, threshold=6):
        self.window_seconds = float(window_seconds)
        self.threshold = int(threshold)
        self._events = deque()
        self._lock = threading.Lock()

    def note_overflow(self):
        now = time.monotonic()
        with self._lock:
            self._events.append(now)
            cutoff = now - self.window_seconds
            while self._events and self._events[0] < cutoff:
                self._events.popleft()
            count = len(self._events)
            return count >= self.threshold, count

    def reset(self):
        with self._lock:
            self._events.clear()


class ResumeGapDetector:
    def __init__(self, *, gap_seconds=20.0):
        self.gap_seconds = float(gap_seconds)
        self._last_tick = time.monotonic()
        self._lock = threading.Lock()

    def check(self):
        now = time.monotonic()
        with self._lock:
            gap = now - self._last_tick
            self._last_tick = now
        return gap >= self.gap_seconds, gap

    def mark_now(self):
        with self._lock:
            self._last_tick = time.monotonic()
