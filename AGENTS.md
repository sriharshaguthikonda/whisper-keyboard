# Agent rules for whisper-keyboard

## Input-chain coordination (MANDATORY)

Hotkeys reach this app as synthetic function keys emitted by EXTERNAL remappers.
Any hotkey change must be coordinated across ALL of these, in the same change set:

| Layer | Where | Notes |
|---|---|---|
| Kanata | `C:\Tools\kanata-runtime-repo\vd-toggle.kbd` | Runs on every machine (SSD roams laptop/desktop). Validate with `--check` before restart; restart kanata to apply. |
| HID Remapper | Hardware dongle, configured via its web UI | Desktop ONLY (pass-through keyboard lives there). Agent cannot edit it — post exact mapping instructions in `Q and A.md` for the user. |
| App hotkey profiles | `wkey/settings_manager.py` `DEFAULT_HOTKEY_PROFILES` + `wkey/transcription_config.json` | pynput listener consumes the synthetic keys. |
| Tests | `tests/test_settings_manager.py`, `tests/test_keyboard_shortcuts.py` | Keep trigger assertions in sync. |
| Docs | `README.md`, `docs/ROADMAP.md` | Hotkey table. |

Current triggers:
- `d+f` hold (Kanata chord, 100ms) → **F23** → dictation/paste
- backtick hold (HID remapper / legacy) → **F24** → command/tool-use
- `s+d` hold (Kanata chord, 100ms) → **F13** → ask-AI (ChatGPT/AI pathway)

## Other standing rules
- Rust broker (`native/wkey-broker`) is RETIRED. Do not wire anything to it.
- Entry points: `..\Whisper.bat` → `Start-WhisperKeyboard.bat` → `scripts/Start-WhisperKeyboard.ps1` (also the scheduled-task action, hidden). Keep all paths `%~dp0`/script-relative — the SSD moves between machines.
- Never kill the user's running dictation instance during tests.
- Runtime logs/lock: `%LOCALAPPDATA%\WhisperKeyboard\runtime`.
- Q&A protocol: communicate in `C:\Windows_software\openai whisper\Q and A.md` (live channel); archives in `docs/qa-archive/`.
- Small commits, push after green tests (`..\openai\Scripts\python.exe -m pytest tests -q`).
