# Native Hotkey Broker Design

## Summary

Build a separate native Windows hotkey broker workflow. The broker will eventually own keyboard hook state, stuck-key reset, and tray/supervision. Python remains the transcription engine: audio capture, Groq/Faster-Whisper fallback, transcript cleanup, paste, and command routing stay in Python.

Plan first, then implement phase by phase with small commits.

## Current Ground Truth

- Active repo root: `C:\Windows_software\openai whisper\whisper-keyboard`.
- Active branch: `refactor/clean-architecture`.
- Current manual hotkey path is Python `pynput.Listener` in `wkey/faster_whisper_Mother_of_all_wkey.py`, with state in `wkey/keyboard_shortcuts.py`.
- Current GUI/tray/settings live in `wkey/Whisper_GUI.py`.
- Current default is `f24,ctrl_l`; Left Ctrl release-alone dictates, any chord cancels.
- Left Ctrl is too noisy in practice, so the broker must not hardcode it.
- Rust toolchain is available (`rustc`/`cargo` 1.94.0); `cl` and `cmake` are not on PATH.
- No Rust/C++ scaffold exists in this repo yet.

## Architecture

Use Rust first. C++ remains fallback only if Rust low-level Win32 hook work hits a hard blocker.

The Python engine gets a narrow broker-control seam before native code controls anything. The seam accepts structured commands:

- `start` with route `dictation` or `command`
- `stop` with route `dictation` or `command`
- `cancel` with route and reason
- `status`
- `shutdown`

The first transport is JSONL over child-process stdio. Broker writes command JSON to Python stdin. Python emits only explicit status/event lines prefixed with `WKEY_CONTROL_EVENT ` so broker can ignore normal logs.

Long-term startup shape:

1. Windows scheduled task starts the Rust broker.
2. Broker starts Python in broker-control mode.
3. Broker owns manual keyboard hooks.
4. Python disables only its manual `pynput` listener in broker-managed mode.
5. Python still owns audio, transcription, paste, command routing, wake-word path, and settings.

## Hotkey Policy

Trigger profiles must be configurable:

- `f24`: command/tool-use route.
- `left_ctrl_release_alone`: current fallback profile, not assumed final.
- `d_f_hold`: experimental dictation profile.

`D+F` is not safe to make default blindly. Ordinary-letter chords can fire while typing and can damage normal text input if suppression/replay is wrong. The broker must ship diagnostic mode first:

- observe `D+F` timing without suppressing keys;
- log event type, timing, trigger decision, and cancel reason only;
- never log raw text, transcripts, or long key streams;
- switch `D+F` to active mode only after false-activation evidence is acceptable.

## Non-Goals

- Do not rewrite audio capture, Groq, Faster-Whisper, transcript cleanup, paste, or command routing in Rust/C++.
- Do not add broker config UI before hook and IPC reliability are proven.
- Do not run Python hotkeys and broker hotkeys long term.
- Do not expose a localhost control port unless stdio supervision proves unsuitable.
- Do not migrate the scheduled task until broker-managed smoke tests pass.

## Phases

1. Documentation and phase plan only.
2. Python broker-control seam and stdio transport behind explicit broker flags.
3. Rust console broker with pure trigger-state tests and diagnostic output.
4. Rust low-level Windows keyboard hook proof.
5. Broker starts/controls Python engine over stdio.
6. Broker-managed mode disables Python manual listener.
7. `D+F` diagnostic evaluation, then optional active profile.
8. Tray/supervision and scheduled-task migration.

## Acceptance Criteria

- Each phase has its own small commit.
- Existing Python hotkeys stay unchanged until broker-managed mode is explicitly enabled.
- Broker commands map to existing `start_recording`, `stop_recording`, and `cancel_recording` behavior without changing transcription pipeline semantics.
- Tests cover command parsing, idempotent dispatch, broker mode listener disabling, Rust trigger state, and broker/Python stdio handshake.
- After code changes, run focused tests, full tests where practical, `git diff --check`, and bounded primary-script smoke per repo instructions.
