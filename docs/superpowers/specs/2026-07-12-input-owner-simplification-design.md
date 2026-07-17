# Input-Owner Simplification (Rust Broker Retirement) — Design

Status: DRAFT — planning only. Recommended direction below; three decisions
(Q1–Q3) are still open in `Q and A.md` (2026-07-12 section). No code until they
are answered and the approach is approved.

Supersedes the reliability goals of
`docs/superpowers/specs/2026-06-18-native-hotkey-broker-design.md`. That design
is now treated as a wrong turn for the reliability problem; see "Why the broker
is being retired".

## Summary

Stop making a native process own, start, and supervise the Python engine.
Move low-level key handling OUT to an external remapper that emits clean
function keys, and let the existing Python `pynput` listener catch them:

```
physical keys / chords -> [external remapper] -> F23 / F24 -> Python Whisper Keyboard
```

One low-level input owner. One application process. One startup owner (a
logon-only scheduled task). Windows resumes the process across sleep; Python's
own mic/stream recovery handles device changes. No wake-kill, no PowerShell
restart loop, no Rust→Python stdio, no 5-second reply timeout, no competing
runtime-lock ownership.

## Why the broker is being retired (confirmed root cause)

The Rust keyboard hook is not what dies. The five-layer chain fights itself on
wake:

`Scheduler(wake-kill) -> Start-WKeyBroker.bat -> PowerShell supervisor -> Rust broker -> Python -> runtime lock`

Observed wake failure (Q&A log, 2026-07-07, ~lines 1003–1049):

1. Wake fires the scheduled task.
2. Task kills the old python + wkey-broker (`MultipleInstancesPolicy=StopExisting`).
3. New broker starts a new python.
4. Python sees a stale `wkey_runtime.lock (pid=unknown)` still held → "Another
   Whisper Keyboard backend is already running. Exiting."
5. Broker's event channel disconnects → "python event channel disconnected while
   child was still running" → exit 1.
6. PowerShell retries with backoff 5 times, then gives up. Dictation stays dead
   until manual restart.

Three code-level faults confirmed:

- `scripts/Install-WKeyBrokerTask.ps1`: `StopExisting` +
  `StopIfGoingOnBatteries=true` + a wake `EventTrigger`
  (Microsoft-Windows-Power-Troubleshooter, EventID 1) alongside the logon
  trigger. Wake = kill-and-restart by design; on-battery = stop by design
  (wrong for a ThinkPad). This is the user's 2026-06-15 scheduled-task change.
- `native/wkey-broker/src/main.rs:292`:
  `engine.recv_event_timeout(Duration::from_secs(5))?` — any slow Python reply
  (mic reopen, audio-driver delay, volume op, lock wait, slow `stop_recording`)
  kills the broker. Python also does the work synchronously before replying, so
  there is no early ack.
- The Rust "supervisor" (`BrokerSupervisorPolicy`) never restarts Python. On
  Python exit, `ensure_engine_live()` returns an error and the broker exits.
  PowerShell (5 retries) is the real supervisor.

Stale-lock race = proximate killer. Wake-kill = repeated trigger.

The broker's only genuinely-valuable job was low-level suppression of
letter-chords (e.g. `D+F`) while typing. A clean function-key trigger does not
need a suppressing hook, so that value disappears once triggers are F23/F24.

## Options (decision pending Q1/Q2)

| Opt | What | Trade-off | Recommendation |
|---|---|---|---|
| A | Delete broker. External remapper (Kanata or PowerToys) emits F23/F24; Python catches them. | Lowest code. One external dep to maintain. | **Recommended** if a remapper already emits F23/F24 reliably |
| B | Keep a tiny Rust input-only bridge: low-level hook → `SendInput` F23/F24. No Python ownership, no stdio, no supervision. | Keeps a Rust binary + a second process to launch. No external dep. | Fallback if no external remapper is acceptable |
| C | Keep broker, fix the three faults. | Retains most code and most fragility. | Rejected (ChatGPT concurs) |

Both A and B converge on: **something emits F23/F24, Python catches them.** The
difference is only what emits them.

## Target architecture

- **Input owner:** external remapper (A) or input-only Rust bridge (B).
  - F23 → dictation/paste route.
  - F24 → command/tool-use route.
- **Application:** unchanged Python engine — audio capture, Groq/Faster-Whisper
  fallback, transcript cleanup, paste, command routing, wake-word path,
  settings, speaker filter, Ask-AI. Python's `pynput` listener owns F23/F24
  (input-owner = python).
- **Startup:** one logon-only scheduled task launching the Python engine
  directly (via `Whisper.bat`).
- **Sleep/resume:** rely on Windows resuming the process; Python's existing mic
  and stream recovery handles device churn. Optional in-app supervision toggle
  (below) replaces the external kill/restart.

## Scheduler + in-app supervision fix (applies regardless of A/B/C)

Independent of the broker decision, the startup path must change:

