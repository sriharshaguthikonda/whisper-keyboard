import threading
import time
from collections import deque


class VolumeRestoreGuard:
    """Verifies post-restore volume and re-applies target if needed."""

    def __init__(
        self,
        get_volume_fn,
        set_volume_fn,
        logger,
        *,
        window_seconds=300,
        max_samples=5,
        tolerance=0.03,
    ):
        self._get_volume = get_volume_fn
        self._set_volume = set_volume_fn
        self._log = logger
        self._window_seconds = window_seconds
        self._samples = deque(maxlen=max_samples)
        self._tolerance = tolerance
        self._target_volume = None
        self._restore_generation = 0
        self._lock = threading.Lock()

        # Five checks inside a five-minute window.
        self._checkpoints_seconds = (1.0, 10.0, 45.0, 120.0, 300.0)

    def set_target(self, target_volume, reason="set_target"):
        with self._lock:
            self._target_volume = target_volume
        self._record_sample(reason)

    def restore_with_monitor(self, reason="restore"):
        with self._lock:
            if self._target_volume is None:
                return False
            target = self._target_volume
            self._restore_generation += 1
            generation = self._restore_generation

        self._set_and_record(target, f"{reason}:initial")
        threading.Thread(
            target=self._monitor_restore,
            args=(generation, target, reason),
            daemon=True,
            name="volume-restore-guard",
        ).start()
        return True

    def _monitor_restore(self, generation, target, reason):
        started_at = time.time()
        for checkpoint in self._checkpoints_seconds:
            elapsed = time.time() - started_at
            wait_seconds = checkpoint - elapsed
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            with self._lock:
                if generation != self._restore_generation:
                    return

            observed = self._record_sample(f"{reason}:check@{int(checkpoint)}s")
            if observed is None:
                continue
            if abs(observed - target) > self._tolerance:
                self._log.warning(
                    "Volume restore drift detected (target=%.2f, observed=%.2f). Re-applying.",
                    target,
                    observed,
                )
                self._set_and_record(target, f"{reason}:reapply@{int(checkpoint)}s")

    def _set_and_record(self, target, reason):
        try:
            self._set_volume(target)
        except Exception:
            self._log.error("Volume restore set failed (%s)", reason, exc_info=True)
            return None
        time.sleep(0.15)
        return self._record_sample(reason)

    def _record_sample(self, reason):
        try:
            observed = self._get_volume()
        except Exception:
            self._log.error("Volume read failed while tracking (%s)", reason, exc_info=True)
            return None
        now = time.time()
        with self._lock:
            self._prune_locked(now)
            self._samples.append(
                {
                    "ts": now,
                    "reason": reason,
                    "value": observed,
                    "target": self._target_volume,
                }
            )
        return observed

    def _prune_locked(self, now):
        cutoff = now - self._window_seconds
        while self._samples and self._samples[0]["ts"] < cutoff:
            self._samples.popleft()
