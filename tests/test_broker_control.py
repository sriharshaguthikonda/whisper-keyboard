import json

from wkey.broker_control import (
    EVENT_PREFIX,
    BrokerCommand,
    BrokerRuntimeDeps,
    dispatch_command,
    format_event,
    parse_command_line,
)


def _deps(calls):
    return BrokerRuntimeDeps(
        start=lambda keyword_index: calls.append(("start", keyword_index)),
        stop=lambda keyword_index: calls.append(("stop", keyword_index)),
        cancel=lambda keyword_index, reason: calls.append(
            ("cancel", keyword_index, reason)
        ),
        status=lambda: {"recording": False},
        shutdown=lambda: calls.append(("shutdown", None)),
    )


def test_parse_start_dictation_command():
    command = parse_command_line('{"id":"1","command":"start","route":"dictation"}')

    assert command.id == "1"
    assert command.command == "start"
    assert command.route == "dictation"


def test_dispatch_start_dictation_calls_start_with_none():
    calls = []
    deps = _deps(calls)

    event = dispatch_command(
        BrokerCommand(id="1", command="start", route="dictation", reason=None),
        deps,
    )

    assert calls == [("start", None)]
    assert event.ok is True
    assert event.command == "start"
    assert event.route == "dictation"


def test_dispatch_start_command_route_maps_to_keyword_zero():
    calls = []
    deps = _deps(calls)

    event = dispatch_command(
        BrokerCommand(id="2", command="start", route="command", reason=None),
        deps,
    )

    assert calls == [("start", 0)]
    assert event.ok is True


def test_dispatch_unknown_command_returns_error_event():
    calls = []
    deps = _deps(calls)

    event = dispatch_command(
        BrokerCommand(id="3", command="launch", route="dictation", reason=None),
        deps,
    )

    assert calls == []
    assert event.ok is False
    assert event.command == "launch"
    assert "unknown command" in event.error


def test_malformed_json_returns_parse_error_event():
    calls = []
    deps = _deps(calls)

    command = parse_command_line("{not-json")
    event = dispatch_command(command, deps)

    assert calls == []
    assert event.ok is False
    assert event.event == "parse_error"
    assert event.error


def test_format_event_prefixes_compact_json_line():
    event = dispatch_command(
        BrokerCommand(id="4", command="status", route=None, reason=None),
        _deps([]),
    )

    line = format_event(event)

    assert line.startswith(EVENT_PREFIX)
    payload = json.loads(line.removeprefix(EVENT_PREFIX))
    assert payload["id"] == "4"
    assert payload["event"] == "status"
    assert payload["ok"] is True
    assert payload["status"] == {"recording": False}
