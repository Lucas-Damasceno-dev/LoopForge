# CLI Reference

## Usage

```bash
loopforge [command] [options] [directory]
```

---

## Global Options

| Option | Description |
|---|---|
| `-V, --version` | Display version number (3.0.0) |
| `-h, --help` | Display help for command |

---

## Commands

### `init`

Inicializa a configuração, memórias e templates de skills no repositório.

```bash
loopforge init [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `directory` | Target directory (default: current directory) |

**Options:**
| Option | Description |
|---|---|
| `--template <name>` | Skill template to install: `node-typescript`, `python-pytest`, `rust-cargo` |

**Creates:**
- `.loopforge.json` — Configuração do projeto
- `.loopforge/handoff.md` — Instruções de transição
- `.loopforge/lessons.md` — Lições aprendidas
- `.loopforge/skills/` — Diretório de skills (se template fornecida)

---

### `run`

Executa o ciclo completo do Loop Engine.

```bash
loopforge run [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `directory` | Target directory with `.loopforge.json` (default: current directory) |

**Options:**
| Option | Description |
|---|---|
| `--create-pr` | Create a GitHub PR automatically on success |

**Pipeline:**
1. Harness — Executa runners configurados
2. Parser — Analisa falhas
3. Memory — Carrega lessons/handoff
4. LLM — Envia contexto para o provedor
5. Sandbox — Isola mudanças em branch
6. Fallback — Escalona modelo se necessário
7. Checkpoint — Commita progresso
8. PR — (opcional) Cria pull request no GitHub

---

### `bootstrap`

Gera automaticamente uma suíte de testes baseline para o projeto.

```bash
loopforge bootstrap
```

**Alias:** `harness:bootstrap`

**Comportamento:**
- Analisa a estrutura do repositório
- Detecta linguagem e framework
- Gera sensores de qualidade
- Cria testes baseline para os módulos identificados

---

### `refactor`

Executa o motor de auto-refatoração com isolamento Git Sandbox.

```bash
loopforge refactor <rule>
```

**Arguments:**
| Argument | Description |
|---|---|
| `rule` | Regra de refatoração (ex: `"converter para ESM"`, `"extrair service layer"`) |

**Comportamento:**
- Analisa o código-fonte com base na regra fornecida
- Isola mudanças em branch dedicada
- Executa refatoração em lote
- Valida com o harness após modificações
- Commita ou reverte conforme resultado

---

### `workspace`

Orquestra loops em lote através de múltiplos projetos configurados no manifesto.

```bash
loopforge workspace [workspaceFile]
```

**Arguments:**
| Argument | Description |
|---|---|
| `workspaceFile` | Caminho para o manifesto `loopforge-workspace.json` (default: `loopforge-workspace.json` no diretório atual) |

**Comportamento:**
- Lê o manifesto com a lista de projetos
- Instancia o Loop Engine para cada projeto
- Coleta e exibe resultados agregados
- Ideal para monorepos e migrações em lote

---

### `audit`

Scanner de segurança e code smells integrado.

```bash
loopforge audit [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `directory` | Diretório a ser escaneado (default: diretório atual) |

**Detecta:**
- **Secrets expostos**: `sk-` (API keys), `AKIA` (AWS tokens), JWT
- **SQL Injection**: strings SQL concatenadas
- **Código inseguro**: `eval()` e similares

**Scanning:**
- Varre `.ts`, `.js`, `.py`, `.go` recursivamente
- Exibe vulnerabilidades por arquivo e linha

---

### `wizard`

Assistente interativo de configuração e onboarding para novos usuários.

```bash
loopforge wizard [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `directory` | Diretório alvo (default: diretório atual) |

**Pipeline:**
1. Inicializa `.loopforge.json` com template Node/TypeScript
2. Gera suíte de testes baseline via `bootstrap`
3. Exibe sumário final da configuração

---

### `replay`

Reproduz telemetria quadro-a-quadro de sessões passadas do Loop Engine.

```bash
loopforge replay <sessionId> [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `sessionId` | ID da sessão a ser reproduzida (obrigatório) |
| `directory` | Diretório do projeto (default: diretório atual) |

**Comportamento:**
- Carrega frames de `.loopforge/telemetry/{sessionId}.json`
- Reproduz em tempo real no terminal com delay de 300ms entre frames
- Exibe: timestamp, iteração, papel do agente, modelo, status do harness

---

### `ui`

Inicia o Web Dashboard local para visualização gráfica de relatórios.

```bash
loopforge ui [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `directory` | Project directory (default: current directory) |

**Options:**
| Option | Description |
|---|---|
| `-p, --port <port>` | Server port (default: `3000`) |

**Access:**
- `http://localhost:3000`

**Features:**
- Relatórios de execução do Loop Engine
- Histórico de ciclos
- Métricas de custo por execução
- Visualização de falhas e taxa de aprovação

---

### `ci:setup`

Gera pipeline de CI/CD nativo para GitHub Actions.

```bash
loopforge ci:setup
```

**Creates:**
- `.github/workflows/loopforge-ci.yml`

**Geração inclui:**
- Triggers: `push` e `pull_request` na branch principal
- Setup Node.js
- Instalação de dependências
- Execução do Loop Engine

---

### `status`

Exibe painel de status da configuração atual.

```bash
loopforge status [directory]
```

**Arguments:**
| Argument | Description |
|---|---|
| `directory` | Project directory (default: current directory) |

**Displays:**
- Configuração ativa (.loopforge.json)
- Provedor LLM configurado e modelo
- Skills ativas e templates disponíveis
- Estado das memórias (lessons/handoff)
- Runners do harness
- Configurações de guardrails

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error |
| `2` | Circuit breaker tripped |
| `3` | Harness failure |
| `4` | Git sandbox error |
