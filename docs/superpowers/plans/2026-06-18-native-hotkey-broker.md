# Native Hotkey Broker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Rust Windows hotkey broker that eventually owns keyboard hooks and controls the existing Python transcription engine.

**Architecture:** Python gets a tested broker-control seam first. Rust then adds a console broker, Win32 low-level keyboard hook, Python child supervision over JSONL stdio, and later tray/status. Hotkey profiles are configurable; `D+F` is diagnostic before default.

**Tech Stack:** Python 3, pytest, Rust 1.94, Cargo, Rust `windows` crate, JSONL over child-process stdio.

## Global Constraints

- Keep audio capture, Groq/Faster-Whisper fallback, transcript cleanup, paste, wake-word path, and command routing in Python.
- Do not make `D+F` default until diagnostic evidence is reviewed.
- Do not disable existing Python hotkeys unless `WKEY_INPUT_OWNER=broker`.
- Broker protocol must not log raw transcripts, audio, or long key streams.
- Use small commits; each task below ends with a commit.
- After any code change, run the primary script smoke: `..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py`, bounded and stopped.

---

## File Structure

- `wkey/broker_control.py`: Python command schema, JSONL parse/format helpers, dispatcher.
- `wkey/faster_whisper_Mother_of_all_wkey.py`: wires broker-control mode, stdin control thread, and Python-listener ownership switch.
- `tests/test_broker_control.py`: Python command parser/dispatcher/stdio tests.
- `tests/test_faster_whisper.py`: broker-mode startup and listener-disable regressions.
- `native/wkey-broker/Cargo.toml`: Rust broker crate.
- `native/wkey-broker/src/protocol.rs`: Rust JSONL command/event types.
- `native/wkey-broker/src/triggers.rs`: pure hotkey state machine.
- `native/wkey-broker/src/win_hook.rs`: Windows low-level keyboard hook.
- `native/wkey-broker/src/engine.rs`: Python child process supervisor.
- `native/wkey-broker/src/main.rs`: broker CLI entrypoint.
- `docs/ROADMAP.md` and `README.md`: updated only after behavior exists.

---

### Task 0: Planning Commit

**Files:**
- Create: `docs/superpowers/specs/2026-06-18-native-hotkey-broker-design.md`
- Create: `docs/superpowers/plans/2026-06-18-native-hotkey-broker.md`
- Modify: `docs/ROADMAP.md`
- Modify: `Q and A.md`

**Interfaces:**
- Produces: agreed design and phase plan.

- [x] **Step 1: Verify docs are staged only with planning files**

Run:

```powershell
git status --short
```

Expected: planning docs and `Q and A.md` are changed; runtime state files may remain modified but must not be staged.

- [x] **Step 2: Run whitespace check**

Run:

```powershell
git diff --check -- docs "Q and A.md"
```

Expected: no whitespace errors.

- [x] **Step 3: Commit**

```powershell
git add docs/ROADMAP.md docs/superpowers/specs/2026-06-18-native-hotkey-broker-design.md docs/superpowers/plans/2026-06-18-native-hotkey-broker.md "Q and A.md"
git commit -m "docs: plan native hotkey broker workflow"
```

---

### Task 1: Python Broker Command Dispatcher

**Files:**
- Create: `wkey/broker_control.py`
- Create: `tests/test_broker_control.py`

**Interfaces:**
- Produces: `BrokerRuntimeDeps`, `parse_command_line(line: str) -> BrokerCommand`, `format_event(event: BrokerEvent) -> str`, `dispatch_command(command: BrokerCommand, deps: BrokerRuntimeDeps) -> BrokerEvent`.
- Consumes later: Rust broker sends commands matching this schema.

- [x] **Step 1: Write failing parser and dispatcher tests**

Add tests for:

```python
def test_parse_start_dictation_command():
    command = parse_command_line('{"id":"1","command":"start","route":"dictation"}')
    assert command.id == "1"
    assert command.command == "start"
    assert command.route == "dictation"

def test_dispatch_start_dictation_calls_start_with_none():
    calls = []
    deps = BrokerRuntimeDeps(
        start=lambda keyword_index: calls.append(("start", keyword_index)),
        stop=lambda keyword_index: calls.append(("stop", keyword_index)),
        cancel=lambda keyword_index, reason: calls.append(("cancel", keyword_index, reason)),
        status=lambda: {"recording": False},
        shutdown=lambda: None,
    )
    event = dispatch_command(
        BrokerCommand(id="1", command="start", route="dictation", reason=None),
        deps,
    )
    assert calls == [("start", None)]
    assert event.ok is True
```

