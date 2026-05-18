"""F24 keyboard-only launcher for the current Mother-of-all runtime.

This file intentionally delegates to `faster_whisper_Mother_of_all_wkey.py` so
the keyboard path does not drift from the main recovery, buffering, settings,
and transcription code.
"""

import os

os.environ.setdefault("WKEY", "f24")
os.environ.setdefault("WKEY_RUNTIME_MODE", "keyboard")
os.environ.setdefault("WKEY_RECORD_KEYS", "f24")

try:
    from faster_whisper_Mother_of_all_wkey import main
except ModuleNotFoundError:
    from wkey.faster_whisper_Mother_of_all_wkey import main


if __name__ == "__main__":
    main()
