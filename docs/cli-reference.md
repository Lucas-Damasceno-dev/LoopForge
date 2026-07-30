# Referência da CLI (`lf` / `loopforge`)

Todos os 16 comandos registrados em `src/lf/cli/main.py`:

| Comando | Sintaxe | Descrição |
|---|---|---|
| `lf run` | `lf run [--idea] [--stack] [--pr] [--mock] [-i] [--review-mode] [--notify] [--webhook-url] [--resume] [--wizard]` | Executa o pipeline autônomo dos agentes. |
| `lf serve` | `lf serve [--host 127.0.0.1] [--port 8000]` | Inicia servidor REST API + WebSockets + Dashboard UI. |
| `lf benchmark` | `lf benchmark [--runs <N>] [--mock/--no-mock]` | Executa suíte de 10 benchmarks curados e calcula rating ELO. |
| `lf resume` | `lf resume --resume <session_id>` | Retoma pipeline interrompido de checkpoint. |
| `lf diff` | `lf diff [--dir <path>]` | Exibe diffs de código entre retentativas do Developer. |
| `lf explore` | `lf explore [--dir <path>]` | Navega interativamente por artefatos e relatórios. |
| `lf pr` | `lf pr [--dir <path>] [--idea]` | Commit + Pull Request via GitHub CLI. |
| `lf init` | `lf init [--project-id]` | Inicializa projeto LoopForge (.loopforge.json). |
| `lf plan` | `lf plan [--list] [--show]` | Gerencia planos de tarefas do pipeline. |
| `lf status` | `lf status [--task-id]` | Exibe status da execução atual. |
| `lf release` | `lf release --version <ver>` | Gera changelog e release notes. |
| `lf completion` | `lf completion <bash\|zsh\|fish>` | Gera script de shell completion. |
| `lf generate-tests` | `lf generate-tests --dir <path>` | Geração automática de testes via agente. |
| `lf audit` | `lf audit [--dir <path>]` | Auditoria completa do pipeline. |
| `lf export` | `lf export --dir <path> [--format]` | Exporta artefatos gerados. |
| `lf studio` | `lf studio [--port 3000]` | Interface web studio interativa. |

---

## Flags de `lf run`

| Flag | Descrição |
|---|---|
| `--idea` | Descrição ou objetivo da funcionalidade |
| `--stack` | Override manual de tecnologia (`rust`, `java`, `python`, `go`, `js`) |
| `--pr` | Cria commit e Pull Request no GitHub ao concluir |
| `--mock` | Usa respostas LLM simuladas (offline) |
| `-i, --interactive` | Ativa HITL (gates humano entre nós) |
| `--review-mode` | Pausa antes de salvar artefatos em disco |
| `--notify` | Notificações desktop (notify-send) |
| `--webhook-url` | URL de webhook Slack/Discord para notificações |
| `--resume` | Retoma pipeline pelo ID da tarefa |
| `--wizard` | Força wizard interativo de inicialização |

---

## Flags Globais

- `--help`: Exibe ajuda do comando
- `--version`: Exibe versão do LoopForge
