def test_record_release_stops_even_inside_press_debounce_window():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_r},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_r, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_r, recording=True)

    assert events == [("start", None), ("stop", None)]


def test_record_release_stops_if_start_thread_has_not_flipped_recording_yet():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.ctrl_r},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        clock=lambda: now[0],
    )

    handler.on_press(Key.ctrl_r, recording=False)
    now[0] += 0.1
    handler.on_release(Key.ctrl_r, recording=False)

    assert events == [("start", None), ("stop", None)]


def test_record_press_ignored_until_release_rearm_delay_passes():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.caps_lock},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.on_press(Key.caps_lock, recording=False)
    now[0] += 0.1
    handler.on_release(Key.caps_lock, recording=False)
    now[0] += 0.6
    handler.on_press(Key.caps_lock, recording=False)
    now[0] += 0.5
    handler.on_press(Key.caps_lock, recording=False)

    assert events == [("start", None), ("stop", None), ("start", None)]


def test_reset_can_preserve_record_release_rearm_delay():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.caps_lock},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.on_press(Key.caps_lock, recording=False)
    now[0] += 0.1
    handler.on_release(Key.caps_lock, recording=False)
    handler.reset_state(preserve_rearm=True)
    now[0] += 0.6
    handler.on_press(Key.caps_lock, recording=False)
    now[0] += 0.5
    handler.on_press(Key.caps_lock, recording=False)

    assert events == [("start", None), ("stop", None), ("start", None)]


def test_record_key_suppression_blocks_stale_press_after_restart():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.caps_lock},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.suppress_record_keys(2.0, "recovery")
    handler.on_press(Key.caps_lock, recording=False)
    now[0] += 2.1
    handler.on_press(Key.caps_lock, recording=False)

    assert events == [("start", None)]


def test_record_key_release_during_suppression_only_stops_active_recording():
    from pynput.keyboard import Key
    from wkey.keyboard_shortcuts import KeyboardShortcutHandler

    events = []
    now = [100.0]
    handler = KeyboardShortcutHandler(
        record_keys={Key.caps_lock},
        map_key_to_keyword_index=lambda key: None,
        start_recording=lambda keyword_index: events.append(("start", keyword_index)),
        stop_recording=lambda keyword_index: events.append(("stop", keyword_index)),
        toggle_pause=lambda: events.append(("pause", None)),
        debounce_time=0.5,
        record_rearm_delay=1.0,
        clock=lambda: now[0],
    )

    handler.suppress_record_keys(2.0, "recovery")
    handler.on_release(Key.caps_lock, recording=False)
    handler.on_release(Key.caps_lock, recording=True)

    assert events == [("stop", None)]
