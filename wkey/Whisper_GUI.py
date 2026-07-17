# Whisper_GUI.py
"""Thin entry-point shim.

The legacy PyQt6 settings dialog (VoicePauseController) was retired; Control
Center (wkey/control_center.py) owns settings now. This file stays only
because Whisper.bat / Start-WhisperKeyboard.ps1 launch it by name.
"""

import sys

try:
    from control_center import main as control_center_main
except ModuleNotFoundError:
    from wkey.control_center import main as control_center_main


def main():
    return control_center_main()


if __name__ == "__main__":
    sys.exit(main())
