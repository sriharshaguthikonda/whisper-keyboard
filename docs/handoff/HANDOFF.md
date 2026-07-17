# HANDOFF

---

## 2026-07-13T06:50:28+05:30 — Launcher venv fix; app verified running end-to-end

### State
Reliability core (P1+P3) shipped earlier. This session: user reported "powershell
starts and disappears / whisper bat feels like broker." Root-caused + fixed +
VERIFIED the app actually runs. All pushed to `feature/ask-ai-voice`.

### What was wrong + fix (commit 05d8761)
- Bug: `scripts/Start-WhisperKeyboard.ps1` fell back to bare PATH python
  `C:\Python312` (no `groq`) -> app crashed on `import groq`, window vanished.
- Fix: resolve the REAL venv `C:\Windows_software\openai whisper\openai\Scripts\python.exe`
  (repo-parent + `openai\Scripts`, same interpreter the old broker used at
  engine.rs:41). Order: `$env:WKEY_PYTHON` -> repo `.venv` -> parent `openai` venv
  -> PATH python ONLY if it imports groq -> else throw. Added double-click
  `Start-WhisperKeyboard.bat` (repo root) running the ps1 in -Console mode.
- "whisper bat = broker" confusion: only `Start-WKeyBroker.bat` (OLD broker)
  existed; user ran that. Now there's `Start-WhisperKeyboard.bat` (direct).

