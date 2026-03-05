import argparse
import asyncio
import json
import os
import tempfile
import wave
import winsound
from urllib.request import Request, urlopen
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

AVA_US_FEMALE_SHORTLIST = [
    # Microsoft / Edge voices (baseline + closest adjacent)
    {"provider": "edge", "voice": "en-US-AvaNeural", "label": "Microsoft Ava (baseline)"},
    {"provider": "edge", "voice": "en-US-JennyNeural", "label": "Microsoft Jenny"},
    {"provider": "edge", "voice": "en-US-AriaNeural", "label": "Microsoft Aria"},
    # Local Piper voices (Hugging Face)
    {"provider": "piper", "voice": "en_US-amy-medium", "label": "Piper Amy (local)"},
    {"provider": "piper", "voice": "en_US-kathleen-low", "label": "Piper Kathleen (local)"},
    {"provider": "piper", "voice": "en_US-lessac-medium", "label": "Piper Lessac (local)"},
    # Google Cloud TTS
    {"provider": "google", "voice": "en-US-Studio-O", "locale": "en-US", "label": "Google Studio-O"},
    {"provider": "google", "voice": "en-US-Neural2-F", "locale": "en-US", "label": "Google Neural2-F"},
    # Amazon Polly (neural)
    {"provider": "polly", "voice": "Joanna", "label": "Polly Joanna"},
    {"provider": "polly", "voice": "Kendra", "label": "Polly Kendra"},
    {"provider": "polly", "voice": "Kimberly", "label": "Polly Kimberly"},
    # ElevenLabs premade voices (voice_id)
    {"provider": "elevenlabs", "voice": "21m00Tcm4TlvDq8ikWAM", "label": "ElevenLabs Rachel"},
    {"provider": "elevenlabs", "voice": "EXAVITQu4vr4xnSDxMaL", "label": "ElevenLabs Sarah"},
    {"provider": "elevenlabs", "voice": "LcfcDJNUP1GQjkzn1xUU", "label": "ElevenLabs Emily"},
]

PIPER_POPULAR_VOICES = [
    "en_US-amy-low",
    "en_US-amy-medium",
    "en_US-kathleen-low",
    "en_US-kristin-medium",
    "en_US-lessac-low",
    "en_US-lessac-medium",
    "en_US-ljspeech-medium",
    "en_US-hfc_female-medium",
]

KOKORO_POPULAR_VOICES = [
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_heart",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "bf_alice",
    "bf_emma",
    "bf_isabella",
    "bf_lily",
]

PIPER_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
PIPER_VOICES_US_FEMALE = {
    "en_US-amy-low": {
        "model": f"{PIPER_BASE_URL}/en/en_US/amy/low/en_US-amy-low.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/amy/low/en_US-amy-low.onnx.json",
    },
    "en_US-amy-medium": {
        "model": f"{PIPER_BASE_URL}/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
    },
    "en_US-kathleen-low": {
        "model": f"{PIPER_BASE_URL}/en/en_US/kathleen/low/en_US-kathleen-low.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/kathleen/low/en_US-kathleen-low.onnx.json",
    },
    "en_US-kristin-medium": {
        "model": f"{PIPER_BASE_URL}/en/en_US/kristin/medium/en_US-kristin-medium.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/kristin/medium/en_US-kristin-medium.onnx.json",
    },
    "en_US-lessac-low": {
        "model": f"{PIPER_BASE_URL}/en/en_US/lessac/low/en_US-lessac-low.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/lessac/low/en_US-lessac-low.onnx.json",
    },
    "en_US-lessac-medium": {
        "model": f"{PIPER_BASE_URL}/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    },
    "en_US-ljspeech-medium": {
        "model": f"{PIPER_BASE_URL}/en/en_US/ljspeech/medium/en_US-ljspeech-medium.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/ljspeech/medium/en_US-ljspeech-medium.onnx.json",
    },
    "en_US-hfc_female-medium": {
        "model": f"{PIPER_BASE_URL}/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx",
        "config": f"{PIPER_BASE_URL}/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json",
    },
}


def _play_wav(path: str) -> None:
    winsound.PlaySound(path, winsound.SND_FILENAME)


def _write_pcm_wav(path: str, pcm_bytes: bytes, sample_rate: int = 16000) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _keep_or_cleanup(path: str, keep: bool) -> None:
    if keep:
        print(f"Saved audio: {path}")
    else:
        try:
            os.remove(path)
        except OSError:
            pass


def _apply_pitch_shift(path: str, n_steps: float) -> str:
    try:
        import librosa
        import soundfile as sf
    except Exception:
        print("librosa/soundfile not installed; cannot pitch shift.")
        return path

    try:
        y, sr = librosa.load(path, sr=None, mono=True)
        if y is None or sr is None:
            return path
        y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=n_steps)
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(out_path, y_shifted, sr)
        return out_path
    except Exception as e:
        print(f"Pitch shift failed: {e}")
        return path


