# whisper-keyboard

Windows-first voice keyboard and voice-command runner.

The active runtime is `wkey/faster_whisper_Mother_of_all_wkey.py`. It keeps a microphone stream warm, records while a manual key is held, captures wake-word commands, transcribes through Groq STT with local Faster-Whisper fallback, and routes results either to clipboard paste or command execution.

## Entry Points

Production entry point (same path the scheduled task runs, just hidden):

```text
..\Whisper.bat -> Start-WhisperKeyboard.bat -> scripts\Start-WhisperKeyboard.ps1
```

Keep those paths `%~dp0`/script-relative — the SSD this repo lives on roams between machines.

Run the runtime directly instead (for debugging):

```powershell
python .\wkey\faster_whisper_Mother_of_all_wkey.py
```

Mode-specific launchers:

```powershell
python .\wkey\faster_whisper_Mother_of_all_wkey_just_f24.py
python .\wkey\faster_whisper_Mother_of_all_wkey_no_f24.py
```

- `faster_whisper_Mother_of_all_wkey.py`: main runtime; defaults to keyboard-only and can run wake-word mode when enabled in settings.
- `faster_whisper_Mother_of_all_wkey_just_f24.py`: keyboard-only F24 runtime.
- `faster_whisper_Mother_of_all_wkey_no_f24.py`: wake-word-only runtime.
- `wkey/Whisper_GUI.py`: thin shim, delegates straight to `wkey/control_center.py` (the settings GUI).

## Activation

Hotkeys reach the app as synthetic function keys emitted by an external remapper (Kanata, or the HID remapper dongle on desktop) — see `AGENTS.md` before changing any of these:

| Trigger | Synthetic key | Route |
| --- | --- | --- |
| `d+f` hold (Kanata chord, 100ms) | `F23` | Dictation/paste |
| backtick hold (HID remapper / legacy) | `F24` | Command/tool-use |
| `s+d` hold (Kanata chord, 100ms) | `F13` | Ask-AI (ChatGPT/AI pathway), opt-in — disabled unless `f13` is in `record_keys`/`ask_hotkey_profiles.ask_ai.enabled` |

Wake words are handled by `wkey/wakeword.py` using local OpenWakeWord models under `wkey/openwakeword_models/`.

Optional environment variables:

- `WKEY`: display/default key label, usually `ctrl_l` or `f24`. Default: `ctrl_l`.
- `WKEY_RUNTIME_MODE`: `combined`, `keyboard`, or `wakeword`. Default from settings: `keyboard`.
- `WKEY_RECORD_KEYS`: comma-separated enabled manual keys. Default: `f24,ctrl_l`. Stale `ctrl_r` config is migrated to `ctrl_l`. Example: `f24`.
- `WKEY_ALLOW_ENV_OVERRIDES`: set to `1` to allow `WKEY_RUNTIME_MODE` and `WKEY_RECORD_KEYS` to override settings/defaults.

## Native Broker (Deleted)

The Rust broker (`native/wkey-broker`) that used to own native Windows hotkeys and supervise the Python runtime is retired and its source was deleted 2026-07-17 (recoverable from git history). Input ownership today is Kanata/HID remapper -> synthetic function keys -> Python's own `pynput` listener; see the Activation table above and `AGENTS.md`. The scheduled task and `Whisper.bat`/`Start-WhisperKeyboard.bat` launch the direct-Python path (`scripts\Start-WhisperKeyboard.ps1`), not the old broker binary. `scripts\Install-WKeyBrokerTask.ps1` still exists to (re)point the Windows scheduled task at the current launcher — the "Broker" in its name is legacy naming only.

## Settings

Settings live in `wkey/transcription_config.json` and are managed by:

```powershell
python .\wkey\Whisper_GUI.py
```

The settings layer controls local GPU/CPU fallback, Groq fallback, Selenium/browser automation, wake-word precheck, transcript context memory, command routing context, max recording length, and wake-volume timing.

Prerecord and wake-word behavior:

| Setting state | Runtime behavior |
| --- | --- |
| Default settings | Keyboard-only runtime. No wake stream. |
| Wake-word detection off | No wake stream and no prerecord-only transcription. Manual keyboard triggers still work. |
| Pre-recording keyword check off | Wake-word prerecord validation is skipped; no prerecord-only STT request is sent. |
| Manual keyboard recording | One transcription request is queued: manual prerecord buffer plus current recording. |
| Very short manual tap | Dropped before transcription so prerecord-only audio is not sent as dictation. |
| Wake-word detection on and precheck on | Wake-word prerecord buffer is transcribed only for keyword validation before command capture. |

## Groq Model Catalog

Set `GROQ_API_KEY` for Groq STT and tool-use model calls.

