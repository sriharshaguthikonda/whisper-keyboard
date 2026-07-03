use std::{
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, ExitStatus, Stdio},
    sync::mpsc::{self, Receiver},
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

#[cfg(windows)]
use std::os::windows::io::AsRawHandle;

use anyhow::{Context, Result, anyhow, bail};

#[cfg(windows)]
use windows::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, JobObjectExtendedLimitInformation,
        SetInformationJobObject,
    },
};

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
    child_job: Option<ChildJob>,
    _stdout_thread: JoinHandle<()>,
    _stderr_thread: JoinHandle<()>,
}

#[cfg(windows)]
struct ChildJob {
    handle: HANDLE,
}

#[cfg(windows)]
impl ChildJob {
    fn attach(child: &Child) -> Result<Self> {
        unsafe {
            let job = CreateJobObjectW(None, None).context("create child job object")?;
            let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
            .context("configure child job object kill-on-close")?;
            AssignProcessToJobObject(job, HANDLE(child.as_raw_handle()))
                .context("assign python child to job object")?;
            Ok(Self { handle: job })
        }
    }
}

#[cfg(windows)]
impl Drop for ChildJob {
    fn drop(&mut self) {
        unsafe {
            let _ = CloseHandle(self.handle);
        }
    }
}

#[cfg(not(windows))]
struct ChildJob;

fn attach_child_job(child: &mut Child) -> Result<Option<ChildJob>> {
    #[cfg(windows)]
    {
        match ChildJob::attach(child) {
            Ok(job) => Ok(Some(job)),
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                Err(error)
            }
        }
    }
    #[cfg(not(windows))]
    {
        let _ = child;
        Ok(None)
    }
}

impl PythonEngine {
    pub fn spawn(config: PythonEngineConfig) -> Result<Self> {
        let mut command = Command::new(&config.python_exe);
        command
            .arg(&config.script_path)
            .current_dir(&config.repo_dir)
            .env("WKEY_BROKER_CONTROL", "stdio")
            .env("WKEY_INPUT_OWNER", "broker");
        Self::spawn_command(
            command,
            format!(
                "spawn python engine: {} {}",
                config.python_exe.display(),
                config.script_path.display()
            ),
        )
    }

    fn spawn_command(mut command: Command, context: String) -> Result<Self> {
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .with_context(|| context.clone())?;
        let child_job = attach_child_job(&mut child).with_context(|| context.clone())?;

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
            child_job,
            _stdout_thread: stdout_thread,
            _stderr_thread: stderr_thread,
        })
    }

    #[cfg(test)]
    pub fn spawn_test_process(command: Command) -> Result<Self> {
        Self::spawn_command(command, "spawn test process".to_string())
    }

    pub fn child_id(&self) -> u32 {
        self.child.id()
    }

    pub fn child_job_attached(&self) -> bool {
        self.child_job.is_some()
    }

    pub fn poll_exit(&mut self) -> Result<Option<ExitStatus>> {
        Ok(self.child.try_wait()?)
    }

    #[cfg(test)]
    pub fn has_child_job_for_test(&self) -> bool {
        self.child_job.is_some()
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    #[test]
    fn poll_exit_reports_child_exit_without_control_event() -> Result<()> {
        let mut command = Command::new("cmd");
        command.args(["/D", "/C", "exit 7"]);
        let mut engine = PythonEngine::spawn_test_process(command)?;

        let started = Instant::now();
        loop {
            if let Some(status) = engine.poll_exit()? {
                assert!(!status.success());
                return Ok(());
            }
            if started.elapsed() > Duration::from_secs(5) {
                bail!("test process did not exit");
            }
            thread::sleep(Duration::from_millis(25));
        }
    }

    #[cfg(windows)]
    #[test]
    fn spawned_engine_owns_child_job_object() -> Result<()> {
        let mut command = Command::new("cmd");
        command.args(["/D", "/C", "ping -n 3 127.0.0.1 >NUL"]);
        let engine = PythonEngine::spawn_test_process(command)?;

        assert!(engine.has_child_job_for_test());
        Ok(())
    }
}
