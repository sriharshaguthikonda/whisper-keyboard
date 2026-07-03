mod engine;
mod protocol;
mod triggers;
mod win_hook;

use std::{
    env, fs,
    path::Path,
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

use anyhow::{Context, Result, bail};
use engine::{PythonEngine, PythonEngineConfig};
use protocol::{EngineCommandMessage, EngineEvent};
use triggers::{DfDiagnosticCounters, TriggerDecision, TriggerEvent, TriggerStateMachine};
use win_hook::HookKeyEvent;

#[derive(Clone, Debug)]
struct BrokerSupervisorPolicy {
    recoverable_python_exit_code: i32,
    base_restart_delay: Duration,
    max_restart_delay: Duration,
}

impl Default for BrokerSupervisorPolicy {
    fn default() -> Self {
        Self {
            recoverable_python_exit_code: 75,
            base_restart_delay: Duration::from_secs(2),
            max_restart_delay: Duration::from_secs(30),
        }
    }
}

impl BrokerSupervisorPolicy {
    fn should_restart_python_exit(&self, exit_code: i32) -> bool {
        exit_code == self.recoverable_python_exit_code
    }

    fn restart_delay(&self, attempt: u32) -> Duration {
        self.base_restart_delay
            .saturating_mul(attempt)
            .min(self.max_restart_delay)
    }
}

fn main() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--broker-smoke") {
        return run_broker_smoke(parse_seconds(&args)?);
    }
    if args.iter().any(|arg| arg == "--engine-smoke") {
        return run_engine_smoke();
    }
    if args.iter().any(|arg| arg == "--diagnose-keys") {
        return run_key_diagnostic(parse_seconds(&args)?);
    }
    if args.iter().any(|arg| arg == "--run") {
        return run_broker_runtime(parse_optional_seconds(&args)?);
    }

    println!("wkey-broker scaffold");
    Ok(())
}

fn parse_seconds(args: &[String]) -> Result<u64> {
    let Some(index) = args.iter().position(|arg| arg == "--seconds") else {
        return Ok(30);
    };
    let Some(value) = args.get(index + 1) else {
        bail!("--seconds requires a value");
    };
    let seconds = value
        .parse::<u64>()
        .with_context(|| format!("invalid --seconds value: {value}"))?;
    Ok(seconds.max(1))
}

fn parse_optional_seconds(args: &[String]) -> Result<Option<u64>> {
    if args.iter().any(|arg| arg == "--seconds") {
        Ok(Some(parse_seconds(args)?))
    } else {
        Ok(None)
    }
}

fn run_key_diagnostic(seconds: u64) -> Result<()> {
    let duration = Duration::from_secs(seconds);
    let started_at = Instant::now();
    let (sender, receiver) = mpsc::channel::<HookKeyEvent>();
    let hook_thread = thread::spawn(move || win_hook::run_keyboard_hook_for(sender, duration));
    let mut state = TriggerStateMachine::default();
    let mut counters = DfDiagnosticCounters::default();
    let mut decision_count = 0usize;

    println!("diagnostic_start seconds={seconds}");
    while started_at.elapsed() < duration {
        match receiver.recv_timeout(Duration::from_millis(20)) {
            Ok(event) => {
                let trigger_event = if event.pressed {
                    TriggerEvent::press(event.key, started_at.elapsed())
                } else {
                    TriggerEvent::release(event.key, started_at.elapsed())
                };
                let decisions = state.handle_event(trigger_event);
                counters.note(trigger_event, &decisions);
                decision_count += print_decisions(decisions);
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                let trigger_event = TriggerEvent::tick(started_at.elapsed());
                let decisions = state.handle_event(trigger_event);
                counters.note(trigger_event, &decisions);
                decision_count += print_decisions(decisions);
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }

    hook_thread
        .join()
        .map_err(|_| anyhow::anyhow!("keyboard hook thread panicked"))??;
    println!("diagnostic_report {}", counters.report_line());
    println!("diagnostic_complete decisions={decision_count}");
    Ok(())
}

fn run_broker_runtime(seconds: Option<u64>) -> Result<()> {
    let repo_dir = env::current_dir()?;
    let config = PythonEngineConfig::for_repo(repo_dir.clone())?;
    let mut engine = PythonEngine::spawn(config)?;
    println!(
        "broker_python_child pid={} job_object={}",
        engine.child_id(),
        engine.child_job_attached()
    );
    let startup = request_status(&mut engine, "runtime-startup-status")?;
    ensure_python_listener_disabled(&startup)?;
    println!("broker_runtime_startup {startup:?}");

    let duration = seconds.map(Duration::from_secs);
    let started_at = Instant::now();
    let (sender, receiver) = mpsc::channel::<HookKeyEvent>();
    let hook_thread = thread::spawn(move || match duration {
        Some(limit) => win_hook::run_keyboard_hook_for(sender, limit),
        None => win_hook::run_keyboard_hook(sender),
    });

    let mut state = trigger_state_for_repo(&repo_dir);
    let mut command_sequence = 0u64;
    loop {
        if duration.is_some_and(|limit| started_at.elapsed() >= limit) {
            break;
        }
        ensure_engine_live(&mut engine)?;
        match receiver.recv_timeout(Duration::from_millis(20)) {
            Ok(event) => {
                let trigger_event = if event.pressed {
                    TriggerEvent::press(event.key, started_at.elapsed())
                } else {
                    TriggerEvent::release(event.key, started_at.elapsed())
                };
                let decisions = state.handle_event(trigger_event);
                dispatch_engine_decisions(&mut engine, decisions, &mut command_sequence)?;
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                let decisions = state.handle_event(TriggerEvent::tick(started_at.elapsed()));
                dispatch_engine_decisions(&mut engine, decisions, &mut command_sequence)?;
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }

    hook_thread
        .join()
        .map_err(|_| anyhow::anyhow!("keyboard hook thread panicked"))??;
    if let Some(shutdown) = engine.shutdown()? {
        println!("broker_runtime_shutdown {shutdown:?}");
    }
    Ok(())
}

fn trigger_state_for_repo(repo_dir: &Path) -> TriggerStateMachine {
    if let Some(profiles) = configured_hotkey_profiles(repo_dir) {
        match TriggerStateMachine::from_hotkey_profiles_json(&profiles) {
            Ok(state) => {
                println!("broker_trigger_config hotkey_profiles=true");
                return state;
            }
            Err(err) => {
                println!("broker_trigger_config hotkey_profiles_error={err}");
            }
        }
    }
    if let Some(record_keys) = configured_record_keys(repo_dir) {
        println!("broker_trigger_config record_keys={record_keys}");
        TriggerStateMachine::from_record_keys(&record_keys)
    } else {
        TriggerStateMachine::default()
    }
}

fn configured_hotkey_profiles(repo_dir: &Path) -> Option<String> {
    if let Ok(value) = env::var("WKEY_HOTKEY_PROFILES") {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Some(trimmed.to_string());
        }
    }

    let config_path = repo_dir.join("wkey").join("transcription_config.json");
    let text = fs::read_to_string(config_path).ok()?;
    let parsed: serde_json::Value = serde_json::from_str(&text).ok()?;
    let profiles = parsed.get("hotkey_profiles")?;
    Some(profiles.to_string())
}

fn configured_record_keys(repo_dir: &Path) -> Option<String> {
    if let Ok(value) = env::var("WKEY_RECORD_KEYS") {
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            return Some(trimmed.to_string());
        }
    }

    let config_path = repo_dir.join("wkey").join("transcription_config.json");
    let text = fs::read_to_string(config_path).ok()?;
    let parsed: serde_json::Value = serde_json::from_str(&text).ok()?;
    let record_keys = parsed.get("record_keys")?.as_str()?.trim();
    if record_keys.is_empty() {
        None
    } else {
        Some(record_keys.to_string())
    }
}

fn run_engine_smoke() -> Result<()> {
    let config = PythonEngineConfig::for_repo(env::current_dir()?)?;
    let mut engine = PythonEngine::spawn(config)?;
    println!(
        "engine_python_child pid={} job_object={}",
        engine.child_id(),
        engine.child_job_attached()
    );

    let status = request_status(&mut engine, "status-1")?;
    println!("engine_event {status:?}");

    if let Some(shutdown) = engine.shutdown()? {
        println!("engine_event {shutdown:?}");
    }
    Ok(())
}

fn run_broker_smoke(seconds: u64) -> Result<()> {
    let config = PythonEngineConfig::for_repo(env::current_dir()?)?;
    let mut engine = PythonEngine::spawn(config)?;
    println!(
        "broker_smoke_python_child pid={} job_object={}",
        engine.child_id(),
        engine.child_job_attached()
    );
    let duration = Duration::from_secs(seconds);

    let startup = request_status(&mut engine, "startup-status")?;
    ensure_python_listener_disabled(&startup)?;
    println!("broker_smoke_startup {startup:?}");

    thread::sleep(duration);
    let runtime = request_status(&mut engine, "runtime-status")?;
    ensure_python_listener_disabled(&runtime)?;
    println!("broker_smoke_runtime {runtime:?}");

    if let Some(shutdown) = engine.shutdown()? {
        println!("broker_smoke_shutdown {shutdown:?}");
    }
    Ok(())
}

fn dispatch_engine_decisions(
    engine: &mut PythonEngine,
    decisions: Vec<TriggerDecision>,
    command_sequence: &mut u64,
) -> Result<usize> {
    let mut sent = 0usize;
    for decision in decisions {
        let TriggerDecision::Engine(command) = decision;
        *command_sequence += 1;
        let id = format!("trigger-{command_sequence}");
        engine.send(&EngineCommandMessage::from_engine_command(id, &command))?;
        let event = engine.recv_event_timeout(Duration::from_secs(5))?;
        println!("broker_runtime_event {event:?}");
        sent += 1;
    }
    Ok(sent)
}

fn request_status(engine: &mut PythonEngine, id: &str) -> Result<EngineEvent> {
    ensure_engine_live(engine)?;
    engine.send(&EngineCommandMessage::status(id))?;
    engine.recv_event_timeout(Duration::from_secs(180))
}

fn ensure_engine_live(engine: &mut PythonEngine) -> Result<()> {
    if let Some(status) = engine.poll_exit()? {
        let exit_code = status.code().unwrap_or(-1);
        let policy = BrokerSupervisorPolicy::default();
        let suggested_delay = policy.restart_delay(1);
        bail!(
            "python engine exited during broker runtime: status={status} code={exit_code} recoverable={} suggested_restart_delay_ms={}",
            policy.should_restart_python_exit(exit_code),
            suggested_delay.as_millis()
        );
    }
    Ok(())
}

fn ensure_python_listener_disabled(event: &EngineEvent) -> Result<()> {
    let disabled = event
        .status
        .as_ref()
        .and_then(|status| status.get("python_keyboard_listener_enabled"))
        .and_then(|value| value.as_bool())
        == Some(false);
    if disabled {
        Ok(())
    } else {
        bail!("broker-managed Python listener is not disabled: {event:?}");
    }
}

fn print_decisions(decisions: Vec<TriggerDecision>) -> usize {
    let count = decisions.len();
    for decision in decisions {
        println!("trigger_decision {decision:?}");
    }
    count
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn supervisor_policy_restarts_recoverable_python_exit() {
        let policy = BrokerSupervisorPolicy::default();

        assert!(policy.should_restart_python_exit(75));
        assert!(!policy.should_restart_python_exit(0));
    }

    #[test]
    fn supervisor_policy_caps_backoff_delay() {
        let policy = BrokerSupervisorPolicy::default();

        assert_eq!(policy.restart_delay(1), Duration::from_secs(2));
        assert_eq!(policy.restart_delay(99), Duration::from_secs(30));
    }
}
