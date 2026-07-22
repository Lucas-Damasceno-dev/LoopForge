import { z } from "zod";

export const RunnerTypeSchema = z.enum(["unit", "linter", "e2e", "custom"]);
export type RunnerType = z.infer<typeof RunnerTypeSchema>;

export const RunnerConfigSchema = z.object({
  name: z.string(),
  type: RunnerTypeSchema,
  command: z.string(),
  timeoutMs: z.number().optional().default(60000),
  enabled: z.boolean().optional().default(true),
});
export type RunnerConfig = z.infer<typeof RunnerConfigSchema>;

export const HarnessConfigSchema = z.object({
  runners: z.array(RunnerConfigSchema).min(1),
  stopOnFirstFailure: z.boolean().optional().default(false),
  parallel: z.boolean().optional().default(true),
});
export type HarnessConfig = z.infer<typeof HarnessConfigSchema>;

export const MemoryConfigSchema = z.object({
  lessonsFile: z.string().optional().default(".loopforge/lessons.md"),
  handoffFile: z.string().optional().default(".loopforge/handoff.md"),
  maxLessonsPrompt: z.number().optional().default(5),
});
export type MemoryConfig = z.infer<typeof MemoryConfigSchema>;

export const GuardrailsConfigSchema = z.object({
  maxConsecutiveFailures: z.number().optional().default(3),
  maxTotalIterations: z.number().optional().default(10),
  maxBudgetUsd: z.number().optional().default(5.0),
  requireCleanGit: z.boolean().optional().default(true),
});
export type GuardrailsConfig = z.infer<typeof GuardrailsConfigSchema>;

export const LLMConfigSchema = z.object({
  provider: z.enum(["opencode", "ollama", "openai", "anthropic", "custom"]).optional().default("opencode"),
  model: z.string().optional().default("deepseek-v3"),
  fallbackModel: z.string().optional().default("anthropic/claude-3-5-sonnet"),
  baseUrl: z.string().optional().default("http://localhost:11434"),
  temperature: z.number().optional().default(0.2),
});
export type LLMConfig = z.infer<typeof LLMConfigSchema>;

export const LoopForgeConfigSchema = z.object({
  projectName: z.string(),
  version: z.string().optional().default("3.0.0"),
  harness: HarnessConfigSchema,
  memory: MemoryConfigSchema.optional().default({}),
  guardrails: GuardrailsConfigSchema.optional().default({}),
  llm: LLMConfigSchema.optional().default({}),
});
export type LoopForgeConfig = z.infer<typeof LoopForgeConfigSchema>;
