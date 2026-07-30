use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, Paragraph};
use ratatui::Frame;

use crate::app::{App, AppMode};
use crate::models::Status;

pub fn draw(
    f: &mut Frame,
    app: &App,
) {
    let size = f.size();
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(1), Constraint::Length(3)])
        .split(size);

    let main_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Ratio(1, 3),
            Constraint::Ratio(1, 3),
            Constraint::Ratio(1, 3),
        ])
        .split(chunks[0]);

    for (i, status) in Status::all().iter().enumerate() {
        let tasks_in_col: Vec<_> = app
            .tasks
            .iter()
            .filter(|t| t.status == *status)
            .collect();

        let items: Vec<ListItem> = tasks_in_col
            .iter()
            .map(|t| {
                let title = t.title.clone();
                let style = if i == app.selected_column {
                    let is_selected = tasks_in_col.iter().position(|x| x.id == t.id)
                        == Some(app.selected_task_indices[i]);
                    if is_selected {
                        Style::default().fg(Color::Yellow).bg(Color::DarkGray)
                    } else {
                        Style::default().fg(Color::White).bg(Color::DarkGray)
                    }
                } else {
                    Style::default()
                };
                ListItem::new(Line::from(Span::styled(title, style)))
            })
            .collect();

        let block = Block::default()
            .borders(Borders::ALL)
            .title(status.to_string())
            .border_style(if i == app.selected_column {
                Style::default().fg(Color::Cyan)
            } else {
                Style::default()
            });

        let list = List::new(items).block(block);
        f.render_widget(list, main_chunks[i]);
    }

    // Bottom status bar
    let status_text = match app.mode {
        AppMode::Normal => {
            let pomodoro_str = match app.pomodoro.state {
                crate::pomodoro::PomodoroState::Idle => "Pomodoro: Idle".to_string(),
                _ => format!(
                    "Pomodoro: {:?} {}",
                    app.pomodoro.state,
                    app.pomodoro.display_remaining()
                ),
            };
            format!(
                "{} | [Tab/←/→] columns  [↑/↓] navigate  [Enter] move  [a] add  [p] pomodoro  [q] quit",
                pomodoro_str
            )
        }
        AppMode::AddingTask => {
            format!("Add task: [{}] (press Enter to save, Esc to cancel)", app.input_buffer)
        }
    };
    let status_paragraph = Paragraph::new(status_text)
        .style(Style::default().fg(Color::Cyan).bg(Color::DarkGray));
    f.render_widget(status_paragraph, chunks[1]);
}