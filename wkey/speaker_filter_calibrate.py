from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io.wavfile import read as wav_read

try:
    from speaker_filter import (
        DEFAULT_THRESHOLDS,
        SpeechBrainEcapaEmbedder,
        cosine_similarity,
    )
except ModuleNotFoundError:
    from wkey.speaker_filter import (
        DEFAULT_THRESHOLDS,
        SpeechBrainEcapaEmbedder,
        cosine_similarity,
    )


DEFAULT_ENROLLMENT_DIR = Path(r"I:\Record_only_by_harsha")
DEFAULT_NEGATIVE_DIR = Path(r"I:\Record_others_16k_wav")
DEFAULT_PROFILE_PATH = Path("wkey/speaker_filter_profile.json")
DEFAULT_REPORT_PATH = Path("wkey/speaker_filter_calibration_report.json")
AUDIO_SUFFIXES = {".wav"}


def discover_audio_files(directory: str | Path | None, limit: int | None = None) -> list[Path]:
    if not directory:
        return []
    root = Path(directory)
    if not root.exists():
        return []
    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
    ]
    if limit is not None:
        return files[: max(0, int(limit))]
    return files


def load_wav_mono(path: str | Path) -> tuple[np.ndarray, int]:
    sample_rate, data = wav_read(path)
    audio = np.asarray(data)
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float32)
    if np.issubdtype(np.asarray(data).dtype, np.integer):
        max_value = float(np.iinfo(np.asarray(data).dtype).max)
        if max_value > 0:
            audio = audio / max_value
    return audio.reshape(-1), int(sample_rate)


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


def _embed_files(files: list[Path], embedder: Any) -> list[dict[str, Any]]:
    rows = []
    for path in files:
        audio, sample_rate = load_wav_mono(path)
        embedding = _normalize_embedding(embedder.embed(audio, sample_rate))
        rows.append({"path": str(path), "embedding": embedding})
    return rows


def _round(value: float) -> float:
    return round(float(value), 6)


def _round_list(values: np.ndarray) -> list[float]:
    return [_round(value) for value in np.asarray(values, dtype=np.float32).reshape(-1)]


def _threshold_suggestions(
    positive_scores: list[float], negative_scores: list[float]
) -> dict[str, float]:
    if not positive_scores:
        return dict(DEFAULT_THRESHOLDS)
    positive_floor = float(np.percentile(positive_scores, 10))
    if negative_scores:
        negative_ceiling = float(np.percentile(negative_scores, 90))
        balanced = (positive_floor + negative_ceiling) / 2.0
        permissive = max(negative_ceiling + 0.05, balanced - 0.15)
        conservative = min(positive_floor - 0.02, balanced + 0.15)
    else:
        balanced = positive_floor * 0.9
        permissive = balanced - 0.12
        conservative = min(0.98, positive_floor - 0.02)

    balanced = max(0.01, min(0.99, balanced))
    permissive = max(0.01, min(balanced - 0.01, permissive))
    conservative = max(balanced + 0.01, min(0.99, conservative))
    return {
        "conservative": _round(conservative),
        "balanced": _round(balanced),
        "permissive": _round(permissive),
    }


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def calibrate_speaker_filter(
    *,
    enrollment_dir: str | Path = DEFAULT_ENROLLMENT_DIR,
    negative_dir: str | Path = DEFAULT_NEGATIVE_DIR,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    embedder: Any | None = None,
    max_positive_files: int | None = None,
    max_negative_files: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    positive_files = discover_audio_files(enrollment_dir, max_positive_files)
    negative_files = discover_audio_files(negative_dir, max_negative_files)
    if not positive_files:
        raise ValueError(f"No positive enrollment audio found in {enrollment_dir}")

    embedding_backend = embedder or SpeechBrainEcapaEmbedder()
    positive_rows = _embed_files(positive_files, embedding_backend)
    negative_rows = _embed_files(negative_files, embedding_backend)
    positive_embeddings = [row["embedding"] for row in positive_rows]
    centroid = _normalize_embedding(np.mean(np.stack(positive_embeddings), axis=0))

    positive_scores = [
        _round(cosine_similarity(row["embedding"], centroid)) for row in positive_rows
    ]
    negative_scores = [
        _round(cosine_similarity(row["embedding"], centroid)) for row in negative_rows
    ]
    thresholds = _threshold_suggestions(positive_scores, negative_scores)
    created_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "created_at": created_at,
        "positive_count": len(positive_rows),
        "negative_count": len(negative_rows),
        "enrollment_dir": str(Path(enrollment_dir)),
        "negative_dir": str(Path(negative_dir)),
        "backend": embedding_backend.__class__.__name__,
    }
    profile = {
        "schema_version": 1,
        "target_embedding": _round_list(centroid),
        "thresholds": thresholds,
        "metadata": metadata,
    }
    report = {
        "schema_version": 1,
        "metadata": metadata,
        "positive_files": [row["path"] for row in positive_rows],
        "negative_files": [row["path"] for row in negative_rows],
        "positive_scores": positive_scores,
        "negative_scores": negative_scores,
        "threshold_suggestions": thresholds,
    }

    write_json(profile_path, profile)
    write_json(report_path, report)
    return profile, report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate a target-speaker filter profile from local voice folders."
    )
    parser.add_argument("--enrollment-dir", default=str(DEFAULT_ENROLLMENT_DIR))
    parser.add_argument("--negative-dir", default=str(DEFAULT_NEGATIVE_DIR))
    parser.add_argument("--profile-path", default=str(DEFAULT_PROFILE_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--max-positive-files", type=int, default=None)
    parser.add_argument("--max-negative-files", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    profile, report = calibrate_speaker_filter(
        enrollment_dir=args.enrollment_dir,
        negative_dir=args.negative_dir,
        profile_path=args.profile_path,
        report_path=args.report_path,
        max_positive_files=args.max_positive_files,
        max_negative_files=args.max_negative_files,
    )
    print(
        "Wrote speaker profile to "
        f"{args.profile_path} using {profile['metadata']['positive_count']} positive "
        f"and {profile['metadata']['negative_count']} negative files."
    )
    print(f"Threshold suggestions: {report['threshold_suggestions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
