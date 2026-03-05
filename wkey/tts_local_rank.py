import argparse
import asyncio
import os
import tempfile
from pathlib import Path
import shutil
import subprocess
import sys

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    load_dotenv(repo_root / ".env")
    load_dotenv(script_dir / ".env", override=True)

try:
    from tts_voice_audition import PIPER_VOICES_US_FEMALE, ensure_piper_voice, KOKORO_POPULAR_VOICES
except Exception:
    PIPER_VOICES_US_FEMALE = {}
    ensure_piper_voice = None
    KOKORO_POPULAR_VOICES = []


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


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _synthesize_edge_ava(text: str, out_path: Path, speed: float = 1.0) -> Path | None:
    try:
        import edge_tts
    except Exception:
        print("edge-tts not installed. Cannot generate Ava reference.")
        return None

    async def _run():
        rate = "+0%"
        if speed and speed != 1.0:
            rate = f"{int(round((speed - 1.0) * 100.0)):+d}%"
        communicate = edge_tts.Communicate(text, voice="en-US-AvaNeural", rate=rate)
        await communicate.save(str(out_path))

    try:
        asyncio.run(_run())
        return out_path
    except Exception as e:
        print(f"Failed to generate Ava reference: {e}")
        return None


def _convert_mp3_to_wav(mp3_path: Path, wav_path: Path) -> Path | None:
    try:
        from pydub import AudioSegment
    except Exception:
        print("pydub not installed; cannot convert mp3 to wav.")
        return None
    try:
        audio = AudioSegment.from_file(mp3_path, format="mp3")
        audio = audio.set_channels(1)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"MP3->WAV conversion failed: {e}")
        return None


def _generate_pyttsx4_voice_samples(text: str, out_dir: Path, tag: str) -> list[Path]:
    try:
        import pyttsx4
    except Exception:
        print("pyttsx4 not installed.")
        return []

    engine = pyttsx4.init()
    voices = engine.getProperty("voices")
    samples = []

    for voice in voices:
        voice_name = getattr(voice, "name", "") or ""
        voice_id = getattr(voice, "id", "") or ""
        label = voice_name.replace(" ", "_").replace("/", "_")
        if not label:
            label = voice_id.replace(" ", "_").replace("/", "_")
        out_path = out_dir / f"{tag}_pyttsx4_{label}.wav"
        try:
            if out_path.exists():
                samples.append(out_path)
                continue
            engine.setProperty("voice", voice_id)
            engine.save_to_file(text, str(out_path))
            engine.runAndWait()
            if out_path.exists():
                samples.append(out_path)
        except Exception as e:
            print(f"pyttsx4 voice failed ({voice_name}): {e}")

    try:
        engine.stop()
    except Exception:
        pass
    return samples


def _generate_piper_samples(text: str, out_dir: Path, tag: str) -> list[Path]:
    piper_bin = shutil.which("piper")
    if not piper_bin:
        candidate = Path(sys.executable).resolve().parent / "piper.exe"
        if candidate.exists():
            piper_bin = str(candidate)
    if not piper_bin:
        print("piper not installed. Try: pip install piper-tts")
        return []
    if not PIPER_VOICES_US_FEMALE or ensure_piper_voice is None:
        print("Piper voice list not available.")
        return []

    samples = []
    base_dir = Path("pretrained_models") / "piper"
    for voice_id in PIPER_VOICES_US_FEMALE.keys():
        voice_files = ensure_piper_voice(voice_id, base_dir)
        if not voice_files:
            continue
        model_path, config_path = voice_files
        out_path = out_dir / f"{tag}_piper_{voice_id}.wav"
        try:
            if out_path.exists():
                samples.append(out_path)
                continue
            subprocess.run(
                [
                    piper_bin,
                    "--model",
                    str(model_path),
                    "--config",
                    str(config_path),
                    "--output_file",
                    str(out_path),
                ],
                input=text.encode("utf-8"),
                check=True,
            )
            if out_path.exists():
                samples.append(out_path)
        except Exception as e:
            print(f"Piper voice failed ({voice_id}): {e}")
    return samples


