import json

import numpy as np
import pytest
from scipy.io.wavfile import write as wav_write


class FakeEmbedder:
    def embed(self, audio, sample_rate):
        _ = sample_rate
        if float(np.mean(audio)) >= 0:
            return np.array([1.0, 0.0], dtype=np.float32)
        return np.array([0.0, 1.0], dtype=np.float32)


def write_wav(path, value, sample_rate=16000):
    audio = np.full(sample_rate // 10, value, dtype=np.float32)
    wav_write(path, sample_rate, audio)


def test_calibration_writes_profile_and_report(tmp_path):
    from wkey.speaker_filter_calibrate import calibrate_speaker_filter

    positives = tmp_path / "positives"
    negatives = tmp_path / "negatives"
    positives.mkdir()
    negatives.mkdir()
    write_wav(positives / "harsha_1.wav", 0.8)
    write_wav(positives / "harsha_2.wav", 0.7)
    write_wav(negatives / "other_1.wav", -0.8)

    profile_path = tmp_path / "profile.json"
    report_path = tmp_path / "report.json"

    profile, report = calibrate_speaker_filter(
        enrollment_dir=positives,
        negative_dir=negatives,
        profile_path=profile_path,
        report_path=report_path,
        embedder=FakeEmbedder(),
    )

    assert profile_path.exists()
    assert report_path.exists()
    assert profile["target_embedding"] == [1.0, 0.0]
    assert profile["thresholds"]["balanced"] > profile["thresholds"]["permissive"]
    assert profile["thresholds"]["conservative"] > profile["thresholds"]["balanced"]
    assert profile["metadata"]["positive_count"] == 2
    assert profile["metadata"]["negative_count"] == 1
    assert report["positive_scores"] == [1.0, 1.0]
    assert report["negative_scores"] == [0.0]
    assert report["threshold_suggestions"] == profile["thresholds"]

    saved_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_profile == profile
    assert saved_report == report


def test_calibration_requires_positive_audio(tmp_path):
    from wkey.speaker_filter_calibrate import calibrate_speaker_filter

    positives = tmp_path / "empty"
    negatives = tmp_path / "negatives"
    positives.mkdir()
    negatives.mkdir()

    with pytest.raises(ValueError, match="positive enrollment"):
        calibrate_speaker_filter(
            enrollment_dir=positives,
            negative_dir=negatives,
            profile_path=tmp_path / "profile.json",
            report_path=tmp_path / "report.json",
            embedder=FakeEmbedder(),
        )
