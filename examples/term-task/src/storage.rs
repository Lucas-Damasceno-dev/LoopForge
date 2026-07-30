use anyhow::{Context, Result};
use rusqlite::{params, Connection};

use crate::models::{Status, Task};

/// Repository trait for task persistence.
pub trait TaskRepository {
    fn create_task(&self, title: &str) -> Result<Task>;
    fn get_tasks_by_status(&self, status: &Status) -> Result<Vec<Task>>;
    fn update_task_status(&self, task_id: i64, new_status: &Status) -> Result<()>;
    fn get_all_tasks(&self) -> Result<Vec<Task>>;
}

/// SQLite implementation of TaskRepository.
pub struct SqliteRepository {
    conn: Connection,
}

impl SqliteRepository {
    pub fn new(path: &str) -> Result<Self> {
        let conn = Connection::open(path)
            .with_context(|| format!("Failed to open database at {}", path))?;
        let repo = SqliteRepository { conn };
        repo.run_migrations()?;
        Ok(repo)
    }

    pub fn new_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        let repo = SqliteRepository { conn };
        repo.run_migrations()?;
        Ok(repo)
    }

    fn run_migrations(&self) -> Result<()> {
        self.conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'Todo',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );"
        )?;
        Ok(())
    }
}

impl TaskRepository for SqliteRepository {
    fn create_task(&self, title: &str) -> Result<Task> {
        let now = chrono::Utc::now().to_rfc3339();
        self.conn.execute(
            "INSERT INTO tasks (title, status, created_at, updated_at) VALUES (?1, 'Todo', ?2, ?3)",
            params![title, now, now],
        )?;
        let id = self.conn.last_insert_rowid();
        Ok(Task {
            id,
            title: title.to_string(),
            status: Status::Todo,
            created_at: now.clone(),
            updated_at: now,
        })
    }

    fn get_tasks_by_status(&self, status: &Status) -> Result<Vec<Task>> {
        let status_str = match status {
            Status::Todo => "Todo",
            Status::InProgress => "InProgress",
            Status::Done => "Done",
        };
        let mut stmt = self.conn.prepare(
            "SELECT id, title, status, created_at, updated_at FROM tasks WHERE status = ?1 ORDER BY created_at ASC"
        )?;
        let tasks = stmt.query_map(params![status_str], |row| {
            let status_str: String = row.get(2)?;
            let status = match status_str.as_str() {
                "Todo" => Status::Todo,
                "InProgress" => Status::InProgress,
                "Done" => Status::Done,
                _ => Status::Todo,
            };
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                status,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
            })
        })?.filter_map(|r| r.ok()).collect();
        Ok(tasks)
    }

    fn update_task_status(&self, task_id: i64, new_status: &Status) -> Result<()> {
        let status_str = match new_status {
            Status::Todo => "Todo",
            Status::InProgress => "InProgress",
            Status::Done => "Done",
        };
        let now = chrono::Utc::now().to_rfc3339();
        self.conn.execute(
            "UPDATE tasks SET status = ?1, updated_at = ?2 WHERE id = ?3",
            params![status_str, now, task_id],
        )?;
        Ok(())
    }

    fn get_all_tasks(&self) -> Result<Vec<Task>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, title, status, created_at, updated_at FROM tasks ORDER BY created_at ASC"
        )?;
        let tasks = stmt.query_map([], |row| {
            let status_str: String = row.get(2)?;
            let status = match status_str.as_str() {
                "Todo" => Status::Todo,
                "InProgress" => Status::InProgress,
                "Done" => Status::Done,
                _ => Status::Todo,
            };
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                status,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
            })
        })?.filter_map(|r| r.ok()).collect();
        Ok(tasks)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_and_retrieve_tasks() {
        let repo = SqliteRepository::new_in_memory().unwrap();
        let task = repo.create_task("Test task").unwrap();
        assert_eq!(task.title, "Test task");
        assert_eq!(task.status, Status::Todo);

        let todo_tasks = repo.get_tasks_by_status(&Status::Todo).unwrap();
        assert_eq!(todo_tasks.len(), 1);
        assert_eq!(todo_tasks[0].id, task.id);
    }

    #[test]
    fn test_update_status() {
        let repo = SqliteRepository::new_in_memory().unwrap();
        let task = repo.create_task("Move me").unwrap();
        repo.update_task_status(task.id, &Status::InProgress).unwrap();
        let in_progress = repo.get_tasks_by_status(&Status::InProgress).unwrap();
        assert_eq!(in_progress.len(), 1);
        let todo = repo.get_tasks_by_status(&Status::Todo).unwrap();
        assert_eq!(todo.len(), 0);
    }
}