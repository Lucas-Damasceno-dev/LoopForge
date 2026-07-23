# CLI Reference

## Usage

```bash
loopforge [command] [options] [directory]
```

---

## Global Options

| Option | Description |
|---|---|
| `-V, --version` | Display version number (5.0.0) |
| `-h, --help` | Display help for command |

---

## Commands

### `run`

Executa o ciclo completo do Loop Engine.

```bash
loopforge run [directory] [options]
```

**Options:**
| Option | Description |
|---|---|
| `--create-pr` | Cria automaticamente um PR no GitHub após sucesso |
| `--review` | Modo de revisão interativa que exibe diff e solicita confirmação antes de criar PR |
| `--auto` | Modo automatizado sem confirmação interativa (headless) |
| `-w, --watch` | Re-executa o ciclo automaticamente sempre que arquivos `.ts` ou arquivos de configuração (`.loopforge.json`/`.yml`) forem alterados |
| `--format <format>` | Formato de saída no terminal: `text` (padrão) ou `json` |

---

### `generate-tests`

Gera suítes de teste unitário multi-stack (Vitest para Node.js, pytest para Python e cargo test para Rust).

```bash
loopforge generate-tests [directory] [options]
```

**Options:**
| Option | Description |
|---|---|
| `--dry-run` | Simula a criação de testes exibindo a lista e o diff sem gravar arquivos |
| `--format <format>` | Formato de saída: `text` ou `json` |

---

### `workspace`

Orquestra loops em lote através de múltiplos projetos.

```bash
loopforge workspace [workspaceFile] [directory] [options]
```

**Options:**
| Option | Description |
|---|---|
| `--parallel` | Executa loops nos projetos do workspace em paralelo via pool concorrente |
| `-c, --concurrency <number>` | Limite de concorrência simultânea para o modo paralelo (padrão: 3) |
| `--format <format>` | Formato de saída: `text` ou `json` |

---

### `audit`

Scanner de segurança e code smells integrado com capacidade de auto-correção.

```bash
loopforge audit [directory] [options]
```

**Options:**
| Option | Description |
|---|---|
| `--fix` | Aplica auto-correção automática para segredos expostos (movendo para `.env`) e chamadas de `eval()` (substituindo por `JSON.parse()`) |
| `--format <format>` | Formato de saída: `text` ou `json` |

---

### `ui`

Inicia o Web Dashboard local com histórico SQLite e visualização gráfica de diffs e WebSocket em tempo real.

```bash
loopforge ui [directory] [options]
```

**Options:**
| Option | Description |
|---|---|
| `-p, --port <port>` | Porta do servidor HTTP (padrão: `3000`) |

---

### `release`

Gera notas de lançamento semânticas e atualiza o `CHANGELOG.md` do projeto.

```bash
loopforge release [version] [directory]
```