def _apply_speed_change(path: str, speed: float) -> str:
    if speed <= 0 or speed == 1.0:
        return path
    try:
        import librosa
        import soundfile as sf
    except Exception:
        print("librosa/soundfile not installed; cannot change speed.")
        return path
    try:
        y, sr = librosa.load(path, sr=None, mono=True)
        if y is None or sr is None:
            return path
        y_stretched = librosa.effects.time_stretch(y, rate=speed)
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(out_path, y_stretched, sr)
        return out_path
    except Exception as e:
        print(f"Speed change failed: {e}")
        return path


def _download_file(url: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return True
        with urlopen(url) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"Download failed: {url} ({e})")
        return False


def ensure_piper_voice(voice_id: str, base_dir: Path) -> tuple[Path, Path] | None:
    voice_info = PIPER_VOICES_US_FEMALE.get(voice_id)
    if not voice_info:
        print(f"Unknown Piper voice: {voice_id}")
        return None
    model_path = base_dir / voice_id / Path(voice_info["model"]).name
    config_path = base_dir / voice_id / Path(voice_info["config"]).name

    ok_model = _download_file(voice_info["model"], model_path)
    ok_config = _download_file(voice_info["config"], config_path)
    if not (ok_model and ok_config):
        return None
    return model_path, config_path


def _find_piper_binary() -> str | None:
    found = shutil.which("piper")
    if found:
        return found
    candidate = Path(sys.executable).resolve().parent / "piper.exe"
    if candidate.exists():
        return str(candidate)
    return None


def piper_speak(
    text: str,
    voice_id: str,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    piper_bin = _find_piper_binary()
    if not piper_bin:
        print("piper not installed. Try: pip install piper-tts")
        return
    base_dir = Path("pretrained_models") / "piper"
    voice_files = ensure_piper_voice(voice_id, base_dir)
    if not voice_files:
        return
    model_path, config_path = voice_files
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            [
                piper_bin,
                "--model",
                str(model_path),
                "--config",
                str(config_path),
                "--output_file",
                out_path,
            ],
            input=text.encode("utf-8"),
            check=True,
        )
        play_path = _apply_pitch_shift(out_path, pitch) if pitch else out_path
        if speed and speed != 1.0:
            play_path = _apply_speed_change(play_path, speed)
        _play_wav(play_path)
        if (pitch or (speed and speed != 1.0)) and play_path != out_path:
            _keep_or_cleanup(play_path, keep)
    except Exception as e:
        print(f"Piper playback failed: {e}")
    _keep_or_cleanup(out_path, keep)


_kokoro_pipeline = None


def _get_kokoro_pipeline():
    global _kokoro_pipeline
    if _kokoro_pipeline is not None:
        return _kokoro_pipeline
    try:
        from kokoro import KPipeline
    except Exception:
        print("kokoro not installed. Try: pip install kokoro>=0.9.2")
        return None
    try:
        _kokoro_pipeline = KPipeline(lang_code="a")
    except Exception as e:
        print(f"Failed to initialize kokoro pipeline: {e}")
        return None
    return _kokoro_pipeline


