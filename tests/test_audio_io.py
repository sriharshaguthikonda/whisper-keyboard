import threading
import types

import numpy as np


def test_create_audio_buffers_shapes():
    from wkey import audio_io

    pre, pre_f24, idx, buf = audio_io.create_audio_buffers(
        buffer_size=3200, sample_rate=16000, channels=1
    )
    assert pre.shape == (3200, 1)
    assert pre_f24.shape == (48000, 1)
    assert idx == 0
    assert buf == []


def test_audio_callback_updates_pre_buffer():
    from wkey import audio_io

    pre, pre_f24, idx, buf = audio_io.create_audio_buffers(
        buffer_size=10, sample_rate=16000, channels=1
    )
    indata = np.ones((5, 1), dtype=np.float32)
    idx, buf = audio_io.audio_callback(
        indata=indata,
        frames=5,
        time_info=None,
        status=None,
        is_recording=lambda: False,
        buffer_index=idx,
        audio_buffer=buf,
        pre_recording_buffer=pre,
        pre_recording_buffer_f24=pre_f24,
        buffer_size=10,
        recording_lock=threading.Lock(),
        audio_data_lock=threading.Lock(),
    )
    assert idx == 5
    assert np.allclose(pre[:5], 1.0)


def test_audio_callback_wraps_entire_pre_buffer_chunk():
    from wkey import audio_io

    pre, pre_f24, idx, buf = audio_io.create_audio_buffers(
        buffer_size=10, sample_rate=16000, channels=1
    )
    idx = 8
    indata = np.arange(1, 6, dtype=np.float32).reshape(-1, 1)

    idx, buf = audio_io.audio_callback(
        indata=indata,
        frames=5,
        time_info=None,
        status=None,
        is_recording=lambda: False,
        buffer_index=idx,
        audio_buffer=buf,
        pre_recording_buffer=pre,
        pre_recording_buffer_f24=pre_f24,
        buffer_size=10,
        recording_lock=threading.Lock(),
        audio_data_lock=threading.Lock(),
    )

    assert idx == 3
    assert np.allclose(pre[8:10].flatten(), [1.0, 2.0])
    assert np.allclose(pre[0:3].flatten(), [3.0, 4.0, 5.0])


def test_audio_callback_appends_when_recording():
    from wkey import audio_io

    pre, pre_f24, idx, buf = audio_io.create_audio_buffers(
        buffer_size=10, sample_rate=16000, channels=1
    )
    indata = np.ones((3, 1), dtype=np.float32)
    idx, buf = audio_io.audio_callback(
        indata=indata,
        frames=3,
        time_info=None,
        status=None,
        is_recording=lambda: True,
        buffer_index=idx,
        audio_buffer=buf,
        pre_recording_buffer=pre,
        pre_recording_buffer_f24=pre_f24,
        buffer_size=10,
        recording_lock=threading.Lock(),
        audio_data_lock=threading.Lock(),
    )
    assert isinstance(buf, list)
    assert len(buf) == 1
    assert np.allclose(buf[0], np.ones(3, dtype=np.float32))


def test_audio_callback_keeps_chunks_until_snapshot():
    from wkey import audio_io

    pre, pre_f24, idx, buf = audio_io.create_audio_buffers(
        buffer_size=10, sample_rate=16000, channels=1
    )
    lock = threading.Lock()

    for value in (1.0, 2.0):
        idx, buf = audio_io.audio_callback(
            indata=np.full((3, 1), value, dtype=np.float32),
            frames=3,
            time_info=None,
            status=None,
            is_recording=lambda: True,
            buffer_index=idx,
            audio_buffer=buf,
            pre_recording_buffer=pre,
            pre_recording_buffer_f24=pre_f24,
            buffer_size=10,
            recording_lock=threading.Lock(),
            audio_data_lock=lock,
        )

    assert len(buf) == 2
    assert np.allclose(
        audio_io.snapshot_audio_buffer(buf, lock),
        np.array([1, 1, 1, 2, 2, 2], dtype=np.float32),
    )


def test_snapshot_audio_buffer_handles_list_and_array():
    from wkey import audio_io

    lock = threading.Lock()
    arr = audio_io.snapshot_audio_buffer([1, 2, 3], lock)
    assert np.allclose(arr, np.array([1, 2, 3]))

    arr2 = audio_io.snapshot_audio_buffer(np.array([4, 5], dtype=np.float32), lock)
    assert np.allclose(arr2, np.array([4, 5], dtype=np.float32))


def test_initialize_input_stream_returns_stream():
    from wkey import audio_io

    ok, stream = audio_io.initialize_input_stream(
        stream=None,
        audio_callback=lambda *a, **k: None,
        sample_rate=16000,
    )
    assert ok is True
    assert stream is not None


def test_get_default_input_device_returns_input_side_of_sounddevice_default(monkeypatch):
    from wkey import audio_io

    fake_sd = types.SimpleNamespace(
        default=types.SimpleNamespace(device=(3, 7)),
        query_devices=lambda device=None, kind=None: {"name": "default mic"},
    )
    monkeypatch.setattr(audio_io, "sd", fake_sd)

    assert audio_io.get_default_input_device() == 3
