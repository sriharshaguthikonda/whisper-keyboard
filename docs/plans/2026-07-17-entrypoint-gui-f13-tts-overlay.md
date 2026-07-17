# Whisper-Keyboard: startup fix, GUI fix, F13 ask-hotkey, TTS answers, cursor overlay, splits

Approved 2026-07-17. Execution: Claude orchestrates/reviews; Codex CLI implements; one phase = one atomic commit, pushed.

## REVISION 2026-07-17 (after re-reading repo Q&A history — supersedes Phase 1/3 broker details below)

Standing user-confirmed decisions from `Q and A.md` (2026-07-12): **Rust broker is retired**. Kanata (`C:\Tools\kanata`, vd-toggle.kbd) is the input owner — `d+f` chord → F23 (dictation), backtick hold → F24 (command); Python pynput catches the clean function keys. Scheduled task must be logon-only, IgnoreNew, no battery/idle stop, NO wake trigger, RestartOnFailure (wake-kill + stale-lock race was the proven killer — see 07-07 log in Q&A). In-app resume recovery already shipped (P3, `WKEY_RESUME_RECOVERY` default on). SSD roams between machines → all launchers stay `%~dp0`/script-relative, venv fallbacks kept.

**Phase 1 (revised):** converge every entry on the direct-python launcher.
- Root `Whisper.bat` → call `whisper-keyboard\Start-WhisperKeyboard.bat` (console mode). Delete `Start-WKeyBroker.bat` + `scripts/Start-WKeyBroker.ps1` (user-approved broker retirement; also unhooks Whisper.bat's broker delegation).
- Task installer (`Install-WKeyBrokerTask.ps1`, rename target action): `powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "…\scripts\Start-WhisperKeyboard.ps1"` — NO `-Console` so output goes to `whisper-keyboard-startup.log`; fully quoted (paths contain spaces); logon-only PT1M; remove any user-added hibernation-wake kill/restart trigger (explain in Q&A why: destructive wake-kill is the root cause fixed on 07-12; RestartOnFailure + in-app resume recovery replace it).
- Re-register task (may need elevation — if Access denied, give user the elevated one-liner via Q&A).
- Tests: launcher-script tests assert the direct-python action, hidden window, no `-Console`, quoting, and absence of wake trigger.

**Phase 3 (revised):** F13 ask-hotkey is **pynput-only — no Rust changes**. Python: `SUPPORTED_RECORD_KEYS['f13']`, route "ask" → keyword_index 4, `ask_ai` hotkey profile, `ask_hotkey_provider` setting, `clean_transcript` ask branch, GUI group — as detailed below, minus all `native/wkey-broker` items. `broker_control.py` route map addition optional 1-liner for compat. Kanata: user adds a physical mapping → F13 (we propose exact kbd snippet in Q&A; F13 works immediately for any device that can emit it).

**Phase 6 (extended):** physically delete `native/wkey-broker/` crate + dead broker branches/refs (inert since retirement) alongside the other cleanup. `cargo test` drops out of verification once deleted.

**NEW Phase 1.5 — untriggered-transcriptions investigation + logging identifiers** (user priority):
- History: rearm-delay fix (06-13), recovery-reset rearm preservation (06-14), PowerToys repeat fix (06-17) — user reports it STILL recurs.
- Leads: (a) Kanata d+f chord misfire while typing (chords-v2-min-idle 180ms); (b) multiple live backend instances (36 python processes seen 2026-07-17 — identify which run the mother script); (c) stale-lock reclaim races.
- Deliverables: log-mining report (wkey-runtime.log 36MB + voice_commands.log) via Codex; new logging identifiers on every recording start/stop: backend PID + session/start-time id, trigger key, `LLKHF_INJECTED` flag via pynput `win32_event_filter` (distinguishes Kanata-synthetic vs hardware key), route, and rearm/suppression state. Commit as its own small change.

## Context

User pain points (verbatim intent):
1. Task Scheduler PowerShell launcher never starts the app — only `Whisper.bat` works. Make `Whisper.bat` path THE entry point.
2. `Whisper_GUI.bat` doesn't open the GUI at all. GUI cramped, no scrollbars on small windows. Full tests wanted.
3. Dedicate a new function key (F13 if free — it is) to the ChatGPT/AI ask pathway.
4. Visual feedback overlay near cursor, quick fade, knobs in settings.
5. When answer comes via AI pathway (not ChatGPT browser pathway) → speak via TTS. Settings toggle.
6. Split god-files, human-readable code, everything adjustable in settings, production ready.

Repo: `C:\Windows_software\openai whisper\whisper-keyboard` (branch `feature/ask-ai-voice`, dirty ask-ai WIP). Outer folder holds `Whisper.bat`/`Whisper_GUI.bat` + `openai` venv (has PyQt6, tkinter, edge_tts, pyttsx4; no qtpy/watchdog).

**Root causes found (verified):**
- Scheduled task `Whisper` runs `Start-WhisperKeyboard.bat` → forces `-Console` → no console exists in a scheduler logon session → output vanishes, 0-byte log, `LastTaskResult=0xC0000005`. It's also the direct-python path, which the broker's `Stop-ExistingWKeyProcesses` kills — two mechanisms fight. Working path: root `Whisper.bat` → `Start-WKeyBroker.bat` → `scripts\Start-WKeyBroker.ps1` (supervised Rust broker, logs to `%LOCALAPPDATA%\WhisperKeyboard\runtime\wkey-broker-startup.log`).
- GUI bat runs `Whisper_GUI.py` (981 lines of legacy import minefield: unguarded `keyboard`/win32/PyQt6/`settings_manager` imports that must all succeed before line 1064 finally delegates to `control_center.main()`), zero logging → silent death.
- `control_center.py`: `setMinimumSize(960,640)`, **no QScrollArea anywhere** → clipping.
- Broker `win_hook.rs` maps only VK_F23/F24; VK 0x7C (F13) free. `broker_control.py` routes `{"dictation": None, "command": 0}`; keyword_index 4 unused.
- TTS chain (edge-tts → Kokoro → pyttsx4, `TTS_queue` workers) already lives in runtime; `ask_ai` answer only pastes to clipboard (`ask_ai_bridge.py:333`).

## Execution model

- **Claude = orchestrate, plan, review only. Codex CLI agents implement** each phase (announce engine per chunk).
- Q&A protocol: progress + questions via `Q and A.md`; don't block on user.
- One phase = one atomic commit; phase pytest subset + full suite (+ `cargo test` for Rust phases) before each commit.
- ChatGPT design pass: DONE via model_bridge (verdict `CONCERNS: 4`; refinements folded in below, marked **[GPT]**).
- Paths contain a space — always quote. Never touch `tests/conftest.py` stub ordering; new modules use the sibling dual-import pattern (`try: from .x import … except ImportError: from x import …`), heavy imports stay lazy.

## Phase 0 — Checkpoint WIP + green baseline
Commit current ask-ai WIP (modified files + untracked `tests/test_ask_ai_providers.py`, docs) as `wip: ask-ai voice checkpoint`. No logs/binaries (gitignore if needed).
**Verify:** `& $py -m pytest -q` green (baseline 196), `cargo test` green, tree clean.
(`$py = "C:\Windows_software\openai whisper\openai\Scripts\python.exe"`)

## Phase 1 — Scheduled task launches broker stack (fix #1)
Task and `Whisper.bat` converge on one launcher: `scripts\Start-WKeyBroker.ps1`.
- `scripts/Install-WKeyBrokerTask.ps1`: action → `powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "…\scripts\Start-WKeyBroker.ps1" --log`; fix post-install XML verification (currently checks the wrong script name).
- `scripts/Start-WKeyBroker.ps1` `Build-BrokerIfNeeded`: if cargo missing but exe exists → warn + run existing exe (logon sessions lack cargo on PATH); throw only when exe missing. **[GPT]** ensure child exit code + stderr land in the startup log on every death (broker already relays `python_stderr`; verify exit code is logged too).
- `Start-WhisperKeyboard.{bat,ps1}`: keep as manual debug launchers, header comment "NOT the scheduled-task path".
- Root `Whisper.bat`: unchanged (already delegates).
- `tests/test_launcher_scripts.py`: flip installer assertions to Start-WKeyBroker.ps1 + `--log` + `-WindowStyle Hidden`; assert Start-WhisperKeyboard.ps1 NOT registered; add cargo-fallback assertion.
**Verify:** launcher tests; run installer with `-RunAfterInstall`; `Get-ScheduledTask Whisper` action correct; `Get-Process wkey-broker`; tail broker startup log; manual F23 dictation smoke; one logoff/logon test.
**Risk:** 0xC0000005 was the python backend crashing at logon — broker relays `python_stderr` into its log, so recurrence finally leaves a stack trace (root-cause follow-up if it recurs; suspect sounddevice init at logon).

## Phase 2 — GUI opens reliably, scrollable, tested (fix #2)
- Outer `Whisper_GUI.bat`: launch `control_center.py` **directly** (skip Whisper_GUI.py minefield) via `start "" …\pythonw.exe` (no console) **[GPT]**; `control_center.main()` configures file logging to `%LOCALAPPDATA%\WhisperKeyboard\runtime\gui-startup.log` first thing. New `Whisper_GUI_debug.bat`: `python.exe` + full console + `pause` on error — catches import-time crashes the normal bat can't **[GPT]**.
- `wkey/control_center.py`:
  - `_scroll(widget)` helper → `QScrollArea(setWidgetResizable=True, NoFrame)`; wrap all 7 `self.stack.addWidget(...)` pages; grep `stack.widget(`/`currentWidget()` users and unwrap via `.widget()` (check `_set_section` ~:639).
  - `setMinimumSize(960,640)` → `(640,480)`.
  - Persist/restore window geometry via `QSettings("WhisperKeyboard","ControlCenter")`; on restore, if geometry doesn't intersect any available screen → center on primary (monitor/DPI changes) **[GPT]**.
  - Single-instance guard (`QLockFile` in runtime dir) so two GUIs can't write settings simultaneously; second launch just activates/exits **[GPT]**.
- `tests/test_control_center.py`: every stack page is QScrollArea with non-None inner widget; min size ≤ 640×480; resize(700,500)+show doesn't raise.
**Verify:** control-center tests; double-click bat → opens; shrink window → scrollbars, nothing clipped; break PyQt6 temporarily → bat shows log instead of vanishing.

## Phase 3 — F13 hold-to-ask pathway (broker + pynput, end to end)
Hold F13 → speak → release → transcript goes straight to ask pathway (bypasses Groq command router).
- Rust `native/wkey-broker/src/`:
  - `protocol.rs`: `EngineRoute::Ask` (serializes `"ask"`), extend serialization test.
  - `win_hook.rs`: `VK_F13=0x7C` → `BrokerKey::F13` in `map_vk_to_key` + test.
  - `triggers.rs`: `BrokerKey::F13`; label parser `"f13"`; `TriggerConfig.f13_ask: bool` default **true** (broker often runs without profiles env; python still gates via `ask_ai_enabled`); press/release → start/stop `Ask` (mirror F24 block); `trigger_bindings_from_profiles_json` add `("ask_ai", Ask)`; inline tests.
- Python:
  - `wkey/broker_control.py`: route map + `"ask": 4`.
  - `wkey/settings_manager.py`: `"f13"` in key-label normalization + supported labels; `DEFAULT_HOTKEY_PROFILES` add `ask_ai` profile (trigger `f13`, action `ask_ai`, enabled); `normalize_hotkey_profiles` allow action; `trigger_routes_from_hotkey_profiles` → `"ask"`; new setting `ask_hotkey_provider: "chatgpt"` (`"chatgpt"|"ai"`, whitelist-validated).
  - `wkey/faster_whisper_Mother_of_all_wkey.py`: `SUPPORTED_RECORD_KEYS['f13']=Key.f13`; `ASK_KEYWORD_INDEX=4`; `map_key_to_keyword_index` route `"ask"`→4; `clean_transcript` branch before `(0,1)` check: if index 4 and `is_ask_ai_enabled()` → daemon-thread `_dispatch_ask_hotkey(question)` (reads `ask_hotkey_provider`; `"ai"`→`ask_ai_bridge.ask_ai`, else `ask_chatgpt` which already honors fallback); ask disabled → paste like dictation; `_record_recent_transcript` source_map `4:"ask"`. **[GPT]** on chatgpt→ai fallback, surface it (overlay toast "ChatGPT unavailable — using AI provider" once Phase 5 lands; log until then) and keep one total deadline across claim-wait + fallback.
  - GUI: hotkeys section auto-renders new profile; add "Ask AI" QGroupBox in voice-commands section (`ask_ai_enabled`, `ask_hotkey_provider` combo, `ask_chatgpt_fallback_to_ai`, `ask_chatgpt_claim_timeout_sec`); register fields in `control_center_state.py`.
- Tests: rust inline; `test_broker_control.py` route "ask"→start(4); settings tests (f13 normalize, profile default, route mapping, provider validation); keyword-index test F13→4; pipeline test feeding `(transcript, 4)` with `ask_ai_bridge` monkeypatched → ask called, command router NOT called; disabled → paste.
**Verify:** `cargo test`; pytest subsets + full; manual: enable ask_ai, restart backend, hold F13, ask question → answer arrives.

## Phase 4 — Speak ask_ai answers via existing TTS
Only for direct-provider path (incl. chatgpt→ai fallback); never for browser-claimed ChatGPT jobs.
- `settings_manager.py`: `ask_ai_tts_enabled: True` (bool), `ask_ai_tts_max_chars: 400` (int, 0=unlimited).
- `ask_ai_bridge.py`: module attr `tts_speaker=None` (injected callable — avoids importing the 3170-line backend); after paste at :333 → `_maybe_speak(result.answer)` (gate on setting; try/except-log). **[GPT]** `_prepare_speech(text)`: strip markdown/code blocks/long URLs, truncate at sentence boundary near `ask_ai_tts_max_chars` + "…" — pure function, tested.
- `faster_whisper_Mother_of_all_wkey.py`: at TTS worker startup inject `ask_ai_bridge.tts_speaker = <enqueue fn>` — grep `TTS_queue.put(` call sites first, mirror exact payload shape. **[GPT]** each speak carries a generation id; new F13 press bumps generation → cancels/ignores stale speech (late edge-tts failure must not trigger Kokoro over a newer answer). Implement as a simple module-level counter checked at dequeue.
- GUI: two fields into Ask AI group + state registration.
- Tests (`test_ask_ai_bridge.py`): spoken when enabled (truncated), silent when disabled, silent on chatgpt-claimed path, speaker exception doesn't break return; settings validation.
**Verify:** pytest subsets; manual: provider="ai", F13 question → pasted AND spoken; toggle off → silent.

## Phase 5 — Cursor-adjacent feedback overlay (net-new, stdlib only)
- **New** `wkey/overlay_notify.py` (~130 lines): `notify(text, kind="info")` — thread-safe, never raises. Lazy daemon thread owns withdrawn `tk.Tk` root + `queue.Queue`; ALL tk calls on that thread (docstring enforces). Toast = `Toplevel` `overrideredirect` + topmost + alpha, positioned at `winfo_pointerx/y + offset` clamped to monitor work area; hold `overlay_duration_ms` then alpha-fade in ~10 `.after` steps; new message replaces current (never stacks). Settings read per notify (live-apply free). tkinter import guarded → headless no-op. **[GPT] critical:** after creating the toplevel, set Win32 ex-styles on its hwnd via pywin32 (in venv): `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED` (+`WS_EX_TRANSPARENT` for click-through), show without activation — the toast must NEVER steal focus (worst possible bug in a keyboard tool). pywin32 import guarded like tkinter. Pure helpers `_format(text,80)` / `_gate(settings)` for tests. `# ponytail: tkinter toast; upgrade to win32 layered window if click-through ever needed`.
- `settings_manager.py`: `overlay_enabled: True`; `overlay_duration_ms: 1500` (200–10000); `overlay_opacity: 0.85` (0.2–1.0, float pattern per `speaker_filter_threshold`); `overlay_font_size: 11` (8–24); `overlay_offset_px: 24` (0–200).
- Call sites (one-liners): backend — recording start per route ("Listening — dictation/command/ask"), pasted ("Pasted: <40 chars>…"), command dispatched, transcription/audio errors (kind="error"), cancelled. `ask_ai_bridge` — "ChatGPT answering…", "AI answered", unclaimed failure (error).
- GUI: "Overlay" QGroupBox (diagnostics section) with 5 knobs + state registration.
- Tests: new `tests/test_overlay_notify.py` (_format truncation, _gate, no-tkinter no-op); clamping in settings tests. No real-window tests; manual smoke.
**Verify:** pytest; manual: dictate → toast near cursor, fades; change duration/opacity in GUI → next toast reflects live; disable → gone.

## Phase 6 — Conservative splits + cleanup + docs
- **New** `wkey/tts_engine.py`: move TTS queues/workers/`text_to_speech`/edge/Kokoro/pyttsx4 (~300 lines) out of backend; lazy provider imports preserved; dual-import; backend imports from it; Phase-4 injection + generation-id cancel move with it. **[GPT]** public surface stays narrow: `speak(text, request_id)`, `cancel()`, plus compatibility re-imports in the backend module. Grep `TTS_` in tests/ first.
- `wkey/Whisper_GUI.py` → ~10-line shim delegating to `control_center.main()` (nothing imports it; bat bypasses it after Phase 2; check `whisper_keyboard.spec` refs first). ~970 lines gone.
- `wkey/Settings_GUI.py`: **delete** (user confirmed; unwired parallel WIP; control_center owns settings; recoverable from git).
- **No** voice_commands.py / commands_and_tools.py split this round — no cohesive seam, conftest stubs make it riskiest touch. YAGNI, revisit on need.
- Docs: README/ROADMAP — entry points (Whisper.bat→broker, task installer), F13 ask hotkey, new-settings table.
**Verify:** full pytest + cargo test; manual full smoke (dictation, F13 ask, TTS, overlay).

## New settings keys (all in DEFAULT_SETTINGS, validated, GUI-exposed)

| Key | Default | Phase |
|---|---|---|
| `ask_hotkey_provider` | `"chatgpt"` (user confirmed; `"ai"` selectable) | 3 |
| `ask_ai_tts_enabled` | `True` | 4 |
| `ask_ai_tts_max_chars` | `400` (0 = unlimited) | 4 |
| `overlay_enabled` | `True` | 5 |
| `overlay_duration_ms` | `1500` (200–10000) | 5 |
| `overlay_opacity` | `0.85` (0.2–1.0) | 5 |
| `overlay_font_size` | `11` (8–24) | 5 |
| `overlay_offset_px` | `24` (0–200) | 5 |

Plus hotkey profile `ask_ai` (trigger `f13`) in `DEFAULT_HOTKEY_PROFILES` — its `enabled` flag = user-facing on/off for the key.

## Verification (end-to-end)
1. `& $py -m pytest -q` — all green (196 baseline + new).
2. `cargo test --manifest-path native\wkey-broker\Cargo.toml` — green.
3. Re-run task installer; logoff/logon → broker auto-starts, F23 dictation works, log has evidence.
4. `Whisper_GUI.bat` → Control Center opens; shrink to 700×500 → scrollbars.
5. F13 → ask question → answer pasted (+ spoken if provider=ai & TTS on) + overlay toast.
6. Every new knob visible + functional in Control Center; changes apply without restart where the setting is live-watched.