def kokoro_speak(
    text: str,
    voice_id: str,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    pipeline = _get_kokoro_pipeline()
    if pipeline is None:
        return
    try:
        import numpy as np
        import soundfile as sf
    except Exception:
        print("soundfile not installed. Try: pip install soundfile")
        return

    audio_chunks = []
    sample_rate = 24000
    try:
        generator = pipeline(text, voice=voice_id)
        for _, _, audio in generator:
            if audio is None:
                continue
            audio_chunks.append(audio)
        if not audio_chunks:
            print("Kokoro returned no audio.")
            return
        audio = np.concatenate(audio_chunks)
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(out_path, audio, sample_rate)
        play_path = _apply_pitch_shift(out_path, pitch) if pitch else out_path
        if speed and speed != 1.0:
            play_path = _apply_speed_change(play_path, speed)
        _play_wav(play_path)
        if (pitch or (speed and speed != 1.0)) and play_path != out_path:
            _keep_or_cleanup(play_path, keep)
        _keep_or_cleanup(out_path, keep)
    except Exception as e:
        print(f"Kokoro playback failed: {e}")


async def edge_list(locale: str | None) -> None:
    try:
        import edge_tts
    except Exception:
        print("edge-tts not installed. Try: pip install edge-tts")
        return

    voices = await edge_tts.list_voices()
    for voice in voices:
        if locale and voice.get("Locale") != locale:
            continue
        print(
            f"{voice.get('ShortName')} | {voice.get('Gender')} | "
            f"{voice.get('Locale')} | {voice.get('FriendlyName')}"
        )


async def edge_speak(
    text: str,
    voice: str | None,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    try:
        import edge_tts
    except Exception:
        print("edge-tts not installed. Try: pip install edge-tts")
        return

    rate = "+0%"
    if speed and speed != 1.0:
        rate = f"{int(round((speed - 1.0) * 100.0)):+d}%"
    if voice:
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    else:
        communicate = edge_tts.Communicate(text, rate=rate)

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    await communicate.save(path)
    try:
        play_path = path
        if pitch:
            play_path = _apply_pitch_shift(play_path, pitch)
        if speed and speed != 1.0:
            play_path = _apply_speed_change(play_path, speed)
        from pydub import AudioSegment
        from pydub.playback import play

        sound = AudioSegment.from_file(play_path, format="wav" if play_path.endswith(".wav") else "mp3")
        play(sound)
    except Exception as e:
        print(f"Could not play MP3 locally: {e}")
    if (pitch or (speed and speed != 1.0)) and play_path != path:
        _keep_or_cleanup(play_path, keep)
    _keep_or_cleanup(path, keep)


def pyttsx4_list() -> None:
    try:
        import pyttsx4
    except Exception:
        print("pyttsx4 not installed. Try: pip install pyttsx4")
        return

    engine = pyttsx4.init()
    for voice in engine.getProperty("voices"):
        langs = getattr(voice, "languages", [])
        print(f"{voice.id} | {voice.name} | {langs}")


def pyttsx4_speak(text: str, voice_id: str | None, pitch: float = 0.0, speed: float = 1.0) -> None:
    try:
        import pyttsx4
    except Exception:
        print("pyttsx4 not installed. Try: pip install pyttsx4")
        return

    engine = pyttsx4.init()
    if voice_id:
        engine.setProperty("voice", voice_id)
    if speed and speed != 1.0:
        try:
            base_rate = engine.getProperty("rate")
            engine.setProperty("rate", int(round(base_rate * speed)))
        except Exception:
            pass

    if pitch or (speed and speed != 1.0):
        fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        play_path = out_path
        if pitch:
            play_path = _apply_pitch_shift(play_path, pitch)
        if speed and speed != 1.0:
            play_path = _apply_speed_change(play_path, speed)
        _play_wav(play_path)
        if play_path != out_path:
            _keep_or_cleanup(play_path, keep=True)
        _keep_or_cleanup(out_path, keep=False)
    else:
        engine.say(text)
        engine.runAndWait()


def elevenlabs_list() -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY not set.")
        return
    req = Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
    )
    with urlopen(req) as resp:
        data = json.load(resp)
    for voice in data.get("voices", []):
        print(f"{voice.get('voice_id')} | {voice.get('name')}")


def elevenlabs_speak(
    text: str,
    voice_id: str,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY not set.")
        return
    if not voice_id:
        print("Provide --voice with an ElevenLabs voice_id.")
        return

    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/"
        f"{voice_id}?output_format=pcm_16000"
    )
    payload = json.dumps(
        {
            "text": text,
            "model_id": "eleven_multilingual_v2",
        }
    ).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "accept": "audio/*",
        },
        method="POST",
    )
    with urlopen(req) as resp:
        audio_bytes = resp.read()

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    _write_pcm_wav(path, audio_bytes, sample_rate=16000)
    play_path = _apply_pitch_shift(path, pitch) if pitch else path
    if speed and speed != 1.0:
        play_path = _apply_speed_change(play_path, speed)
    _play_wav(play_path)
    if (pitch or (speed and speed != 1.0)) and play_path != path:
        _keep_or_cleanup(play_path, keep)
    _keep_or_cleanup(path, keep)


