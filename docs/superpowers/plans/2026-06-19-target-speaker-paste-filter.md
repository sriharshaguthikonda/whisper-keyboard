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

- [ ] Write failing settings/state tests.
- [ ] Implement defaults and normalization.
- [ ] Run focused settings/state tests.
- [ ] Commit: `feat: add speaker filter settings`

### Task 2: Speaker Filter Core

**Files:**
- Create: `wkey/speaker_filter.py`
- Test: `tests/test_speaker_filter.py`

**Deliverable:** Deterministic fake-embedding tests cover accept, reject, mixed audio, analysis mode, and missing profile behavior.

- [ ] Write failing core tests.
- [ ] Implement filter result/data model, profile loading, chunk scoring, and filtering.
- [ ] Add ECAPA backend with lazy import.
- [ ] Run focused core tests.
- [ ] Commit: `feat: add target speaker audio filter`

### Task 3: Manual Dictation Pipeline Integration

**Files:**
- Modify: `wkey/transcription_pipeline.py`
- Modify: `wkey/faster_whisper_Mother_of_all_wkey.py`
- Test: `tests/test_transcription_pipeline.py`
- Test: `tests/test_faster_whisper.py`

**Deliverable:** Manual dictation audio is filtered before STT; F24 and wake-word paths bypass it.

- [ ] Write failing pipeline tests.
- [ ] Inject speaker filter into `TranscriptionPipeline`.
- [ ] Wire backend runtime factory from settings.
- [ ] Run focused pipeline/runtime tests.
- [ ] Commit: `feat: filter manual dictation by speaker`

### Task 4: Calibration CLI

**Files:**
- Create: `wkey/speaker_filter_calibrate.py`
- Test: `tests/test_speaker_filter_calibrate.py`
- Modify: `.gitignore`

**Deliverable:** CLI writes local profile/report from positive and negative folders and ignored output paths.

- [ ] Write failing calibration tests using temp WAVs and fake embedding backend.
- [ ] Implement calibration sampling, threshold suggestion, profile/report writing.
- [ ] Add gitignore entries for generated profiles/reports.
- [ ] Run focused calibration tests.
- [ ] Commit: `feat: calibrate target speaker profile`

### Task 5: Control Center Controls

**Files:**
- Modify: `wkey/control_center.py`
- Modify: `wkey/control_center_state.py`
- Test: `tests/test_control_center_state.py`

**Deliverable:** Control Center exposes enable/mode/threshold/profile/corpus/status fields while preserving System/Dark/Light themes.

- [ ] Write failing UI-state tests.
- [ ] Add settings controls and status labels.
- [ ] Run state tests and headless Control Center smoke.
- [ ] Commit: `feat: expose speaker filter controls`

### Task 6: Final Verification And Merge

**Files:** All touched files.

**Deliverable:** Verified feature branch pushed, merged to `native-hotkey-broker`, worktree removed.

- [ ] Run `..\openai\Scripts\python.exe -m pytest tests -q`.
- [ ] Run py_compile for touched runtime modules.
- [ ] Run `git diff --check`.
- [ ] Run bounded primary-script smoke.
- [ ] Run small calibration smoke if I: drive folders are present.
- [ ] Push `target-speaker-paste-filter`.
- [ ] Merge into `native-hotkey-broker`.
- [ ] Push `native-hotkey-broker`.
- [ ] Remove `C:\Windows_software\openai whisper\whisper-keyboard-speaker-filter`.
