# Configuration

O LoopForge é configurado via arquivo `.loopforge.json` na raiz do projeto. O schema é validado com **Zod** em runtime.

---

## Schema Completo

```typescript
interface LoopForgeConfig {
  projectName: string;                  // Nome do projeto
  version?: string;                     // Versão do projeto
  harness: HarnessConfig;
  memory?: MemoryConfig;
  guardrails?: GuardrailsConfig;
  llm?: LLMConfig;
}
```

---

## Campos

### `projectName`
- **Tipo:** `string`
- **Obrigatório:** Sim
- **Descrição:** Nome do projeto para identificação nos ciclos e relatórios.

---

### `version`
- **Tipo:** `string`
- **Obrigatório:** Não
- **Padrão:** `"3.0.0"`
- **Descrição:** Versão do projeto.

---

### `harness`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `runners` | `RunnerConfig[]` | — | Lista de runners do harness (mínimo 1) |
| `parallel` | `boolean` | `true` | Executa runners simultaneamente via Promise.all |
| `stopOnFirstFailure` | `boolean` | `false` | Interrompe execução ao primeiro runner que falhar |

**`RunnerConfig`:**

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `name` | `string` | — | Nome do runner (ex: "Unit Tests") |
| `type` | `"unit" \| "linter" \| "e2e" \| "custom"` | — | Tipo de runner para parser |
| `command` | `string` | — | Comando a ser executado |
| `timeoutMs` | `number` | `60000` | Timeout em milissegundos |
| `enabled` | `boolean` | `true` | Habilita/desabilita o runner sem removê-lo |

**Exemplo:**
```json
"harness": {
  "runners": [
    {
      "name": "Unit Tests",
      "type": "unit",
      "command": "npm test",
      "timeoutMs": 60000
    },
    {
      "name": "TypeScript Check",
      "type": "custom",
      "command": "npm run check",
      "timeoutMs": 30000
    },
    {
      "name": "Linter",
      "type": "linter",
      "command": "npm run lint",
      "timeoutMs": 30000,
      "enabled": false
    }
  ],
  "parallel": true,
  "stopOnFirstFailure": false
}
```

---

### `guardrails`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `maxConsecutiveFailures` | `number` | `3` | Falhas consecutivas antes do circuit breaker abrir |
| `maxTotalIterations` | `number` | `10` | Número máximo de iterações totais do loop |
| `maxBudgetUsd` | `number` | `5.0` | Orçamento máximo em dólar — trava financeira que interrompe o loop |
| `requireCleanGit` | `boolean` | `true` | Exige repositório limpo (sem mudanças não commitadas) para iniciar |

**Exemplo:**
```json
"guardrails": {
  "maxConsecutiveFailures": 3,
  "maxTotalIterations": 10,
  "maxBudgetUsd": 5.0,
  "requireCleanGit": true
}
```

---

### `memory`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `lessonsFile` | `string` | `".loopforge/lessons.md"` | Arquivo de lições aprendidas |
| `handoffFile` | `string` | `".loopforge/handoff.md"` | Arquivo de instruções de transição (com git diff stat) |
| `maxLessonsPrompt` | `number` | `5` | Máximo de lições a incluir no prompt do LLM |

**Exemplo:**
```json
"memory": {
  "lessonsFile": ".loopforge/lessons.md",
  "handoffFile": ".loopforge/handoff.md",
  "maxLessonsPrompt": 5
}
```

---

### `llm`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `provider` | `"opencode" \| "ollama" \| "openai" \| "anthropic" \| "custom"` | `"opencode"` | Provedor LLM |
| `model` | `string` | `"deepseek-v3"` | Modelo principal |
| `fallbackModel` | `string` | `"anthropic/claude-3-5-sonnet"` | Modelo de fallback |
| `baseUrl` | `string` | `"http://localhost:11434"` | URL base (usado pelo provedor ollama) |
| `temperature` | `number` | `0.2` | Temperatura do modelo (0.0 a 1.0) |

**Exemplo:**
```json
"llm": {
  "provider": "opencode",
  "model": "deepseek-v3",
  "fallbackModel": "anthropic/claude-3-5-sonnet",
  "temperature": 0.2
}
```

**Exemplo com Ollama (local, offline):**
```json
"llm": {
  "provider": "ollama",
  "baseUrl": "http://localhost:11434",
  "temperature": 0.1
}
```

---

## Configuração Mínima

```json
{
  "projectName": "Meu Projeto",
  "version": "1.0.0",
  "harness": {
    "runners": [
      { "name": "Unit Tests", "type": "unit", "command": "npm test" }
    ]
  }
}
```

---

## Configuração Completa (com defaults explícitos)

```json
{
  "projectName": "Meu Projeto",
  "version": "1.0.0",
  "harness": {
    "runners": [
      {
        "name": "Unit Tests",
        "type": "unit",
        "command": "npm test",
        "timeoutMs": 60000,
        "enabled": true
      }
    ],
    "parallel": true,
    "stopOnFirstFailure": false
  },
  "guardrails": {
    "maxConsecutiveFailures": 3,
    "maxTotalIterations": 10,
    "maxBudgetUsd": 5.0,
    "requireCleanGit": true
  },
  "memory": {
    "lessonsFile": ".loopforge/lessons.md",
    "handoffFile": ".loopforge/handoff.md",
    "maxLessonsPrompt": 5
  },
  "llm": {
    "provider": "opencode",
    "model": "deepseek-v3",
    "fallbackModel": "anthropic/claude-3-5-sonnet",
    "baseUrl": "http://localhost:11434",
    "temperature": 0.2
  }
}
```
