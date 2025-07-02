whisper-keyboard
================

Whisper Keyboard lets you type with your voice by holding a hotkey or saying a wake word.

Features
--------
* Wake word detection powered by Porcupine ("Hey llama")
* Hotkey recording (F24 by default)
* Beep sounds when recording starts, stops and when text is pasted
* System volume is lowered during recording and restored afterwards
* Uses the Groq API for transcription with a local Whisper fallback
* Transcripts are pasted automatically into the active window

Installation
------------

.. code-block:: bash

   pip install -r requirements.txt
   pip install faster-whisper vosk pyaudio pvporcupine pycaw groq clipboard pyautogui

Usage
-----

Create a ``.env`` file with your API keys::

   GROQ_API_KEY=your_groq_api_key
   PICO_ACCESS_KEY=your_picovoice_access_key
   WKEY=f24

Run the main script::

   python wkey/faster_whisper_Mother_of_all_wkey.py

License
-------
MIT
