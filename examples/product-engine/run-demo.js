import { TaskWorkflowEngine } from "./src/index.js";

console.log("🚀 Running Task Workflow Engine Product Demo...\n");

const engine = new TaskWorkflowEngine();

console.log("1. Creating Tasks...");
const task1 = engine.addTask("Setup LoopForge Harness", "high");
const task2 = engine.addTask("Configure Circuit Breaker & Guardrails", "high");
const task3 = engine.addTask("Deploy Web Dashboard", "medium");
console.log("   - Created Task 1:", task1);
console.log("   - Created Task 2:", task2);
console.log("   - Created Task 3:", task3);

console.log("\n2. Completing Task 1 & 2...");
engine.completeTask(1);
engine.completeTask(2);

console.log("\n3. Testing Priority Validation...");
try {
  engine.addTask("Invalid Task", "super-high");
} catch (err) {
  console.log("   ✔ Priority Validation Error caught successfully:", err.message);
}

console.log("\n4. Final Workflow Summary:");
console.log(engine.getSummary());

console.log("\n🎉 Product Execution Completed Successfully!");
