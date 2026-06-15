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


## 2026-06-13 Prerecord/Loop Beep Hardening

Status: implemented and verified.

Current findings:

- Current config has `enable_wakeword_detection=false`.
- Current config has `enable_pre_recording_keyword_check=false`.
- Manual CapsLock/F24 path queues one combined audio item: prerecord buffer plus current recording.
- Prerecord-only STT is only for wake-word keyword validation.
- Log evidence for repeated untriggered transcriptions: `wkey/voice_commands.log` at `2026-06-13 09:49:03` through `09:50:10` shows repeated `Starting recording...` followed within milliseconds by `stop_recording_claimed ... keyword_index=None`, then `Saved manual recording ... 1000ms.wav`, then `transcribe_with_groq_async ... keyword_index=None`.
- That means the live loop was manual-key tap/bounce/repeat, not wake-word detection and not prerecord keyword precheck.
- Fix added: record-key release rearm delay blocks repeated starts for 1s after release.
- Fix added: manual recordings shorter than 0.25s are dropped before prerecord prefix is queued, so prerecord-only audio is not sent as dictation.

Truth table:

- Default settings: keyboard-only runtime; no wake stream.
- Wake-word detection off: no wake stream and no prerecord-only transcription.
- Pre-recording keyword check off: no prerecord-only STT request is sent.
- Manual CapsLock/F24 recording: one transcription request, with prerecord prefix included in same audio buffer.
- Very short manual tap: dropped before transcription.
- Wake-word detection on and precheck on: prerecord-only STT runs only for keyword validation before command capture.

Tests so far:

- `..\openai\Scripts\python.exe -m pytest tests\test_faster_whisper.py -q`
- Red result before code: 1 failed because `should_run_pre_recording_keyword_check` was missing.
- Green result after code: 28 passed.
- `..\openai\Scripts\python.exe -m pytest tests\test_keyboard_shortcuts.py tests\test_faster_whisper.py -q`
- Red result before manual-loop fix: 2 failed because `record_rearm_delay` was missing and immediate manual tap still queued prerecord-only audio.
- Green result after manual-loop fix: 32 passed.
- `..\openai\Scripts\python.exe -m pytest tests\test_keyboard_shortcuts.py tests\test_faster_whisper.py tests\test_settings_manager.py -q`
- Result: 34 passed.
- `..\openai\Scripts\python.exe -m pytest tests -q`
- Result: 71 passed.
- `git diff --check`
- Result: clean.
- Bounded primary-script smoke with `..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py`
- Result: ran for 20 seconds, stopped, no stderr, no matching primary-script Python process remains.

Questions for user:

- None pending.



## user comments

1. forget about solving ......did you even investigate ....why we were still getting the repeated untirggered transcriptions?!
2. add needed logging identiifers for future trouble shooting i f this keeps occuring!!


## 2026-06-14 Wake/Recovery Recording Loop Fix

Status: implemented and verified.

Current findings:

- `input overflow burst` recovery was doing a full keyboard-listener restart plus `handle_resume_event`, even in keyboard-only runtime.
- `volume timeout 2.0s` recovery was scheduling audio recovery, which could also restart/reset keyboard state.
- Those recovery resets cleared the record-key rearm guard, so stale CapsLock/F24 events after wake/recovery could start a new manual recording.
- Latest log evidence was recovery-scoped, not wakeword-scoped: runtime mode was keyboard, wakeword disabled, keys were `f24,caps_lock`.

Implementation:

- `KeyboardShortcutHandler.reset_state(preserve_rearm=True)` now preserves record-key rearm/suppression state for recovery resets.
- `KeyboardShortcutHandler.suppress_record_keys(...)` blocks stale record-key presses after recovery/listener restart and logs `record_key_event` with action, key, recording flag, suppression remaining, reason, active keys, and pressed keys.
- Manual `start_recording` now respects a 2s recovery suppression window.
- `input overflow burst` now recovers the audio stream only; it does not restart the keyboard listener and does not call full resume reset.
- `volume timeout` callback now only force-releases volume ducking and applies manual trigger suppression; it does not queue audio recovery.
- `system resume:*` and `microphone restore` still use full reset/restart paths, with manual trigger suppression after wake.

Verification:

- Red tests first: 6 new regression tests failed before implementation.
- `..\openai\Scripts\python.exe -m pytest tests\test_keyboard_shortcuts.py::test_reset_can_preserve_record_release_rearm_delay tests\test_keyboard_shortcuts.py::test_record_key_suppression_blocks_stale_press_after_restart tests\test_keyboard_shortcuts.py::test_record_key_release_during_suppression_only_stops_active_recording tests\test_faster_whisper.py::test_input_overflow_recovery_is_audio_only tests\test_faster_whisper.py::test_volume_timeout_callback_releases_volume_without_audio_recovery tests\test_faster_whisper.py::test_system_resume_restarts_listener_once_and_suppresses_manual_keys -q`
- Green result after code: 6 passed.
- `..\openai\Scripts\python.exe -m pytest tests\test_keyboard_shortcuts.py tests\test_faster_whisper.py -q`
- Result: 38 passed.
- `..\openai\Scripts\python.exe -m pytest tests -q`
- Result: 77 passed.
- `git diff --check`
- Result: clean.
- Bounded primary-script smoke with `..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py`
- First smoke attempt failed due unquoted path with spaces in the test harness command only; no leftover process.
- Corrected smoke result: started, stayed alive for 20s, stopped, no stderr, no new primary-script process remains.

Questions for user:

- None pending.







## user comments

1. i have already modified the scheduled task to start up as well as to after every hibernation wake up it will kill the existing script and will start it again. so i don't know if that is actually correct modify if it needs to be modified.
2. update memory system regarding this QUESTION so that it will be injected into your context IN THE REPO nextTIME



## 2026-06-15 Recovery Simplification

Status: implemented and verified.

Locked decisions:

- Recovery policy moves to external restart.
- Primary runtime should stop doing in-process hibernate/resume/audio-reconnect recovery.
- CapsLock/F24 behavior stays.
- Wake-word code stays available but disabled by default.
- Scheduled task was already modified by user; discuss task behavior next runtime before changing task automation again.

Current questions for user:

- None pending.

Verification:

- `..\openai\Scripts\python.exe -m pytest tests -q`
- Result: 76 passed.
- `git diff --check`
- Result: clean.
- Bounded primary-script smoke with `..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py`
- Result: process stayed alive for 20s with no stdout/stderr, then bounded smoke process was stopped.
- Cleanup check: no leftover primary-script process from the smoke run.
