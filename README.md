# Whisper Keyboard

Whisper Keyboard lets you dictate text on Windows using either a hotkey or a wake word. It records your speech, transcribes it, and pastes the result into the current window.

## Features
- **Wake word detection** using Porcupine ("Hey llama").
- **Hotkey recording**: hold a configurable key (F24 by default) to record.
- **Beep notifications** for start, stop and paste events.
- **Volume management**: lowers system volume while recording and restores it afterwards.
- **Asynchronous transcription** pipeline that uses the Groq API and falls back to a local Whisper model when needed.
- **Automatic pasting** of the transcript into the active window.

## Installation
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install faster-whisper vosk pyaudio pvporcupine pycaw groq clipboard pyautogui
   ```
   Additional system libraries such as PortAudio may be required for `pyaudio`.

## Usage
1. Create a `.env` file containing:
   ```plaintext
   GROQ_API_KEY=your_groq_api_key
   PICO_ACCESS_KEY=your_picovoice_access_key
   WKEY=f24
   ```
2. Run the main script:
   ```bash
   python wkey/faster_whisper_Mother_of_all_wkey.py
   ```
   Say the wake word or hold the configured key to start dictating.

## Project Layout
- `wkey/faster_whisper_Mother_of_all_wkey.py` – main application.
- `wkey/beep_utils.py` – definitions for beep sounds.
- `wkey/transcription_utils.py` – helper functions for Groq and local transcription.
- `wkey/volume_manipulation.py` – utilities to adjust system volume.

## License
MIT
