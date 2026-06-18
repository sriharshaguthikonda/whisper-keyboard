from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable


EVENT_PREFIX = "WKEY_CONTROL_EVENT "
PARSE_ERROR_COMMAND = "parse_error"
ROUTE_KEYWORD_INDEX = {"dictation": None, "command": 0}


@dataclass(frozen=True)
class BrokerCommand:
    id: str | None
    command: str
    route: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class BrokerEvent:
    id: str | None
    event: str
    ok: bool
    command: str | None = None
    route: str | None = None
    reason: str | None = None
    status: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class BrokerRuntimeDeps:
    start: Callable[[int | None], None]
    stop: Callable[[int | None], None]
    cancel: Callable[[int | None, str], None]
    status: Callable[[], dict[str, Any]]
    shutdown: Callable[[], None]


def parse_command_line(line: str) -> BrokerCommand:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        return _parse_error(f"invalid json: {exc.msg}")

    if not isinstance(payload, dict):
        return _parse_error("command payload must be an object")

    command_id = payload.get("id")
    if command_id is not None and not isinstance(command_id, str):
        return _parse_error("command id must be a string")

    command = payload.get("command")
    if not isinstance(command, str) or not command:
        return _parse_error("command must be a non-empty string", command_id)

    route = payload.get("route")
    if route is not None and not isinstance(route, str):
        return _parse_error("route must be a string", command_id)

    reason = payload.get("reason")
    if reason is not None and not isinstance(reason, str):
        return _parse_error("reason must be a string", command_id)

    return BrokerCommand(
        id=command_id,
        command=command,
        route=route,
        reason=reason,
    )


def dispatch_command(command: BrokerCommand, deps: BrokerRuntimeDeps) -> BrokerEvent:
    if command.command == PARSE_ERROR_COMMAND:
        return BrokerEvent(
            id=command.id,
            event="parse_error",
            ok=False,
            error=command.reason or "parse error",
        )

    try:
        if command.command == "start":
            keyword_index = _keyword_index_for_route(command)
            deps.start(keyword_index)
            return _success_event(command)

        if command.command == "stop":
            keyword_index = _keyword_index_for_route(command)
            deps.stop(keyword_index)
            return _success_event(command)

        if command.command == "cancel":
            keyword_index = _keyword_index_for_route(command)
            reason = command.reason or "broker_cancel"
            deps.cancel(keyword_index, reason)
            return _success_event(command, reason=reason)

        if command.command == "status":
            return BrokerEvent(
                id=command.id,
                event="status",
                ok=True,
                command=command.command,
                status=deps.status(),
            )

        if command.command == "shutdown":
            deps.shutdown()
            return _success_event(command)
    except ValueError as exc:
        return _error_event(command, str(exc))
    except Exception as exc:
        return _error_event(command, f"{command.command} failed: {exc}")

    return _error_event(command, f"unknown command: {command.command}")


def format_event(event: BrokerEvent) -> str:
    payload = {key: value for key, value in asdict(event).items() if value is not None}
    return EVENT_PREFIX + json.dumps(payload, separators=(",", ":"), sort_keys=True)


def run_control_stdio(input_stream, output_stream, deps: BrokerRuntimeDeps) -> None:
    for raw_line in input_stream:
        line = raw_line.strip()
        if not line:
            continue

        command = parse_command_line(line)
        event = dispatch_command(command, deps)
        output_stream.write(format_event(event) + "\n")
        output_stream.flush()

        if command.command == "shutdown" and event.ok:
            break


def _parse_error(message: str, command_id: str | None = None) -> BrokerCommand:
    return BrokerCommand(
        id=command_id,
        command=PARSE_ERROR_COMMAND,
        reason=message,
    )


def _keyword_index_for_route(command: BrokerCommand) -> int | None:
    route = command.route or "dictation"
    if route not in ROUTE_KEYWORD_INDEX:
        raise ValueError(f"unknown route: {route}")
    return ROUTE_KEYWORD_INDEX[route]


def _success_event(command: BrokerCommand, reason: str | None = None) -> BrokerEvent:
    return BrokerEvent(
        id=command.id,
        event="command",
        ok=True,
        command=command.command,
        route=command.route,
        reason=reason,
    )


def _error_event(command: BrokerCommand, error: str) -> BrokerEvent:
    return BrokerEvent(
        id=command.id,
        event="error",
        ok=False,
        command=command.command,
        route=command.route,
        reason=command.reason,
        error=error,
    )
