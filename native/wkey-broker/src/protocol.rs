use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const EVENT_PREFIX: &str = "WKEY_CONTROL_EVENT ";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EngineRoute {
    Dictation,
    Command,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EngineCommand {
    Start { route: EngineRoute },
    Stop { route: EngineRoute },
    Cancel { route: EngineRoute, reason: String },
}

impl EngineCommand {
    pub fn start(route: EngineRoute) -> Self {
        Self::Start { route }
    }

    pub fn stop(route: EngineRoute) -> Self {
        Self::Stop { route }
    }

    pub fn cancel(route: EngineRoute, reason: impl Into<String>) -> Self {
        Self::Cancel {
            route,
            reason: reason.into(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct EngineCommandMessage {
    pub id: String,
    pub command: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub route: Option<EngineRoute>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

impl EngineCommandMessage {
    #[allow(dead_code)]
    pub fn from_engine_command(id: impl Into<String>, command: &EngineCommand) -> Self {
        match command {
            EngineCommand::Start { route } => Self {
                id: id.into(),
                command: "start".to_string(),
                route: Some(*route),
                reason: None,
            },
            EngineCommand::Stop { route } => Self {
                id: id.into(),
                command: "stop".to_string(),
                route: Some(*route),
                reason: None,
            },
            EngineCommand::Cancel { route, reason } => Self {
                id: id.into(),
                command: "cancel".to_string(),
                route: Some(*route),
                reason: Some(reason.clone()),
            },
        }
    }

    pub fn status(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            command: "status".to_string(),
            route: None,
            reason: None,
        }
    }

    pub fn shutdown(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            command: "shutdown".to_string(),
            route: None,
            reason: None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq)]
pub struct EngineEvent {
    pub id: Option<String>,
    pub event: String,
    pub ok: bool,
    pub command: Option<String>,
    pub route: Option<String>,
    pub reason: Option<String>,
    pub status: Option<Value>,
    pub error: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_dictation_command_serializes_to_python_schema() {
        let message = EngineCommandMessage::from_engine_command(
            "1",
            &EngineCommand::start(EngineRoute::Dictation),
        );

        assert_eq!(
            serde_json::to_string(&message).unwrap(),
            r#"{"id":"1","command":"start","route":"dictation"}"#
        );
    }

    #[test]
    fn cancel_command_serializes_reason() {
        let message = EngineCommandMessage::from_engine_command(
            "2",
            &EngineCommand::cancel(EngineRoute::Dictation, "left_ctrl_chord"),
        );

        assert_eq!(
            serde_json::to_string(&message).unwrap(),
            r#"{"id":"2","command":"cancel","route":"dictation","reason":"left_ctrl_chord"}"#
        );
    }
}
