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

### Execuções (`/api/runs`)
| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/runs` | Cria nova execução e dispara pipeline em background |
| `GET` | `/api/runs` | Lista execuções com paginação (`?skip=0&limit=20`) |
| `GET` | `/api/runs/{id}` | Retorna detalhes de uma execução |
| `PATCH` | `/api/runs/{id}` | Atualiza status/campos da execução |
| `DELETE` | `/api/runs/{id}` | Remove registro da execução |
| `POST` | `/api/runs/{id}/execute` | Dispara execução assíncrona em background |
| `POST` | `/api/runs/{id}/resume` | Retoma execução de checkpoint |

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
  "status": "pending",
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
| `POST` | `/api/runs/{id}/decide` | Registra decisão humana (approve/retry/adjust_prompt/abort) |
| `GET` | `/api/runs/{id}/decisions` | Lista histórico de decisões HITL |

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
| Evento | Descrição |
|---|---|
| `connected` | Confirmação de conexão |
| `run_created` | Nova run criada |
| `run_updated` | Atualização de run |
| `pipeline_started` | Pipeline iniciou execução |
| `node_execution` | Nó iniciou/finalizou execução |
| `pipeline_finished` | Pipeline concluída (com status e duração) |
| `pipeline_error` | Erro na execução |
| `human_decision_submitted` | Decisão HITL registrada |

### Heartbeat
O cliente pode enviar `{"type": "ping"}` para receber `{"type": "pong"}` como keep-alive.
