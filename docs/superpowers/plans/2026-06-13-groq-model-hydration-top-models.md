# Hydrate Groq Models And Use Top Models

## Goal

Make Groq model selection live-catalog-aware so tool-use starts with current top models and stale hardcoded choices cannot dominate retries.

## Incident Evidence

- Live `/models` returned GPT-OSS 120B/20B, Qwen3 32B, Llama 4 Scout, Llama 3.3 70B, Llama 3.1 8B, Whisper v3/turbo, prompt guards, compound models, and Orpheus audio models.
- Runtime logs showed `llama-3.3-70b-versatile` first for tool-use despite GPT-OSS models being available.
- Runtime logs showed Groq 400 `tool_use_failed` for a valid local `launch_application("Device Manager")` call.
- Runtime logs showed 429s that should cool down briefly, not quarantine the model as unavailable.

## Implemented Design

- `wkey/groq_model_catalog.py`
  - Builds task-aware groups from the model catalog.
  - Tool-use group is ranked and allowlisted to known tool-capable chat models.
  - STT group ranks `whisper-large-v3-turbo` before `whisper-large-v3`.
  - Classifies `tool_use_failed` as recoverable model failure.
  - Classifies 429/rate-limit as rate cooldown, not model unavailability.

- `wkey/model_rotation.py`
  - Static defaults now mirror the ranked task groups.
  - Cache refresh is available immediately; startup hydration can force-refresh live models in a bounded daemon thread.
  - Model-specific failures quarantine one model.
  - 429s apply a short per-model cooldown.
  - If every model is blocked, the first ranked model is used once with a warning.

- `wkey/voice_commands.py`
  - Tool-use HTTP errors now route through the classifier.
  - 400 `tool_use_failed` retries another model.
  - 429 applies cooldown and retries another model.
  - Launch prompt now lists Device Manager and the other schema-supported app names.

- `wkey/transcription_utils.py`
  - Groq STT reports model-specific failures and rate limits separately.

- `wkey/faster_whisper_Mother_of_all_wkey.py`
  - Startup uses cache-first hydration plus bounded background live refresh.
  - STT wrappers pass model-failure and rate-limit callbacks.

## Verification Plan

- Focused tests:
  - `tests/test_groq_model_catalog.py`
  - `tests/test_model_rotation.py`
  - `tests/test_voice_commands_model_errors.py`
  - `tests/test_transcription_utils.py`
  - `tests/test_faster_whisper.py`
- Requested tests:
  - `..\openai\Scripts\python.exe -m pytest tests\test_groq_model_catalog.py tests\test_model_rotation.py tests\test_voice_commands_model_errors.py -q`
- Primary smoke:
  - Start `wkey\faster_whisper_Mother_of_all_wkey.py` with the repo venv Python.
  - Stop the process before handoff.
