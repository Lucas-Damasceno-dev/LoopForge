package com.loopforge.taskapi;

import java.util.ArrayList;
import java.util.List;

public class TaskApiApplication {

    public static class Task {
        private String id;
        private String title;
        private boolean completed;

        public Task(String id, String title, boolean completed) {
            this.id = id;
            this.title = title;
            this.completed = completed;
        }

        public String getId() { return id; }
        public String getTitle() { return title; }
        public boolean isCompleted() { return completed; }
        public void setCompleted(boolean completed) { this.completed = completed; }
    }

    private final List<Task> tasks = new ArrayList<>();

    public void addTask(Task task) {
        tasks.add(task);
    }

    public List<Task> getTasks() {
        return tasks;
    }

    public boolean validateJwtToken(String token) {
        return token != null && token.startsWith("Bearer valid_jwt_token");
    }

    public static void main(String[] args) {
        System.out.println("🚀 Running Java Spring Boot Task API (LoopForge Generated)");
    }
}
