# Target-Speaker Paste Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paste only Harsha-matching manual dictation audio when other speakers are present.

**Architecture:** Add a local speaker verification filter before manual dictation STT. Calibration creates a local profile; runtime filtering reads settings and applies only to `keyword_index is None`.

**Tech Stack:** Python, NumPy, SciPy WAV writing, SpeechBrain ECAPA, torch/torchaudio, existing Qt Control Center.

## Global Constraints

- Do not commit audio files, generated speaker profiles, or calibration reports.
- Keep F24 command and wake-word routes unchanged.
- Default adjustable modes are `analysis`, `conservative`, `balanced`, `permissive`, and `custom`.
- Use TDD for production code changes.
- After code changes, run focused tests, full tests, py_compile, `git diff --check`, and bounded primary-script smoke.

---

### Task 1: Settings And UI State

**Files:**
- Modify: `wkey/settings_manager.py`
- Modify: `wkey/control_center_state.py`
- Test: `tests/test_settings_manager.py`
- Test: `tests/test_control_center_state.py`

**Deliverable:** New speaker-filter settings normalize, clamp, and appear in UI snapshots.

- [x] Write failing settings/state tests.
- [x] Implement defaults and normalization.
- [x] Run focused settings/state tests.
- [x] Commit: `feat: add speaker filter settings`

### Task 2: Speaker Filter Core

**Files:**
- Create: `wkey/speaker_filter.py`
- Test: `tests/test_speaker_filter.py`

**Deliverable:** Deterministic fake-embedding tests cover accept, reject, mixed audio, analysis mode, and missing profile behavior.

- [x] Write failing core tests.
- [x] Implement filter result/data model, profile loading, chunk scoring, and filtering.
- [x] Add ECAPA backend with lazy import.
- [x] Run focused core tests.
- [x] Commit: `feat: add target speaker audio filter`

### Task 3: Manual Dictation Pipeline Integration

**Files:**
- Modify: `wkey/transcription_pipeline.py`
- Modify: `wkey/faster_whisper_Mother_of_all_wkey.py`
- Test: `tests/test_transcription_pipeline.py`
- Test: `tests/test_faster_whisper.py`

**Deliverable:** Manual dictation audio is filtered before STT; F24 and wake-word paths bypass it.

- [x] Write failing pipeline tests.
- [x] Inject speaker filter into `TranscriptionPipeline`.
- [x] Wire backend runtime factory from settings.
- [x] Run focused pipeline/runtime tests.
- [x] Commit: `feat: filter manual dictation by speaker`

### Task 4: Calibration CLI

**Files:**
- Create: `wkey/speaker_filter_calibrate.py`
- Test: `tests/test_speaker_filter_calibrate.py`
- Modify: `.gitignore`

**Deliverable:** CLI writes local profile/report from positive and negative folders and ignored output paths.

- [x] Write failing calibration tests using temp WAVs and fake embedding backend.
- [x] Implement calibration sampling, threshold suggestion, profile/report writing.
- [x] Add gitignore entries for generated profiles/reports.
- [x] Run focused calibration tests.
- [x] Commit: `feat: calibrate target speaker profile`

### Task 5: Control Center Controls

**Files:**
- Modify: `wkey/control_center.py`
- Modify: `wkey/control_center_state.py`
- Test: `tests/test_control_center_state.py`

**Deliverable:** Control Center exposes enable/mode/threshold/profile/corpus/status fields while preserving System/Dark/Light themes.

- [x] Write failing UI-state tests.
- [x] Add settings controls and status labels.
- [x] Run state tests and headless Control Center smoke.
- [x] Commit: `feat: expose speaker filter controls`

### Task 6: Final Verification And Merge

**Files:** All touched files.

**Deliverable:** Verified feature branch pushed, merged to `native-hotkey-broker`, worktree removed.

- [x] Run `..\openai\Scripts\python.exe -m pytest tests -q`.
- [x] Run py_compile for touched runtime modules.
- [x] Run `git diff --check`.
- [x] Run bounded primary-script smoke.
- [x] Run small calibration smoke if I: drive folders are present.
- [x] Push `target-speaker-paste-filter`.
- [x] Merge into `native-hotkey-broker`.
- [x] Push `native-hotkey-broker`.
- [x] Remove `C:\Windows_software\openai whisper\whisper-keyboard-speaker-filter`.
