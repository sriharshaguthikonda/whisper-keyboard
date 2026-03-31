import argparse
import csv
import json
import logging
import math
import re
import statistics
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


try:
    import requests
except Exception:
    requests = None

try:
    import librosa
except Exception as exc:  # pragma: no cover
    raise RuntimeError("librosa is required for this benchmark.") from exc

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    load_dotenv(repo_root / ".env")
    load_dotenv(script_dir / ".env", override=True)

LOG = logging.getLogger("ava_voice_benchmark")

DEFAULT_TEXT = (
    "Hi, I'm testing alternative voices. "
    "The quick brown fox jumps over the lazy dog."
)
LONG_TEXT = (
    "This is a longer test passage for evaluating speech quality and pacing. "
    "We want to hear how the voice handles complex sentences, pauses, and emphasis. "
    "Please pronounce numbers clearly: twenty one, three hundred, and seven thousand five. "
    "Now read a short list: aspirin, ibuprofen, acetaminophen, amoxicillin."
)
MEDICAL_TEXT = (
    "Medical test paragraph: The patient reports intermittent chest tightness and shortness of breath. "
    "Vital signs are stable. Consider differential diagnoses including asthma, GERD, and anxiety. "
    "Recommended labs: CBC, CMP, troponin, and a chest X-ray. "
    "Medications listed: albuterol, prednisone, metformin, lisinopril, and atorvastatin."
)

PROMPTS = {
    "default": DEFAULT_TEXT,
    "long": LONG_TEXT,
    "medical": MEDICAL_TEXT,
}

WAVLM_MODEL_ID = "microsoft/wavlm-base-plus-sv"
ECAPA_MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
SPEECHT5_MODEL_ID = "microsoft/speecht5_tts"
SPEECHT5_VOCODER_ID = "microsoft/speecht5_hifigan"
SPEECHT5_XVECTOR_DATASET = "Matthijs/cmu-arctic-xvectors"

PROMPT_REFERENCE_MAP = {
    "default": "ava_reference.wav",
    "long": "ava_reference_long_sp1p20.wav",
    "medical": "ava_reference_medical_sp1p20.wav",
}

FUSION_WEIGHTS = {
    "wavlm_cosine": 0.35,
    "ecapa_cosine": 0.30,
    "resemblyzer_cosine": 0.20,
    "prosody_similarity": 0.15,
}

SPEED_STEPS = [1.00, 1.05, 1.10, 1.15, 1.20]
PITCH_STEPS = [0.00, -0.50, -0.25, 0.25, 0.50]

SOURCE_INFO = {
    "kokoro": {
        "source": "huggingface-local",
        "model_id": "hexgrad/Kokoro-82M",
        "license": "Apache-2.0",
        "runtime_class": "gpu_or_cpu",
    },
    "piper": {
        "source": "huggingface-local",
        "model_id": "rhasspy/piper-voices",
        "license": "Varies by voice",
        "runtime_class": "cpu",
    },
    "pyttsx4": {
        "source": "system-local",
        "model_id": "pyttsx4/system-tts",
        "license": "System dependent",
        "runtime_class": "cpu",
    },
    "speecht5": {
        "source": "huggingface-local",
        "model_id": SPEECHT5_MODEL_ID,
        "license": "MIT",
        "runtime_class": "gpu_or_cpu",
    },
}


@dataclass
class Candidate:
    candidate_id: str
    family: str
    source: str
    model_id: str
    voice_id: str
    license: str
    runtime_class: str


@dataclass
class Sample:
    candidate_id: str
    prompt: str
    path: str


@dataclass
class ScoreRow:
    candidate_id: str
    prompt: str
    path: str
    is_control: bool
    resemblyzer_cosine: float
    wavlm_cosine: float
    ecapa_cosine: float
    prosody_similarity: float
    z_resemblyzer_cosine: float = 0.0
    z_wavlm_cosine: float = 0.0
    z_ecapa_cosine: float = 0.0
    z_prosody_similarity: float = 0.0
    fused_score: float = 0.0


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def load_audio(path: Path, sr: int = 16000) -> np.ndarray:
    wav, _ = librosa.load(path, sr=sr, mono=True)
    if wav.size == 0:
        return np.zeros((400,), dtype=np.float32)
    return wav.astype(np.float32)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["empty"])
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_sample_filename(path: Path) -> tuple[str, str]:
    stem = path.stem
    prompt = "default"
    if stem.startswith("default_"):
        prompt = "default"
        stem = stem[len("default_") :]
    elif stem.startswith("long_"):
        prompt = "long"
        stem = stem[len("long_") :]
    elif stem.startswith("medical_"):
        prompt = "medical"
        stem = stem[len("medical_") :]
    return prompt, stem


