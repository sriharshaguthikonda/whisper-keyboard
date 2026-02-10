import itertools
import logging
import threading
from typing import Iterable, List


class ModelRotator:
    def __init__(self, name: str, models: Iterable[str]):
        self.name = name
        self._lock = threading.Lock()
        self.update_models(list(models))

    def update_models(self, models: List[str]):
        cleaned = [m for m in models if m]
        if not cleaned:
            raise ValueError(f"Model list for {self.name} must not be empty")
        self.models = cleaned
        self._cycle = itertools.cycle(self.models)

    def next(self) -> str:
        with self._lock:
            model = next(self._cycle)
        logging.info(f"[ModelRotator] Using {self.name} model: {model}")
        return model


# Tool-use models (as configured in voice_commands)
TOOL_USE_MODELS = [
    "llama-3.3-70b-versatile",
    #"meta-llama/llama-4-scout-17b-16e-instruct",
    #"qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "moonshotai/kimi-k2-instruct-0905",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

# Audio/STT models for Groq whisper endpoint
AUDIO_STT_MODELS = [
    "whisper-large-v3",
    "whisper-large-v3-turbo",
]

tool_use_rotator = ModelRotator("tool_use", TOOL_USE_MODELS)
audio_stt_rotator = ModelRotator("audio_transcription", AUDIO_STT_MODELS)


def next_tool_use_model() -> str:
    return tool_use_rotator.next()


def next_audio_stt_model() -> str:
    return audio_stt_rotator.next()
