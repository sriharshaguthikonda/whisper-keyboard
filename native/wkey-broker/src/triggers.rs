use std::time::Duration;

use crate::protocol::{EngineCommand, EngineRoute};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum BrokerKey {
    F23,
    F24,
    LeftCtrl,
    RightCtrl,
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TriggerConfig {
    pub f23_dictation: bool,
    pub f24_command: bool,
    pub left_ctrl_dictation: bool,
    pub right_ctrl_dictation: bool,
}

impl Default for TriggerConfig {
    fn default() -> Self {
        Self {
            f23_dictation: true,
            f24_command: true,
            left_ctrl_dictation: true,
            right_ctrl_dictation: true,
        }
    }
}

impl TriggerConfig {
    pub fn from_record_keys(source: &str) -> Self {
        let mut config = Self {
            f23_dictation: false,
            f24_command: false,
            left_ctrl_dictation: false,
            right_ctrl_dictation: false,
        };
        for label in source
            .split(',')
            .map(|item| item.trim().to_ascii_lowercase())
        {
            match label.as_str() {
                "f23" => config.f23_dictation = true,
                "f24" => config.f24_command = true,
                "ctrl_l" | "left_ctrl" | "left control" => config.left_ctrl_dictation = true,
                "ctrl_r" | "right_ctrl" | "right control" => config.right_ctrl_dictation = true,
                _ => {}
            }
        }
        config
    }
}

#[derive(Debug)]
pub struct TriggerStateMachine {
    config: TriggerConfig,
    df_hold_threshold: Duration,
    f23_down: bool,
    f23_cancelled: bool,
    f24_down: bool,
    left_ctrl_down: bool,
    left_ctrl_started: bool,
    left_ctrl_cancelled: bool,
    right_ctrl_down: bool,
    right_ctrl_started: bool,
    right_ctrl_cancelled: bool,
    d_down_at: Option<Duration>,
    f_down_at: Option<Duration>,
    df_started: bool,
    df_cancelled: bool,
}

impl Default for TriggerStateMachine {
    fn default() -> Self {
        Self::new(TriggerConfig::default())
    }
}

impl TriggerStateMachine {
    pub fn new(config: TriggerConfig) -> Self {
        Self {
            config,
            df_hold_threshold: Duration::from_millis(180),
            f23_down: false,
            f23_cancelled: false,
            f24_down: false,
            left_ctrl_down: false,
            left_ctrl_started: false,
            left_ctrl_cancelled: false,
            right_ctrl_down: false,
            right_ctrl_started: false,
            right_ctrl_cancelled: false,
            d_down_at: None,
            f_down_at: None,
            df_started: false,
            df_cancelled: false,
        }
    }

    pub fn from_record_keys(source: &str) -> Self {
        Self::new(TriggerConfig::from_record_keys(source))
    }

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
        self.cancel_manual_dictation_chord_if_needed(key, decisions);
        self.cancel_df_if_needed(key, decisions);

        match key {
            BrokerKey::F23 => {
                if self.config.f23_dictation && !self.f23_down {
                    self.f23_down = true;
                    self.f23_cancelled = false;
                    decisions.push(engine(EngineCommand::start(EngineRoute::Dictation)));
                }
            }
            BrokerKey::F24 => {
                if self.config.f24_command && !self.f24_down {
                    self.f24_down = true;
                    decisions.push(engine(EngineCommand::start(EngineRoute::Command)));
                }
            }
            BrokerKey::LeftCtrl => {
                if self.config.left_ctrl_dictation && !self.left_ctrl_down {
                    self.left_ctrl_down = true;
                    self.left_ctrl_started = true;
                    self.left_ctrl_cancelled = false;
                    decisions.push(engine(EngineCommand::start(EngineRoute::Dictation)));
                }
            }
            BrokerKey::RightCtrl => {
                if self.config.right_ctrl_dictation && !self.right_ctrl_down {
                    self.right_ctrl_down = true;
                    self.right_ctrl_started = true;
                    self.right_ctrl_cancelled = false;
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
            BrokerKey::F23 => {
                if self.f23_down && !self.f23_cancelled {
                    decisions.push(engine(EngineCommand::stop(EngineRoute::Dictation)));
                }
                self.f23_down = false;
                self.f23_cancelled = false;
            }
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
            BrokerKey::RightCtrl => {
                if self.right_ctrl_down && self.right_ctrl_started && !self.right_ctrl_cancelled {
                    decisions.push(engine(EngineCommand::stop(EngineRoute::Dictation)));
                }
                self.right_ctrl_down = false;
                self.right_ctrl_started = false;
                self.right_ctrl_cancelled = false;
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

    fn cancel_manual_dictation_chord_if_needed(
        &mut self,
        key: BrokerKey,
        decisions: &mut Vec<TriggerDecision>,
    ) {
        if key != BrokerKey::F23 && self.f23_down && !self.f23_cancelled {
            self.f23_cancelled = true;
            decisions.push(engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "f23_chord",
            )));
        }
        if key != BrokerKey::LeftCtrl && self.left_ctrl_started && !self.left_ctrl_cancelled {
            self.left_ctrl_started = false;
            self.left_ctrl_cancelled = true;
            decisions.push(engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "left_ctrl_chord",
            )));
        }
        if key != BrokerKey::RightCtrl && self.right_ctrl_started && !self.right_ctrl_cancelled {
            self.right_ctrl_started = false;
            self.right_ctrl_cancelled = true;
            decisions.push(engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "right_ctrl_chord",
            )));
        }
    }

    fn cancel_df_if_needed(&mut self, key: BrokerKey, decisions: &mut Vec<TriggerDecision>) {
        if matches!(key, BrokerKey::D | BrokerKey::F) {
            return;
        }
        let candidate_active = self.d_down_at.is_some() && self.f_down_at.is_some();
        if (self.df_started || candidate_active) && !self.df_cancelled {
            self.df_cancelled = true;
            if self.df_started {
                decisions.push(engine(EngineCommand::cancel(
                    EngineRoute::Dictation,
                    "df_other_key",
                )));
            }
        }
    }
}