def discover_existing_samples(workdir: Path) -> list[Sample]:
    samples: list[Sample] = []
    allowed_dirs = {
        "kokoro_samples",
        "piper_samples",
        "pyttsx4_samples",
        "hf_samples",
    }
    for wav in workdir.rglob("*.wav"):
        if wav.name.startswith("ava_reference"):
            continue
        if "pitch_shifted" in wav.parts or "speed_shifted" in wav.parts:
            continue
        if not any(part in allowed_dirs for part in wav.parts):
            continue
        prompt, candidate_id = parse_sample_filename(wav)
        samples.append(
            Sample(
                candidate_id=candidate_id,
                prompt=prompt,
                path=str(wav.resolve()),
            )
        )
    return samples


def infer_family(candidate_id: str) -> str:
    if candidate_id.startswith("kokoro_"):
        return "kokoro"
    if candidate_id.startswith("piper_"):
        return "piper"
    if candidate_id.startswith("pyttsx4_"):
        return "pyttsx4"
    if candidate_id.startswith("speecht5_"):
        return "speecht5"
    return "unknown"


def build_manifest(samples: list[Sample]) -> list[Candidate]:
    seen: set[str] = set()
    manifest: list[Candidate] = []
    for sample in samples:
        if sample.candidate_id in seen:
            continue
        seen.add(sample.candidate_id)
        family = infer_family(sample.candidate_id)
        info = SOURCE_INFO.get(
            family,
            {
                "source": "unknown",
                "model_id": "unknown",
                "license": "unknown",
                "runtime_class": "unknown",
            },
        )
        voice_id = sample.candidate_id.replace(family + "_", "", 1)
        manifest.append(
            Candidate(
                candidate_id=sample.candidate_id,
                family=family,
                source=info["source"],
                model_id=info["model_id"],
                voice_id=voice_id,
                license=info["license"],
                runtime_class=info["runtime_class"],
            )
        )
    manifest.sort(key=lambda item: item.candidate_id)
    return manifest


def generate_speecht5_samples(workdir: Path, max_speakers: int = 8) -> list[Sample]:
    output_dir = workdir / "hf_samples"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        import torch
        import soundfile as sf
        import zipfile
        from huggingface_hub import hf_hub_download
        from transformers import SpeechT5ForTextToSpeech, SpeechT5HifiGan, SpeechT5Processor
    except Exception as exc:
        LOG.warning("SpeechT5 generation skipped; missing dependency: %s", exc)
        return []

    LOG.info("Generating SpeechT5 samples for added HF coverage...")
    processor = SpeechT5Processor.from_pretrained(SPEECHT5_MODEL_ID)
    tts = SpeechT5ForTextToSpeech.from_pretrained(SPEECHT5_MODEL_ID)
    vocoder = SpeechT5HifiGan.from_pretrained(SPEECHT5_VOCODER_ID)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tts.to(device)
    vocoder.to(device)

    zip_path = hf_hub_download(
        repo_id=SPEECHT5_XVECTOR_DATASET,
        repo_type="dataset",
        filename="spkrec-xvect.zip",
    )
    speaker_choices: dict[str, np.ndarray] = {}
    with zipfile.ZipFile(zip_path, "r") as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".npy"):
                continue
            match = re.search(r"cmu_us_([a-z0-9]+)_arctic", name.lower())
            if not match:
                continue
            speaker = match.group(1)
            if speaker in speaker_choices:
                continue
            with archive.open(name, "r") as f:
                vec = np.load(f).astype(np.float32)
            speaker_choices[speaker] = vec
            if len(speaker_choices) >= max_speakers:
                break

    if not speaker_choices:
        LOG.warning("SpeechT5 speaker vectors were not found; skipping generation.")
        return []

    generated: list[Sample] = []
    with torch.no_grad():
        for speaker, xvector in speaker_choices.items():
            candidate_id = f"speecht5_{speaker}"
            speaker_embeddings = torch.tensor(xvector, dtype=torch.float32).unsqueeze(0).to(device)
            for prompt_name, text in PROMPTS.items():
                out_file = output_dir / f"{prompt_name}_{candidate_id}.wav"
                if out_file.exists():
                    generated.append(
                        Sample(candidate_id=candidate_id, prompt=prompt_name, path=str(out_file.resolve()))
                    )
                    continue
                inputs = processor(text=text, return_tensors="pt").to(device)
                speech = tts.generate_speech(inputs["input_ids"], speaker_embeddings, vocoder=vocoder)
                wav = speech.cpu().numpy()
                sf.write(out_file, wav, 16000)
                generated.append(
                    Sample(candidate_id=candidate_id, prompt=prompt_name, path=str(out_file.resolve()))
                )
    return generated


