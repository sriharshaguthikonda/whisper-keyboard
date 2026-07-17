def test_record_release_stops_even_inside_press_debounce_window():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=True)

    assert events == [("start", None), ("stop", None)]


def test_record_release_stops_if_start_thread_has_not_flipped_recording_yet():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)

    assert events == [("start", None), ("stop", None)]


def test_record_press_ignored_until_release_rearm_delay_passes():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)
    now[0] += 0.6
    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)
    now[0] += 0.5
    handler.on_press(Key.ctrl_l, recording=False)

    assert events == [("start", None), ("stop", None), ("start", None)]


def test_held_record_key_repeats_do_not_restart_after_rearm_delay():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)

    now[0] += 0.1
    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 1.1
    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)
    now[0] += 1.1
    handler.on_press(Key.ctrl_l, recording=False)

    assert events == [("start", None), ("stop", None), ("start", None)]


def test_right_ctrl_chord_cancels_recording_and_release_does_not_stop():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_r},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        cancel_recording=lambda keyword_index, reason: events.append(
            ("cancel", keyword_index, reason)
        ),
        toggle_pause=lambda: events.append(("pause", None)),
        cancel_on_chord_keys={Key.ctrl_r},
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_r, recording=False)
    handler.on_press("c", recording=True)
    handler.on_release(Key.ctrl_r, recording=False)

    assert events == [("start", None), ("cancel", None, "chord:c")]


def test_unconfigured_caps_lock_is_not_tracked_with_left_ctrl_record_key():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        clock=lambda: now[0],
    )

    handler.on_press(Key.caps_lock, recording=False)
    handler.on_press(Key.ctrl_l, recording=False)

    assert Key.caps_lock not in handler._pressed
    assert events == [("start", None)]


def test_reset_can_preserve_record_release_rearm_delay():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)
    handler.reset_state(preserve_rearm=True)
    now[0] += 0.6
    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_l, recording=False)
    now[0] += 0.5
    handler.on_press(Key.ctrl_l, recording=False)

    assert events == [("start", None), ("stop", None), ("start", None)]


def test_record_key_suppression_blocks_stale_press_after_restart():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.suppress_record_keys(2.0, "recovery")
    handler.on_press(Key.ctrl_l, recording=False)
    now[0] += 2.1
    handler.on_release(Key.ctrl_l, recording=False)
    handler.on_press(Key.ctrl_l, recording=False)

    assert events == [("start", None)]


def test_record_key_release_during_suppression_only_stops_active_recording():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_l},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.suppress_record_keys(2.0, "recovery")
    handler.on_release(Key.ctrl_l, recording=False)
    handler.on_release(Key.ctrl_l, recording=True)

    assert events == [("stop", None)]


def test_record_key_event_log_includes_pid():
    import os
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    class FakeLog:
        def __init__(self):
            self.messages = []

        def info(self, fmt, *args):
            self.messages.append(fmt % args)

    fake_log = FakeLog()
    handler = KeyboardShortcutHandler(
        record_keys={Key.f23},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: None,
        stop_recording=lambda keyword_index: None,
        toggle_pause=lambda: None,
        clock=lambda: 100.0,
        log=fake_log,
    )

    handler.on_press(Key.f23, recording=False)

    assert any(f"pid={os.getpid()}" in msg for msg in fake_log.messages)


def test_describe_trigger_state_reports_active_key_and_rearm_status():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.f23},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: None,
        stop_recording=lambda keyword_index: None,
        toggle_pause=lambda: None,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    trigger_key_label, rearm_state = handler.describe_trigger_state()
    assert trigger_key_label == "none"
    assert rearm_state == "armed"  # never released yet -> rearm gap is +inf

    handler.on_press(Key.f23, recording=False)
    trigger_key_label, rearm_state = handler.describe_trigger_state()
    assert trigger_key_label == str(Key.f23)

    now[0] += 0.1
    handler.on_release(Key.f23, recording=True)
    trigger_key_label, rearm_state = handler.describe_trigger_state()
    assert trigger_key_label == "none"
    assert rearm_state.startswith("rearming(")
