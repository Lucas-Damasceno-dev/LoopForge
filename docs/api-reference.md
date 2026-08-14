# REST & WebSockets API Reference

O servidor REST API e os WebSockets do LoopForge fornecem endpoints para gerenciamento de execuções de pipeline e transmissão de eventos ao vivo em tempo real.

---

## Autenticação

A autenticação é opcional e configurada via `APISettings`. Dois métodos suportados:

- **X-API-Key**: Header `X-API-Key` no request
- **HTTP Basic**: Username ou password contendo a chave

WebSockets validam via query parameter: `ws://host/ws/streaming?token=<api_key>`

---

## Endpoints REST API

### Sistema & Interface
- `GET /` — Serve a Dashboard Web UI (Glassmorphic)
- `GET /dashboard` — Serve a Dashboard Web UI
- `GET /health` — Verifica status da API

### Execuções (`/api/v1/runs` — canônico; `/api/runs` — alias legado)

> **Padrão M-18**: cada rota canônica `/api/v1/runs/...` tem um alias legado `/api/runs/...` (mesma implementação, header `X-Legacy`). Os exemplos abaixo usam o prefixo legado por compatibilidade.

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/v1/runs` | Cria nova execução (`queued`) e dispara pipeline em background |
| `GET` | `/api/v1/runs` | Lista execuções com paginação (`?skip=0&limit=20`, máx. 100) |
| `GET` | `/api/v1/runs/queue` | Estado da fila E3 (runs ativas + FIFO de `queued`) |
| `GET` | `/api/v1/runs/{id}` | Retorna detalhes de uma execução (inclui `degraded`) |
| `PATCH` | `/api/v1/runs/{id}` | Atualiza status/campos da execução |
| `DELETE` | `/api/v1/runs/{id}` | Remove registro da execução |
| `POST` | `/api/v1/runs/{id}/execute` | Dispara execução assíncrona em background |
| `POST` | `/api/v1/runs/{id}/resume` | Retoma execução de checkpoint |
| `GET` | `/api/v1/runs/{id}/cost` | Custo estimado por nó da run (tabela `llm_costs`) |
| `POST` | `/api/v1/runs/{id}/cost/override` | Override de budget para a run |

**Exemplo de criação de run:**
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-key" \
  -d '{"idea": "API REST em Java", "stack": "java", "routing_mode": "full"}'
```

**Resposta:**
```json
{
  "id": "uuid",
  "idea": "API REST em Java",
  "stack": "java",
  "status": "queued",
  "current_node": null,
  "logs": null,
  "duration_seconds": 0.0,
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:00"
}
```

### Human-in-the-Loop (`/api/runs/{id}/decide`)
| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/v1/runs/{id}/decide` | Registra decisão humana (approve/retry/adjust_prompt/adjust_state/abort) |
| `GET` | `/api/v1/runs/{id}/decisions` | Lista histórico de decisões HITL |

O payload aceita `gate_node`, `action`, `feedback_category` (bug/style/missing_feature/general), `feedback_message` e `state_patch` (dict aplicado ao checkpoint quando `action=adjust_state`).

**Exemplo de decisão HITL:**
```bash
curl -X POST http://localhost:8000/api/runs/{id}/decide \
  -H "Content-Type: application/json" \
  -d '{"gate_node": "developer", "action": "approve", "feedback_message": "LGTM"}'
```

### Trilogia Agentic
| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/genome` | Metadados do Codebase Genome (AST, bus factor) |
| `GET` | `/api/registry` | Contratos de interface e breaking changes |
| `GET` | `/api/retro` | Histórico de sessões e recomendações |

### Routers adicionais (`/api/v1/...`, autenticados)

| Prefixo | Descrição |
|---|---|
| `/api/v1/trajectories` | Checkpoints LangGraph: listar, diff, export, import, fork |
| `/api/v1/mcp` | Servidores MCP e execução de tools (`/servers`, `/servers/{name}/tools`) |
| `/api/v1/providers` | Provedores LLM configurados |
| `/api/v1/config` | Configuração de runtime |
| `/api/v1/memory` | CRUD de lessons (memória persistente) |
| `/api/v1/evals` | Avaliações/benchmarks |
| `/api/v1/git` | Operações git (checkpoint, PR, sandbox) |
| `/api/v1/prompts` | Prompts registrados |
| `/api/v1/artifacts` | Artefatos gerados |
| `/api/v1/terminal` | Terminal remoto |
| `/api/v1/ast` | Análise AST de codebases |
| `/api/v1/coverage` | Relatórios de cobertura |
| `/api/v1/docker` | Geração de Dockerfile/CI |

---

## CORS

Configurado via `CORSMiddleware` com permissão total:
- `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`
- Custom header: `X-Process-Time` com duração do request

---

## WebSockets Streaming

### Conexões
- `WS /ws/streaming` — Stream global de eventos de pipeline
- `WS /ws/runs/{run_id}` — Canal dedicado por run

### Eventos emitidos (broadcast)

Envelope: `{seq, event, run_id, timestamp, payload}` (journal persistido na tabela `events` de `telemetry.sqlite`).

| Evento | Descrição |
|---|---|
| `connected` | Confirmação de conexão |
| `run_created` | Nova run criada |
| `run_updated` | Atualização de run |
| `pipeline_started` | Pipeline iniciou execução |
| `node_execution` | Nó iniciou/finalizou execução |
| `pipeline_finished` | Pipeline concluída (com status e duração) |
| `pipeline_failed` | Pipeline falhou |
| `pipeline_error` | Erro na execução |
| `pipeline_resumed` | Pipeline retomada de checkpoint |
| `hitl_gate_reached` | Gate HITL aguardando decisão |
| `human_decision_submitted` | Decisão HITL registrada |
| `human_decision_expired` | Decisão HITL expirou (timeout) |
| `token_delta` | Stream de tokens do LLM |
| `circuit_breaker_changed` | Estado do CircuitBreaker mudou |

### Heartbeat
O cliente pode enviar `{"type": "ping"}` para receber `{"type": "pong"}` como keep-alive.
