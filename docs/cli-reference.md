# Referência da CLI (`lf` / `loopforge`)

Todos os 16 comandos registrados em `src/lf/cli/main.py`:

| Comando | Sintaxe | Descrição |
|---|---|---|
| `lf run` | `lf run [--idea] [--stack] [--pr] [--mock] [-i] [--review-mode] [--notify] [--webhook-url] [--resume] [--mvp] [--advanced] [--wizard] [--report-cost]` | Executa o pipeline autônomo dos agentes. |
| `lf serve` | `lf serve [--host 127.0.0.1] [--port 8000] [--reload] [--no-ui]` | Inicia servidor REST API + WebSockets + Dashboard UI. |
| `lf benchmark` | `lf benchmark [--limit <N>] [--runs <N>] [--mock/--no-mock] [--storage-dir <path>]` | Executa suíte de benchmarks curados e calcula rating ELO. |
| `lf resume` | `lf resume [--project-id <id>] [--task-id <id>] [--list]` | Retoma pipeline interrompido de checkpoint (ou lista checkpoints). |
| `lf diff` | `lf diff [--project-id <id>] [--target-dir <path>]` | Exibe diffs de código entre retentativas do Developer. |
| `lf explore` | `lf explore [--db-path <path>]` | Navega interativamente por artefatos e relatórios. |
| `lf pr` | `lf pr [--dir <path>] [--idea <título>]` | Commit + Pull Request via GitHub CLI. |
| `lf init` | `lf init [--name] [--stack] [--framework] [--llm-provider] [--llm-model] [--budget]` | Inicializa projeto LoopForge (.loopforge.json). |
| `lf plan` | `lf plan [--vision/-v] [--mode/-m full\|fast] [--interactive/--no-interactive]` | Gera plano de execução com Spec Review Gate. |
| `lf status` | `lf status` | Exibe status do projeto e telemetria de tarefas. |
| `lf release` | `lf release [versão] [--dry-run]` | Gera changelog e release notes (git log da última tag → HEAD; versão explícita ou patch bump; sem tag usa 0.1.0). |
| `lf completion` | `lf completion [--shell bash\|zsh\|fish]` | Exibe instruções/script de shell completion. |
| `lf generate-tests` | `lf generate-tests [diretório] [--stack python\|node] [--dry-run]` | Gera suítes de teste baseline para módulos sem cobertura (node usa vitest). |
| `lf audit` | `lf audit [diretório] [--fix] [--format text\|json]` | Auditoria completa do pipeline. |
| `lf export` | `lf export [--dir/-d <path>] [--output/-o <arquivo>] [--format zip\|json]` | Exporta artefatos gerados (ZIP por padrão). |
| `lf studio` | `lf studio [--duration <s>] [--db-path <path>]` | Visualizador TUI de telemetria em tempo real (lê `.loopforge/telemetry.sqlite`; teclas `R` refresh, `Q` sair). |

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
| `--resume` | Retoma pipeline pelo ID da tarefa (`--resume <task_id>`) |
| `--mvp` | Modo MVP: escopo enxuto, prototipagem rápida |
| `--advanced` | Modo Avançado: escopo completo, múltiplos módulos |
| `--wizard` | Força wizard interativo de inicialização |
| `--report-cost` | Imprime relatório de custo real por nó, cache hit rate e retries consumidos |

---

## Flags Globais

- `--help`: Exibe ajuda do comando
- `--version`: Exibe versão do LoopForge
