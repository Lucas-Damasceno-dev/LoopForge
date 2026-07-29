# Referência da CLI (`lf` / `loopforge`)

Centralização dos comandos essenciais da CLI do LoopForge v6:

| Comando | Sintaxe | Descrição |
|---|---|---|
| `lf run` | `lf run [--idea <txt>] [--stack <stack>] [--pr] [--mock] [-i/--interactive] [--resume <id>]` | Executa o pipeline autônomo dos agentes. A stack é decidida autonomamente pelo Tech Lead se `--stack` for omitido. |
| `lf serve` | `lf serve [--host 127.0.0.1] [--port 8000]` | Inicia o servidor REST API, transmissão via WebSockets e a Dashboard Web UI em tempo real. |
| `lf benchmark` | `lf benchmark [--runs <N>] [--mock/--no-mock]` | Executa a suíte de 10 problemas curados multi-stack e calcula a pontuação de rating ELO do pipeline. |
| `lf resume` | `lf resume --resume <session_id>` | Retoma um pipeline interrompido ou em aprovação a partir de checkpoints no LangGraph. |
| `lf diff` | `lf diff [--dir <path>]` | Exibe as alterações e diffs de código gerados entre retentativas do nó Developer. |
| `lf explore` | `lf explore [--dir <path>]` | Navega interativamente pelos artefatos gerados, especificações técnicas e relatórios do QA. |
| `lf pr` | `lf pr [--dir <path>] [--idea <txt>]` | Inicializa repositório Git no diretório, realiza commit das alterações e abre Pull Request via GitHub CLI (`gh`). |

---

## Flags Globais de `lf run`

- `--idea`: Descrição ou objetivo da funcionalidade.
- `--stack`: (Opcional) Override manual de tecnologia (`rust`, `java`, `python`, `go`, `javascript`). Se omitido, o Tech Lead decide.
- `--pr`: Executa `git init`, `git commit` e tenta abrir Pull Request no GitHub ao concluir a tarefa.
- `--mock`: Utiliza respostas simuladas rápidas para testes de integração offline sem chamadas a APIs pagas.
- `-i, --interactive`: Ativa aprovação humana (HITL) entre as transições dos nós.
- `--review-mode`: Pausa a execução no final antes de salvar as alterações em disco.
- `--notify`: Envia notificações desktop no sistema operacional quando o pipeline requer atenção ou finaliza.
