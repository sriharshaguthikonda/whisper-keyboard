# Whisper Keyboard Current State And Roadmap

Generated: 2026-05-18

## Current Runtime Spec

Primary runtime: `wkey/faster_whisper_Mother_of_all_wkey.py`.

Entry points: `..\Whisper.bat` -> `Start-WhisperKeyboard.bat` -> `scripts\Start-WhisperKeyboard.ps1` (also the scheduled-task action, hidden). Paths stay `%~dp0`/script-relative since the SSD roams machines.

User-facing GUI: `wkey/Whisper_GUI.py` (thin shim, delegates to `wkey/control_center.py`).

Settings:

- `wkey/transcription_config.json`
- `wkey/settings_manager.py`

Activation surfaces (hotkeys arrive as synthetic function keys from an external remapper — Kanata or the HID dongle — see `AGENTS.md`):

- `d+f` hold (Kanata chord) -> `F23`: dictation/paste route.
- backtick hold (HID remapper / legacy) -> `F24`: command/tool-use route.
- `s+d` hold (Kanata chord) -> `F13`: ask-AI route, opt-in.
- Wake words: OpenWakeWord route through `wkey/wakeword.py`.

Runtime modes:

- `combined`: manual keys plus wake words.
- `keyboard`: manual keys only.
- `wakeword`: wake words only.

Mode-specific launchers:

- `wkey/faster_whisper_Mother_of_all_wkey_just_f24.py`
- `wkey/faster_whisper_Mother_of_all_wkey_no_f24.py`

Transcription:

- Groq STT is the default network path when `GROQ_API_KEY` is set.
- Local Faster-Whisper is the fallback path.
- Dynamic model catalog and quarantine live in `wkey/groq_model_catalog.py` and `wkey/model_rotation.py`.

Audio:

- `wkey/audio_io.py` owns input stream creation, callback buffering, snapshots, and silence wait.
- Pre-recording buffers are ring buffers and must preserve wraparound samples.
- `wkey/volume_lease_manager.py` owns nested volume-duck restore behavior.

Recovery:

- Hibernate/wake and audio overflow recovery live in `wkey/faster_whisper_Mother_of_all_wkey.py`.
- Wake-stream recovery must initialize the PyAudio stream before the wake listener starts.
- Keyboard release must stop active manual recording even if press/release happens inside debounce time.

## Native Hotkey Broker Workflow

> SUPERSEDED 2026-07-12 (planning): the broker is being retired for reliability.
> On wake the five-layer chain kills and races itself into a stale-lock loop.
> See `docs/superpowers/specs/2026-07-12-input-owner-simplification-design.md`
> and the "Input-Owner Simplification (Broker Retirement)" section below. The
> notes here describe the retired design.

> DELETED 2026-07-17 (Phase 6 cleanup): `native/wkey-broker` source was removed
> (`git rm -r`, recoverable from history). The Control Center's D+F diagnostic
> button that shelled out to it now reports itself unavailable instead of
> failing. Everything below describes a design that no longer has code.

Status: broker startup enabled 2026-06-27.

Goal: move fragile Windows keyboard hook ownership out of Python while keeping Python as the transcription engine.

Design docs:

- `docs/superpowers/specs/2026-06-18-native-hotkey-broker-design.md`
- `docs/superpowers/plans/2026-06-18-native-hotkey-broker.md`

Architecture:

- Rust broker first; C++ only if Rust low-level Win32 hook work hits a hard blocker.
- Python keeps audio capture, Groq/Faster-Whisper fallback, transcript cleanup, paste, command routing, wake-word path, and settings.
- Broker controls Python through JSONL over child-process stdio.
- Python manual `pynput` listener is disabled only when `WKEY_INPUT_OWNER=broker`.
- `Start-WKeyBroker.bat` launches the Rust broker, which launches Python in broker-control mode.
- Manual launcher output defaults to live console mode; pass `--log` or `-OutputMode Log` for scheduled/background output in `logs\wkey-broker-startup.log`.
- Windows scheduled task `\Whisper` may keep pointing to `C:\Windows_software\openai whisper\Whisper.bat`; that parent batch file delegates to `Start-WKeyBroker.bat` when present.
- `scripts/Install-WKeyBrokerTask.ps1` can change the task action directly when run elevated.

Trigger policy:

- `F24`: command/tool-use route.
- `left_ctrl_release_alone`: current fallback profile, not assumed final.
- `D+F`: experimental dictation profile; must run diagnostic mode before becoming default.

Completed phase order:

1. Planning docs and roadmap.
2. Python broker command dispatcher.
3. Python stdio control mode.
4. Rust broker scaffold and pure trigger-state tests.
5. Rust low-level keyboard hook diagnostic.
6. Rust broker starts/controls Python engine.
7. Broker-managed runtime smoke.
8. `D+F` diagnostic decision.
9. Broker launcher and scheduled-task migration script.

Current startup files:

- `C:\Windows_software\openai whisper\Whisper.bat`
- `Start-WKeyBroker.bat`
- `scripts/Start-WKeyBroker.ps1`
- `scripts/Install-WKeyBrokerTask.ps1`

## Whisper Control Center V1

Status: implemented 2026-06-18.

Entry point:

- `wkey/Whisper_GUI.py` now launches the Qt sidebar control center.
- New UI internals live in `wkey/control_center.py` and `wkey/control_center_state.py`.

Sections:

- Dashboard: backend PID/status, runtime mode, active keys, pause state, config path, provider status.
- Hotkeys: structured per-action profile cards for dictation, command/tool-use, pause/resume, timed pause, wake mode, restart backend, and `D+F` diagnostic.
- Transcription: local/Groq/wake/context toggles plus context sizes, context age, max recording seconds, wake-volume hold timing, and retry count.
- Voice Commands: provider/status view only; no API-key editing.
- Diagnostics: D+F key diagnostic button; reports unavailable since the Rust broker it depended on was deleted 2026-07-17.
- Startup: current `Whisper.bat` and scheduled-task status display only.
- Logs: tail view for repo log files.

Settings:

- `hotkey_profiles` is the structured UI schema.
- `record_keys` remains preserved for the Python runtime and is derived from profile save/load.
- Stale `ctrl_l` config values migrate to the current Right Ctrl dictation default.
- `D+F` remains a disabled diagnostic preset and is not made the default.

Backend management:

- `wkey/backend_process.py` provides `find_backend_processes()`, `start_backend()`, `stop_backend()`, `restart_backend()`, and runtime-status helpers.
- The control center manages the Python backend directly for v1.
- Rust broker is now the scheduled-task startup path.
- Tray supervision remains future work.

## Target-Speaker Paste Filter

Status: planned 2026-06-19; implementation in branch `target-speaker-paste-filter`.

Goal: prevent nearby speakers from being pasted during manual dictation by filtering the audio to Harsha-matching chunks before transcription.

Design docs:

- `docs/superpowers/specs/2026-06-19-target-speaker-paste-filter-design.md`
- `docs/superpowers/plans/2026-06-19-target-speaker-paste-filter.md`

Architecture:

- V1 uses target-speaker verification over VAD chunks, not full diarization.
- SpeechBrain ECAPA is the default speaker embedding backend because it is already installed locally.
- Positive enrollment defaults to `I:\Record_only_by_harsha`.
- Negative calibration defaults to `I:\Record_others_16k_wav`.
- Generated speaker profiles and calibration reports remain local ignored runtime artifacts.

Runtime policy:

- Apply only to manual dictation/paste (`keyword_index is None`) in v1.
- F24 command/tool-use and wake-word command routes bypass the filter.
- `analysis` mode logs scores without changing audio.
- `conservative`, `balanced`, `permissive`, and `custom` modes are adjustable in settings.

Future work:

- Full diarization plus word-timestamp alignment if v1 proves useful but overlapping speakers remain a problem.
- Source separation only after diarization/verification is not enough.

## Active Groq Follow-up

Status: implemented 2026-06-13.