- Scheduled task settings → `MultipleInstancesPolicy: IgnoreNew`,
  `StopIfGoingOnBatteries: false`, `DisallowStartIfOnBatteries: false`, remove
  the wake `EventTrigger`, keep **logon trigger only**.
- Retire the "kill old instances then restart" behavior in the launcher.
- Move sleep/resume health into the app behind a settings toggle (user request,
  2026-07-07: "inbuilt, behind a toggle, not this complicated bat and
  scheduler"). A single owning process that self-heals on resume, guarded by a
  PID-validated runtime lock, replaces the external StopExisting churn.
- Fix the runtime lock so a stale `pid=unknown` lock from a dead process is
  reclaimed instead of blocking a fresh start (defensive even after the
  wake-kill is gone).

## Broker retirement surface (current tree)

Bounded and behind the input-owner flag — safe forward removal:

- `native/wkey-broker/` — whole Rust crate. Delete.
- `wkey/broker_control.py` — broker-only module. Delete.
- `wkey/faster_whisper_Mother_of_all_wkey.py` — 30 references: broker-mode
  branches gated by `WKEY_INPUT_OWNER=broker` and `run_control_stdio`. Set
  input-owner = python and remove the broker branches.
- `wkey/control_center.py` — one broker status reference. Un-wire / relabel.
- `scripts/Start-WKeyBroker.ps1`, `Start-WKeyBroker.bat`,
  `scripts/Install-WKeyBrokerTask.ps1` — delete or repoint to the direct
  Python launcher + logon-only task installer.

## Git strategy (decision pending Q3)

Broker code is spread across the Rust crate (pure), `broker_control.py`
(pure), broker-mode branches inside the shared main runtime, the launcher
scripts, and settings/runtime-path helpers. In history these are interleaved
with Control-Center, speaker-filter, and Ask-AI commits since `03edf96`
(pure-broker ≈ 4, mixed ≈ 6+, plus launcher-wiring commits that touch shared
scripts). Control-Center and activation code reference broker mode.

- **Recommended: abandon-in-place.** One forward commit (or a short series)
  that deletes the retirement surface above and repoints startup. Keeps all
  history, zero cherry-pick risk, same functional end state.
- **Alternative: clean-history rewind** to `03edf96` and cherry-pick only the
  non-broker commits. Higher effort and risk because of the interleaving and
  the shared-file entanglement; produces history that looks broker-free but no
  functional benefit. Only worth it if a broker-free history is explicitly
  wanted.

See `docs/superpowers/plans/2026-07-12-broker-retirement-git-strategy.md` for
the commit-level map (to be written once Q3 is answered).

## Phases (commit-by-commit; detail finalized after Q1–Q3)

0. Docs/spec/roadmap linkage (this doc + ROADMAP update). No code.
1. Scheduler + launcher fix: logon-only, IgnoreNew, no battery-stop, no wake
   trigger. Reclaim stale PID-unknown lock. (Applies even if broker kept.)
2. Input path: ensure Python `pynput` reliably catches F23 (dictation) and F24
   (command); confirm suppression/toggle behavior with clean function keys.
   For B: build the input-only Rust bridge (hook → `SendInput`), tests for
   trigger→keycode mapping only.
3. Retire broker wiring: set input-owner = python by default; remove broker-mode
   branches; delete `broker_control.py` and `native/` (A) or reduce `native/`
   to the input-only bridge (B).
4. In-app sleep/resume supervision behind a settings toggle; remove external
   kill/restart.
5. Cleanup: delete/relabel Control-Center broker status; delete dead launcher
   scripts; update tests and docs.

Each phase: focused tests, full suite where practical, `git diff --check`, and
bounded primary-script smoke, per repo instructions.

## Non-goals

- No rewrite of audio/STT/paste/command routing.
- No new localhost control port.
- No letter-chord default trigger unless Q2 explicitly asks for one (only then
  is a suppressing hook — option B — justified).
- No history rewrite unless Q3 explicitly asks for broker-free history.

## Acceptance criteria

- After sleep/hibernate + wake, dictation still works without any kill/restart.
- Going on battery does not stop the app.
- F23 dictates/pastes; F24 runs command/tool-use; no dependence on the Rust
  broker.
- No `wkey-broker.exe` in the startup path; no PowerShell restart loop.
- Stale `pid=unknown` runtime lock is reclaimed on a fresh start.
- Existing Python test suite still passes; broker-specific tests removed or
  repurposed.

## Open decisions (answer in `Q and A.md` 2026-07-12)

- Q1 — Is Kanata + Interception actually installed and emitting F23/F24 now, or
  is remapping only PowerToys today?
- Q2 — Are clean F23/F24 enough as permanent triggers, or is a letter-chord
  (D+F) still wanted (the only case needing option B's suppressing hook)?
- Q3 — Abandon-in-place (recommended) vs clean-history rewind for retiring the
  broker?
