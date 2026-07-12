# ChatGPT review of P1 + P3 (2026-07-12)

Second-head review (ChatGPT, via model bridge) of the broker-retirement work,
reviewed against pushed commit `fa30763` (P1). Public-model review agreed on the
core points. Distilled to actionable items.

## Validated (no change needed)
- P1 singleton: the OS file lock — not the PID text — is the correct liveness
  oracle. Two launchers cannot both acquire byte 0; a named mutex / PID probe is
  NOT required (PID reuse makes probing less authoritative). Keep the lock in
  `%LOCALAPPDATA%` on a local FS; do NOT allow `WKEY_RUNTIME_DIR` to point at
  OneDrive/SMB/synced storage for the production singleton.
- P3 audio epoch/generation guard: correct and NON-optional. A recovery mutex
  serialises workers but does NOT stop an old PortAudio callback already in
  flight; the per-stream epoch guard (shipped in `8f25120`) is what prevents a
  stale callback from marking the new pipeline healthy or corrupting its buffer.
- Wiring `reset_state()` on resume is correct; replacing the no-op recovery fns
  (rather than layering) is correct.

## Fixed this session
- `tests/test_launcher_scripts.py` stale broker assertions vs the new installer
  (was a latent red branch) — corrected assertions committed.

## Release gates ChatGPT flagged (triage)

MUST before public release (deferred to a supervised/release pass):
- Lock: classify `OSError` — only retry on lock-contention errno; a bad
  descriptor/argument should be a fatal startup error, not "already running".
- Launcher: map duplicate-instance exit (Python exits when a live instance holds
  the lock) to exit 0 in the SCHEDULED launcher, else Task Scheduler retries a
  healthy duplicate 3x. Keep the nonzero code for interactive dev runs.
- Task privilege: `RunLevel HighestAvailable` -> `LeastPrivilege` for a mic +
  hotkey + paste app (tradeoff: least-privilege cannot paste into elevated
  windows — confirm with user which they want).
- Packaging: bundle a pinned Python runtime; do not fall back to arbitrary PATH
  python; launch a signed exe; per-user install under
  `%LOCALAPPDATA%\Programs\WhisperKeyboard`; remove `ExecutionPolicy Bypass` from
  the installed path; sign + timestamp; rotate `wkey-runtime.log` and
  `whisper-keyboard-startup.log` (currently grow unbounded).
- Resume signal: Win32 `PBT_APMRESUMEAUTOMATIC` as PRIMARY, monotonic-gap as
  fallback, callback-staleness as independent signal. The 20s gap threshold
  misses short suspends; the Win32 callback must only enqueue RECOVER and return.
- Audio health: add default-device IDENTITY monitoring (poll default input every
  2-5s, or `IMMNotificationClient`) IN ADDITION to callback-age — a dock/default
  mic switch keeps callbacks healthy on the OLD device, so the watchdog alone
  never switches.
- Session lock/unlock (`WTS_SESSION_LOCK`/`UNLOCK`): stop/pause mic + cancel
  recording + reset key state on lock; reopen on unlock. Do not silently capture
  while the workstation is locked.
- FOCUS-SAFE PASTING (ChatGPT: "may be more dangerous than the wake bug"):
  transcription is async and focus can change between key-release and paste.
  Capture foreground HWND/PID/title at recording end; before pasting, verify the
  same target still has focus. If changed: copy to clipboard + notify, do NOT
  auto Ctrl+V. Prevents a transcript landing in the wrong window/terminal.
- First-run mic onboarding: classic desktop apps use the global "let desktop
  apps access microphone" setting; distinguish permission-denied from no-device;
  open Windows mic privacy settings when blocked; show idle/listening/recording/
  processing/paused states; state plainly that audio goes to Groq.
- Crash reporting opt-in; exclude raw audio/transcript/clipboard/window-titles/
  API keys by default.
- Updater: signed releases, atomic install, rollback, don't replace files while
  running, settings separate from binaries.

Genuinely safe to defer (ChatGPT): formal lifecycle state-machine class; named
mutex; explicit PID-liveness; the Rust broker (P2); generation bookkeeping beyond
the one audio epoch; direct IMMNotificationClient IF default-device polling
exists; automatic crash upload; MSIX/Store; a formal 20-cycle certification gate.

## Hardware test matrix before public beta (ChatGPT)
5x sleep/resume, 3x hibernate/resume, dock/undock, default-mic switch, USB mic
unplug/replug, Bluetooth mic connect/disconnect, suspend during active dictation,
lock/unlock during active dictation, two simultaneous launches, 24h idle run.

Central rule: recovery SIGNALS may be duplicated or wrong; RECOVERY itself must
be serialized, idempotent, generation-safe, and component-local.
