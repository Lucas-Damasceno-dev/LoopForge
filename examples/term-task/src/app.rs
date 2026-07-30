use anyhow::Result;
use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, Paragraph, Widget};
use ratatui::{Frame, Terminal};

use crate::models::{Status, Task};
use crate::pomodoro::Pomodoro;
use crate::storage::TaskRepository;
use crate::ui;

#[derive(Debug, Clone, PartialEq)]
pub enum AppMode {
    Normal,
    AddingTask,
}

pub struct App {
    pub tasks: Vec<Task>,
    pub selected_column: usize,
    pub selected_task_indices: [usize; 3], // one per column
    pub mode: AppMode,
    pub input_buffer: String,
    pub pomodoro: Pomodoro,
    pub should_quit: bool,
}

impl App {
    pub fn new() -> Self {
        App {
            tasks: Vec::new(),
            selected_column: 0,
            selected_task_indices: [0, 0, 0],
            mode: AppMode::Normal,
            input_buffer: String::new(),
            pomodoro: Pomodoro::default(),
            should_quit: false,
        }
    }

    pub fn load_tasks<R: TaskRepository>(&mut self, repo: &R) -> Result<()> {
        self.tasks = repo.get_all_tasks()?;
        // Ensure selection indices are within bounds
        for (i, status) in Status::all().iter().enumerate() {
            let count = self.tasks.iter().filter(|t| t.status == *status).count();
            if self.selected_task_indices[i] >= count && count > 0 {
                self.selected_task_indices[i] = count.saturating_sub(1);
            }
        }
        Ok(())
    }

    pub fn handle_key<R: TaskRepository>(&mut self, key: KeyEvent, repo: &R) -> Result<()> {
        match self.mode {
            AppMode::Normal => self.handle_normal_key(key, repo),
            AppMode::AddingTask => self.handle_adding_key(key, repo),
        }
    }

    fn handle_normal_key<R: TaskRepository>(&mut self, key: KeyEvent, repo: &R) -> Result<()> {
        match key.code {
            KeyCode::Char('q') => {
                self.should_quit = true;
            }
            KeyCode::Char('a') => {
                self.mode = AppMode::AddingTask;
                self.input_buffer.clear();
            }
            KeyCode::Char('p') => {
                self.pomodoro.toggle();
            }
            KeyCode::Tab | KeyCode::Right => {
                self.selected_column = (self.selected_column + 1).min(2);
            }
            KeyCode::Left => {
                self.selected_column = self.selected_column.saturating_sub(1);
            }
            KeyCode::Up => {
                let idx = &mut self.selected_task_indices[self.selected_column];
                if *idx > 0 {
                    *idx -= 1;
                }
            }
            KeyCode::Down => {
                let idx = &mut self.selected_task_indices[self.selected_column];
                let tasks_in_col = self
                    .tasks
                    .iter()
                    .filter(|t| t.status == Status::all()[self.selected_column])
                    .count();
                if *idx < tasks_in_col.saturating_sub(1) {
                    *idx += 1;
                }
            }
            KeyCode::Enter => {
                // Move selected task to next column
                let tasks_in_col: Vec<usize> = self
                    .tasks
                    .iter()
                    .enumerate()
                    .filter(|(_, t)| t.status == Status::all()[self.selected_column])
                    .map(|(i, _)| i)
                    .collect();
                if let Some(&task_index) = tasks_in_col.get(self.selected_task_indices[self.selected_column]) {
                    let task = &self.tasks[task_index];
                    let new_status = task.status.next();
                    if let Err(e) = repo.update_task_status(task.id, &new_status) {
                        eprintln!("Failed to update task: {}", e);
                    } else {
                        self.tasks[task_index].status = new_status;
                        // Keep selection index in bounds for target column if needed
                    }
                }
            }
            _ => {}
        }
        Ok(())
    }

    fn handle_adding_key<R: TaskRepository>(&mut self, key: KeyEvent, repo: &R) -> Result<()> {
        match key.code {
            KeyCode::Enter => {
                if !self.input_buffer.is_empty() {
                    if let Ok(task) = repo.create_task(&self.input_buffer) {
                        self.tasks.push(task);
                    }
                }
                self.mode = AppMode::Normal;
                self.input_buffer.clear();
            }
            KeyCode::Esc => {
                self.mode = AppMode::Normal;
                self.input_buffer.clear();
            }
            KeyCode::Char(c) => {
                if !key.modifiers.contains(KeyModifiers::CONTROL) {
                    self.input_buffer.push(c);
                }
            }
            KeyCode::Backspace => {
                self.input_buffer.pop();
            }
            _ => {}
        }
        Ok(())
    }

    pub fn update_timer(&mut self, delta: std::time::Duration) {
        self.pomodoro.tick(delta);
    }
}