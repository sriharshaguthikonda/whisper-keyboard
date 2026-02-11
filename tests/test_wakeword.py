import pytest


def test_wakeword_waits_for_mic(monkeypatch):
    from wkey.wakeword import WakeWordListener

    listener = WakeWordListener()
    messages = []

    def log(msg):
        messages.append(msg)

    def get_wake_stream():
        return None

    def set_wake_stream(_):
        pass

    def check_pause_status():
        return False

    def is_recording():
        return False

    def start_recording_async(_):
        pass

    def stop_recording_async(_):
        pass

    def decrease_volume_all():
        pass

    def restore_volume_all():
        pass

    def stop_sleep(_):
        raise StopIteration()

    monkeypatch.setattr("wkey.wakeword.time.sleep", stop_sleep)

    with pytest.raises(StopIteration):
        listener.listen(
            get_wake_stream=get_wake_stream,
            set_wake_stream=set_wake_stream,
            check_pause_status=check_pause_status,
            is_recording=is_recording,
            start_recording_async=start_recording_async,
            stop_recording_async=stop_recording_async,
            decrease_volume_all=decrease_volume_all,
            restore_volume_all=restore_volume_all,
            log=log,
        )

    assert any("Listening for wake words" in msg for msg in messages)
    assert any("Waiting for microphone" in msg for msg in messages)
