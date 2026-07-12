# P3 Resume Recovery + Release Readiness

Status: DESIGN (2026-07-12). Follows shipped P1 (`fa30763`: non-destructive
scheduled task + stale-lock reclaim + direct-python launcher). Validated against
a public-model review; ChatGPT review pending.

## Why P3 is now necessary (not optional)

P1 stopped the scheduled task from killing+restarting the backend on wake. Good
— but the app still runs with `RECOVERY_POLICY = "external_restart"` (line
~1091) and every in-app recovery function is a no-op that logs `*_ignored` /
`*_disabled`. So P1 traded "killed on every wake" for "**survives wake but can
go deaf**": if the audio stream dies on resume, nothing reopens it. P3 supplies
the missing in-app recovery.

Kanata already emits the two function-key triggers at driver level; input owner
defaults to python. Broker is de-facto retired (nothing launches it). Physically
deleting `native/wkey-broker` + `wkey/broker_control.py` is P2 = low-priority
cleanup.

## P3 design (lean, conservative, behind a toggle)

Toggle: `RESUME_RECOVERY_ENABLED = os.environ.get("WKEY_RESUME_RECOVERY","1") ==
"1"` (default ON). OFF preserves today's behavior exactly.

1. **Callback-liveness, not `stream.active`.** Record `LAST_AUDIO_CALLBACK_TS =
   time.monotonic()` at the top of `audio_callback` (line ~1456). `stream.active`
   lies after resume; the last-callback age is the real oracle.
2. **Serialized recovery.** One lock; concurrent triggers coalesce into a single
   reopen. Replaces the stubbed `audio_recovery_worker` / `_perform_audio_recovery`.
3. **Audio watchdog thread.** Every ~5s, if enabled and audio is expected
   (recording or wakeword runtime on) and `now - LAST_AUDIO_CALLBACK_TS` > ~10s:
   fully stop+close the stream, then `initialize_input_stream()` (re-enumerates
   default device). Backoff 1/2/4s; on repeated failure log DEGRADED and keep
   retrying slowly. **Never kills the process.**
4. **Stale-callback guard (from review).** A late callback from the OLD stream
   must not corrupt the NEW one. Fully close before reopen (callbacks stop) +
   a generation counter the recovery bumps so an in-flight stale callback drops
   its frame. This is the one item promoted from "defer" — it's a real bug guard.
5. **Resume signal = existing `ResumeGapDetector`.** The watchdog ticks
   `.check()`; a detected monotonic gap (sleep/resume) proactively (a) calls the
   keyboard handler `reset_state()` (line ~2812) to clear phantom held keys and
   (b) requests an audio recovery. Wire `handle_resume_event` /
   `maybe_handle_system_resume` to this instead of logging `*_ignored`.
6. **Overflow burst** currently calls `request_broker_control_shutdown(...)`
   (line ~1479) — when enabled, route to an in-app audio recovery request instead.

## Review verdicts (public model, 2026-07-12)

- P1 singleton "retry OS lock, reclaim if it frees" is **production-adequate**;
  the OS lock guarantees no double-run. Optional hardening: read the recorded
  pid and `OpenProcess`/`GetExitCodeProcess` to give the racing loser a
  definitive answer instead of a spurious "already running". Not blocking.
- Generation-token guard on audio callbacks: **do it** (item 4 above).
- Monotonic-gap resume detector: enough for ~95%; Modern/Connected Standby keeps
  the clock ticking, but the callback-age watchdog is the safety net. Win32
  `RegisterSuspendResumeNotification` = deferrable latency improvement.
- Callback-age watchdog vs WASAPI device-change notification: ship both for
  release; watchdog catches "active but dead", `IMMNotificationClient` catches
  unplug/dock immediately. Device-change listener = **P3.1 follow-up**.

## Release-readiness checklist (the "release as an app" track)

Non-negotiable for v1:
- Singleton: file-lock + pid-liveness (done-ish; add pid check as hardening).
- Dual resume detection: ResumeGapDetector + audio callback-age watchdog (P3).
- Audio recovery: reopen with generation guard, drop stale callbacks (P3).
- Device-change listener (`IMMNotificationClient`) routing to the same reopen (P3.1).
- Microphone consent: detect `E_ACCESSDENIED`/`AUDCLNT_E_DEVICE_INVALIDATED`,
  show a clear "enable mic in Settings" prompt, persist consent flag.
- Per-user install only: HKCU + `%APPDATA%`/`%LOCALAPPDATA%`, no admin.
- Code-signed binaries + installer (SmartScreen/AV: global-hotkey + paste reads
  as keylogger-like without a signature).
- Elevated-window paste guard: check foreground window integrity level; skip
  paste + toast when target is higher-integrity (paste silently fails otherwise).
- Crash-report opt-in (stacktrace + OS only, never audio). Rotating diagnostic
  log (no raw audio).

Defer to v2: full Win32 suspend/resume API, auto-update infra, i18n chord
validation, low-power UI, accessibility/screen-reader integration.

## Constraints for implementation

- Do not touch the uncommitted Ask-AI WIP files or `scripts/Start-WKeyBroker.ps1`.
- Edit only `wkey/faster_whisper_Mother_of_all_wkey.py` +
  `wkey/faster_whisper_Mother_of_all_wkey_recovery.py`; new test files.
- Minimal + reversible; OFF toggle must preserve current behavior. Do not
  refactor the audio impl modules.
