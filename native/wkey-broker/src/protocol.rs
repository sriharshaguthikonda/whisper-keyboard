use serde::{Deserialize, Serialize};

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
