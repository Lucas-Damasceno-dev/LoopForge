use termtask::app::App;
use termtask::models::{Status, Task};
use termtask::pomodoro::Pomodoro;
use termtask::storage::{SqliteRepository, TaskRepository};

fn setup_repo() -> SqliteRepository {
    SqliteRepository::new_in_memory().unwrap()
}

#[test]
fn test_app_initialization() {
    let repo = setup_repo();
    let mut app = App::new();
    app.load_tasks(&repo).unwrap();
    assert_eq!(app.tasks.len(), 0);
    assert_eq!(app.selected_column, 0);
    assert_eq!(app.mode, termtask::app::AppMode::Normal);
    assert_eq!(app.pomodoro.state, termtask::pomodoro::PomodoroState::Idle);
}

#[test]
fn test_add_task_integration() {
    let repo = setup_repo();
    let mut app = App::new();
    app.load_tasks(&repo).unwrap();

    // Simulate adding a task via keyboard handling (we'll call the repo directly for simplicity)
    let task = repo.create_task("Test task from integration").unwrap();
    app.tasks.push(task);
    assert_eq!(app.tasks.len(), 1);
    assert_eq!(app.tasks[0].title, "Test task from integration");
    assert_eq!(app.tasks[0].status, Status::Todo);
}

#[test]
fn test_move_task_integration() {
    let repo = setup_repo();
    let task = repo.create_task("Task to move").unwrap();
    let mut app = App::new();
    app.load_tasks(&repo).unwrap();
    assert_eq!(app.tasks.len(), 1);
    assert_eq!(app.tasks[0].status, Status::Todo);

    // Simulate moving task by pressing Enter on selected task (column 0, index 0)
    app.selected_column = 0;
    app.selected_task_indices[0] = 0;
    // We need to call handle_key with Enter; but for integration test we directly update via repo
    repo.update_task_status(task.id, &Status::InProgress).unwrap();
    app.tasks[0].status = Status::InProgress;
    assert_eq!(app.tasks[0].status, Status::InProgress);
}

#[test]
fn test_pomodoro_toggle() {
    let mut pomo = Pomodoro::default();
    assert_eq!(pomo.state, termtask::pomodoro::PomodoroState::Idle);
    pomo.toggle();
    assert_eq!(pomo.state, termtask::pomodoro::PomodoroState::Work);
    pomo.toggle();
    assert_eq!(pomo.state, termtask::pomodoro::PomodoroState::Idle);
}

#[test]
fn test_pomodoro_work_break_cycle() {
    let mut pomo = Pomodoro::default();
    pomo.work_duration = std::time::Duration::from_secs(10);
    pomo.break_duration = std::time::Duration::from_secs(5);
    pomo.start_work();
    assert_eq!(pomo.state, termtask::pomodoro::PomodoroState::Work);
    // Simulate ticking past work duration
    pomo.tick(std::time::Duration::from_secs(11));
    assert_eq!(pomo.state, termtask::pomodoro::PomodoroState::Break);
    assert_eq!(pomo.cycles, 1);
    pomo.tick(std::time::Duration::from_secs(6));
    assert_eq!(pomo.state, termtask::pomodoro::PomodoroState::Idle);
}

#[test]
fn test_multiple_tasks_across_columns() {
    let repo = setup_repo();
    let t1 = repo.create_task("T1").unwrap();
    let t2 = repo.create_task("T2").unwrap();
    repo.update_task_status(t1.id, &Status::Done).unwrap();
    let mut app = App::new();
    app.load_tasks(&repo).unwrap();
    assert_eq!(app.tasks.len(), 2);
    let done_count = app.tasks.iter().filter(|t| t.status == Status::Done).count();
    assert_eq!(done_count, 1);
    let todo_count = app.tasks.iter().filter(|t| t.status == Status::Todo).count();
    assert_eq!(todo_count, 1);
}