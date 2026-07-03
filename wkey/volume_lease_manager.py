import threading
import time
from collections import deque
from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.callbacks import AudioEndpointVolumeCallback
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class _EndpointCallback(AudioEndpointVolumeCallback):
    def __init__(self, manager):
        super().__init__()
        self._manager = manager

    def on_notify(
        self,
        new_volume,
        new_mute,
        event_context,
        channels,
        channel_volumes,
    ):
        self._manager.on_volume_notify(new_volume)


class VolumeLeaseManager:
    """
    Manages temporary volume ducking with nested leases.
    Uses endpoint callbacks to re-apply target volume only when drift happens.
    """

    def __init__(
        self,
        get_volume_fn,
        set_volume_fn,
        logger,
        *,
        duck_volume=0.1,
        tolerance=0.03,
        callback_reapply_cooldown=0.25,
        history_window_seconds=300,
        history_max_samples=5,
        enable_endpoint_callback=True,
    ):
        self._get_volume = get_volume_fn
        self._set_volume = set_volume_fn
        self._log = logger
        self._duck_volume = duck_volume
        self._tolerance = tolerance
        self._callback_reapply_cooldown = callback_reapply_cooldown
        self._history_window_seconds = history_window_seconds
        self._history = deque(maxlen=history_max_samples)

        self._lock = threading.RLock()
        self._lease_count = 0
        self._restore_target = None
        self._restore_pending = False
        self._last_reapply_ts = 0.0

        self._endpoint_devices = None
        self._endpoint_interface = None
        self._endpoint_volume = None
        self._endpoint_callback = None

        self._callback_ready = threading.Event()
        self._stop_event = threading.Event()
        self._callback_thread = None
        if enable_endpoint_callback:
            self._callback_thread = threading.Thread(
                target=self._callback_worker,
                daemon=True,
                name="volume-endpoint-callback",
            )
            self._callback_thread.start()
        else:
            self._callback_ready.set()
            self._log.info(
                "Volume endpoint callback disabled; lease manager uses verify fallback"
            )

    def begin_duck(self, reason="duck"):
        baseline = None
        reuse_cached_target = False
        with self._lock:
            if self._lease_count == 0:
                if self._restore_pending and self._restore_target is not None:
                    baseline = self._restore_target
                    reuse_cached_target = True
            else:
                baseline = self._restore_target

        if baseline is None:
            baseline = self._safe_get_volume(default=0.5)

        with self._lock:
            if self._lease_count == 0:
                # Restore still in flight — read would return stale ducked value.
                # Reuse the known target so we don't clobber it with 0.1.
                if reuse_cached_target and self._restore_target is not None:
                    baseline = self._restore_target
                if baseline is None:
                    baseline = 0.5
                self._restore_target = baseline
                self._restore_pending = False  # cancel in-flight restore; new duck owns it
            else:
                baseline = self._restore_target
                if baseline is None:
                    baseline = 0.5
                    self._restore_target = baseline
            self._lease_count += 1
            lease_count = self._lease_count

        if reuse_cached_target:
            self._log.warning(
                "begin_duck called while restore in flight "
                "(reason=%s); reusing cached target=%.2f to avoid race",
                reason, baseline,
            )
        self._log.info(
            "begin_duck reason=%s lease_count=%d restore_target=%.2f duck_volume=%.2f",
            reason, lease_count, baseline, self._duck_volume,
        )
        self._record_sample(reason=f"{reason}:begin", value=baseline)
        self._safe_set_volume(self._duck_volume, reason=f"{reason}:duck")
        return baseline, lease_count

    def end_duck(self, reason="restore"):
        with self._lock:
            if self._lease_count <= 0:
                self._log.warning(
                    "end_duck called with lease_count=0 (reason=%s) — unbalanced call", reason
                )
                return None, 0, False

            self._lease_count -= 1
            remaining = self._lease_count
            target = self._restore_target
            should_restore = remaining == 0 and target is not None
            if should_restore:
                self._restore_pending = True

        self._log.info(
            "end_duck reason=%s remaining_leases=%d target=%.2f should_restore=%s",
            reason, remaining, target if target is not None else -1, should_restore,
        )
        if should_restore:
            self._start_restore(
                target,
                reason,
                async_set=False,
                thread_name="volume-restore-verify",
            )

        self._record_sample(reason=f"{reason}:end", value=target)
        return target, remaining, should_restore

    def force_release_all(self, reason="force_release", *, restore=True, async_restore=True):
        with self._lock:
            released_leases = self._lease_count
            target = self._restore_target
            had_restore_pending = self._restore_pending
            should_restore = bool(
                restore and target is not None and (released_leases > 0 or had_restore_pending)
            )
            self._lease_count = 0
            self._restore_pending = should_restore
            self._last_reapply_ts = 0.0

        if released_leases <= 0 and not should_restore:
            self._log.debug(
                "force_release_all noop (reason=%s target=%s)",
                reason,
                f"{target:.2f}" if target is not None else "None",
            )
            return target, released_leases, False

        self._log.warning(
            "force_release_all reason=%s released_leases=%d target=%s "
            "had_restore_pending=%s should_restore=%s",
            reason,
            released_leases,
            f"{target:.2f}" if target is not None else "None",
            had_restore_pending,
            should_restore,
        )
        if should_restore:
            self._start_restore(
                target,
                reason,
                async_set=async_restore,
                thread_name="volume-force-restore",
            )
        self._record_sample(reason=f"{reason}:force_release", value=target)
        return target, released_leases, should_restore

    def on_volume_notify(self, new_volume):
        now = time.time()
        self._log.debug("on_volume_notify new_volume=%.2f", new_volume)
        self._record_sample(reason="callback", value=new_volume)

        should_reapply = False
        target = None
        with self._lock:
            if (
                self._lease_count > 0
                or not self._restore_pending
                or self._restore_target is None
            ):
                return

            target = self._restore_target
            if abs(new_volume - target) <= self._tolerance:
                self._restore_pending = False
                return

            if (
                new_volume < target - self._tolerance
                and now - self._last_reapply_ts >= self._callback_reapply_cooldown
            ):
                self._last_reapply_ts = now
                should_reapply = True

        if should_reapply:
            self._log.warning(
                "Volume drift after restore (target=%.2f observed=%.2f). Re-applying.",
                target,
                new_volume,
            )
            self._safe_set_volume(target, reason="callback_reapply")

    def recent_history(self):
        with self._lock:
            return list(self._history)

    def try_snapshot_state(self):
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return None
        try:
            return self._snapshot_state_unlocked()
        finally:
            self._lock.release()

    def snapshot_state(self):
        with self._lock:
            return self._snapshot_state_unlocked()

    def _fallback_restore_verify(self, target, reason):
        for delay_seconds in (0.4, 1.2):
            time.sleep(delay_seconds)
            with self._lock:
                if self._lease_count > 0 or not self._restore_pending:
                    self._log.debug(
                        "_fallback_restore_verify early exit at %.1fs "
                        "(lease_count=%d restore_pending=%s reason=%s)",
                        delay_seconds, self._lease_count, self._restore_pending, reason,
                    )
                    return
            observed = self._safe_get_volume(default=None)
            self._log.debug(
                "_fallback_restore_verify delay=%.1fs target=%.2f observed=%s reason=%s",
                delay_seconds, target, f"{observed:.2f}" if observed is not None else "None", reason,
            )
            if observed is None:
                continue
            if abs(observed - target) <= self._tolerance:
                with self._lock:
                    self._restore_pending = False
                return
            self._log.warning(
                "Volume verify detected mismatch (target=%.2f observed=%.2f). Re-applying.",
                target,
                observed,
            )
            self._safe_set_volume(target, reason=f"{reason}:verify_reapply")

    def _safe_get_volume(self, default=None):
        try:
            return self._get_volume()
        except Exception:
            self._log.error("Volume read failed", exc_info=True)
            return default

    def _safe_set_volume(self, value, reason):
        try:
            self._set_volume(value)
        except Exception:
            self._log.error("Volume set failed (%s)", reason, exc_info=True)

    def _start_restore(self, target, reason, *, async_set, thread_name):
        if target is None:
            return

        if async_set:
            def _run():
                self._safe_set_volume(target, reason=f"{reason}:initial_restore")
                self._fallback_restore_verify(target, reason)

            threading.Thread(
                target=_run,
                daemon=True,
                name=thread_name,
            ).start()
            return

        self._safe_set_volume(target, reason=f"{reason}:initial_restore")
        threading.Thread(
            target=self._fallback_restore_verify,
            args=(target, reason),
            daemon=True,
            name=thread_name,
        ).start()

    def _snapshot_state_unlocked(self):
        return {
            "lease_count": self._lease_count,
            "restore_target": self._restore_target,
            "restore_pending": self._restore_pending,
            "last_reapply_ts": self._last_reapply_ts,
            "history_size": len(self._history),
        }

    def _record_sample(self, reason, value):
        now = time.time()
        with self._lock:
            cutoff = now - self._history_window_seconds
            while self._history and self._history[0]["ts"] < cutoff:
                self._history.popleft()
            self._history.append({"ts": now, "value": value, "reason": reason})

    def _callback_worker(self):
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except Exception:
            self._log.error("Volume callback COM initialization failed", exc_info=True)
            self._callback_ready.set()
            return

        try:
            self._endpoint_devices = AudioUtilities.GetSpeakers()
            self._endpoint_interface = self._endpoint_devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self._endpoint_volume = cast(
                self._endpoint_interface, POINTER(IAudioEndpointVolume)
            )
            self._endpoint_callback = _EndpointCallback(self)
            self._endpoint_volume.RegisterControlChangeNotify(self._endpoint_callback)
            self._log.info("Volume endpoint callback registered")
        except Exception:
            self._log.warning(
                "Volume endpoint callback unavailable; lease manager uses verify fallback",
                exc_info=True,
            )
        finally:
            self._callback_ready.set()

        self._stop_event.wait()

    def stop(self):
        self._stop_event.set()
