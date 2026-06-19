# Whisper Keyboard Control Center V1

Date: 2026-06-18

## Scope

Build a Python Qt operator UI while keeping Python as the production runtime. Keep `wkey/Whisper_GUI.py` as the documented entrypoint and move new UI internals into smaller modules.

## Delivered Shape

- `wkey/control_center.py`: sidebar control-center UI.
- `wkey/control_center_state.py`: UI-independent settings snapshot/apply helpers.
- `wkey/backend_process.py`: backend status/process-control helpers.
- `wkey/settings_manager.py`: structured `hotkey_profiles` schema with legacy `record_keys` compatibility.

## V1 Sections

1. Dashboard
2. Hotkeys
3. Transcription
4. Voice Commands
5. Diagnostics
6. Startup
7. Logs

## Guardrails

- Do not store or edit API keys.
- Do not migrate the Windows scheduled task.
- Keep `D+F` diagnostic-only.
- Keep Rust broker experimental until diagnostic/runtime smoke proves it.
- Keep `record_keys` compatible with the current Python runtime.

## Verification

- Settings migration tests for old `record_keys` to `hotkey_profiles`.
- Backend process detection tests for command-line matching.
- UI-state tests for hotkeys and advanced settings.
- Full test suite.
- Required bounded primary runtime smoke for `wkey/faster_whisper_Mother_of_all_wkey.py`.