def _generate_kokoro_samples(text: str, out_dir: Path, tag: str) -> list[Path]:
    try:
        from kokoro import KPipeline
    except Exception:
        print("kokoro not installed. Try: pip install kokoro>=0.9.2")
        return []
    try:
        import numpy as np
        import soundfile as sf
    except Exception:
        print("soundfile not installed. Try: pip install soundfile")
        return []

    samples = []
    try:
        pipeline = KPipeline(lang_code="a")
    except Exception as e:
        print(f"Failed to initialize kokoro pipeline: {e}")
        return []

    for voice_id in KOKORO_POPULAR_VOICES:
        out_path = out_dir / f"{tag}_kokoro_{voice_id}.wav"
        try:
            if out_path.exists():
                samples.append(out_path)
                continue
            audio_chunks = []
            generator = pipeline(text, voice=voice_id)
            for _, _, audio in generator:
                if audio is None:
                    continue
                audio_chunks.append(audio)
            if not audio_chunks:
                continue
            audio = np.concatenate(audio_chunks)
            sf.write(out_path, audio, 24000)
            if out_path.exists():
                samples.append(out_path)
        except Exception as e:
            print(f"Kokoro voice failed ({voice_id}): {e}")
    return samples


def _compute_similarity(reference_wav: Path, candidate_wavs: list[Path]) -> list[tuple[str, float]]:
    from resemblyzer import VoiceEncoder, preprocess_wav
    import numpy as np

    encoder = VoiceEncoder()
    ref_wav = preprocess_wav(str(reference_wav))
    ref_emb = encoder.embed_utterance(ref_wav)

    scores = []
    for wav_path in candidate_wavs:
        try:
            wav = preprocess_wav(str(wav_path))
            emb = encoder.embed_utterance(wav)
            sim = float(np.dot(ref_emb, emb) / (np.linalg.norm(ref_emb) * np.linalg.norm(emb)))
            scores.append((wav_path.name, sim))
        except Exception as e:
            print(f"Failed to score {wav_path.name}: {e}")
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _pitch_shift_wav(path: Path, n_steps: float, out_path: Path) -> bool:
    try:
        import librosa
        import soundfile as sf
    except Exception:
        print("librosa/soundfile not installed; cannot pitch shift.")
        return False
    try:
        y, sr = librosa.load(str(path), sr=None, mono=True)
        if y is None or sr is None:
            return False
        y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=n_steps)
        sf.write(str(out_path), y_shifted, sr)
        return True
    except Exception as e:
        print(f"Pitch shift failed: {e}")
        return False