def google_list(locale: str) -> None:
    try:
        from google.cloud import texttospeech
        from google.auth.exceptions import DefaultCredentialsError
    except Exception:
        print("google-cloud-texttospeech not installed. Try: pip install google-cloud-texttospeech")
        return

    try:
        client = texttospeech.TextToSpeechClient()
        response = client.list_voices(language_code=locale)
        for voice in response.voices:
            print(f"{voice.name} | {voice.ssml_gender.name} | {','.join(voice.language_codes)}")
    except DefaultCredentialsError:
        print("Google credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS to your JSON key.")


def google_speak(
    text: str,
    voice_name: str | None,
    locale: str,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    try:
        from google.cloud import texttospeech
        from google.auth.exceptions import DefaultCredentialsError
    except Exception:
        print("google-cloud-texttospeech not installed. Try: pip install google-cloud-texttospeech")
        return

    try:
        client = texttospeech.TextToSpeechClient()
        voice = texttospeech.VoiceSelectionParams(
            language_code=locale,
            name=voice_name or None,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        response = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=voice,
            audio_config=audio_config,
        )

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        _write_pcm_wav(path, response.audio_content, sample_rate=24000)
        play_path = _apply_pitch_shift(path, pitch) if pitch else path
        if speed and speed != 1.0:
            play_path = _apply_speed_change(play_path, speed)
        _play_wav(play_path)
        if (pitch or (speed and speed != 1.0)) and play_path != path:
            _keep_or_cleanup(play_path, keep)
        _keep_or_cleanup(path, keep)
    except DefaultCredentialsError:
        print("Google credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS to your JSON key.")


def polly_list(locale: str) -> None:
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, PartialCredentialsError
    except Exception:
        print("boto3 not installed. Try: pip install boto3")
        return

    try:
        polly = boto3.client("polly")
        response = polly.describe_voices(LanguageCode=locale)
        for voice in response.get("Voices", []):
            print(f"{voice.get('Id')} | {voice.get('Gender')} | {voice.get('LanguageCode')}")
    except (NoCredentialsError, PartialCredentialsError):
        print("AWS credentials not found. Configure AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY.")


def polly_speak(
    text: str,
    voice_id: str,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, PartialCredentialsError
    except Exception:
        print("boto3 not installed. Try: pip install boto3")
        return
    if not voice_id:
        print("Provide --voice with a Polly VoiceId (e.g., Joanna).")
        return

    try:
        polly = boto3.client("polly")
        response = polly.synthesize_speech(
            Text=text,
            VoiceId=voice_id,
            OutputFormat="pcm",
            SampleRate="16000",
            Engine="neural",
        )
        audio_stream = response.get("AudioStream")
        if not audio_stream:
            print("No audio stream returned from Polly.")
            return
        audio_bytes = audio_stream.read()

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        _write_pcm_wav(path, audio_bytes, sample_rate=16000)
        play_path = _apply_pitch_shift(path, pitch) if pitch else path
        if speed and speed != 1.0:
            play_path = _apply_speed_change(play_path, speed)
        _play_wav(play_path)
        if (pitch or (speed and speed != 1.0)) and play_path != path:
            _keep_or_cleanup(play_path, keep)
        _keep_or_cleanup(path, keep)
    except (NoCredentialsError, PartialCredentialsError):
        print("AWS credentials not found. Configure AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY.")


async def run_preset(
    preset_name: str,
    text: str,
    keep: bool,
    pitch: float = 0.0,
    speed: float = 1.0,
) -> None:
    if preset_name == "ava-us-female":
        entries = AVA_US_FEMALE_SHORTLIST
    elif preset_name == "piper-popular":
        entries = [
            {"provider": "piper", "voice": vid, "label": f"Piper {vid}"}
            for vid in PIPER_POPULAR_VOICES
        ]
    elif preset_name == "kokoro-popular":
        entries = [
            {"provider": "kokoro", "voice": vid, "label": f"Kokoro {vid}"}
            for vid in KOKORO_POPULAR_VOICES
        ]
    elif preset_name == "local-popular":
        entries = (
            [{"provider": "piper", "voice": vid, "label": f"Piper {vid}"} for vid in PIPER_POPULAR_VOICES]
            + [{"provider": "kokoro", "voice": vid, "label": f"Kokoro {vid}"} for vid in KOKORO_POPULAR_VOICES]
        )
    else:
        print("Unknown preset. Available: ava-us-female, piper-popular, kokoro-popular, local-popular")
        return

    for entry in entries:
        provider = entry["provider"]
        voice = entry.get("voice")
        label = entry.get("label", voice)
        locale = entry.get("locale", "en-US")
        print(f"\n=== {provider.upper()} | {label} ===")

        try:
            if provider == "edge":
                await edge_speak(text, voice, keep, pitch, speed)
            elif provider == "pyttsx4":
                pyttsx4_speak(text, voice, pitch, speed)
            elif provider == "elevenlabs":
                elevenlabs_speak(text, voice, keep, pitch, speed)
            elif provider == "google":
                google_speak(text, voice, locale, keep, pitch, speed)
            elif provider == "polly":
                polly_speak(text, voice, keep, pitch, speed)
            elif provider == "piper":
                piper_speak(text, voice, keep, pitch, speed)
            elif provider == "kokoro":
                kokoro_speak(text, voice, keep, pitch, speed)
        except Exception as e:
            print(f"{provider} playback failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audition TTS voices from multiple providers.")
    parser.add_argument("--provider", choices=["edge", "pyttsx4", "elevenlabs", "google", "polly", "piper", "kokoro"])
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--text-file", default=None)
    parser.add_argument("--sample", choices=["default", "long", "medical"], default="default")
    parser.add_argument("--voice", default=None)
    parser.add_argument("--pitch", type=float, default=0.0, help="Pitch shift in semitones")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier (e.g., 1.1 = 10%% faster)")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--locale", default="en-US")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--preset", default=None)
    args = parser.parse_args()

    if args.text_file:
        try:
            with open(args.text_file, "r", encoding="utf-8") as f:
                args.text = f.read().strip() or args.text
        except Exception as e:
            print(f"Could not read text file: {e}")

    if args.sample == "long":
        args.text = LONG_TEXT
    elif args.sample == "medical":
        args.text = MEDICAL_TEXT

    if args.preset:
        asyncio.run(run_preset(args.preset, args.text, args.keep, args.pitch, args.speed))
        return

    if not args.provider:
        parser.error("--provider is required unless --preset is used")

    if args.provider == "edge":
        if args.list:
            asyncio.run(edge_list(args.locale))
        else:
            asyncio.run(edge_speak(args.text, args.voice, args.keep, args.pitch, args.speed))
        return

    if args.provider == "pyttsx4":
        if args.list:
            pyttsx4_list()
        else:
            pyttsx4_speak(args.text, args.voice, args.pitch, args.speed)
        return

    if args.provider == "elevenlabs":
        if args.list:
            elevenlabs_list()
        else:
            elevenlabs_speak(args.text, args.voice, args.keep, args.pitch, args.speed)
        return

    if args.provider == "google":
        if args.list:
            google_list(args.locale)
        else:
            google_speak(args.text, args.voice, args.locale, args.keep, args.pitch, args.speed)
        return

    if args.provider == "polly":
        if args.list:
            polly_list(args.locale)
        else:
            polly_speak(args.text, args.voice, args.keep, args.pitch, args.speed)
        return

    if args.provider == "piper":
        if args.list:
            for vid in PIPER_VOICES_US_FEMALE:
                print(vid)
        else:
            if not args.voice:
                print("Provide --voice with a Piper voice id (e.g., en_US-amy-medium).")
            else:
                piper_speak(args.text, args.voice, args.keep, args.pitch, args.speed)
        return

    if args.provider == "kokoro":
        if args.list:
            for vid in KOKORO_POPULAR_VOICES:
                print(vid)
        else:
            if not args.voice:
                print("Provide --voice with a Kokoro voice id (e.g., af_bella).")
            else:
                kokoro_speak(args.text, args.voice, args.keep, args.pitch, args.speed)
        return


if __name__ == "__main__":
    main()
