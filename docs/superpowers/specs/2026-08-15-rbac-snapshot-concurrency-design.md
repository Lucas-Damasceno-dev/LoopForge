# Design — RBAC na UI, Snapshot no create-run, Concurrency multi-worker

- **Data**: 2026-08-15
- **Escopo**: LoopForge (engine, `agentes/LoopForge`) + LoopForge ADE (SPA, `web/loopforge-ade/frontend`)
- **Status**: aprovado pelo usuário (brainstorming concluído)

## Contexto

Roadmap do usuário, 3 itens, ordem de implementação definida: **RBAC → snapshot → concurrency**.

| Fase | Problema atual |
|---|---|
| 1. RBAC na UI | Backend já tem RBAC (`auth.py`, roles viewer<runner<admin), mas SPA assume admin; `GET /api/v1/pipelines` CRUD não é admin-gated (runner pode criar/editar/deletar); SPA sem login |
| 2. Snapshot no create-run | `RunCreate` só tem `pipeline_id`; snapshot derivado server-side é informativo — UI não mostra nem edita antes de criar; `RunResponse` não expõe snapshot |
| 3. Concurrency | Fila `RunQueueState` 100% in-memory (pending/active/params/lock), event bus WS in-memory, rate limit in-memory — tudo process-local; `serve.py` sem `--workers`; compose sem Redis |

## Fase 1 — RBAC na UI

### Backend (`agentes/LoopForge`)

1. **Endpoint `GET /api/v1/auth/me`** → `{name: str, roles: list[str]}`. Usa `verify_authentication` (já cai em viewer na matrix) e retorna o `Principal` resolvido (auth.py:134-144).
2. **Matrix `_required_role`** (auth.py:66-102): adicionar regra admin:
   `p.startswith("/api/v1/pipelines")` + `m in ("POST","PUT","DELETE")` → `admin`. GET/HEAD permanecem viewer (default). Fecha o gap do S3 editor.

### Frontend (`web/loopforge-ade/frontend`)

3. **Auth store** (zustand): `{key, principal}` persistido em `localStorage`; `login(key)` → `GET /api/v1/auth/me` → salva principal; `logout()` limpa e redireciona `/login`.
4. **Fetch wrapper** (api client): injeta header `X-API-Key` quando `key` presente; resposta 401 → logout + redirect login; 403 → toast de permissão insuficiente.
5. **Tela de login** (`/login`): campo de API key; sem rota protegida sem principal.
6. **Role-aware UI**: helper `can(role)` (usa `Principal.has_role` equivalência: admin⊇runner⊇viewer) + hook `useAuth()`.
   - admin: tudo (settings, MCP, costs, editor de pipelines, delete)
   - runner: runs, prompts, memória; esconde settings/MCP/costs admin e delete
   - viewer: read-only — esconde criar run, resume/cancel, prompts write, memória write

## Fase 2 — Snapshot no create-run

### Backend

1. **`RunCreate`** (schemas.py:11) ganha `snapshot: dict | None = None` — override do snapshot do pipeline.
2. **`_create_run_impl`** (app.py:309): se `payload.snapshot` presente → valida via `validate_pipeline` (422 se inválido) → usa como snapshot; senão deriva do template (comportamento atual). Persistido em `PipelineRun.pipeline_snapshot`.
3. **`RunResponse`** (schemas.py:28) ganha `snapshot: dict | None = None` (aditivo).

### Frontend

4. **Modal de create-run**: ao selecionar pipeline → preview do snapshot (nome, descrição, DAG read-only via xyflow) → campos editáveis: params do run (idea, stack, model, routing_mode, interactive, mock_llm) + descrição do snapshot → POST `RunCreate` com `snapshot` override quando editado.
5. **Run detail**: exibe `snapshot` persistido.

## Fase 3 — Concurrency multi-worker (Redis)

### Backend

1. **Deps**: `redis` (async); `fakeredis` como dev-dep (testes sem infra). Atualizar `uv.lock` (`uv add`).
2. **Config** (env):
   - `LF_REDIS_URL` (default `redis://localhost:6379`)
   - `LF_QUEUE_BACKEND` (`memory` default — BC local; `redis` para multi-worker)
3. **`RunQueueState` → interface com 2 backends**:
   - `memory`: implementação atual (BC, testes existentes intocados)
   - `redis`:
     - pending: Redis LIST (FIFO)
     - active: Redis ZSET com lease/score timestamp; executor renova lease periodicamente (heartbeat); expiração só ocorre com worker morto → run volta a pending (crash de worker não trava run)
     - params: Redis HASH `lf:q:params:{run_id}` com TTL (ex. 24h)
     - **promoção global atômica**: script Lua — `SCARD(active) < max → RPOP pending → SADD/ZADD active`, retorna run_id+params
4. **Worker loop por processo**: cada worker escuta notificação (pub/sub `lf:notify`) → tenta promoção → vencedor executa `_run_pipeline` localmente; `finally` libera slot e re-notifica.
5. **Event bus**: journal já é SQLite (`event_seq` atômico, ok cross-process); broadcast WS cross-worker via pub/sub `lf:events` → cada worker repassa aos seus WS clients (ws_manager local permanece).
6. **Rate limit**: quando `LF_QUEUE_BACKEND=redis`, sliding window via ZSET Redis (global entre workers); senão mantém in-memory atual.
7. **Cancel cross-worker**: pub/sub `lf:cancel` → worker dono da task cancela localmente (run_tasks registry); fallback: flag Redis checada pelo worker loop.
8. **`serve.py`**: opção `--workers N`; `workers > 1` exige `LF_QUEUE_BACKEND=redis` (erro claro caso contrário); `--reload` + `--workers` inválido.
9. **`docker-compose.yml`**: serviço `redis:7` + env `LF_REDIS_URL` no app loopforge.

### Testes

- Backend: unit do backend redis via fakeredis (promoção global, lease/expiração, cancel, params TTL); rate limit redis; validação `--workers`.
- Frontend: vitest (auth store, role-gated render, modal snapshot); e2e Playwright (login → RBAC flow, create-run com snapshot).

## Validação (critérios de pronto)

- Engine: `pytest --cov=src/lf --cov-fail-under=75 tests/` + `ruff check --select E,F,W,I,N,UP,SIM src/lf tests` + `mypy src/lf`
- SPA: `npm run lint && npm run test && npm run build` (em `web/loopforge-ade/frontend`)
- E2E: `npm run test:e2e` (Playwright)
- Fase 1: `/auth/me` responde principal; pipelines CRUD bloqueado para runner (403); SPA login + UI role-aware (verificação manual + e2e)
- Fase 2: POST `/api/v1/runs` com `snapshot` override persiste e aparece no `RunResponse`; snapshot inválido → 422
- Fase 3: `lf serve --workers 2` com redis: fila global (2 runs ativas no total), WS broadcast cross-worker, cancel remoto, rate limit global

## Fora de escopo

- Auth no dashboard legacy `/dashboard` (Jinja) — SPA é o alvo
- JWT/sessões — keys estáticas do ade.yaml continuam sendo o mecanismo
- Snapshot editável de DAG completo (nós/arestas) no create-run — só params + descrição
- Rate limit Redis quando backend=memory (mantém in-memory)
