from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ECAPA_MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
DEFAULT_THRESHOLDS = {
    "conservative": 0.82,
    "balanced": 0.72,
    "permissive": 0.62,
}
VALID_MODES = {"analysis", "conservative", "balanced", "permissive", "custom"}


@dataclass
class SpeakerFilterResult:
    audio: np.ndarray
    accepted_seconds: float
    rejected_seconds: float
    decision: str
    scores: list[float]
    threshold: float | None = None
    profile_loaded: bool = False


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_vec = np.asarray(a, dtype=np.float32).reshape(-1)
    b_vec = np.asarray(b, dtype=np.float32).reshape(-1)
    denom = float(np.linalg.norm(a_vec) * np.linalg.norm(b_vec))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a_vec, b_vec) / denom)


def load_profile(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        profile_path = Path(path)
        if not profile_path.exists():
            return None
        with profile_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _target_embedding_from_profile(profile: dict[str, Any] | None) -> np.ndarray | None:
    if not isinstance(profile, dict):
        return None
    value = (
        profile.get("target_embedding")
        or profile.get("target_centroid")
        or profile.get("embedding")
        or profile.get("centroid")
    )
    if value is None:
        return None
    vector = np.asarray(value, dtype=np.float32).reshape(-1)
    if vector.size == 0:
        return None
    return vector


def _as_mono_float32(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 0:
        return np.zeros((0,), dtype=np.float32)
    if array.ndim == 2:
        if array.shape[1] == 1:
            array = array[:, 0]
        else:
            array = np.mean(array, axis=1)
    return np.asarray(array.reshape(-1), dtype=np.float32)


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


class SpeechBrainEcapaEmbedder:
    def __init__(
        self,
        *,
        source: str = ECAPA_MODEL_ID,
        savedir: str | Path | None = None,
        target_sample_rate: int = 16000,
    ):
        self.source = source
        self.savedir = Path(savedir) if savedir else Path(tempfile.gettempdir()) / "ecapa_voxceleb_cache"
        self.target_sample_rate = target_sample_rate
        self._classifier = None

    def _load_classifier(self):
        if self._classifier is not None:
            return self._classifier
        try:
            import torchaudio

            if not hasattr(torchaudio, "list_audio_backends"):
                torchaudio.list_audio_backends = lambda: ["soundfile"]  # type: ignore[attr-defined]
            if not hasattr(torchaudio, "set_audio_backend"):
                torchaudio.set_audio_backend = lambda _backend: None  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            import inspect

            import huggingface_hub

            signature = inspect.signature(huggingface_hub.hf_hub_download)
            if "use_auth_token" not in signature.parameters:
                original_download = huggingface_hub.hf_hub_download

                def compat_hf_hub_download(*args, use_auth_token=None, **kwargs):
                    if use_auth_token is not None and "token" not in kwargs:
                        kwargs["token"] = use_auth_token
                    try:
                        return original_download(*args, **kwargs)
                    except Exception as exc:
                        filename = kwargs.get("filename")
                        if filename == "custom.py":
                            raise ValueError("Optional custom.py not found") from exc
                        raise

                huggingface_hub.hf_hub_download = compat_hf_hub_download
        except Exception:
            pass
        try:
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy
        except Exception:
            from speechbrain.pretrained import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

        self._classifier = EncoderClassifier.from_hparams(
            source=self.source,
            savedir=str(self.savedir),
            local_strategy=LocalStrategy.COPY,
        )
        return self._classifier

    def embed(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        import torch

        waveform = _as_mono_float32(audio)
        if waveform.size == 0:
            return np.zeros((1,), dtype=np.float32)
        if sample_rate != self.target_sample_rate:
            waveform = self._resample(waveform, sample_rate, self.target_sample_rate)
            sample_rate = self.target_sample_rate
        classifier = self._load_classifier()
        signal = torch.tensor(waveform, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            embedding = classifier.encode_batch(signal)
        vector = embedding.squeeze().detach().cpu().numpy().astype(np.float32)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    def _resample(
        self, audio: np.ndarray, source_sample_rate: int, target_sample_rate: int
    ) -> np.ndarray:
        if source_sample_rate <= 0 or source_sample_rate == target_sample_rate:
            return audio.astype(np.float32, copy=False)
        try:
            import torch
            import torchaudio.functional as F

            tensor = torch.tensor(audio, dtype=torch.float32)
            return (
                F.resample(tensor, source_sample_rate, target_sample_rate)
                .detach()
                .cpu()
                .numpy()
                .astype(np.float32)
            )
        except Exception:
            duration = audio.size / float(source_sample_rate)
            target_size = max(1, int(round(duration * target_sample_rate)))
            source_x = np.linspace(0.0, duration, num=audio.size, endpoint=False)
            target_x = np.linspace(0.0, duration, num=target_size, endpoint=False)
            return np.interp(target_x, source_x, audio).astype(np.float32)


class TargetSpeakerFilter:
    def __init__(
        self,
        *,
        profile: dict[str, Any] | None = None,
        embedder: Any | None = None,
        mode: str = "analysis",
        threshold: float = 0.72,
        chunk_seconds: float = 0.8,
        padding_seconds: float = 0.05,
        min_chunk_rms: float = 0.0,
        logger: logging.Logger | None = None,
    ):
        self.profile = profile
        self.embedder = embedder
        self.mode = mode if mode in VALID_MODES else "analysis"
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.chunk_seconds = max(0.05, float(chunk_seconds))
        self.padding_seconds = max(0.0, float(padding_seconds))
        self.min_chunk_rms = max(0.0, float(min_chunk_rms))
        self.log = logger or logging.getLogger(__name__)

    @classmethod
    def from_profile_path(cls, path: str | Path | None, **kwargs):
        return cls(profile=load_profile(path), **kwargs)

    def threshold_for_mode(self) -> float:
        if self.mode == "custom":
            return self.threshold
        thresholds = {}
        if isinstance(self.profile, dict) and isinstance(self.profile.get("thresholds"), dict):
            thresholds = self.profile["thresholds"]
        value = thresholds.get(self.mode, DEFAULT_THRESHOLDS.get(self.mode, self.threshold))
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return self.threshold

    def filter_audio(self, audio: np.ndarray, sample_rate: int) -> SpeakerFilterResult:
        waveform = _as_mono_float32(audio)
        total_seconds = self._seconds(waveform.size, sample_rate)
        target_embedding = _target_embedding_from_profile(self.profile)
        if target_embedding is None:
            if self.mode == "analysis":
                return SpeakerFilterResult(
                    audio=waveform,
                    accepted_seconds=0.0,
                    rejected_seconds=total_seconds,
                    decision="profile_missing_analysis",
                    scores=[],
                    threshold=None,
                    profile_loaded=False,
                )
            return SpeakerFilterResult(
                audio=np.zeros((0,), dtype=np.float32),
                accepted_seconds=0.0,
                rejected_seconds=total_seconds,
                decision="profile_missing",
                scores=[],
                threshold=None,
                profile_loaded=False,
            )

        if waveform.size == 0:
            return SpeakerFilterResult(
                audio=waveform,
                accepted_seconds=0.0,
                rejected_seconds=0.0,
                decision="empty",
                scores=[],
                threshold=self.threshold_for_mode(),
                profile_loaded=True,
            )

        threshold = self.threshold_for_mode()
        chunk_scores: list[float] = []
        accepted_intervals: list[tuple[int, int]] = []
        chunk_samples = max(1, int(round(self.chunk_seconds * sample_rate)))
        padding_samples = int(round(self.padding_seconds * sample_rate))

        for start in range(0, waveform.size, chunk_samples):
            end = min(waveform.size, start + chunk_samples)
            chunk = waveform[start:end]
            score = self._score_chunk(chunk, sample_rate, target_embedding)
            chunk_scores.append(score)
            if score >= threshold:
                accepted_intervals.append(
                    (
                        max(0, start - padding_samples),
                        min(waveform.size, end + padding_samples),
                    )
                )

        intervals = _merge_intervals(accepted_intervals)
        accepted_samples = sum(end - start for start, end in intervals)
        accepted_seconds = self._seconds(accepted_samples, sample_rate)
        rejected_seconds = max(0.0, total_seconds - accepted_seconds)

        if self.mode == "analysis":
            self.log.info(
                "Speaker filter analysis: threshold=%.3f accepted=%.2fs rejected=%.2fs scores=%s",
                threshold,
                accepted_seconds,
                rejected_seconds,
                [round(score, 3) for score in chunk_scores],
            )
            return SpeakerFilterResult(
                audio=waveform,
                accepted_seconds=accepted_seconds,
                rejected_seconds=rejected_seconds,
                decision="analysis",
                scores=chunk_scores,
                threshold=threshold,
                profile_loaded=True,
            )

        if not intervals:
            decision = "rejected"
            filtered = np.zeros((0,), dtype=np.float32)
        elif accepted_samples >= waveform.size:
            decision = "accepted"
            filtered = waveform
        else:
            decision = "filtered"
            filtered = np.concatenate([waveform[start:end] for start, end in intervals])

        self.log.info(
            "Speaker filter %s: threshold=%.3f accepted=%.2fs rejected=%.2fs",
            decision,
            threshold,
            accepted_seconds,
            rejected_seconds,
        )
        return SpeakerFilterResult(
            audio=filtered.astype(np.float32, copy=False),
            accepted_seconds=accepted_seconds,
            rejected_seconds=rejected_seconds,
            decision=decision,
            scores=chunk_scores,
            threshold=threshold,
            profile_loaded=True,
        )

    def _score_chunk(
        self, chunk: np.ndarray, sample_rate: int, target_embedding: np.ndarray
    ) -> float:
        if chunk.size == 0:
            return 0.0
        if self.min_chunk_rms > 0.0:
            rms = float(np.sqrt(np.mean(np.square(chunk))))
            if rms < self.min_chunk_rms:
                return 0.0
        embedder = self.embedder or SpeechBrainEcapaEmbedder()
        embedding = embedder.embed(chunk, sample_rate)
        return cosine_similarity(embedding, target_embedding)

    @staticmethod
    def _seconds(samples: int, sample_rate: int) -> float:
        if sample_rate <= 0:
            return 0.0
        return round(samples / float(sample_rate), 6)