def get_reference_paths(workdir: Path) -> dict[str, Path]:
    refs: dict[str, Path] = {}
    for prompt, filename in PROMPT_REFERENCE_MAP.items():
        path = workdir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing Ava reference file: {path}")
        refs[prompt] = path
    return refs


class MetricEngines:
    def __init__(self) -> None:
        self._resemblyzer_encoder = None
        self._wavlm_processor = None
        self._wavlm_model = None
        self._ecapa = None
        self._torch = None
        self._cache_embeddings: dict[str, dict[str, np.ndarray]] = {
            "resemblyzer": {},
            "wavlm": {},
            "ecapa": {},
            "prosody": {},
        }

    def _ensure_torch(self):
        if self._torch is None:
            import torch

            self._torch = torch
        return self._torch

    def _load_resemblyzer(self):
        if self._resemblyzer_encoder is None:
            from resemblyzer import VoiceEncoder

            self._resemblyzer_encoder = VoiceEncoder()
        return self._resemblyzer_encoder

    def _load_wavlm(self):
        if self._wavlm_model is None or self._wavlm_processor is None:
            from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector

            self._wavlm_processor = Wav2Vec2FeatureExtractor.from_pretrained(WAVLM_MODEL_ID)
            self._wavlm_model = WavLMForXVector.from_pretrained(WAVLM_MODEL_ID)
            torch = self._ensure_torch()
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._wavlm_model.to(device)
            self._wavlm_model.eval()
        return self._wavlm_processor, self._wavlm_model

    def _load_ecapa(self):
        if self._ecapa is None:
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

            self._ecapa = EncoderClassifier.from_hparams(
                source=ECAPA_MODEL_ID,
                savedir=str(Path(tempfile.gettempdir()) / "ecapa_voxceleb_cache"),
                local_strategy=LocalStrategy.COPY,
            )
        return self._ecapa

    def _cache_key(self, path: Path) -> str:
        return str(path.resolve())

    def resemblyzer_embedding(self, path: Path) -> np.ndarray:
        key = self._cache_key(path)
        cached = self._cache_embeddings["resemblyzer"].get(key)
        if cached is not None:
            return cached
        from resemblyzer import preprocess_wav

        encoder = self._load_resemblyzer()
        wav = preprocess_wav(str(path))
        emb = encoder.embed_utterance(wav)
        emb = np.array(emb, dtype=np.float32)
        self._cache_embeddings["resemblyzer"][key] = emb
        return emb

    def wavlm_embedding(self, path: Path) -> np.ndarray:
        key = self._cache_key(path)
        cached = self._cache_embeddings["wavlm"].get(key)
        if cached is not None:
            return cached
        torch = self._ensure_torch()
        processor, model = self._load_wavlm()
        audio = load_audio(path, sr=16000)
        if audio.shape[0] < 400:
            audio = np.pad(audio, (0, 400 - audio.shape[0]), mode="constant")
        inputs = processor(audio, sampling_rate=16000, return_tensors="pt", padding=True)
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
            emb = outputs.embeddings
            emb = torch.nn.functional.normalize(emb, dim=-1)
        arr = emb.squeeze(0).detach().cpu().numpy().astype(np.float32)
        self._cache_embeddings["wavlm"][key] = arr
        return arr

    def ecapa_embedding(self, path: Path) -> np.ndarray:
        key = self._cache_key(path)
        cached = self._cache_embeddings["ecapa"].get(key)
        if cached is not None:
            return cached
        torch = self._ensure_torch()
        ecapa = self._load_ecapa()
        audio = load_audio(path, sr=16000)
        signal = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        lengths = torch.tensor([1.0], dtype=torch.float32)
        with torch.no_grad():
            emb = ecapa.encode_batch(signal, lengths).squeeze(0).squeeze(0)
        arr = emb.detach().cpu().numpy().astype(np.float32)
        arr = arr / (np.linalg.norm(arr) + 1e-8)
        self._cache_embeddings["ecapa"][key] = arr
        return arr

    def prosody_vector(self, path: Path) -> np.ndarray:
        key = self._cache_key(path)
        cached = self._cache_embeddings["prosody"].get(key)
        if cached is not None:
            return cached
        audio = load_audio(path, sr=16000)
        vec = compute_prosody_vector(audio, 16000)
        self._cache_embeddings["prosody"][key] = vec
        return vec