The app discovers current Groq models from `https://api.groq.com/openai/v1/models`.

Runtime behavior:

- tool-use models and Groq STT models are filtered against the live catalog when available;
- the catalog is cached in `wkey/groq_model_catalog_cache.json`;
- the cache stores model IDs only, never API keys or transcripts;
- if a model returns a model-specific HTTP 400 or 404, it is quarantined and the next model is tried;
- if a model returns HTTP 429/rate-limit, it gets a short cooldown instead of bad-model quarantine;
- if catalog refresh fails, the app uses the cache, then configured defaults.

Optional environment variables:

- `GROQ_MODEL_CATALOG_TTL_SECONDS`: cache freshness window. Default: `86400`.
- `GROQ_MODEL_CATALOG_BACKGROUND_TIMEOUT_SECONDS`: startup live-refresh timeout. Default: `4.0`.
- `GROQ_BAD_MODEL_COOLDOWN_SECONDS`: bad-model quarantine duration. Default: `3600`.
- `GROQ_RATE_LIMIT_COOLDOWN_SECONDS`: per-model rate-limit cooldown. Default: `30`.

## Ask-AI Provider Routing

Ask-AI voice commands use a separate provider router for direct AI answers. Set `ask_ai_model` to `auto` for model selection by task complexity, or set an explicit model as `provider/model` or `provider:model`.

Provider discovery is adapted from the Patient_Avatar multi-provider pattern. Supported provider keys:

- `CEREBRAS_API_KEY`
- `SAMBANOVA_API_KEY`
- `OPENROUTER_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID` plus `CLOUDFLARE_API_TOKEN`
- `OLLAMA_CLOUD_API_KEY`
- `GROQ_API_KEYS`, `GROQ_API_KEY_2`, or `GROQ_API_KEY`

Runtime behavior:

- model catalogs are refreshed from configured providers and cached in `%LOCALAPPDATA%\WhisperKeyboard\runtime\ask_ai_model_catalog.json`;
- the cache stores provider/model metadata only, never API keys, transcripts, audio, or command text;
- `auto` favors non-Groq providers first so Groq STT/tool-use quota is not consumed by direct Ask-AI when alternatives exist;
- simple and standard questions prefer fast current defaults; complex questions may use higher-capability models;
- `ask_chatgpt_fallback_to_ai` defaults to `false`, so an unclaimed ChatGPT browser job does not make a hidden direct provider request.

Current live-catalog smoke defaults on 2026-07-07:

- simple: `cerebras/llama-3.3-70b`
- standard: `cerebras/qwen-3-235b-a22b-instruct-2507`
- complex: `openrouter/deepseek/deepseek-r1-0528`

Ask-AI hotkey, TTS, and cursor-overlay settings (all in `wkey/transcription_config.json`, defaults in `wkey/settings_manager.py`):

| Setting | Default | Meaning |
| --- | --- | --- |
| `ask_hotkey_provider` | `chatgpt` | Which provider the F13 ask-AI hotkey routes to |
| `ask_ai_tts_enabled` | `true` | Speak direct-provider Ask-AI answers back through the TTS engine |
| `ask_ai_tts_max_chars` | `400` | Truncate Ask-AI answers before they are queued for TTS |
| `overlay_enabled` | `true` | Show the cursor-adjacent feedback toast |
| `overlay_duration_ms` | `1500` | How long the toast stays on screen |
| `overlay_opacity` | `0.85` | Toast opacity |
| `overlay_font_size` | `11` | Toast font size |
| `overlay_offset_px` | `24` | Toast offset from the cursor, in pixels |

## Recovery Policy

The main keyboard runtime uses `recovery_policy=external_restart`.

- hibernate/wake/logon recovery belongs to the Windows scheduled task;
- input overflow is logged but does not schedule in-process stream recovery;
- keyboard mode starts no wake-word listener, audio recovery worker, or microphone monitor;
- wake-word runtime remains available only when settings enable it;
- volume-duck cleanup remains local through `wkey/volume_lease_manager.py`.

## Testing

Run focused tests:

```powershell
python -m pytest tests\test_audio_io.py tests\test_keyboard_shortcuts.py tests\test_faster_whisper.py -q
```

Run all tests:

```powershell
python -m pytest tests -q
```

After changing runtime code, also run the bounded primary-script smoke and stop it before handoff:

```powershell
$proc = Start-Process -FilePath python -ArgumentList 'wkey/faster_whisper_Mother_of_all_wkey.py' -WorkingDirectory 'C:\Windows_software\openai whisper\whisper-keyboard' -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 20
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
```

## Security

This tool records microphone audio and can paste text or execute commands through keyboard/browser automation. Groq requests use configured API keys. Local cache files must not contain API keys, transcripts, audio, or command text.
