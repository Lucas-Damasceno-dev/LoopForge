use serde::{Deserialize, Serialize}; // optional, not used for now

#[derive(Debug, Clone, PartialEq)]
pub enum Status {
    Todo,
    InProgress,
    Done,
}

impl std::fmt::Display for Status {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Status::Todo => write!(f, "To Do"),
            Status::InProgress => write!(f, "In Progress"),
            Status::Done => write!(f, "Done"),
        }
    }
}

impl Status {
    pub fn next(&self) -> Self {
        match self {
            Status::Todo => Status::InProgress,
            Status::InProgress => Status::Done,
            Status::Done => Status::Todo,
        }
    }

    pub fn all() -> &'static [Status] {
        &[Status::Todo, Status::InProgress, Status::Done]
    }
}

#[derive(Debug, Clone)]
pub struct Task {
    pub id: i64,
    pub title: String,
    pub status: Status,
    pub created_at: String,
    pub updated_at: String,
}

impl Task {
    pub fn new(id: i64, title: String) -> Self {
        let now = chrono::Utc::now().to_rfc3339();
        Task {
            id,
            title,
            status: Status::Todo,
            created_at: now.clone(),
            updated_at: now,
        }
    }
}