Also test `route="command"` maps to keyword index `0`, unknown commands return `ok=False`, and malformed JSON returns parse error event.

- [x] **Step 2: Run tests to verify failure**

```powershell
..\openai\Scripts\python.exe -m pytest tests\test_broker_control.py -q
```

Expected: import or symbol failures.

- [x] **Step 3: Implement `wkey/broker_control.py`**

Implement dataclasses:

```python
@dataclass(frozen=True)
class BrokerCommand:
    id: str
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
```

Use route map:

```python
ROUTE_KEYWORD_INDEX = {"dictation": None, "command": 0}
EVENT_PREFIX = "WKEY_CONTROL_EVENT "
```

- [x] **Step 4: Run focused tests**

```powershell
..\openai\Scripts\python.exe -m pytest tests\test_broker_control.py -q
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add wkey/broker_control.py tests/test_broker_control.py
git commit -m "feat: add Python broker command dispatcher"
```

---

### Task 2: Python Stdio Control Mode

**Files:**
- Modify: `wkey/faster_whisper_Mother_of_all_wkey.py`
- Modify: `tests/test_faster_whisper.py`
- Modify: `tests/test_broker_control.py`

**Interfaces:**
- Produces: `is_broker_control_stdio_enabled()`, `is_python_keyboard_listener_enabled()`, `start_broker_control_stdio_thread()`.

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_broker_input_owner_disables_python_keyboard_listener(monkeypatch):
    monkeypatch.setenv("WKEY_INPUT_OWNER", "broker")
    mod = importlib.reload(importlib.import_module("wkey.faster_whisper_Mother_of_all_wkey"))
    assert mod.is_keyboard_runtime_enabled() is True
    assert mod.is_python_keyboard_listener_enabled() is False

def test_python_input_owner_keeps_keyboard_listener(monkeypatch):
    monkeypatch.delenv("WKEY_INPUT_OWNER", raising=False)
    mod = importlib.reload(importlib.import_module("wkey.faster_whisper_Mother_of_all_wkey"))
    assert mod.is_python_keyboard_listener_enabled() is True
```

Add stdio loop unit test using `io.StringIO` input and output.

- [ ] **Step 2: Run tests to verify failure**

```powershell
..\openai\Scripts\python.exe -m pytest tests\test_faster_whisper.py::test_broker_input_owner_disables_python_keyboard_listener tests\test_broker_control.py -q
```

Expected: missing functions.

- [ ] **Step 3: Wire broker stdio mode**

Add import fallback for `broker_control`.

Add:

```python
def is_broker_control_stdio_enabled():
    return os.environ.get("WKEY_BROKER_CONTROL", "").strip().lower() == "stdio"

def is_python_keyboard_listener_enabled():
    return (
        is_keyboard_runtime_enabled()
        and os.environ.get("WKEY_INPUT_OWNER", "python").strip().lower() != "broker"
    )
