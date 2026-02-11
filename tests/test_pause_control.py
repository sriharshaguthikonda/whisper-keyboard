import time

import pytest


def test_read_pause_flag(tmp_path):
    from wkey import pause_control

    flag = tmp_path / "voice_pause_flag.txt"
    assert pause_control.read_pause_flag(str(flag)) is False
    flag.write_text("PAUSED")
    assert pause_control.read_pause_flag(str(flag)) is True
    flag.write_text("ACTIVE")
    assert pause_control.read_pause_flag(str(flag)) is False


def test_check_pause_status_respects_min_interval(tmp_path):
    from wkey import pause_control

    flag = tmp_path / "voice_pause_flag.txt"
    flag.write_text("PAUSED")
    paused, last_check, status = pause_control.check_pause_status(
        str(flag), 0, False, min_interval=0
    )
    assert paused is True
    assert status is True
    # Within min interval returns cached state
    paused2, last_check2, status2 = pause_control.check_pause_status(
        str(flag), last_check, False, min_interval=999
    )
    assert paused2 is False
    assert status2 is False
    assert last_check2 == last_check


def test_toggle_pause_state_beeps(monkeypatch, tmp_path):
    from wkey import pause_control

    flag = tmp_path / "voice_pause_flag.txt"
    beeps = []

    def fake_beep(freq, dur):
        beeps.append((freq, dur))

    monkeypatch.setattr(pause_control.winsound, "Beep", fake_beep)

    new_state = pause_control.toggle_pause_state(str(flag), False)
    assert new_state is True
    assert len(beeps) == len(pause_control.PAUSE_BEEP_SEQUENCE)

    beeps.clear()
    new_state = pause_control.toggle_pause_state(str(flag), True)
    assert new_state is False
    assert len(beeps) == len(pause_control.RESUME_BEEP_SEQUENCE)