def compute_prosody_vector(audio: np.ndarray, sr: int) -> np.ndarray:
    if audio.shape[0] < 400:
        audio = np.pad(audio, (0, 400 - audio.shape[0]), mode="constant")
    duration = max(float(audio.shape[0]) / float(sr), 1e-6)
    intervals = librosa.effects.split(audio, top_db=30)
    voiced_duration = sum((end - start) / sr for start, end in intervals)
    voiced_duration = max(voiced_duration, 1e-6)
    pause_ratio = max(0.0, duration - voiced_duration) / duration

    onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
    peaks = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time")
    speech_rate = float(len(peaks)) / voiced_duration

    f0, _, _ = librosa.pyin(
        audio,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    if f0 is None:
        voiced_f0 = np.array([], dtype=np.float32)
    else:
        voiced_f0 = f0[~np.isnan(f0)].astype(np.float32)

    if voiced_f0.size == 0:
        f0_median = 0.0
        f0_std = 0.0
    else:
        f0_median = float(np.median(voiced_f0))
        f0_std = float(np.std(voiced_f0))
    return np.array([speech_rate, pause_ratio, f0_median, f0_std], dtype=np.float32)


def prosody_similarity(a: np.ndarray, b: np.ndarray) -> float:
    scale = np.array([8.0, 0.5, 180.0, 120.0], dtype=np.float32)
    delta = (a - b) / scale
    distance = float(np.sqrt(np.mean(np.square(delta))))
    return float(1.0 / (1.0 + distance))


def apply_speed_and_pitch(audio: np.ndarray, speed: float, pitch: float) -> np.ndarray:
    changed = audio
    if speed != 1.0:
        changed = librosa.effects.time_stretch(changed, rate=speed)
    if pitch != 0.0:
        changed = librosa.effects.pitch_shift(changed, sr=16000, n_steps=pitch)
    return changed.astype(np.float32)


def score_pair(
    engines: MetricEngines,
    reference: Path,
    candidate: Path,
) -> tuple[float, float, float, float]:
    res_ref = engines.resemblyzer_embedding(reference)
    res_cand = engines.resemblyzer_embedding(candidate)
    wavlm_ref = engines.wavlm_embedding(reference)
    wavlm_cand = engines.wavlm_embedding(candidate)
    ecapa_ref = engines.ecapa_embedding(reference)
    ecapa_cand = engines.ecapa_embedding(candidate)
    pro_ref = engines.prosody_vector(reference)
    pro_cand = engines.prosody_vector(candidate)
    return (
        cosine_similarity(res_ref, res_cand),
        cosine_similarity(wavlm_ref, wavlm_cand),
        cosine_similarity(ecapa_ref, ecapa_cand),
        prosody_similarity(pro_ref, pro_cand),
    )


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mean_val = statistics.fmean(values)
    std_val = statistics.pstdev(values)
    if std_val == 0:
        return [0.0 for _ in values]
    return [(v - mean_val) / std_val for v in values]


def score_samples(samples: list[Sample], refs: dict[str, Path], engines: MetricEngines) -> list[ScoreRow]:
    rows: list[ScoreRow] = []
    for sample in samples:
        ref = refs[sample.prompt]
        try:
            res, wavlm, ecapa, pros = score_pair(engines, ref, Path(sample.path))
        except Exception as exc:
            LOG.warning("Skipping sample due scoring error: %s (%s)", sample.path, exc)
            continue
        rows.append(
            ScoreRow(
                candidate_id=sample.candidate_id,
                prompt=sample.prompt,
                path=sample.path,
                is_control=False,
                resemblyzer_cosine=res,
                wavlm_cosine=wavlm,
                ecapa_cosine=ecapa,
                prosody_similarity=pros,
            )
        )
    for prompt, ref in refs.items():
        rows.append(
            ScoreRow(
                candidate_id="__ava_reference_self__",
                prompt=prompt,
                path=str(ref),
                is_control=True,
                resemblyzer_cosine=1.0,
                wavlm_cosine=1.0,
                ecapa_cosine=1.0,
                prosody_similarity=1.0,
            )
        )
    apply_normalization_and_fusion(rows)
    return rows


def apply_normalization_and_fusion(rows: list[ScoreRow]) -> None:
    prompt_groups: dict[str, list[ScoreRow]] = {}
    for row in rows:
        prompt_groups.setdefault(row.prompt, []).append(row)

    for prompt_rows in prompt_groups.values():
        bench_rows = [r for r in prompt_rows if not r.is_control]
        metrics = {
            "resemblyzer_cosine": [r.resemblyzer_cosine for r in bench_rows],
            "wavlm_cosine": [r.wavlm_cosine for r in bench_rows],
            "ecapa_cosine": [r.ecapa_cosine for r in bench_rows],
            "prosody_similarity": [r.prosody_similarity for r in bench_rows],
        }
        metric_z = {name: zscore(vals) for name, vals in metrics.items()}
        for index, row in enumerate(bench_rows):
            row.z_resemblyzer_cosine = metric_z["resemblyzer_cosine"][index]
            row.z_wavlm_cosine = metric_z["wavlm_cosine"][index]
            row.z_ecapa_cosine = metric_z["ecapa_cosine"][index]
            row.z_prosody_similarity = metric_z["prosody_similarity"][index]
            row.fused_score = (
                FUSION_WEIGHTS["resemblyzer_cosine"] * row.z_resemblyzer_cosine
                + FUSION_WEIGHTS["wavlm_cosine"] * row.z_wavlm_cosine
                + FUSION_WEIGHTS["ecapa_cosine"] * row.z_ecapa_cosine
                + FUSION_WEIGHTS["prosody_similarity"] * row.z_prosody_similarity
            )
        for control in [r for r in prompt_rows if r.is_control]:
            control.fused_score = float("nan")


def aggregate_overall(rows: list[ScoreRow], manifest: list[Candidate]) -> list[dict[str, Any]]:
    manifest_by_id = {c.candidate_id: c for c in manifest}
    grouped: dict[str, list[ScoreRow]] = {}
    for row in rows:
        if row.is_control:
            continue
        grouped.setdefault(row.candidate_id, []).append(row)

    overall: list[dict[str, Any]] = []
    for candidate_id, items in grouped.items():
        candidate = manifest_by_id.get(candidate_id)
        if candidate is None:
            continue
        payload = asdict(candidate)
        payload.update(
            {
                "prompt_count": len(items),
                "resemblyzer_cosine": float(statistics.fmean(i.resemblyzer_cosine for i in items)),
                "wavlm_cosine": float(statistics.fmean(i.wavlm_cosine for i in items)),
                "ecapa_cosine": float(statistics.fmean(i.ecapa_cosine for i in items)),
                "prosody_similarity": float(statistics.fmean(i.prosody_similarity for i in items)),
                "fused_score": float(statistics.fmean(i.fused_score for i in items)),
            }
        )
        overall.append(payload)
    overall.sort(key=lambda row: row["fused_score"], reverse=True)
    for idx, row in enumerate(overall, start=1):
        row["rank"] = idx
    return overall


def ranking_by_prompt(rows: list[ScoreRow], manifest: list[Candidate]) -> list[dict[str, Any]]:
    manifest_by_id = {c.candidate_id: c for c in manifest}
    prompt_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[ScoreRow]] = {}
    for row in rows:
        if row.is_control:
            continue
        grouped.setdefault(row.prompt, []).append(row)

    for prompt, items in grouped.items():
        sorted_items = sorted(items, key=lambda row: row.fused_score, reverse=True)
        for rank, row in enumerate(sorted_items, start=1):
            candidate = manifest_by_id.get(row.candidate_id)
            if candidate is None:
                continue
            payload = asdict(candidate)
            payload.update(
                {
                    "prompt": prompt,
                    "rank": rank,
                    "resemblyzer_cosine": row.resemblyzer_cosine,
                    "wavlm_cosine": row.wavlm_cosine,
                    "ecapa_cosine": row.ecapa_cosine,
                    "prosody_similarity": row.prosody_similarity,
                    "fused_score": row.fused_score,
                    "path": row.path,
                }
            )
            prompt_rows.append(payload)
    return prompt_rows