```

Main loop must call `start_listener()` only when `is_python_keyboard_listener_enabled()` is true.

Start a daemon stdin-control thread when `is_broker_control_stdio_enabled()` is true.

- [ ] **Step 4: Run focused tests**

```powershell
..\openai\Scripts\python.exe -m pytest tests\test_broker_control.py tests\test_faster_whisper.py -q
```

Expected: pass.

- [ ] **Step 5: Run required smoke**

```powershell
$proc = Start-Process -FilePath '..\openai\Scripts\python.exe' -ArgumentList 'wkey\faster_whisper_Mother_of_all_wkey.py' -WorkingDirectory 'C:\Windows_software\openai whisper\whisper-keyboard' -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 20
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
```

Expected: process stays alive until stopped; no leftover primary-script process.

- [ ] **Step 6: Commit**

```powershell
git add wkey/faster_whisper_Mother_of_all_wkey.py tests/test_faster_whisper.py tests/test_broker_control.py
git commit -m "feat: add broker stdio mode to Python engine"
```

---

### Task 3: Rust Broker Scaffold And Pure Trigger State

**Files:**
- Create: `native/wkey-broker/Cargo.toml`
- Create: `native/wkey-broker/src/main.rs`
- Create: `native/wkey-broker/src/protocol.rs`
- Create: `native/wkey-broker/src/triggers.rs`

**Interfaces:**
- Produces Rust `EngineCommand`, `TriggerEvent`, `TriggerDecision`, `TriggerStateMachine`.

- [ ] **Step 1: Add failing Rust tests in `triggers.rs`**

Cover:

```rust
df_quick_roll_does_not_trigger()
df_hold_emits_start_dictation()
df_release_after_start_emits_stop_dictation()
df_other_key_after_start_emits_cancel()
f24_press_release_emits_command_start_stop()
left_ctrl_chord_cancels()
```

Use default `D+F` hold threshold `180ms`.

- [ ] **Step 2: Run test to verify failure**

```powershell
cargo test --manifest-path native\wkey-broker\Cargo.toml
```

Expected: scaffold/tests missing or failing.

- [ ] **Step 3: Implement pure state machine**

Rules:

- `F24` route is `command`.
- `LeftCtrl` route is `dictation`, release-alone stop, any other key cancel.
- `D+F` diagnostic route is `dictation` only after both keys are held for at least `180ms`.
- Diagnostic mode emits decisions but does not claim suppression.

- [ ] **Step 4: Run Rust tests**

```powershell
cargo test --manifest-path native\wkey-broker\Cargo.toml
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add native/wkey-broker
git commit -m "feat: scaffold Rust hotkey broker state machine"
```

---

### Task 4: Rust Low-Level Hook Diagnostic

**Files:**
- Modify: `native/wkey-broker/Cargo.toml`
- Create: `native/wkey-broker/src/win_hook.rs`
- Modify: `native/wkey-broker/src/main.rs`

**Interfaces:**
- Produces: `run_keyboard_hook(sender: Sender<KeyEvent>) -> anyhow::Result<()>`.

- [ ] **Step 1: Add `windows` crate features**

Use:

```toml
windows = { version = "0.62", features = [
  "Win32_Foundation",
  "Win32_UI_Input_KeyboardAndMouse",
  "Win32_UI_WindowsAndMessaging",
  "Win32_System_LibraryLoader"
] }
```

- [ ] **Step 2: Implement diagnostic CLI**

Command:

```powershell
cargo run --manifest-path native\wkey-broker\Cargo.toml -- --diagnose-keys
```

Expected behavior: prints broker decisions only, not raw long key streams.

- [ ] **Step 3: Manual diagnostic smoke**

Run broker for 30 seconds, press F24 if available, Left Ctrl, and `D+F`.

Expected:

- no crash;
- `D+F` only emits diagnostic decision after hold threshold;
- normal typing is not suppressed in diagnostic mode.

- [ ] **Step 4: Commit**

```powershell
git add native/wkey-broker
git commit -m "feat: add Rust keyboard hook diagnostic"
```

---

### Task 5: Rust Broker Controls Python Child

**Files:**
- Create: `native/wkey-broker/src/engine.rs`
- Modify: `native/wkey-broker/src/main.rs`
- Modify: `native/wkey-broker/src/protocol.rs`

**Interfaces:**
- Produces: `PythonEngine::spawn(config)`, `PythonEngine::send(command)`, `PythonEngine::shutdown()`.

- [ ] **Step 1: Add protocol round-trip tests**

Test JSON emitted by Rust matches Python schema:

```json
{"id":"1","command":"start","route":"dictation"}
```

- [ ] **Step 2: Implement child process launch**

Broker launches:

```powershell
..\openai\Scripts\python.exe wkey\faster_whisper_Mother_of_all_wkey.py
```

with env:

```text
WKEY_BROKER_CONTROL=stdio
WKEY_INPUT_OWNER=broker
```

- [ ] **Step 3: Add broker smoke command**

Command:

```powershell
cargo run --manifest-path native\wkey-broker\Cargo.toml -- --engine-smoke
```

Expected: starts Python, sends `status`, receives or logs `WKEY_CONTROL_EVENT`, shuts child down.

- [ ] **Step 4: Commit**

```powershell
git add native/wkey-broker
git commit -m "feat: let Rust broker supervise Python engine"
```

---

### Task 6: Broker-Managed Runtime Smoke

**Files:**
- Modify: `wkey/faster_whisper_Mother_of_all_wkey.py`
- Modify: `tests/test_faster_whisper.py`
- Modify: `native/wkey-broker/src/main.rs`
- Modify: `README.md`

**Interfaces:**
- Produces: documented broker-managed launch command.

- [ ] **Step 1: Write regression test**

Assert broker mode starts no Python `pynput` listener but still starts audio/transcription worker setup.

- [ ] **Step 2: Run focused tests**

```powershell
..\openai\Scripts\python.exe -m pytest tests\test_broker_control.py tests\test_faster_whisper.py -q
cargo test --manifest-path native\wkey-broker\Cargo.toml
```

- [ ] **Step 3: Run broker-managed smoke**

```powershell
cargo run --manifest-path native\wkey-broker\Cargo.toml -- --broker-smoke --seconds 20
```

Expected: Python child starts, broker stays alive, no duplicate Python listener, child exits cleanly after smoke.

- [ ] **Step 4: Commit**

```powershell
git add wkey/faster_whisper_Mother_of_all_wkey.py tests/test_faster_whisper.py native/wkey-broker README.md
git commit -m "feat: smoke broker-managed Python runtime"
```

---

### Task 7: `D+F` Diagnostic Decision Gate

**Files:**
- Modify: `native/wkey-broker/src/triggers.rs`
- Modify: `native/wkey-broker/src/main.rs`
- Modify: `docs/ROADMAP.md`
- Modify: `Q and A.md`

**Interfaces:**
- Produces: diagnostic report format in Q&A/roadmap.

- [ ] **Step 1: Add diagnostic counters**

Track:

- candidate `D+F` starts;
- canceled candidates;
- quick rolls below threshold;
- other-key interruptions;
- active trigger decisions.

- [ ] **Step 2: Run 5-minute local diagnostic**

Command:

```powershell
cargo run --manifest-path native\wkey-broker\Cargo.toml -- --diagnose-keys --seconds 300
```

Expected: report contains counts only, no raw text.

- [ ] **Step 3: Write decision note**

Append to `Q and A.md`:

- whether `D+F` looks viable;
- whether to keep Left Ctrl fallback;
- whether active `D+F` needs suppress-and-replay before default.

- [ ] **Step 4: Commit**

```powershell
git add native/wkey-broker docs/ROADMAP.md "Q and A.md"
git commit -m "docs: record d-f hotkey diagnostic decision"
```

---

### Task 8: Tray And Scheduled Task Migration

**Files:**
- Modify: `native/wkey-broker/Cargo.toml`
- Create: `native/wkey-broker/src/tray.rs`
- Modify: `native/wkey-broker/src/main.rs`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`

