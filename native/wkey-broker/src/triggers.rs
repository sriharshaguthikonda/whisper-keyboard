use std::time::Duration;

use crate::protocol::{EngineCommand, EngineRoute};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum BrokerKey {
    F24,
    LeftCtrl,
    D,
    F,
    Other(u16),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TriggerEventKind {
    Press(BrokerKey),
    Release(BrokerKey),
    Tick,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TriggerEvent {
    pub at: Duration,
    pub kind: TriggerEventKind,
}

impl TriggerEvent {
    pub fn press(key: BrokerKey, at: Duration) -> Self {
        Self {
            at,
            kind: TriggerEventKind::Press(key),
        }
    }

    pub fn release(key: BrokerKey, at: Duration) -> Self {
        Self {
            at,
            kind: TriggerEventKind::Release(key),
        }
    }

    pub fn tick(at: Duration) -> Self {
        Self {
            at,
            kind: TriggerEventKind::Tick,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TriggerDecision {
    Engine(EngineCommand),
}

#[derive(Debug)]
pub struct TriggerStateMachine {
    df_hold_threshold: Duration,
    f24_down: bool,
    left_ctrl_down: bool,
    left_ctrl_started: bool,
    left_ctrl_cancelled: bool,
    d_down_at: Option<Duration>,
    f_down_at: Option<Duration>,
    df_started: bool,
    df_cancelled: bool,
}

impl Default for TriggerStateMachine {
    fn default() -> Self {
        Self {
            df_hold_threshold: Duration::from_millis(180),
            f24_down: false,
            left_ctrl_down: false,
            left_ctrl_started: false,
            left_ctrl_cancelled: false,
            d_down_at: None,
            f_down_at: None,
            df_started: false,
            df_cancelled: false,
        }
    }
}

impl TriggerStateMachine {
    pub fn handle_event(&mut self, event: TriggerEvent) -> Vec<TriggerDecision> {
        let mut decisions = Vec::new();
        match event.kind {
            TriggerEventKind::Press(key) => self.handle_press(key, event.at, &mut decisions),
            TriggerEventKind::Release(key) => self.handle_release(key, event.at, &mut decisions),
            TriggerEventKind::Tick => self.maybe_start_df(event.at, &mut decisions),
        }
        decisions
    }

    fn handle_press(&mut self, key: BrokerKey, at: Duration, decisions: &mut Vec<TriggerDecision>) {
        self.cancel_left_ctrl_chord_if_needed(key, decisions);
        self.cancel_df_if_needed(key, decisions);

        match key {
            BrokerKey::F24 => {
                if !self.f24_down {
                    self.f24_down = true;
                    decisions.push(engine(EngineCommand::start(EngineRoute::Command)));
                }
            }
            BrokerKey::LeftCtrl => {
                if !self.left_ctrl_down {
                    self.left_ctrl_down = true;
                    self.left_ctrl_started = true;
                    self.left_ctrl_cancelled = false;
                    decisions.push(engine(EngineCommand::start(EngineRoute::Dictation)));
                }
            }
            BrokerKey::D => {
                if self.d_down_at.is_none() {
                    self.d_down_at = Some(at);
                }
                self.maybe_start_df(at, decisions);
            }
            BrokerKey::F => {
                if self.f_down_at.is_none() {
                    self.f_down_at = Some(at);
                }
                self.maybe_start_df(at, decisions);
            }
            BrokerKey::Other(_) => {}
        }
    }

    fn handle_release(
        &mut self,
        key: BrokerKey,
        _at: Duration,
        decisions: &mut Vec<TriggerDecision>,
    ) {
        match key {
            BrokerKey::F24 => {
                if self.f24_down {
                    self.f24_down = false;
                    decisions.push(engine(EngineCommand::stop(EngineRoute::Command)));
                }
            }
            BrokerKey::LeftCtrl => {
                if self.left_ctrl_down && self.left_ctrl_started && !self.left_ctrl_cancelled {
                    decisions.push(engine(EngineCommand::stop(EngineRoute::Dictation)));
                }
                self.left_ctrl_down = false;
                self.left_ctrl_started = false;
                self.left_ctrl_cancelled = false;
            }
            BrokerKey::D | BrokerKey::F => {
                let should_stop = self.df_started && !self.df_cancelled;
                match key {
                    BrokerKey::D => self.d_down_at = None,
                    BrokerKey::F => self.f_down_at = None,
                    _ => {}
                }
                if should_stop {
                    decisions.push(engine(EngineCommand::stop(EngineRoute::Dictation)));
                    self.df_started = false;
                    self.df_cancelled = false;
                }
                if self.d_down_at.is_none() && self.f_down_at.is_none() {
                    self.df_started = false;
                    self.df_cancelled = false;
                }
            }
            BrokerKey::Other(_) => {}
        }
    }

    fn maybe_start_df(&mut self, at: Duration, decisions: &mut Vec<TriggerDecision>) {
        if self.df_started || self.df_cancelled {
            return;
        }
        let Some(d_down_at) = self.d_down_at else {
            return;
        };
        let Some(f_down_at) = self.f_down_at else {
            return;
        };
        let both_down_since = d_down_at.max(f_down_at);
        if at.saturating_sub(both_down_since) >= self.df_hold_threshold {
            self.df_started = true;
            decisions.push(engine(EngineCommand::start(EngineRoute::Dictation)));
        }
    }

    fn cancel_left_ctrl_chord_if_needed(
        &mut self,
        key: BrokerKey,
        decisions: &mut Vec<TriggerDecision>,
    ) {
        if key == BrokerKey::LeftCtrl {
            return;
        }
        if self.left_ctrl_started && !self.left_ctrl_cancelled {
            self.left_ctrl_started = false;
            self.left_ctrl_cancelled = true;
            decisions.push(engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "left_ctrl_chord",
            )));
        }
    }

    fn cancel_df_if_needed(&mut self, key: BrokerKey, decisions: &mut Vec<TriggerDecision>) {
        if matches!(key, BrokerKey::D | BrokerKey::F) {
            return;
        }
        if self.df_started && !self.df_cancelled {
            self.df_cancelled = true;
            decisions.push(engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "df_other_key",
            )));
        }
    }
}

fn engine(command: EngineCommand) -> TriggerDecision {
    TriggerDecision::Engine(command)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ms(value: u64) -> Duration {
        Duration::from_millis(value)
    }

    fn engine(command: EngineCommand) -> Vec<TriggerDecision> {
        vec![TriggerDecision::Engine(command)]
    }

    #[test]
    fn df_quick_roll_does_not_trigger() {
        let mut state = TriggerStateMachine::default();

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::D, ms(0))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::F, ms(30))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::D, ms(100))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::tick(ms(250))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::F, ms(260))),
            Vec::<TriggerDecision>::new()
        );
    }

    #[test]
    fn df_hold_emits_start_dictation() {
        let mut state = TriggerStateMachine::default();

        state.handle_event(TriggerEvent::press(BrokerKey::D, ms(0)));
        state.handle_event(TriggerEvent::press(BrokerKey::F, ms(0)));
        assert_eq!(
            state.handle_event(TriggerEvent::tick(ms(179))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::tick(ms(180))),
            engine(EngineCommand::start(EngineRoute::Dictation))
        );
    }

    #[test]
    fn df_release_after_start_emits_stop_dictation() {
        let mut state = TriggerStateMachine::default();

        state.handle_event(TriggerEvent::press(BrokerKey::D, ms(0)));
        state.handle_event(TriggerEvent::press(BrokerKey::F, ms(0)));
        state.handle_event(TriggerEvent::tick(ms(180)));

        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::D, ms(200))),
            engine(EngineCommand::stop(EngineRoute::Dictation))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::F, ms(210))),
            Vec::<TriggerDecision>::new()
        );
    }

    #[test]
    fn df_other_key_after_start_emits_cancel() {
        let mut state = TriggerStateMachine::default();

        state.handle_event(TriggerEvent::press(BrokerKey::D, ms(0)));
        state.handle_event(TriggerEvent::press(BrokerKey::F, ms(0)));
        state.handle_event(TriggerEvent::tick(ms(180)));

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::Other(0x43), ms(200))),
            engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "df_other_key"
            ))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::D, ms(220))),
            Vec::<TriggerDecision>::new()
        );
    }

    #[test]
    fn f24_press_release_emits_command_start_stop() {
        let mut state = TriggerStateMachine::default();

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::F24, ms(0))),
            engine(EngineCommand::start(EngineRoute::Command))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::F24, ms(100))),
            engine(EngineCommand::stop(EngineRoute::Command))
        );
    }

    #[test]
    fn left_ctrl_chord_cancels() {
        let mut state = TriggerStateMachine::default();

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::LeftCtrl, ms(0))),
            engine(EngineCommand::start(EngineRoute::Dictation))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::Other(0x43), ms(30))),
            engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "left_ctrl_chord"
            ))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::LeftCtrl, ms(60))),
            Vec::<TriggerDecision>::new()
        );
    }
}
