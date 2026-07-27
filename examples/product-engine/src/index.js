export class TaskWorkflowEngine {
  constructor() {
    this.tasks = [];
    this.nextId = 1;
  }

  addTask(title, priority = "medium") {
    if (!title || typeof title !== "string") {
      throw new Error("Task title must be a non-empty string");
    }
    const validPriorities = ["low", "medium", "high", "critical"];
    if (!validPriorities.includes(priority)) {
      throw new Error(`Invalid priority level: ${priority}`);
    }
    const task = {
      id: this.nextId++,
      title: title.trim(),
      priority,
      status: "pending",
      createdAt: new Date().toISOString(),
      completedAt: null
    };
    this.tasks.push(task);
    return task;
  }

  completeTask(id) {
    const task = this.tasks.find((t) => t.id === id);
    if (!task) {
      throw new Error(`Task with ID ${id} not found`);
    }
    task.status = "completed";
    task.completedAt = new Date().toISOString();
    return task;
  }

  listTasks(statusFilter) {
    if (!statusFilter) return [...this.tasks];
    return this.tasks.filter((t) => t.status === statusFilter);
  }

  getSummary() {
    const total = this.tasks.length;
    const completed = this.tasks.filter((t) => t.status === "completed").length;
    const pending = total - completed;
    return { total, completed, pending };
  }
}