### VERIFIED (ran the app 35s with the venv)
Healthy boot, stayed alive, no crash (faulthandler didn't grow):
`wkey is active. Enabled manual keys: F24,F23` / `recovery_policy=in_app` /
`Startup background threads: WakeWordListener,AudioRecovery,ResumeAudioWatchdog,...`
/ `Listening for wake words`. Runtime log now at
`%LOCALAPPDATA%\WhisperKeyboard\runtime\wkey-runtime.log` (NOT repo `logs/`).

### Gotchas / open
- App came up PAUSED via leftover `wkey\voice_pause_flag.txt`. Unpause:
  Ctrl+Alt+Shift+ScrollLock, or delete the flag. If app "looks dead" it may be paused.
- Offered user: make the .bat start hidden/minimized (background, no console) for
  daily use; and clear the stale pause flag. AWAITING user answer.
- Still open from prior section: RunLevel decision (HighestAvailable vs LeastPrivilege);
  user hardware sleep/wake test; P2 broker deletion (supervised); release gates.
- Live scheduled task "Whisper" already re-registered -> Start-WhisperKeyboard.ps1 (good).

### Commands
- Start app (test): `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Start-WhisperKeyboard.ps1 -Console`
  or double-click `Start-WhisperKeyboard.bat`.
- Correct python: `"C:/Windows_software/openai whisper/openai/Scripts/python.exe"`.
- Last commits: 05d8761 (launcher fix), b4f2b5a, 8f25120 (P3), fa30763 (P1). All pushed.

---

## 2026-07-12T22:34:38+05:30 — Broker retirement P1+P3 shipped

### Current task state
Retiring the redundant Rust `wkey-broker` and fixing the years-long sleep/wake
"dictation dies" bug. **Reliability core done, tested, reviewed, pushed.**
Branch `feature/ask-ai-voice`. Autonomous work PAUSED pending user hardware test
+ one decision. Goal elevated by user: make production-ready + release as an app.

### Key decisions
- Root cause = NOT the Rust hook. Kanata (`C:\Tools\kanata\windows-binaries-x64`,
  autostart, running) already emits the triggers: `(d f)` chord -> F23 dictation,
  hold-backtick -> F24 command. `input_owner` defaults to `python`. Broker redundant.
- Q1 Kanata installed (confirmed). Q2 chord suppression lives in Kanata -> Option A
  (delete broker), NOT option B (Rust bridge). Q3 abandon-in-place (no history rewrite).
- Recovery: layered/minimal, NOT the over-engineered `docs/Recovery_methods.txt`
  rewrite. External scheduler fix + stale-lock reclaim + lean in-app resume recovery.
- Both AI heads (public gpt-oss-120b + ChatGPT) validated; confirmed the audio
  generation/epoch guard is non-optional.

### Modified files (COMMITTED, pushed)
- `scripts/Install-WKeyBrokerTask.ps1` — task fixed (logon-only, IgnoreNew,
  StopIfGoingOnBatteries=false, StopOnIdleEnd=false, RestartOnFailure, repointed).
- `scripts/Start-WhisperKeyboard.ps1` — NEW direct-python launcher (no broker).
- `wkey/faster_whisper_Mother_of_all_wkey.py` — stale-lock reclaim + P3 recovery.
- `tests/test_faster_whisper.py`, `tests/test_resume_recovery.py` (NEW),
  `tests/test_launcher_scripts.py` — tests.
- `docs/superpowers/plans/2026-07-12-P3-resume-recovery-and-release-readiness.md`,
  `docs/superpowers/reviews/2026-07-12-chatgpt-p1-p3-review.md` — design + review.

### Modified files (UNCOMMITTED — user's Ask-AI WIP, DO NOT TOUCH)
`wkey/commands_and_tools.py` (+592), `wkey/Settings_GUI.py`,
`wkey/settings_manager.py`, `wkey/transcription_config.json`,
`wkey/direct_sd_to_transcribe.py`, `wkey/ask_ai_bridge.py`,
`tests/test_ask_ai_bridge.py`, `tests/test_voice_command_tools.py`,
`tests/test_ask_ai_providers.py`, `scripts/Start-WKeyBroker.ps1`,
`docs/ROADMAP.md`, `Q and A.md`, + 2 untracked stale planning docs.

### Blockers / open questions
- USER DECISION: scheduled-task `RunLevel` = keep `HighestAvailable` (can paste
  into elevated apps) vs `LeastPrivilege` (safer, cannot). Then flip installer.
- Needs USER hardware test (can't sleep the machine from here).
- Leftover `wkey-broker.exe` pid 17036 still running from before — user should kill.

### Next steps
1. User re-registers task: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Install-WKeyBrokerTask.ps1`, kills `wkey-broker.exe`, sleep/wake tests.
2. On user go: P2 (delete `native/wkey-broker`, `wkey/broker_control.py`, ~30
   broker-mode branches, broker launcher scripts) — supervised (touches WIP + live runtime).
3. Release gates (review doc): focus-safe paste guard (HIGH; touches WIP
   `commands_and_tools.py`), Win32 resume notification, default-device monitoring,
   session-lock mic-pause, packaging/signing/log-rotation, mic-consent onboarding.

### Critical context
- Communicate via `Q and A.md` (root `C:\Windows_software\openai whisper\Q and A.md`),
  NOT cloud popups — user watches it; pre/post-tool hooks inject `[Q&A CHANNEL]`.
- Codex CLI: ChatGPT-account rejects ALL `*-codex` model names; only
  `gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna` work; Windows needs
  `sandbox=danger-full-access` (workspace-write blocks writes). Do NOT brute-force
  model names inline — delegate or beep the user.
- ChatGPT model bridge flags `F23`/`F24` as ICD-10 codes -> `medical_identifier`
  refusal; refer to them as function-key triggers when prompting ChatGPT.
- `RESUME_RECOVERY_ENABLED` = env `WKEY_RESUME_RECOVERY` (default on); OFF restores
  old external_restart no-op behavior. `RUNTIME_LOCK_PATH` line 274;
  `acquire_runtime_singleton` ~3351; `audio_callback` ~1456; recovery module
  `wkey/faster_whisper_Mother_of_all_wkey_recovery.py` (ResumeGapDetector).

### Model summary
- Rust broker was a 5-layer chain that ate itself on wake; retired in favor of Kanata + python pynput.
- P1 (fa30763): scheduler no longer destructive on wake + stale-lock reclaim + direct launcher.
- P3 (8f25120): in-app audio/keyboard resume recovery behind a default-on toggle, with generation-guarded callbacks.
- b4f2b5a: fixed a red branch (committed installer vs old launcher tests) + saved ChatGPT review.
- 69 tests pass across the three touched test files.
- Only retirement files were staged; user's Ask-AI WIP left uncommitted and untouched.
- Public model + ChatGPT both reviewed; approach validated, release gates enumerated.
- Deferred P2 (inert cleanup) and release-engineering by judgement while user away.
- Kanata config: `C:\Tools\kanata\windows-binaries-x64\vd-toggle.kbd`.
- User goal: production-ready, release as an app.

### Handoff context (actionable)
1. `cd "C:/Windows_software/openai whisper/whisper-keyboard"` (Git Bash; forward slashes).
2. Test: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_faster_whisper.py tests/test_resume_recovery.py tests/test_launcher_scripts.py -q` -> expect 69 passed.
3. Branch `feature/ask-ai-voice`; last 3 commits fa30763, 8f25120, b4f2b5a; pushed to origin.
4. NEVER stage the Ask-AI WIP files listed above into retirement commits.
5. Read `Q and A.md` first each turn; reply in it, proactively, don't block on popups.
6. Codex: use `mcp__codex-cli__codex` with `model=gpt-5.6-sol`, `sandbox=danger-full-access`; review its output, don't trust its summary (it deviates on file names/placement).
7. Verify codex diffs with `git --no-pager diff -- <files>` and re-run tests independently.
8. P2 broker delete: `native/wkey-broker/` (Rust crate, nothing Python imports it),
   `wkey/broker_control.py` (imported at line 142 via run_control_stdio — guard/remove),
   broker-mode branches gated by `WKEY_INPUT_OWNER=broker`, `wkey/control_center.py` broker ref.
9. Do NOT delete/reregister the live scheduled task or kill processes without user OK (system changes).
10. Release review + gates: `docs/superpowers/reviews/2026-07-12-chatgpt-p1-p3-review.md`.
11. Focus-safe paste (release-critical): capture foreground HWND/PID at record-end; before paste verify same target has focus, else clipboard+notify (touches WIP commands_and_tools.py — coordinate with user).
12. Memory saved: mem_20260712_whisper-keyboard-broker_8eaf5a (state), mem_20260712_feedback-2026-07-12-whis_2dea03 (codex lesson).
13. Two stale planning docs (`2026-07-12-input-owner-simplification-design.md`, `-broker-retirement-git-strategy.md`) have a WRONG "zero Kanata trace" claim — corrected in Q&A + P3 doc; update or leave.
14. ChatGPT bridge job id for this review: `20260712T071932Z_6d60c807ff00527d` (already fetched).
