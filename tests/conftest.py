import sys
import types
import os
import pytest

class DummyStream:
    def __init__(self, *args, **kwargs):
        self.active = False
        self.callback = kwargs.get('callback')
    def start_stream(self):
        self.active = True
    def stop_stream(self):
        self.active = False
    def close(self):
        pass
    def read(self, n, exception_on_overflow=False):
        return b"\x00" * n
    def is_active(self):
        return self.active
    def start(self):
        self.active = True
    def stop(self):
        self.active = False
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass

class DummyInputStream(DummyStream):
    pass

class DummyPyAudio:
    def open(self, *args, **kwargs):
        return DummyStream()
    def terminate(self):
        pass

sounddevice = types.SimpleNamespace(InputStream=DummyInputStream, query_devices=lambda: [{'max_input_channels':1}])
pyaudio = types.SimpleNamespace(PyAudio=DummyPyAudio, paInt16=0)
winsound = types.SimpleNamespace(Beep=lambda *a, **k: None)

class DummyGroq:
    def __init__(self, api_key=None):
        self.audio = types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=lambda **kwargs: types.SimpleNamespace(text="")))
class RateLimitError(Exception):
    pass

groq = types.SimpleNamespace(Groq=DummyGroq, RateLimitError=RateLimitError)

class DummyModel:
    def __init__(self, *args, **kwargs):
        self.prediction_buffer = {0:[0.0],1:[0.0],2:[0.0],3:[0.0]}
    def predict(self, pcm):
        return self.prediction_buffer

openwakeword = types.ModuleType('openwakeword')
openwakeword.model = types.ModuleType('openwakeword.model')
openwakeword.model.Model = DummyModel

class DummyCuda:
    @staticmethod
    def is_available():
        return True

torch = types.ModuleType('torch')
torch.cuda = DummyCuda()

aiohttp = types.ModuleType('aiohttp')
aiohttp.ClientSession = object
aiohttp.FormData = lambda: types.SimpleNamespace(add_field=lambda *a, **k: None)
aiohttp.ClientResponseError = Exception

pyautogui = types.ModuleType('pyautogui')
webrtcvad = types.ModuleType('webrtcvad')
webrtcvad.Vad = lambda *a, **k: types.SimpleNamespace(is_speech=lambda *a, **k: False)
pythoncom = types.ModuleType('pythoncom')
pythoncom.CoInitialize = lambda : None
comtypes = types.ModuleType('comtypes')
comtypes.CLSCTX_ALL = 0

pycaw = types.ModuleType('pycaw')
pycaw.callbacks = types.ModuleType('pycaw.callbacks')
pycaw.pycaw = types.ModuleType('pycaw.pycaw')

class DummyAudioEndpointVolumeCallback:
    pass

class DummyEndpointDevices:
    def Activate(self, *a, **k):
        return object()

class DummyAudioUtilities:
    @staticmethod
    def GetSpeakers():
        return DummyEndpointDevices()

class DummyIAudioEndpointVolume:
    _iid_ = object()

pycaw.callbacks.AudioEndpointVolumeCallback = DummyAudioEndpointVolumeCallback
pycaw.pycaw.AudioUtilities = DummyAudioUtilities
pycaw.pycaw.IAudioEndpointVolume = DummyIAudioEndpointVolume
faster_whisper = types.ModuleType('faster_whisper')
class DummyWhisperModel:
    def __init__(self, *a, **k):
        pass
    def transcribe(self, audio, language="en"):
        return ([types.SimpleNamespace(text="test")], None)

faster_whisper.WhisperModel = DummyWhisperModel
pynput = types.ModuleType('pynput')
class DummyKey(dict):
    def __getitem__(self, item):
        return item
    def __getattr__(self, attr):
        return attr
pynput.keyboard = types.SimpleNamespace(
    Controller=lambda: None,
    Key=DummyKey(),
    Listener=lambda *a, **k: None,
)

dotenv = types.ModuleType('dotenv')
dotenv.load_dotenv = lambda: None

try:
    import scipy  # type: ignore
    import scipy.io  # type: ignore
    import scipy.io.wavfile  # type: ignore
    _has_scipy = True
except Exception:
    _has_scipy = False
    scipy = types.ModuleType('scipy')
    scipy_io = types.ModuleType('scipy.io')
    scipy_io_wavfile = types.ModuleType('scipy.io.wavfile')
    scipy_io_wavfile.write = lambda *a, **k: None
    scipy.io = scipy_io
    scipy.io.wavfile = scipy_io_wavfile

voice_commands = types.ModuleType('voice_commands')
voice_commands.execute_command_fuzzy = lambda *a, **k: None
voice_commands.execute_command_run_with_tool = lambda *a, **k: None
voice_commands.start_driver = lambda: None
voice_commands.get_volume = lambda: 0.5
voice_commands.set_volume = lambda v: None
voice_commands.driver = None

google_assistant = types.ModuleType('google_assistant')
async def dummy_google_assistant(*a, **k):
    pass
google_assistant.google_assistant = dummy_google_assistant

pause_all = types.ModuleType('pause_all')
pause_all.is_sound_playing_windows_processing = lambda x: False

clipboard_utils = types.ModuleType('clipboard_utils')
clipboard_utils.paste_transcript = lambda *a, **k: None

voice_activity_detection = types.ModuleType('voice_activity_detection')
class DummyVoiceDetector:
    pass
voice_activity_detection.VoiceDetector = DummyVoiceDetector

modules = {
    'sounddevice': sounddevice,
    'pyaudio': pyaudio,
    'winsound': winsound,
    'groq': groq,
    'openwakeword': openwakeword,
    'openwakeword.model': openwakeword.model,
    'torch': torch,
    'aiohttp': aiohttp,
    'pyautogui': pyautogui,
    'webrtcvad': webrtcvad,
    'pythoncom': pythoncom,
    'comtypes': comtypes,
    'pycaw': pycaw,
    'pycaw.callbacks': pycaw.callbacks,
    'pycaw.pycaw': pycaw.pycaw,
    'faster_whisper': faster_whisper,
    'pynput': pynput,
    'pynput.keyboard': pynput.keyboard,
    'dotenv': dotenv,
    'voice_commands': voice_commands,
    'google_assistant': google_assistant,
    'pause_all': pause_all,
    'clipboard_utils': clipboard_utils,
    'voice_activity_detection': voice_activity_detection,
}

if not _has_scipy:
    modules.update({
        'scipy': scipy,
        'scipy.io': scipy_io,
        'scipy.io.wavfile': scipy_io_wavfile,
    })

@pytest.fixture(scope='session', autouse=True)
def patch_modules():
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    original = {}
    for name, mod in modules.items():
        original[name] = sys.modules.get(name)
        sys.modules[name] = mod
    yield
    for name, orig in original.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig
