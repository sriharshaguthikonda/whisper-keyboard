import importlib
import sys
import types

import numpy as np


def load_pre_recording(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "keyboard",
        types.SimpleNamespace(is_pressed=lambda _key: False),
    )
    sys.modules.pop("pre_recording", None)
    return importlib.import_module("pre_recording")


def test_pre_recording_callback_keeps_recorded_audio_as_chunks(monkeypatch):
    pre_recording = load_pre_recording(monkeypatch)
    pre_recording.recording = True
    pre_recording.audio_buffer = []
    pre_recording.buffer_index = 0

    pre_recording.audio_callback(
        np.full((2, 1), 1.0, dtype=np.float32),
        2,
        None,
        None,
    )
    pre_recording.audio_callback(
        np.full((3, 1), 2.0, dtype=np.float32),
        3,
        None,
        None,
    )

    assert isinstance(pre_recording.audio_buffer, list)
    assert len(pre_recording.audio_buffer) == 2
    assert np.allclose(
        np.concatenate([chunk.flatten() for chunk in pre_recording.audio_buffer]),
        np.array([1.0, 1.0, 2.0, 2.0, 2.0], dtype=np.float32),
    )