**Interfaces:**
- Produces: tray menu with status, pause/resume, restart Python engine, quit.

- [ ] **Step 1: Add tray after broker path is reliable**

Use `tray-icon = "0.24.1"` only in this phase.

- [ ] **Step 2: Add tray actions**

Actions:

- Show status.
- Restart Python engine.
- Pause/resume.
- Quit broker and child.

- [ ] **Step 3: Scheduled task migration docs**

Document old task command and new broker command. Do not change Windows Task Scheduler automatically unless user explicitly asks.

- [ ] **Step 4: Run verification**

```powershell
cargo test --manifest-path native\wkey-broker\Cargo.toml
..\openai\Scripts\python.exe -m pytest tests -q
git diff --check
```

Run broker tray manually and verify child cleanup.

- [ ] **Step 5: Commit**

```powershell
git add native/wkey-broker README.md docs/ROADMAP.md
git commit -m "feat: add broker tray supervision"
```

---

## Final Verification For Workflow

Run:

```powershell
..\openai\Scripts\python.exe -m pytest tests -q
cargo test --manifest-path native\wkey-broker\Cargo.toml
git diff --check
```

Run bounded smokes:

```powershell
$proc = Start-Process -FilePath '..\openai\Scripts\python.exe' -ArgumentList 'wkey\faster_whisper_Mother_of_all_wkey.py' -WorkingDirectory 'C:\Windows_software\openai whisper\whisper-keyboard' -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 20
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }

cargo run --manifest-path native\wkey-broker\Cargo.toml -- --broker-smoke --seconds 20
```

Expected: no stdout/stderr failures, no leftover Python primary-script process, no leftover broker process.

## Self-Review

- Spec coverage: plan covers Python control seam, Rust hook, Python supervision, `D+F` diagnostic, tray, scheduled-task migration.
- Placeholder scan: no placeholder markers.
- Type consistency: command routes are `dictation` and `command`; keyword mapping is `None` and `0`; broker mode env vars are `WKEY_BROKER_CONTROL=stdio` and `WKEY_INPUT_OWNER=broker`.
