# Target-Speaker Paste Filter Design

Date: 2026-06-19

## Summary

Add a local target-speaker filter for manual dictation. When a recording contains other voices, the backend should keep only chunks that match the enrolled Harsha voice before transcription and paste. V1 uses speaker verification over VAD chunks, not diarization.

## Architecture

- `wkey/speaker_filter.py` owns profile loading, ECAPA embedding, chunk scoring, threshold selection, and audio filtering.
- `wkey/speaker_filter_calibrate.py` builds a local profile from positive and negative voice folders.
- `wkey/transcription_pipeline.py` calls the filter only when `keyword_index is None`.
- `wkey/settings_manager.py` and Control Center expose adjustable filter settings.
- Generated speaker profiles and calibration reports are local runtime artifacts and are ignored by git.

Default corpus paths:

- Positive enrollment: `I:\Record_only_by_harsha`
- Negative calibration: `I:\Record_others_16k_wav`

## Behavior

Modes:

- `analysis`: do not modify audio; log scores and threshold decision.
- `conservative`: high threshold; prioritize blocking other speakers.
- `balanced`: calibrated middle threshold; default after profile calibration.
- `permissive`: lower threshold; prioritize keeping Harsha speech.
- `custom`: use `speaker_filter_threshold`.

Failure behavior:

- Disabled filter preserves current dictation behavior.
- Enabled filter with missing/unreadable profile logs a warning and preserves audio in `analysis`, but rejects live filtering in other modes.
- If no chunks pass in live mode, do not transcribe or paste that recording.
- Overlapping speech is not solved in v1; those chunks may be rejected or remain contaminated.

## Interfaces

Settings:

- `speaker_filter_enabled: bool`
- `speaker_filter_mode: str`
- `speaker_filter_threshold: float`
- `speaker_filter_profile_path: str`
- `speaker_filter_enrollment_dir: str`
- `speaker_filter_negative_dir: str`
- `speaker_filter_apply_to: "dictation"`

Runtime API:

- `TargetSpeakerFilter.filter_audio(audio: np.ndarray, sample_rate: int) -> SpeakerFilterResult`
- `SpeakerFilterResult.audio`
- `SpeakerFilterResult.accepted_seconds`
- `SpeakerFilterResult.rejected_seconds`
- `SpeakerFilterResult.decision`
- `SpeakerFilterResult.scores`

## Verification

- Unit tests use fake deterministic embedding functions for red/green cycles.
- Pipeline tests prove only manual dictation is filtered.
- Settings and Control Center tests prove the new controls normalize and persist.
- Calibration smoke uses a small sampled subset of the configured positive/negative folders.
- Required repo verification remains full pytest, compile, diff-check, and bounded primary-script smoke.