- Groq model hydration uses `wkey/groq_model_catalog.py` and `wkey/model_rotation.py` to load cache immediately, then force-refresh `/models` in a bounded background thread.
- Tool-use ranking is live-catalog-first: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3-32b`, `meta-llama/llama-4-scout-17b-16e-instruct`, `llama-3.3-70b-versatile`, then `llama-3.1-8b-instant`.
- Groq STT ranking is `whisper-large-v3-turbo`, then `whisper-large-v3`.
- `tool_use_failed` and model-specific 400/404 responses quarantine only the failing model; 429 responses use a short per-model cooldown instead of bad-model quarantine.
- Prompt guards, `groq/compound*`, Orpheus TTS, Whisper STT, and safeguard models are excluded from normal function-tool routing.

## Ask-AI Provider Routing

Status: implemented 2026-07-07.

Root-cause evidence from recent logs:

- explicit Ask-AI prompts had a direct route in code, but it was not called before the Groq tool-use classifier;
- the classifier used a 4096-token response budget, which made Groq 429 and 413 failures more likely;
- unclaimed ChatGPT browser jobs silently fell back to direct Groq Ask-AI, adding hidden requests after the user-visible tool timeout;
- the Groq SDK retried those direct requests internally, so extra POSTs could continue after the tool path timed out.

Implemented policy:

- explicit `ask chatgpt`, `ask chat gpt`, and `ask ai` commands bypass the Groq LLM classifier;
- the classifier response budget is capped at 256 tokens;
- `ask_chatgpt_fallback_to_ai` defaults to `false`, so a ChatGPT browser timeout does not send a hidden provider request;
- direct Ask-AI uses a Patient_Avatar-style provider chain with Cerebras, SambaNova, OpenRouter, Cloudflare, Ollama Cloud, and Groq;
- direct provider calls use stdlib HTTP without SDK auto-retry loops;
- model catalogs are cached at runtime in `ask_ai_model_catalog.json` under `%LOCALAPPDATA%\WhisperKeyboard\runtime`;
- `ask_ai_model=auto` selects models by task complexity while favoring non-Groq providers for simple and standard questions.

Live-catalog smoke defaults from 2026-07-07:

- simple: `cerebras/llama-3.3-70b`
- standard: `cerebras/qwen-3-235b-a22b-instruct-2507`
- complex: `openrouter/deepseek/deepseek-r1-0528`

## Input-Owner Simplification (Broker Retirement)

Status: planning 2026-07-12; three decisions open in `Q and A.md`.

Goal: stop letting a native process own/start/supervise Python. Move low-level
keys to an external remapper that emits F23/F24; Python's `pynput` listener
catches them. One app process, one logon-only scheduled task, Windows resumes
across sleep, in-app resume health behind a toggle.

Design docs:

- `docs/superpowers/specs/2026-07-12-input-owner-simplification-design.md`
- `docs/superpowers/plans/2026-07-12-broker-retirement-git-strategy.md` (git map; pending Q3)

Key points:

- Root cause: wake-kill scheduled task + stale `wkey_runtime.lock` race + Rust
  5s reply timeout + no real Python restart. Confirmed in code and the
  2026-07-07 log.
- Recommended: option A (external remapper → F23/F24 → Python) + abandon-broker
  in-place (forward deletion, keep history).
- Scheduler fix applies regardless: logon-only, `IgnoreNew`, no battery-stop,
  no wake trigger; reclaim stale PID-unknown lock.
- Replaces the "In-app wake/hibernate supervision" future item below.

## Planned UX (Future, from 2026-07-07 requests)

- Cursor/center-screen visual feedback: a recording/active indicator shown near
  the cursor or at the center of the active screen, rendered behind windows,
  toggleable in settings/GUI.
- Settings search bar: VS Code Ctrl+Shift+P style command/setting palette so any
  setting can be found by typing. Belongs with the Control Center V1 work.

## Open Issues From Repo TODOs

| Issue | Source | Status |
|---|---|---|
| Default input device / hardware detection | `wkey/TODO` | Default input selection wired; broader hardware detection remains open |
| Remove stale `There_is_a_device` reference if found | `wkey/TODO` | No active reference found in current tracked code |
| Previous audio combining into current commands | `wkey/TODO` | Mitigated by clearing recording buffers on start/stop and fixing pre-record ring wraparound |
| Stale isolated scripts | `wkey/faster_whisper_Mother_of_all_wkey_no_f24.py`, `wkey/faster_whisper_Mother_of_all_wkey_just_f24.py` | Updated to wrappers over current main runtime |
| Packaging/docs mismatch | `README.md`, `README.rst`, `setup.py` | README files updated; packaging still needs separate cleanup |
| Google Assistant legacy path | `wkey/google_assistant.py` | Open; main currently imports `google_assistant_stub` |
| In-app wake/hibernate supervision | broker/app runtime | Future: add a setting-gated supervisor that handles Windows sleep/resume health checks inside the app/broker, then replace the fragile scheduled-task kill/restart flow after it is proven |

## Commit Plan

1. Dynamic Groq catalog implementation and tests.
2. Runtime docs and roadmap.
3. Activation responsiveness and pre-record buffer reliability.
4. Stale mode launcher cleanup.
5. Later: packaging dependency cleanup and Google Assistant legacy decision.

## Acceptance Criteria

- Focused tests for audio buffer, keyboard shortcuts, and main wrapper behavior pass.
- Full test suite passes or environment-specific gaps are recorded.
- Bounded primary-script smoke starts without immediate import/config errors and is stopped.
- README files describe the current Windows/Groq/Faster-Whisper implementation.
- Mode launchers do not carry stale forked runtime code.

## Ask-AI / TTS / Overlay Settings (2026-07-17)

New settings in `wkey/transcription_config.json` (defaults in `wkey/settings_manager.py`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `ask_hotkey_provider` | `chatgpt` | Provider the F13 ask-AI hotkey routes to |
| `ask_ai_tts_enabled` | `true` | Speak direct-provider Ask-AI answers through TTS |
| `ask_ai_tts_max_chars` | `400` | Truncate Ask-AI answers before queuing for TTS |
| `overlay_enabled` | `true` | Show the cursor-adjacent feedback toast |
| `overlay_duration_ms` | `1500` | Toast on-screen duration |
| `overlay_opacity` | `0.85` | Toast opacity |
| `overlay_font_size` | `11` | Toast font size |
| `overlay_offset_px` | `24` | Toast offset from cursor, px |

## TTS priority (2026-07-17, user directive)

- Primary voice: server-side edge-tts `en-US-AvaNeural` (`EDGE_TTS_PRIMARY_VOICE`). Local CPU TTS (Kokoro/pyttsx4) is fallback only — never primary.
- Distant roadmap: add the user's voicelink server as an additional TTS fallback tier when available.
- Overlay niceties (future): per-event colors, symbols/icons in the cursor toast (user request 2026-07-17).
