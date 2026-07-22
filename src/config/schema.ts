import { z } from "zod";

export const RunnerTypeSchema = z.enum(["unit", "linter", "typecheck", "e2e", "custom"]);
export type RunnerType = z.infer<typeof RunnerTypeSchema>;

export const HarnessRunnerConfigSchema = z.object({
  name: z.string(),
  type: RunnerTypeSchema,
  command: z.string(),
  timeoutMs: z.number().optional().default(60000),
});
export type HarnessRunnerConfig = z.infer<typeof HarnessRunnerConfigSchema>;

export const SkillsConfigSchema = z.object({
  directory: z.string().default(".loopforge/skills"),
  activeSkills: z.array(z.string()).default([]),
});
export type SkillsConfig = z.infer<typeof SkillsConfigSchema>;

export const GuardrailsConfigSchema = z.object({
  maxIterations: z.number().int().positive().default(10),
  maxConsecutiveFailures: z.number().int().positive().default(3),
  stopOnSuccess: z.boolean().default(true),
  allowGitRollback: z.boolean().default(true),
});
export type GuardrailsConfig = z.infer<typeof GuardrailsConfigSchema>;

export const MemoryConfigSchema = z.object({
  lessonsFile: z.string().default(".loopforge/lessons.md"),
  handoffFile: z.string().default(".loopforge/handoff.md"),
  autoUpdateLessons: z.boolean().default(true),
});
export type MemoryConfig = z.infer<typeof MemoryConfigSchema>;

export const ProviderConfigSchema = z.object({
  name: z.string().default("opencode"),
  model: z.string().default("deepseek-v3"),
  fallbackModel: z.string().default("anthropic/claude-3-5-sonnet"),
  enableModelFallback: z.boolean().default(true),
  fallbackFailureThreshold: z.number().int().positive().default(2),
});
export type ProviderConfig = z.infer<typeof ProviderConfigSchema>;

export const SandboxConfigSchema = z.object({
  enableBranchSandbox: z.boolean().default(true),
  branchPrefix: z.string().default("loopforge/task-"),
});
export type SandboxConfig = z.infer<typeof SandboxConfigSchema>;

export const LoopStrategySchema = z.enum(["fixed", "creator"]);
export type LoopStrategy = z.infer<typeof LoopStrategySchema>;

export const LoopForgeConfigSchema = z.object({
  name: z.string().default("LoopForge Project"),
  version: z.string().default("1.0.0"),
  strategy: LoopStrategySchema.default("creator"),
  provider: ProviderConfigSchema.default({}),
  sandbox: SandboxConfigSchema.default({}),
  skills: SkillsConfigSchema.default({}),
  harness: z.object({
    runners: z.array(HarnessRunnerConfigSchema).default([
      { name: "Unit Tests", type: "unit", command: "npm test", timeoutMs: 60000 },
      { name: "Linter & Typecheck", type: "typecheck", command: "npm run check", timeoutMs: 30000 },
    ]),
  }).default({}),
  guardrails: GuardrailsConfigSchema.default({}),
  memory: MemoryConfigSchema.default({}),
});

export type LoopForgeConfig = z.infer<typeof LoopForgeConfigSchema>;
