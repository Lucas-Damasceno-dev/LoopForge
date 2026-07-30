use std::time::Duration;

#[derive(Debug, Clone, PartialEq)]
pub enum PomodoroState {
    Idle,
    Work,
    Break,
}

#[derive(Debug, Clone)]
pub struct Pomodoro {
    pub state: PomodoroState,
    pub work_duration: Duration,
    pub break_duration: Duration,
    pub remaining: Duration,
    pub cycles: u32,
}

impl Default for Pomodoro {
    fn default() -> Self {
        Pomodoro {
            state: PomodoroState::Idle,
            work_duration: Duration::from_secs(25 * 60),
            break_duration: Duration::from_secs(5 * 60),
            remaining: Duration::default(),
            cycles: 0,
        }
    }
}

impl Pomodoro {
    pub fn start_work(&mut self) {
        self.state = PomodoroState::Work;
        self.remaining = self.work_duration;
    }

    pub fn start_break(&mut self) {
        self.state = PomodoroState::Break;
        self.remaining = self.break_duration;
    }

    pub fn tick(&mut self, delta: Duration) {
        if self.state == PomodoroState::Idle {
            return;
        }
        if self.remaining > delta {
            self.remaining -= delta;
        } else {
            // session finished
            match self.state {
                PomodoroState::Work => {
                    self.cycles += 1;
                    self.start_break();
                }
                PomodoroState::Break => {
                    self.state = PomodoroState::Idle;
                    self.remaining = Duration::default();
                }
                _ => {}
            }
        }
    }

    pub fn reset(&mut self) {
        self.state = PomodoroState::Idle;
        self.remaining = Duration::default();
    }

    pub fn toggle(&mut self) {
        match self.state {
            PomodoroState::Idle => self.start_work(),
            PomodoroState::Work | PomodoroState::Break => self.reset(),
        }
    }

    pub fn display_remaining(&self) -> String {
        let secs = self.remaining.as_secs();
        format!("{:02}:{:02}", secs / 60, secs % 60)
    }
}