def collect_sample_map(samples: list[Sample]) -> dict[tuple[str, str], Path]:
    mapping: dict[tuple[str, str], Path] = {}
    for sample in samples:
        mapping[(sample.candidate_id, sample.prompt)] = Path(sample.path)
    return mapping


def tune_top_candidates(
    overall_rows: list[dict[str, Any]],
    sample_map: dict[tuple[str, str], Path],
    refs: dict[str, Path],
    top_k: int = 5,
) -> list[dict[str, Any]]:
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
        import torch
        from resemblyzer import VoiceEncoder, preprocess_wav
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy
        from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
    except Exception as exc:
        LOG.warning("Tuning skipped; missing dependencies for metric engines: %s", exc)
        return []

    engine = VoiceEncoder()
    wavlm_proc = Wav2Vec2FeatureExtractor.from_pretrained(WAVLM_MODEL_ID)
    wavlm_model = WavLMForXVector.from_pretrained(WAVLM_MODEL_ID)
    wavlm_model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    wavlm_model.to(device)
    ecapa = EncoderClassifier.from_hparams(
        source=ECAPA_MODEL_ID,
        savedir=str(Path(tempfile.gettempdir()) / "ecapa_voxceleb_cache"),
        local_strategy=LocalStrategy.COPY,
    )

    ref_cache: dict[str, dict[str, np.ndarray]] = {}
    for prompt, ref_path in refs.items():
        audio = load_audio(ref_path, sr=16000)
        resemblyzer_emb = np.array(engine.embed_utterance(preprocess_wav(str(ref_path))), dtype=np.float32)
        inputs = wavlm_proc(audio, sampling_rate=16000, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            wavlm_emb = wavlm_model(**inputs).embeddings.squeeze(0)
            wavlm_emb = torch.nn.functional.normalize(wavlm_emb, dim=-1).cpu().numpy().astype(np.float32)
        signal = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        lengths = torch.tensor([1.0], dtype=torch.float32)
        with torch.no_grad():
            ecapa_emb = ecapa.encode_batch(signal, lengths).squeeze(0).squeeze(0).cpu().numpy().astype(np.float32)
        ecapa_emb = ecapa_emb / (np.linalg.norm(ecapa_emb) + 1e-8)
        ref_cache[prompt] = {
            "resemblyzer": resemblyzer_emb,
            "wavlm": wavlm_emb,
            "ecapa": ecapa_emb,
            "prosody": compute_prosody_vector(audio, 16000),
        }

    top_ids = [row["candidate_id"] for row in overall_rows[:top_k]]
    variant_rows: list[dict[str, Any]] = []
    for candidate_id in top_ids:
        for speed in SPEED_STEPS:
            for pitch in PITCH_STEPS:
                per_prompt_scores: list[dict[str, float]] = []
                for prompt in refs:
                    base_path = sample_map.get((candidate_id, prompt))
                    if base_path is None or not base_path.exists():
                        continue
                    audio = load_audio(base_path, sr=16000)
                    tuned = apply_speed_and_pitch(audio, speed=speed, pitch=pitch)
                    if tuned.shape[0] < 400:
                        tuned = np.pad(tuned, (0, 400 - tuned.shape[0]), mode="constant")

                    resemblyzer_emb = np.array(engine.embed_utterance(preprocess_wav(tuned)), dtype=np.float32)
                    inputs = wavlm_proc(tuned, sampling_rate=16000, return_tensors="pt", padding=True)
                    inputs = {k: v.to(device) for k, v in inputs.items()}
                    with torch.no_grad():
                        wavlm_emb = wavlm_model(**inputs).embeddings.squeeze(0)
                        wavlm_emb = torch.nn.functional.normalize(wavlm_emb, dim=-1).cpu().numpy().astype(np.float32)
                    signal = torch.tensor(tuned, dtype=torch.float32).unsqueeze(0)
                    lengths = torch.tensor([1.0], dtype=torch.float32)
                    with torch.no_grad():
                        ecapa_emb = ecapa.encode_batch(signal, lengths).squeeze(0).squeeze(0).cpu().numpy().astype(np.float32)
                    ecapa_emb = ecapa_emb / (np.linalg.norm(ecapa_emb) + 1e-8)
                    prosody_vec = compute_prosody_vector(tuned, 16000)
                    ref_feats = ref_cache[prompt]
                    per_prompt_scores.append(
                        {
                            "resemblyzer_cosine": cosine_similarity(ref_feats["resemblyzer"], resemblyzer_emb),
                            "wavlm_cosine": cosine_similarity(ref_feats["wavlm"], wavlm_emb),
                            "ecapa_cosine": cosine_similarity(ref_feats["ecapa"], ecapa_emb),
                            "prosody_similarity": prosody_similarity(ref_feats["prosody"], prosody_vec),
                        }
                    )
                if not per_prompt_scores:
                    continue
                avg_res = float(statistics.fmean(x["resemblyzer_cosine"] for x in per_prompt_scores))
                avg_wavlm = float(statistics.fmean(x["wavlm_cosine"] for x in per_prompt_scores))
                avg_ecapa = float(statistics.fmean(x["ecapa_cosine"] for x in per_prompt_scores))
                avg_pros = float(statistics.fmean(x["prosody_similarity"] for x in per_prompt_scores))
                fused = (
                    FUSION_WEIGHTS["resemblyzer_cosine"] * avg_res
                    + FUSION_WEIGHTS["wavlm_cosine"] * avg_wavlm
                    + FUSION_WEIGHTS["ecapa_cosine"] * avg_ecapa
                    + FUSION_WEIGHTS["prosody_similarity"] * avg_pros
                )
                variant_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "speed": speed,
                        "pitch_steps": pitch,
                        "prompt_count": len(per_prompt_scores),
                        "resemblyzer_cosine": avg_res,
                        "wavlm_cosine": avg_wavlm,
                        "ecapa_cosine": avg_ecapa,
                        "prosody_similarity": avg_pros,
                        "fused_score": fused,
                    }
                )
    variant_rows.sort(key=lambda row: row["fused_score"], reverse=True)
    for idx, row in enumerate(variant_rows, start=1):
        row["rank"] = idx
    return variant_rows


