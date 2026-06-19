import json

import numpy as np

from wkey.speaker_filter import TargetSpeakerFilter


class FakeEmbedder:
    def embed(self, audio, sample_rate):
        _ = sample_rate
        if float(np.mean(audio)) > 0.5:
            return np.array([1.0, 0.0], dtype=np.float32)
        return np.array([0.0, 1.0], dtype=np.float32)


def make_filter(**overrides):
    profile = {
        "target_embedding": [1.0, 0.0],
        "thresholds": {
            "conservative": 0.9,
            "balanced": 0.7,
            "permissive": 0.4,
        },
    }
    params = {
        "profile": profile,
        "embedder": FakeEmbedder(),
        "mode": "balanced",
        "threshold": 0.7,
        "chunk_seconds": 1.0,
        "padding_seconds": 0.0,
    }
    params.update(overrides)
    return TargetSpeakerFilter(**params)


def test_accepts_target_speaker_audio():
    filt = make_filter()
    audio = np.ones(20, dtype=np.float32)

    result = filt.filter_audio(audio, sample_rate=10)

    assert result.decision == "accepted"
    assert np.array_equal(result.audio, audio)
    assert result.accepted_seconds == 2.0
    assert result.rejected_seconds == 0.0
    assert result.scores == [1.0, 1.0]


def test_rejects_other_speaker_audio():
    filt = make_filter()
    audio = np.zeros(20, dtype=np.float32)

    result = filt.filter_audio(audio, sample_rate=10)

    assert result.decision == "rejected"
    assert result.audio.size == 0
    assert result.accepted_seconds == 0.0
    assert result.rejected_seconds == 2.0
    assert result.scores == [0.0, 0.0]


def test_mixed_audio_keeps_only_target_chunks():
    filt = make_filter()
    audio = np.concatenate(
        [
            np.ones(10, dtype=np.float32),
            np.zeros(10, dtype=np.float32),
            np.ones(10, dtype=np.float32),
        ]
    )

    result = filt.filter_audio(audio, sample_rate=10)

    assert result.decision == "filtered"
    assert np.array_equal(result.audio, np.ones(20, dtype=np.float32))
    assert result.accepted_seconds == 2.0
    assert result.rejected_seconds == 1.0
    assert result.scores == [1.0, 0.0, 1.0]


def test_analysis_mode_logs_scores_but_preserves_audio():
    filt = make_filter(mode="analysis")
    audio = np.zeros(20, dtype=np.float32)

    result = filt.filter_audio(audio, sample_rate=10)

    assert result.decision == "analysis"
    assert np.array_equal(result.audio, audio)
    assert result.accepted_seconds == 0.0
    assert result.rejected_seconds == 2.0
    assert result.scores == [0.0, 0.0]


def test_missing_profile_rejects_live_filtering_but_not_analysis():
    live = TargetSpeakerFilter(profile=None, embedder=FakeEmbedder(), mode="balanced")
    analysis = TargetSpeakerFilter(profile=None, embedder=FakeEmbedder(), mode="analysis")
    audio = np.ones(10, dtype=np.float32)

    live_result = live.filter_audio(audio, sample_rate=10)
    analysis_result = analysis.filter_audio(audio, sample_rate=10)

    assert live_result.decision == "profile_missing"
    assert live_result.audio.size == 0
    assert analysis_result.decision == "profile_missing_analysis"
    assert np.array_equal(analysis_result.audio, audio)


def test_loads_profile_from_json(tmp_path):
    profile_path = tmp_path / "speaker_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "target_embedding": [1.0, 0.0],
                "thresholds": {"balanced": 0.75},
            }
        ),
        encoding="utf-8",
    )

    filt = TargetSpeakerFilter.from_profile_path(
        profile_path,
        embedder=FakeEmbedder(),
        mode="balanced",
        threshold=0.5,
        chunk_seconds=1.0,
        padding_seconds=0.0,
    )

    assert filt.threshold_for_mode() == 0.75
