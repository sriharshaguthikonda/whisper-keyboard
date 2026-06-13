# Q and A

## 2026-06-13 Groq Model Hydration

Status: implemented and verified.

Current findings:

- Repo-map manifest is absent, so live files are the source of truth for this change.
- Live Groq catalog contains GPT-OSS 120B/20B, Qwen3 32B, Llama 4 Scout, Llama 3.3 70B, Llama 3.1 8B, Whisper v3/turbo, prompt guards, compound models, and Orpheus audio models.
- Old effective rotation put `llama-3.3-70b-versatile` first and carried absent legacy choices.
- New behavior uses GPT-OSS first for tool-use and Whisper turbo first for STT.
- 400 `tool_use_failed` quarantines one model and retries; 429 uses short cooldown instead of quarantine.

Tests so far:

- `..\openai\Scripts\python.exe -m pytest tests\test_groq_model_catalog.py tests\test_model_rotation.py tests\test_voice_commands_model_errors.py tests\test_transcription_utils.py tests\test_faster_whisper.py -q`
- Result: 38 passed.
- `..\openai\Scripts\python.exe -m pytest tests\test_groq_model_catalog.py tests\test_model_rotation.py tests\test_voice_commands_model_errors.py -q`
- Result: 21 passed.
- `..\openai\Scripts\python.exe -m pytest tests\test_transcription_utils.py tests\test_transcription_pipeline.py tests\test_faster_whisper.py -q`
- Result: 18 passed.
- `..\openai\Scripts\python.exe -m pytest tests -q`
- Result: 52 passed.
- `git diff --check`
- Result: clean.
- Bounded primary-script smoke with `..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py`
- Result: started without immediate exit, stopped, no matching primary-script process remains.
- Live catalog smoke
- Result: `source=live`, `model_count=16`, `tool_model=openai/gpt-oss-120b`, `stt_model=whisper-large-v3-turbo`.

Pending:

- None.

Questions for user:

- None pending.

## 2026-06-13 CapsLock Manual Trigger

Status: implemented and verified.

Current finding:

- `pynput.keyboard.Key.caps_lock` exists in the repo venv.
- Current manual keys come from `WKEY_RECORD_KEYS`, defaulting to `f24,ctrl_r`.
- `F24` maps to command/tool-use routing; non-F24 manual keys map to dictation/paste routing.

Recommended design:

- Add `caps_lock` to supported manual key labels.
- Change default `WKEY_RECORD_KEYS` from `f24,ctrl_r` to `f24,caps_lock`, so CapsLock replaces Right Ctrl by default.
- Keep `ctrl_r` supported for compatibility if explicitly configured.
- Update tests/docs for default CapsLock behavior.

Decision:

- User approved implementation.

Implementation:

- Add `caps_lock` as supported manual key.
- Default manual keys to `f24,caps_lock`.
- Keep `ctrl_r` supported when explicitly configured.
- Suppress native CapsLock toggling while CapsLock is enabled as a record key.

Verification:

- `..\openai\Scripts\python.exe -m pytest tests\test_faster_whisper.py tests\test_keyboard_shortcuts.py -q`
- Result: 18 passed.
- Bounded primary-script smoke with `..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py`
- Result: started for 20 seconds, stopped, no stderr, no matching Python primary-script process remains.
- `git diff --check`
- Result: clean.
- `..\openai\Scripts\python.exe -m pytest tests -q`
- Result: 55 passed.



# user comments
1. capslock press has to be blocked from reaching the system...because it changes the capslock status...when i use it for this program!!!


