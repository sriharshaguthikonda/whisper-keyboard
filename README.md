# whisper-keyboard

Windows-first voice keyboard and voice-command runner.

The active runtime is `wkey/faster_whisper_Mother_of_all_wkey.py`. It keeps a microphone stream warm, records while a manual key is held, captures wake-word commands, transcribes through Groq STT with local Faster-Whisper fallback, and routes results either to clipboard paste or command execution.

## Entry Points

Run from the repo root:

```powershell
python .\wkey\faster_whisper_Mother_of_all_wkey.py
```

Mode-specific launchers:

```powershell
python .\wkey\faster_whisper_Mother_of_all_wkey_just_f24.py
python .\wkey\faster_whisper_Mother_of_all_wkey_no_f24.py
```

- `faster_whisper_Mother_of_all_wkey.py`: combined keyboard and wake-word runtime.
- `faster_whisper_Mother_of_all_wkey_just_f24.py`: keyboard-only F24 runtime.
- `faster_whisper_Mother_of_all_wkey_no_f24.py`: wake-word-only runtime.
- `wkey/Whisper_GUI.py`: main user-facing settings GUI.

## Activation

Manual keys:

- `F24`: routes transcript to tool-use command execution.
- `right Ctrl`: routes transcript to clipboard paste.

Wake words are handled by `wkey/wakeword.py` using local OpenWakeWord models under `wkey/openwakeword_models/`.

Optional environment variables:

- `WKEY`: display/default key label, usually `f24` or `ctrl_r`.
- `WKEY_RUNTIME_MODE`: `combined`, `keyboard`, or `wakeword`. Default: `combined`.
- `WKEY_RECORD_KEYS`: comma-separated enabled manual keys, for example `f24,ctrl_r` or `f24`.

## Settings

Settings live in `wkey/transcription_config.json` and are managed by:

```powershell
python .\wkey\Whisper_GUI.py
```

The settings layer controls local GPU/CPU fallback, Groq fallback, Selenium/browser automation, wake-word precheck, transcript context memory, command routing context, max recording length, and wake-volume timing.

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

## Audio Recovery

The main runtime includes recovery for hibernate/wake and device churn:

- input-stream restart through `wkey/audio_io.py`;
- wake-stream restart through `initialize_wake_stream()`;
- keyboard listener restart after recovery;
- pre-recording ring buffers for manual and wake-word capture;
- volume-duck lease recovery through `wkey/volume_lease_manager.py`.

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
