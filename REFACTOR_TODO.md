# Refactor TODO (Incremental)

1. [x] Move pause + beep logic into `wkey/pause_control.py`.
2. [x] Move wake-word loop into `wkey/wakeword.py`.
3. [x] Move transcription pipeline into `wkey/transcription_pipeline.py`.
4. [ ] Move audio callback/buffer/VAD into `wkey/audio_io.py`.
5. [ ] Add minimal tests for new modules and run full suite.

After each step:
- Run tests (`python -m pytest`).
- Commit and push.