fn engine(command: EngineCommand) -> TriggerDecision {
    TriggerDecision::Engine(command)
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct DfDiagnosticCounters {
    pub df_candidates: u64,
    pub canceled_candidates: u64,
    pub quick_rolls_below_threshold: u64,
    pub other_key_interruptions: u64,
    pub active_trigger_decisions: u64,
    d_down: bool,
    f_down: bool,
    candidate_active: bool,
    candidate_started: bool,
    candidate_interrupted: bool,
}

impl DfDiagnosticCounters {
    pub fn note(&mut self, event: TriggerEvent, decisions: &[TriggerDecision]) {
        match event.kind {
            TriggerEventKind::Press(BrokerKey::D) => {
                self.d_down = true;
                self.maybe_start_candidate();
            }
            TriggerEventKind::Press(BrokerKey::F) => {
                self.f_down = true;
                self.maybe_start_candidate();
            }
            TriggerEventKind::Press(_) => {
                if self.candidate_active {
                    self.other_key_interruptions += 1;
                    if !self.candidate_started && !self.candidate_interrupted {
                        self.canceled_candidates += 1;
                        self.candidate_interrupted = true;
                    }
                }
            }
            TriggerEventKind::Release(BrokerKey::D) => {
                self.d_down = false;
                self.finish_candidate_if_needed();
            }
            TriggerEventKind::Release(BrokerKey::F) => {
                self.f_down = false;
                self.finish_candidate_if_needed();
            }
            TriggerEventKind::Release(_) | TriggerEventKind::Tick => {}
        }

        for decision in decisions {
            self.active_trigger_decisions += 1;
            match decision {
                TriggerDecision::Engine(EngineCommand::Start {
                    route: EngineRoute::Dictation,
                }) if self.candidate_active => {
                    self.candidate_started = true;
                }
                TriggerDecision::Engine(EngineCommand::Cancel {
                    route: EngineRoute::Dictation,
                    reason,
                }) if reason == "df_other_key" => {
                    if !self.candidate_interrupted {
                        self.canceled_candidates += 1;
                        self.candidate_interrupted = true;
                    }
                }
                _ => {}
            }
        }
    }

    pub fn report_line(&self) -> String {
        format!(
            "df_candidates={} canceled_candidates={} quick_rolls_below_threshold={} other_key_interruptions={} active_trigger_decisions={}",
            self.df_candidates,
            self.canceled_candidates,
            self.quick_rolls_below_threshold,
            self.other_key_interruptions,
            self.active_trigger_decisions,
        )
    }

    fn maybe_start_candidate(&mut self) {
        if self.d_down && self.f_down && !self.candidate_active {
            self.df_candidates += 1;
            self.candidate_active = true;
            self.candidate_started = false;
            self.candidate_interrupted = false;
        }
    }

    fn finish_candidate_if_needed(&mut self) {
        if self.candidate_active && (!self.d_down || !self.f_down) {
            if !self.candidate_started && !self.candidate_interrupted {
                self.quick_rolls_below_threshold += 1;
            }
            self.candidate_active = false;
            self.candidate_started = false;
            self.candidate_interrupted = false;
        }
    }
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
    fn df_other_key_before_threshold_cancels_candidate() {
        let mut state = TriggerStateMachine::default();

        state.handle_event(TriggerEvent::press(BrokerKey::D, ms(0)));
        state.handle_event(TriggerEvent::press(BrokerKey::F, ms(0)));
        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::Other(0x43), ms(50))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::tick(ms(180))),
            Vec::<TriggerDecision>::new()
        );
    }

    #[test]
    fn df_diagnostic_counters_track_quick_roll() {
        let mut counters = DfDiagnosticCounters::default();

        counters.note(
            TriggerEvent::press(BrokerKey::D, ms(0)),
            &Vec::<TriggerDecision>::new(),
        );
        counters.note(
            TriggerEvent::press(BrokerKey::F, ms(20)),
            &Vec::<TriggerDecision>::new(),
        );
        counters.note(
            TriggerEvent::release(BrokerKey::D, ms(80)),
            &Vec::<TriggerDecision>::new(),
        );

        assert_eq!(counters.df_candidates, 1);
        assert_eq!(counters.quick_rolls_below_threshold, 1);
    }

    #[test]
    fn df_diagnostic_counters_track_cancelled_active_trigger() {
        let mut counters = DfDiagnosticCounters::default();

        counters.note(
            TriggerEvent::press(BrokerKey::D, ms(0)),
            &Vec::<TriggerDecision>::new(),
        );
        counters.note(
            TriggerEvent::press(BrokerKey::F, ms(0)),
            &Vec::<TriggerDecision>::new(),
        );
        counters.note(
            TriggerEvent::tick(ms(180)),
            &engine(EngineCommand::start(EngineRoute::Dictation)),
        );
        counters.note(
            TriggerEvent::press(BrokerKey::Other(0x43), ms(200)),
            &engine(EngineCommand::cancel(
                EngineRoute::Dictation,
                "df_other_key",
            )),
        );

        assert_eq!(counters.df_candidates, 1);
        assert_eq!(counters.canceled_candidates, 1);
        assert_eq!(counters.other_key_interruptions, 1);
        assert_eq!(counters.active_trigger_decisions, 2);
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
    fn f23_press_release_emits_dictation_start_stop() {
        let mut state = TriggerStateMachine::default();

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::F23, ms(0))),
            engine(EngineCommand::start(EngineRoute::Dictation))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::F23, ms(100))),
            engine(EngineCommand::stop(EngineRoute::Dictation))
        );
    }

    #[test]
    fn right_ctrl_press_release_emits_dictation_start_stop() {
        let mut state = TriggerStateMachine::default();

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::RightCtrl, ms(0))),
            engine(EngineCommand::start(EngineRoute::Dictation))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::RightCtrl, ms(100))),
            engine(EngineCommand::stop(EngineRoute::Dictation))
        );
    }

    #[test]
    fn configured_record_keys_enable_only_selected_manual_triggers() {
        let mut state = TriggerStateMachine::from_record_keys("f24,f23");

        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::RightCtrl, ms(0))),
            Vec::<TriggerDecision>::new()
        );
        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::F23, ms(10))),
            engine(EngineCommand::start(EngineRoute::Dictation))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::release(BrokerKey::F23, ms(15))),
            engine(EngineCommand::stop(EngineRoute::Dictation))
        );
        assert_eq!(
            state.handle_event(TriggerEvent::press(BrokerKey::F24, ms(20))),
            engine(EngineCommand::start(EngineRoute::Command))
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
