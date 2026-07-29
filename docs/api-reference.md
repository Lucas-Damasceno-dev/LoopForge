# REST & WebSockets API Reference

O servidor REST API e os WebSockets do LoopForge fornecem endpoints para gerenciamento de execuções de pipeline e transmissão de eventos ao vivo em tempo real.

---

## Endpoints REST API

### Sistema & Interface
- `GET /health`: Verifica o status e disponibilidade da API.
- `GET /dashboard`: Serve a Dashboard Web UI interativa.

### Execuções (`/api/runs`)
- `POST /api/runs`: Cria uma nova execução de pipeline no banco de dados.
- `GET /api/runs`: Lista todas as execuções de pipeline cadastradas.
- `GET /api/runs/{id}`: Retorna detalhes e estado de uma execução específica.
- `PATCH /api/runs/{id}`: Atualiza parâmetros ou status de uma execução.
- `DELETE /api/runs/{id}`: Remove o registro da execução.
- `POST /api/runs/{id}/execute`: Dispara a execução assíncrona em segundo plano via corrotina com sessão de banco de dados isolada.
- `POST /api/runs/{id}/resume`: Retoma a execução a partir do checkpoint gravado.

---

## WebSockets Streaming

- `WS /ws/streaming`: Stream universal em tempo real de eventos de execução de nós (`cpo`, `pm`, `tech_lead`, `developer`, `qa`, `parallel_audit`).
- `WS /ws/runs/{run_id}`: Canal dedicado de streaming para uma sessão/run específica.
