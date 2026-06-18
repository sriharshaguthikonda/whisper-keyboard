mod engine;
mod protocol;
mod triggers;
mod win_hook;

use std::{
    env,
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

use anyhow::{Context, Result, bail};
use engine::{PythonEngine, PythonEngineConfig};
use protocol::EngineCommandMessage;
use triggers::{TriggerDecision, TriggerEvent, TriggerStateMachine};
use win_hook::HookKeyEvent;

fn main() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.iter().any(|arg| arg == "--engine-smoke") {
        return run_engine_smoke();
    }
    if args.iter().any(|arg| arg == "--diagnose-keys") {
        return run_key_diagnostic(parse_seconds(&args)?);
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

fn run_key_diagnostic(seconds: u64) -> Result<()> {
    let duration = Duration::from_secs(seconds);
    let started_at = Instant::now();
    let (sender, receiver) = mpsc::channel::<HookKeyEvent>();
    let hook_thread = thread::spawn(move || win_hook::run_keyboard_hook_for(sender, duration));
    let mut state = TriggerStateMachine::default();
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
                decision_count += print_decisions(state.handle_event(trigger_event));
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                decision_count +=
                    print_decisions(state.handle_event(TriggerEvent::tick(started_at.elapsed())));
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }

    hook_thread
        .join()
        .map_err(|_| anyhow::anyhow!("keyboard hook thread panicked"))??;
    println!("diagnostic_complete decisions={decision_count}");
    Ok(())
}

fn run_engine_smoke() -> Result<()> {
    let config = PythonEngineConfig::for_repo(env::current_dir()?)?;
    let mut engine = PythonEngine::spawn(config)?;

    engine.send(&EngineCommandMessage::status("status-1"))?;
    let status = engine.recv_event_timeout(Duration::from_secs(180))?;
    println!("engine_event {status:?}");

    if let Some(shutdown) = engine.shutdown()? {
        println!("engine_event {shutdown:?}");
    }
    Ok(())
}

fn print_decisions(decisions: Vec<TriggerDecision>) -> usize {
    let count = decisions.len();
    for decision in decisions {
        println!("trigger_decision {decision:?}");
    }
    count
}
