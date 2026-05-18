import importlib
import io
import types
import numpy as np
import pytest
import asyncio

@pytest.fixture
def fw_module():
    mod = importlib.import_module('wkey.faster_whisper_Mother_of_all_wkey')
    mod = importlib.reload(mod)
    yield mod
    if hasattr(mod, 'reset_state'):
        mod.reset_state()

def test_validate_audio_buffer(fw_module):
    sr = fw_module.sample_rate
    assert fw_module.validate_audio_buffer(None) is False
    assert fw_module.validate_audio_buffer(np.array([], dtype=np.float32)) is False
    assert fw_module.validate_audio_buffer([1,2,3]) is False
    short = np.zeros(int(sr * 0.05), dtype=np.float32)
    assert fw_module.validate_audio_buffer(short) is False
    good = np.zeros(int(sr * 0.2), dtype=np.float32)
    assert fw_module.validate_audio_buffer(good) is True


def test_create_wav_buffer(fw_module):
    data = np.zeros(fw_module.sample_rate, dtype=np.float32)
    buf = fw_module.create_wav_buffer(data)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_check_pause_status(tmp_path, fw_module, monkeypatch):
    flag = tmp_path / 'voice_pause_flag.txt'

    def fake_pause_check(flag_path, last_pause_check, global_pause_active, min_interval=0.5):
        paused = flag.exists() and flag.read_text().strip() == 'PAUSED'
        return paused, 1, paused

    monkeypatch.setattr(fw_module, 'pause_check_impl', fake_pause_check)
    flag.write_text('PAUSED')
    fw_module.last_pause_check = 0
    assert fw_module.check_pause_status() is True
    flag.write_text('RUNNING')
    fw_module.last_pause_check = 0
    assert fw_module.check_pause_status() is False
    flag.unlink()
    fw_module.last_pause_check = 0
    assert fw_module.check_pause_status() is False


def test_beep(fw_module, monkeypatch):
    called = {}
    def fake(freq, dur):
        called['freq'] = freq
        called['dur'] = dur
    monkeypatch.setattr(fw_module.winsound, 'Beep', fake)
    fw_module.beep((440, 100))
    assert called == {'freq': 440, 'dur': 100}


def test_volume_functions(fw_module, monkeypatch):
    class DummyLeaseManager:
        def begin_duck(self, reason):
            return 0.5, 1

        def end_duck(self, reason):
            return 0.5, 0, True

        def try_snapshot_state(self):
            return {
                "lease_count": 0,
                "restore_pending": False,
                "restore_target": None,
            }

    monkeypatch.setattr(fw_module, 'volume_lease_manager', DummyLeaseManager())
    fw_module.initial_volume = None
    fw_module.decrease_volume_all()
    assert fw_module.initial_volume == 0.5
    fw_module.restore_volume_all()
    assert fw_module.initial_volume is None


def test_save_audio(tmp_path, fw_module):
    data = np.zeros(fw_module.sample_rate // 2, dtype=np.float32)
    fw_module.save_audio(data, 1, directory=str(tmp_path), sample_rate=fw_module.sample_rate, type_of_audio='test')
    files = list(tmp_path.glob('test_1_recording*.wav'))
    assert len(files) == 1


def test_transcribe_pre_recording_buffer(fw_module, monkeypatch):
    monkeypatch.setattr(fw_module, 'transcribe_pre_recording_buffer_util', lambda *args, **kwargs: 'hello')
    data = np.zeros(fw_module.sample_rate // 10, dtype=np.float32)
    text = fw_module.transcribe_pre_recording_buffer(data)
    assert text == 'hello'


def test_transcribe_with_local_model(fw_module, monkeypatch):
    class Seg:
        def __init__(self, text):
            self.text = text
    fw_module.model = types.SimpleNamespace()
    monkeypatch.setattr(
        fw_module.model,
        'transcribe',
        lambda audio, language='en': ([Seg('hello'), Seg('world')], None),
        raising=False,
    )
    data = np.zeros(fw_module.sample_rate // 10, dtype=np.float32)
    text = fw_module.transcribe_with_local_model(data, 0)
    assert text == 'hello world'


def test_get_transcript_with_retries(fw_module, monkeypatch):
    calls = []
    async def fake_groq(byte_io, keyword_index):
        calls.append('remote')
        if len(calls) < 2:
            raise Exception('fail')
        return 'remote text'
    monkeypatch.setattr(fw_module, 'transcribe_with_groq_async', fake_groq)
    monkeypatch.setattr(fw_module, 'transcribe_with_local_model', lambda b, k: 'local text')
    byte_io = fw_module.create_wav_buffer(np.zeros(fw_module.sample_rate // 10, dtype=np.float32))
    result = asyncio.run(fw_module.get_transcript_with_retries(byte_io, 1, max_retries=3))
    assert result == 'remote text'
    assert calls == ['remote', 'remote']


def test_reset_state(fw_module, monkeypatch):
    monkeypatch.setattr(fw_module, 'restore_volume_all', lambda: None)
    fw_module.recording = True
    fw_module.play_pause_pressed = True
    fw_module.audio_buffer = np.ones(5, dtype=np.float32)
    fw_module.reset_state()
    assert fw_module.recording is False
    assert fw_module.play_pause_pressed is False
    assert isinstance(fw_module.audio_buffer, np.ndarray)
    assert fw_module.audio_buffer.size == 0


def test_stop_recording_includes_pre_buffer(fw_module, monkeypatch):
    monkeypatch.setattr(fw_module, 'restore_volume_all', lambda: None)
    monkeypatch.setattr(fw_module, 'beep', lambda *a, **k: None)

    fw_module.recording = True
    fw_module.play_pause_pressed = False
    fw_module.stream = types.SimpleNamespace(active=False)
    fw_module.buffer_index = 0

    fw_module.pre_recording_buffer = np.arange(
        fw_module.BUFFER_SIZE, dtype=np.float32
    ).reshape(-1, 1)
    fw_module.audio_buffer = np.array([10.0, 11.0, 12.0], dtype=np.float32)

    while not fw_module.audio_buffer_queue.empty():
        fw_module.audio_buffer_queue.get()

    fw_module.stop_recording(None)

    queued_audio, idx = fw_module.audio_buffer_queue.get_nowait()
    assert idx is None
    assert len(queued_audio) == len(fw_module.pre_recording_buffer_f24) + 3
    assert np.allclose(queued_audio[-3:], [10.0, 11.0, 12.0])


def test_audio_recovery_reports_cooldown_skip(fw_module):
    fw_module.audio_recovery_in_progress = False
    fw_module.last_audio_recovery_ts = fw_module.time.time()

    assert fw_module._perform_audio_recovery("test-cooldown") is False
