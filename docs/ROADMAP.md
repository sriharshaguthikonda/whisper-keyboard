# Whisper Keyboard Current State And Roadmap

Generated: 2026-05-18

## Current Runtime Spec

Primary runtime: `wkey/faster_whisper_Mother_of_all_wkey.py`.

User-facing GUI: `wkey/Whisper_GUI.py`.

Settings:

- `wkey/transcription_config.json`
- `wkey/settings_manager.py`

Activation surfaces:

- Manual `F24`: command/tool-use route.
- Manual `ctrl_r`: dictation/paste route.
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

## Open Issues From Repo TODOs

| Issue | Source | Status |
|---|---|---|
| Default input device / hardware detection | `wkey/TODO` | Default input selection wired; broader hardware detection remains open |
| Remove stale `There_is_a_device` reference if found | `wkey/TODO` | No active reference found in current tracked code |
| Previous audio combining into current commands | `wkey/TODO` | Mitigated by clearing recording buffers on start/stop and fixing pre-record ring wraparound |
| Stale isolated scripts | `wkey/faster_whisper_Mother_of_all_wkey_no_f24.py`, `wkey/faster_whisper_Mother_of_all_wkey_just_f24.py` | Updated to wrappers over current main runtime |
| Packaging/docs mismatch | `README.md`, `README.rst`, `setup.py` | README files updated; packaging still needs separate cleanup |
| Google Assistant legacy path | `wkey/google_assistant.py` | Open; main currently imports `google_assistant_stub` |

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
