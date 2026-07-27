import { test } from "node:test";
import assert from "node:assert/strict";
import { TaskWorkflowEngine } from "../src/index.js";

test("TaskWorkflowEngine - Add and complete tasks", () => {
  const engine = new TaskWorkflowEngine();
  const t1 = engine.addTask("Implement Roadmap Feature", "high");
  assert.equal(t1.id, 1);
  assert.equal(t1.status, "pending");

  const completed = engine.completeTask(1);
  assert.equal(completed.status, "completed");
  assert.ok(completed.completedAt);
});

test("TaskWorkflowEngine - List and Summary", () => {
  const engine = new TaskWorkflowEngine();
  engine.addTask("Design Architecture", "high");
  engine.addTask("Build Harness Runner", "medium");
  engine.completeTask(1);

  const pending = engine.listTasks("pending");
  assert.equal(pending.length, 1);
  assert.equal(pending[0].title, "Build Harness Runner");

  const summary = engine.getSummary();
  assert.equal(summary.total, 2);
  assert.equal(summary.completed, 1);
  assert.equal(summary.pending, 1);
});

test("TaskWorkflowEngine - Priority Validation", () => {
  const engine = new TaskWorkflowEngine();
  assert.throws(
    () => engine.addTask("Invalid Task", "ultra-high"),
    /Invalid priority level/
  );
});

