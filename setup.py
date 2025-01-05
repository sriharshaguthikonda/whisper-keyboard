from setuptools import setup

setup(
    name="whisper_keyboard",
    version="1.0",
    packages=["wkey"],
    install_requires=[
        "numpy",
        "sounddevice",
        "pyautogui",
        "pynput",
        "python-dotenv",
        "faster-whisper",
        "groq",
        "torch",
        "pyaudio",
        "openwakeword",
        "webrtcvad",
        "edge-tts",
        "pyttsx4",
        "pydub",
        "aiohttp",
        "selenium",
        "psutil",
    ],
)
