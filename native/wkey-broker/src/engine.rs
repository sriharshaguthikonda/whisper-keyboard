use std::{
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, ExitStatus, Stdio},
    sync::mpsc::{self, Receiver},
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

use anyhow::{Context, Result, anyhow, bail};

use crate::protocol::{EVENT_PREFIX, EngineCommandMessage, EngineEvent};

#[derive(Clone, Debug)]
pub struct PythonEngineConfig {
    pub repo_dir: PathBuf,
    pub python_exe: PathBuf,
    pub script_path: PathBuf,
}

impl PythonEngineConfig {
    pub fn for_repo(repo_dir: impl Into<PathBuf>) -> Result<Self> {
        let repo_dir = repo_dir.into();
        let parent = repo_dir
            .parent()
            .ok_or_else(|| anyhow!("repo path has no parent: {}", repo_dir.display()))?;
        Ok(Self {
            python_exe: parent.join("openai").join("Scripts").join("python.exe"),
            script_path: repo_dir
                .join("wkey")
                .join("faster_whisper_Mother_of_all_wkey.py"),
            repo_dir,
        })
    }
}

pub struct PythonEngine {
    child: Child,
    stdin: ChildStdin,
    events: Receiver<EngineEvent>,
    _stdout_thread: JoinHandle<()>,
    _stderr_thread: JoinHandle<()>,
}

impl PythonEngine {
    pub fn spawn(config: PythonEngineConfig) -> Result<Self> {
        let mut child = Command::new(&config.python_exe)
            .arg(&config.script_path)
            .current_dir(&config.repo_dir)
            .env("WKEY_BROKER_CONTROL", "stdio")
            .env("WKEY_INPUT_OWNER", "broker")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .with_context(|| {
                format!(
                    "spawn python engine: {} {}",
                    config.python_exe.display(),
                    config.script_path.display()
                )
            })?;

        let stdin = child
            .stdin
            .take()
            .context("python child stdin unavailable")?;
        let stdout = child
            .stdout
            .take()
            .context("python child stdout unavailable")?;
        let stderr = child
            .stderr
            .take()
            .context("python child stderr unavailable")?;
        let (event_sender, event_receiver) = mpsc::channel::<EngineEvent>();

        let stdout_thread = thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line_result in reader.lines() {
                let Ok(line) = line_result else {
                    break;
                };
                if let Some(payload) = line.strip_prefix(EVENT_PREFIX) {
                    match serde_json::from_str::<EngineEvent>(payload) {
                        Ok(event) => {
                            let _ = event_sender.send(event);
                        }
                        Err(error) => eprintln!("python_event_parse_error {error}: {line}"),
                    }
                } else if !line.trim().is_empty() {
                    println!("python_stdout {line}");
                }
            }
        });

        let stderr_thread = thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line_result in reader.lines() {
                let Ok(line) = line_result else {
                    break;
                };
                if !line.trim().is_empty() {
                    eprintln!("python_stderr {line}");
                }
            }
        });

        Ok(Self {
            child,
            stdin,
            events: event_receiver,
            _stdout_thread: stdout_thread,
            _stderr_thread: stderr_thread,
        })
    }

    pub fn send(&mut self, command: &EngineCommandMessage) -> Result<()> {
        let line = serde_json::to_string(command)?;
        writeln!(self.stdin, "{line}")?;
        self.stdin.flush()?;
        Ok(())
    }

    pub fn recv_event_timeout(&mut self, timeout: Duration) -> Result<EngineEvent> {
        let started_at = Instant::now();
        loop {
            if let Some(status) = self.child.try_wait()? {
                bail!("python engine exited before control event: {status}");
            }

            let elapsed = started_at.elapsed();
            if elapsed >= timeout {
                bail!("timed out waiting for python event after {timeout:?}");
            }

            let wait_for = (timeout - elapsed).min(Duration::from_millis(500));
            match self.events.recv_timeout(wait_for) {
                Ok(event) => return Ok(event),
                Err(mpsc::RecvTimeoutError::Timeout) => {}
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    if let Some(status) = self.child.try_wait()? {
                        bail!("python engine exited before control event: {status}");
                    }
                    bail!("python event channel disconnected while child was still running");
                }
            }
        }
    }

    pub fn shutdown(&mut self) -> Result<Option<EngineEvent>> {
        if self.child.try_wait()?.is_some() {
            return Ok(None);
        }

        self.send(&EngineCommandMessage::shutdown("shutdown-1"))?;
        let event = self.recv_event_timeout(Duration::from_secs(30)).ok();
        self.wait_for_exit(Duration::from_secs(30))?;
        Ok(event)
    }

    pub fn wait_for_exit(&mut self, timeout: Duration) -> Result<ExitStatus> {
        let started_at = Instant::now();
        loop {
            if let Some(status) = self.child.try_wait()? {
                if status.success() {
                    return Ok(status);
                }
                bail!("python engine exited with status {status}");
            }
            if started_at.elapsed() >= timeout {
                self.child.kill()?;
                let status = self.child.wait()?;
                bail!("python engine did not exit after {timeout:?}; killed with {status}");
            }
            thread::sleep(Duration::from_millis(100));
        }
    }
}

impl Drop for PythonEngine {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}
