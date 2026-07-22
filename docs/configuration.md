# Configuration

O LoopForge é configurado via arquivo `.loopforge.json` na raiz do projeto. O schema é validado com **Zod** em runtime.

---

## Schema Completo

```typescript
interface LoopForgeConfig {
  name: string;                        // Nome do projeto
  version: string;                     // Versão do projeto
  strategy: "fixed" | "creator";       // Estratégia de loop
  skills?: SkillsConfig;
  harness?: HarnessConfig;
  guardrails?: GuardrailsConfig;
  memory?: MemoryConfig;
  provider?: ProviderConfig;
  sandbox?: SandboxConfig;
}
```

---

## Campos

### `name`
- **Tipo:** `string`
- **Obrigatório:** Sim
- **Descrição:** Nome do projeto para identificação nos ciclos e relatórios.

---

### `version`
- **Tipo:** `string`
- **Obrigatório:** Sim
- **Descrição:** Versão do projeto.

---

### `strategy`
- **Tipo:** `"fixed" | "creator"`
- **Obrigatório:** Sim
- **Padrão:** `"creator"`
- **Descrição:** Estratégia de execução do loop:
  - `fixed`: Loop com iterações estritas, sem desvios
  - `creator`: Estratégia criativa, permite adaptações no ciclo

---

### `skills`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `directory` | `string` | `".loopforge/skills"` | Diretório dos arquivos de skill |
| `activeSkills` | `string[]` | `[]` | Lista de skills ativas para o ciclo |

**Exemplo:**
```json
"skills": {
  "directory": ".loopforge/skills",
  "activeSkills": ["clean-code", "testing-rules"]
}
```

---

### `harness`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `runners` | `HarnessRunnerConfig[]` | — | Lista de runners do harness |

**`HarnessRunnerConfig`:**

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `name` | `string` | — | Nome do runner (ex: "Unit Tests") |
| `type` | `"unit" | "linter" | "typecheck" | "e2e" | "custom"` | — | Tipo de runner para parser |
| `command` | `string` | — | Comando a ser executado |
| `timeoutMs` | `number` | `60000` | Timeout em milissegundos |

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
      "type": "typecheck",
      "command": "npm run check",
      "timeoutMs": 30000
    },
    {
      "name": "Linter",
      "type": "linter",
      "command": "npm run lint",
      "timeoutMs": 30000
    }
  ]
}
```

---

### `guardrails`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `maxIterations` | `number` | `10` | Número máximo de iterações do loop |
| `maxConsecutiveFailures` | `number` | `3` | Falhas consecutivas antes do circuit breaker |
| `stopOnSuccess` | `boolean` | `true` | Para o loop na primeira iteração bem-sucedida |
| `allowGitRollback` | `boolean` | `true` | Permite rollback automático via git |

**Exemplo:**
```json
"guardrails": {
  "maxIterations": 10,
  "maxConsecutiveFailures": 3,
  "stopOnSuccess": true,
  "allowGitRollback": true
}
```

---

### `memory`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `lessonsFile` | `string` | `".loopforge/lessons.md"` | Arquivo de lições aprendidas |
| `handoffFile` | `string` | `".loopforge/handoff.md"` | Arquivo de instruções de transição |
| `autoUpdateLessons` | `boolean` | `true` | Atualiza lessons.md automaticamente |

**Exemplo:**
```json
"memory": {
  "lessonsFile": ".loopforge/lessons.md",
  "handoffFile": ".loopforge/handoff.md",
  "autoUpdateLessons": true
}
```

---

### `provider`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `name` | `string` | `"opencode"` | Nome do provedor LLM |
| `model` | `string` | `"deepseek-v3"` | Modelo principal |
| `enableModelFallback` | `boolean` | `true` | Ativa fallback automático |
| `fallbackModel` | `string` | `"anthropic/claude-3-5-sonnet"` | Modelo de fallback |
| `fallbackFailureThreshold` | `number` | `2` | Falhas consecutivas para ativar fallback |

**Exemplo:**
```json
"provider": {
  "name": "opencode",
  "model": "deepseek-v3",
  "enableModelFallback": true,
  "fallbackModel": "anthropic/claude-3-5-sonnet",
  "fallbackFailureThreshold": 2
}
```

---

### `sandbox`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `enableBranchSandbox` | `boolean` | `true` | Isola mudanças em branch separada |
| `branchPrefix` | `string` | `"loopforge/task-"` | Prefixo da branch de sandbox |

**Exemplo:**
```json
"sandbox": {
  "enableBranchSandbox": true,
  "branchPrefix": "loopforge/task-"
}
```

---

## Configuração Mínima

```json
{
  "name": "Meu Projeto",
  "version": "1.0.0",
  "strategy": "creator"
}
```

Todos os outros campos usam valores padrão.

---

## Configuração Completa (com defaults explícitos)

```json
{
  "name": "Meu Projeto",
  "version": "1.0.0",
  "strategy": "creator",
  "skills": {
    "directory": ".loopforge/skills",
    "activeSkills": []
  },
  "harness": {
    "runners": [
      {
        "name": "Unit Tests",
        "type": "unit",
        "command": "npm test",
        "timeoutMs": 60000
      }
    ]
  },
  "guardrails": {
    "maxIterations": 10,
    "maxConsecutiveFailures": 3,
    "stopOnSuccess": true,
    "allowGitRollback": true
  },
  "memory": {
    "lessonsFile": ".loopforge/lessons.md",
    "handoffFile": ".loopforge/handoff.md",
    "autoUpdateLessons": true
  },
  "provider": {
    "name": "opencode",
    "model": "deepseek-v3",
    "enableModelFallback": true,
    "fallbackModel": "anthropic/claude-3-5-sonnet",
    "fallbackFailureThreshold": 2
  },
  "sandbox": {
    "enableBranchSandbox": true,
    "branchPrefix": "loopforge/task-"
  }
}
```