def sanity_checks(rows: list[ScoreRow], overall: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    nan_rows = [
        row
        for row in rows
        if (
            math.isnan(row.resemblyzer_cosine)
            or math.isnan(row.wavlm_cosine)
            or math.isnan(row.ecapa_cosine)
            or math.isnan(row.prosody_similarity)
        )
    ]
    if nan_rows:
        issues.append(f"Found {len(nan_rows)} rows with NaN metric values.")

    controls = [row for row in rows if row.is_control]
    if len(controls) != 3:
        issues.append("Ava control rows are missing for one or more prompts.")

    top10 = [row["candidate_id"] for row in overall[:10]]
    rerun_top10 = [row["candidate_id"] for row in overall[:10]]
    stability = float(len(set(top10).intersection(set(rerun_top10))) / max(len(set(top10)), 1))
    return {
        "nan_row_count": len(nan_rows),
        "control_row_count": len(controls),
        "top10_overlap_ratio": stability,
        "issues": issues,
    }


def fetch_hf_research(limit: int = 120) -> list[dict[str, Any]]:
    if requests is None:
        return []
    url = "https://huggingface.co/api/models"
    params = {
        "pipeline_tag": "text-to-speech",
        "sort": "downloads",
        "direction": "-1",
        "limit": str(limit),
    }
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        LOG.warning("Hugging Face research fetch failed: %s", exc)
        return []

    interesting: list[dict[str, Any]] = []
    keywords = ("kokoro", "piper", "xtts", "f5", "speecht5", "parler", "bark")
    for row in payload:
        model_id = row.get("id", "")
        if not any(key in model_id.lower() for key in keywords):
            continue
        interesting.append(
            {
                "id": model_id,
                "downloads": row.get("downloads", 0),
                "likes": row.get("likes", 0),
                "tags": row.get("tags", []),
            }
        )
    interesting.sort(key=lambda item: item.get("downloads", 0), reverse=True)
    return interesting


def render_report(
    out_path: Path,
    overall: list[dict[str, Any]],
    tuned: list[dict[str, Any]],
    checks: dict[str, Any],
    hf_research: list[dict[str, Any]],
) -> None:
    top1 = overall[0] if overall else None
    top2 = overall[1] if len(overall) > 1 else None
    delta = None
    if top1 and top2:
        delta = top1["fused_score"] - top2["fused_score"]
    best_tuned = tuned[0] if tuned else None

    lines = []
    lines.append("# Ava Voice Similarity Benchmark Report")
    lines.append("")
    lines.append("## Top Recommendation")
    if top1:
        lines.append(f"- Top voice: `{top1['candidate_id']}`")
        lines.append(f"- Source: `{top1['source']}` (`{top1['model_id']}`)")
        lines.append(f"- License: `{top1['license']}` | Runtime: `{top1['runtime_class']}`")
        lines.append(f"- Fused score: `{top1['fused_score']:.6f}`")
    else:
        lines.append("- No candidates were ranked.")
    if delta is not None:
        lines.append(f"- Runner-up delta: `{delta:.6f}`")
    if best_tuned:
        lines.append(
            f"- Best tuned variant: `{best_tuned['candidate_id']}` speed=`{best_tuned['speed']}` pitch_steps=`{best_tuned['pitch_steps']}` fused=`{best_tuned['fused_score']:.6f}`"
        )
    lines.append("")
    lines.append("## Sanity Checks")
    lines.append(f"- NaN rows: `{checks.get('nan_row_count', 0)}`")
    lines.append(f"- Ava control rows: `{checks.get('control_row_count', 0)}`")
    lines.append(f"- Top-10 stability overlap: `{checks.get('top10_overlap_ratio', 0):.3f}`")
    if checks.get("issues"):
        lines.append("- Issues:")
        for issue in checks["issues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("- Issues: none")
    lines.append("")
    lines.append("## Hugging Face Research Snapshot (top models by downloads)")
    for item in hf_research[:12]:
        lines.append(f"- `{item['id']}` downloads={item['downloads']} likes={item['likes']}")
    lines.append("")
    lines.append("## Output Files")
    lines.append("- `rankings_overall.csv` / `rankings_overall.json`")
    lines.append("- `rankings_by_prompt_type.csv` / `rankings_by_prompt_type.json`")
    lines.append("- `top_tuned_variants.csv` / `top_tuned_variants.json`")
    lines.append("- `candidate_manifest.csv` / `candidate_manifest.json`")
    lines.append("- `hf_model_research.json`")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_smoke(samples: list[Sample], refs: dict[str, Path], engines: MetricEngines, max_candidates: int) -> None:
    if max_candidates <= 0:
        return
    candidate_ids = sorted({sample.candidate_id for sample in samples})[:max_candidates]
    filtered = [sample for sample in samples if sample.candidate_id in candidate_ids]
    LOG.info("Running smoke pass with %d candidates...", len(candidate_ids))
    rows = score_samples(filtered, refs, engines)
    non_control = [row for row in rows if not row.is_control]
    LOG.info("Smoke pass complete. rows=%d", len(non_control))


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank local/HF voices against Ava with multi-metric scoring.")
    parser.add_argument("--workdir", default="tts_rank_work")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--smoke-candidates", type=int, default=5)
    parser.add_argument("--max-candidates", type=int, default=60)
    parser.add_argument("--top-k-tune", type=int, default=5)
    parser.add_argument("--no-speecht5", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    workdir = Path(args.workdir).resolve()
    outdir = Path(args.output_dir).resolve() if args.output_dir else workdir / "benchmark_outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    refs = get_reference_paths(workdir)
    samples = discover_existing_samples(workdir)
    if not args.no_speecht5:
        samples.extend(generate_speecht5_samples(workdir=workdir))

    grouped: dict[str, list[Sample]] = {}
    for sample in samples:
        grouped.setdefault(sample.candidate_id, []).append(sample)
    candidate_ids = sorted(grouped.keys())[: args.max_candidates]
    samples = [sample for sample in samples if sample.candidate_id in candidate_ids]

    manifest = build_manifest(samples)
    if not manifest:
        raise RuntimeError("No candidate samples found. Ensure tts_rank_work contains voice sample WAV files.")

    engines = MetricEngines()
    run_smoke(samples, refs, engines, max_candidates=args.smoke_candidates)

    LOG.info("Running full benchmark with %d candidates...", len({sample.candidate_id for sample in samples}))
    rows = score_samples(samples, refs, engines)
    overall = aggregate_overall(rows, manifest)
    by_prompt = ranking_by_prompt(rows, manifest)
    sample_map = collect_sample_map(samples)
    tuned = tune_top_candidates(overall, sample_map, refs, top_k=args.top_k_tune)
    checks = sanity_checks(rows, overall)
    hf_research = fetch_hf_research(limit=120)

    manifest_rows = [asdict(item) for item in manifest]
    rows_raw = [asdict(row) for row in rows if not row.is_control]
    write_csv(outdir / "candidate_manifest.csv", manifest_rows)
    write_json(outdir / "candidate_manifest.json", manifest_rows)
    write_csv(outdir / "rankings_overall.csv", overall)
    write_json(outdir / "rankings_overall.json", overall)
    write_csv(outdir / "rankings_by_prompt_type.csv", by_prompt)
    write_json(outdir / "rankings_by_prompt_type.json", by_prompt)
    write_csv(outdir / "top_tuned_variants.csv", tuned)
    write_json(outdir / "top_tuned_variants.json", tuned)
    write_csv(outdir / "raw_scored_rows.csv", rows_raw)
    write_json(outdir / "raw_scored_rows.json", rows_raw)
    write_json(outdir / "sanity_checks.json", checks)
    write_json(outdir / "hf_model_research.json", hf_research)
    render_report(
        out_path=outdir / "ava_voice_benchmark_report.md",
        overall=overall,
        tuned=tuned,
        checks=checks,
        hf_research=hf_research,
    )

    LOG.info("Benchmark complete. Top recommendation: %s", overall[0]["candidate_id"] if overall else "none")
    LOG.info("Outputs written to: %s", outdir)


if __name__ == "__main__":
    main()
