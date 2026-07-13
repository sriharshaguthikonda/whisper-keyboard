@echo off
REM Double-click to start Whisper Keyboard directly (no broker), with a console
REM window so you can see it is running. Uses the project venv automatically.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start-WhisperKeyboard.ps1" -Console