def _time_stretch_wav(path: Path, speed: float, out_path: Path) -> bool:
    try:
        import librosa
        import soundfile as sf
    except Exception:
        print("librosa/soundfile not installed; cannot change speed.")
        return False
    try:
        y, sr = librosa.load(str(path), sr=None, mono=True)
        if y is None or sr is None:
            return False
        y_stretched = librosa.effects.time_stretch(y, rate=speed)
        sf.write(str(out_path), y_stretched, sr)
        return True
    except Exception as e:
        print(f"Speed change failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank local voices by similarity to Ava.")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--reference", default=None, help="Path to Ava reference WAV")
    parser.add_argument("--reference-speed", type=float, default=1.0, help="Speed multiplier for Ava reference generation")
    parser.add_argument("--workdir", default="tts_rank_work")
    parser.add_argument("--sample", choices=["default", "long", "medical", "combined"], default="default")
    parser.add_argument("--pitch-search", action="store_true")
    parser.add_argument("--pitch-steps", default="-2,-1,0,1,2")
    parser.add_argument("--pitch-top-k", type=int, default=5)
    parser.add_argument("--speed-search", action="store_true")
    parser.add_argument("--speed-steps", default="1.05,1.1,1.15")
    parser.add_argument("--speed-top-k", type=int, default=5)
    args = parser.parse_args()

    work_dir = Path(args.workdir).resolve()
    _ensure_dir(work_dir)

    sample_texts: list[tuple[str, str]] = []
    if args.sample == "default":
        sample_texts = [("default", args.text)]
    elif args.sample == "long":
        sample_texts = [("long", LONG_TEXT)]
    elif args.sample == "medical":
        sample_texts = [("medical", MEDICAL_TEXT)]
    elif args.sample == "combined":
        sample_texts = [("long", LONG_TEXT), ("medical", MEDICAL_TEXT)]

    all_scores: dict[str, list[float]] = {}

    for tag, text in sample_texts:
        ref_path = Path(args.reference).resolve() if args.reference else None
        if not ref_path or not ref_path.exists():
            speed_tag = ""
            if args.reference_speed and args.reference_speed != 1.0:
                safe_speed = f"{args.reference_speed:.2f}".replace(".", "p")
                speed_tag = f"_sp{safe_speed}"
            mp3_path = work_dir / f"ava_reference_{tag}{speed_tag}.mp3"
            wav_path = work_dir / f"ava_reference_{tag}{speed_tag}.wav"
            print(f"Generating Ava reference (Edge TTS) for {tag}...")
            mp3 = _synthesize_edge_ava(text, mp3_path, args.reference_speed)
            if not mp3:
                print("Could not generate Ava reference. Provide --reference path to a WAV file.")
                return
            converted = _convert_mp3_to_wav(mp3_path, wav_path)
            if not converted:
                print("Could not convert Ava reference to WAV. Provide --reference path to a WAV file.")
                return
            ref_path = converted

        print(f"Using reference ({tag}): {ref_path}")

        samples = []
        pyttsx4_dir = work_dir / "pyttsx4_samples"
        _ensure_dir(pyttsx4_dir)
        print(f"Generating local pyttsx4 voice samples ({tag})...")
        samples.extend(_generate_pyttsx4_voice_samples(text, pyttsx4_dir, tag))

        piper_dir = work_dir / "piper_samples"
        _ensure_dir(piper_dir)
        print(f"Generating local Piper voice samples ({tag})...")
        samples.extend(_generate_piper_samples(text, piper_dir, tag))

        kokoro_dir = work_dir / "kokoro_samples"
        _ensure_dir(kokoro_dir)
        print(f"Generating local Kokoro voice samples ({tag})...")
        samples.extend(_generate_kokoro_samples(text, kokoro_dir, tag))

        if not samples:
            print("No local samples generated.")
            return

        print(f"Computing similarity scores ({tag})...")
        scores = _compute_similarity(ref_path, samples)
        print(f"\nRanked local voices ({tag}):")
        for name, score in scores:
            print(f"{name}: {score:.3f}")
            key = name.replace(f"{tag}_", "", 1)
            all_scores.setdefault(key, []).append(score)

        if args.pitch_search:
            try:
                steps = [float(s) for s in args.pitch_steps.split(",") if s.strip()]
            except Exception:
                steps = [-2, -1, 0, 1, 2]
            top_candidates = scores[: args.pitch_top_k]
            pitch_dir = work_dir / "pitch_shifted"
            _ensure_dir(pitch_dir)
            print(f"\nPitch-search ({tag}) on top {args.pitch_top_k} voices...")
            pitch_scores: list[tuple[str, float]] = []
            for name, _ in top_candidates:
                base_path = None
                for sample_path in samples:
                    if sample_path.name == name:
                        base_path = sample_path
                        break
                if base_path is None:
                    continue
                for step in steps:
                    if step == 0:
                        continue
                    shifted_name = f"{base_path.stem}_ps{step:+g}.wav"
                    shifted_path = pitch_dir / shifted_name
                    if not shifted_path.exists():
                        ok = _pitch_shift_wav(base_path, step, shifted_path)
                        if not ok:
                            continue
                    pitch_scores.extend(_compute_similarity(ref_path, [shifted_path]))
            pitch_scores.sort(key=lambda x: x[1], reverse=True)
            if pitch_scores:
                print(f"\nTop pitch-shifted matches ({tag}):")
                for name, score in pitch_scores[: min(10, len(pitch_scores))]:
                    print(f"{name}: {score:.3f}")

        if args.speed_search:
            try:
                speeds = [float(s) for s in args.speed_steps.split(",") if s.strip()]
            except Exception:
                speeds = [1.05, 1.1, 1.15]
            top_candidates = scores[: args.speed_top_k]
            speed_dir = work_dir / "speed_shifted"
            _ensure_dir(speed_dir)
            print(f"\nSpeed-search ({tag}) on top {args.speed_top_k} voices...")
            speed_scores: list[tuple[str, float]] = []
            for name, _ in top_candidates:
                base_path = None
                for sample_path in samples:
                    if sample_path.name == name:
                        base_path = sample_path
                        break
                if base_path is None:
                    continue
                for speed in speeds:
                    if speed <= 0 or speed == 1.0:
                        continue
                    shifted_name = f"{base_path.stem}_sp{speed:g}.wav"
                    shifted_path = speed_dir / shifted_name
                    if not shifted_path.exists():
                        ok = _time_stretch_wav(base_path, speed, shifted_path)
                        if not ok:
                            continue
                    speed_scores.extend(_compute_similarity(ref_path, [shifted_path]))
            speed_scores.sort(key=lambda x: x[1], reverse=True)
            if speed_scores:
                print(f"\nTop speed-shifted matches ({tag}):")
                for name, score in speed_scores[: min(10, len(speed_scores))]:
                    print(f"{name}: {score:.3f}")

    if len(sample_texts) > 1:
        print("\nAverage scores across samples:")
        averaged = [(name, sum(vals) / len(vals)) for name, vals in all_scores.items()]
        averaged.sort(key=lambda x: x[1], reverse=True)
        for name, score in averaged:
            print(f"{name}: {score:.3f}")


if __name__ == "__main__":
    main()
