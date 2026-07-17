from wkey import overlay_notify


def test_format_truncates_and_collapses_to_single_line():
    assert overlay_notify._format("hello\nworld  \t  again") == "hello world again"
    long_text = "x" * 100
    result = overlay_notify._format(long_text, max_len=10)
    assert result == "x" * 9 + "…"
    assert len(result) == 10


def test_format_no_ellipsis_when_not_truncated():
    assert overlay_notify._format("short") == "short"


def test_gate_honors_overlay_enabled():
    assert overlay_notify._gate({"overlay_enabled": True}) is True
    assert overlay_notify._gate({"overlay_enabled": False}) is False
    assert overlay_notify._gate({}) is True
    assert overlay_notify._gate(None) is True


def test_notify_is_noop_when_tk_unavailable(monkeypatch):
    monkeypatch.setattr(overlay_notify, "_TK_AVAILABLE", False)
    assert overlay_notify.notify("hello") is None


def test_notify_never_raises_even_if_settings_blow_up(monkeypatch):
    monkeypatch.setattr(overlay_notify, "_TK_AVAILABLE", False)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(overlay_notify, "load_settings", _boom)
    # _TK_AVAILABLE False short-circuits before load_settings is even called,
    # so this asserts the early-return path, not the try/except - both must
    # never raise.
    assert overlay_notify.notify("hello") is None


def test_notify_disabled_by_settings_does_not_start_thread(monkeypatch):
    monkeypatch.setattr(overlay_notify, "_TK_AVAILABLE", True)
    monkeypatch.setattr(overlay_notify, "load_settings", lambda *a, **k: {"overlay_enabled": False})
    monkeypatch.setattr(overlay_notify, "_ensure_thread", lambda: (_ for _ in ()).throw(
        AssertionError("should not start overlay thread when disabled")
    ))
    assert overlay_notify.notify("hello") is None

class _FakeRoot:
    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


def test_clamp_position_uses_monitor_work_area_with_negative_coords(monkeypatch):
    # Secondary monitor left of primary: virtual coords are negative.
    monkeypatch.setattr(
        overlay_notify, "_monitor_work_area", lambda x, y: (-1920, 0, 0, 1040)
    )
    x, y = overlay_notify._clamp_position(_FakeRoot(), -100, 1200, 200, 50)
    assert x == -200  # clamped to right edge of the left monitor
    assert y == 990  # clamped to its work-area bottom


def test_clamp_position_falls_back_to_primary_screen(monkeypatch):
    monkeypatch.setattr(overlay_notify, "_monitor_work_area", lambda x, y: None)
    x, y = overlay_notify._clamp_position(_FakeRoot(), 5000, -50, 200, 50)
    assert x == 1720
    assert y == 0
