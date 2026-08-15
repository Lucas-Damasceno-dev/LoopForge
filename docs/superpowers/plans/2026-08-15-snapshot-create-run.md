# Snapshot no create-run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No create-run, mostrar o snapshot do pipeline antes de criar e permitir editar params/descrição; o override persiste no run (imutável pós-criação) e aparece no detail.

**Architecture:** `RunCreate` ganha `snapshot: dict | None` (override validado com `validate_pipeline`); `_create_run_impl` usa o override quando presente, senão deriva do template (comportamento atual). `RunResponse` expõe `snapshot`. Frontend: modal pré-criação no NewRunForm (preview do snapshot + params editáveis + descrição) e exibição do snapshot no RunInspector.

**Tech Stack:** Python FastAPI + SQLAlchemy (engine), React 19 + zustand + TanStack Query (SPA), Vitest + Playwright.

## Global Constraints

- Idioma: docs/comentários em PT, identificadores em EN.
- Backend: ruff `--select E,F,W,I,N,UP,SIM` (line-length 120), mypy `src/lf`, pytest `tests/` (coverage ≥75%).
- Frontend: `npm run lint && npm run test && npm run build` em `web/loopforge-ade/frontend`.
- Snapshot é IMUTÁVEL pós-criação (S3: `PipelineRun.pipeline_snapshot` models.py:46); template pode mudar/deletar depois — a execução usa sempre o snapshot do run.
- Campos aditivos de API: adicionar, nunca remover (SPA e API dependem dos atuais).
- RunCreate atual (schemas.py:11-18): `idea, stack, mock_llm, routing_mode, interactive, model, pipeline_id`. PipelineTemplate (models.py:101-119): `name, description, nodes, edges`.
- `validate_pipeline(pipeline: PipelineBase, known_agents) -> list[str]` (app.py:337; import local em pipelines.py:180).

---

### Task 1: Backend — `RunCreate.snapshot` + override em `_create_run_impl` + `RunResponse.snapshot`

**Files:**
- Modify: `agentes/LoopForge/src/lf/api/schemas.py` (RunCreate :11, RunResponse :28)
- Modify: `agentes/LoopForge/src/lf/api/app.py` (`_create_run_impl` :309-371)
- Test: `agentes/LoopForge/tests/test_api_snapshot.py` (novo, padrão test_api_queue.py)

**Interfaces:**
- Consumes: `RunCreate`/`RunResponse` (schemas.py), `PipelineBase` (pipelines.py:52), `validate_pipeline`, `PipelineTemplate` (models.py:101)
- Produces: `RunCreate.snapshot: dict | None = None`; `RunResponse.snapshot: dict | None = None`; `_create_run_impl` valida e persiste o override (422 se inválido)

- [ ] **Step 1: Testes que falham**

`tests/test_api_snapshot.py` (fixtures no padrão de test_api_queue.py: `LF_API_TEST=1`, `LF_API_REQUIRE_AUTH=false`, `init_db/close_db`, `create_app()` + `AsyncClient(ASGITransport)`):

```python
"""Snapshot no create-run (S3): override via RunCreate.snapshot.

Cobre: POST /runs com snapshot válido persiste no run; snapshot inválido
(ciclo) → 422; sem snapshot + pipeline_id → deriva do template (regressão);
RunResponse expõe snapshot.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

PIPELINE_BODY = {
    "name": "snap-pipeline",
    "description": "template",
    "nodes": [
        {"id": "n1", "type": "input", "agent_id": None, "config": {}},
        {"id": "n2", "type": "agent", "agent_id": None, "config": {}},
        {"id": "n3", "type": "output", "agent_id": None, "config": {}},
    ],
    "edges": [
        {"source": "n1", "target": "n2", "type": "sequential", "condition": None, "max_retries": 0},
        {"source": "n2", "target": "n3", "type": "sequential", "condition": None, "max_retries": 0},
    ],
}


@pytest_asyncio.fixture(autouse=True)
async def setup_snapshot_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


async def _create_pipeline(app, body: dict) -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/pipelines", json=body)
        assert r.status_code == 201, r.text
        return r.json()["id"]


@pytest.mark.asyncio
async def test_snapshot_override_persiste_no_run():
    app = create_app()
    pid = await _create_pipeline(app, PIPELINE_BODY)
    override = {**PIPELINE_BODY, "description": "editada pelo usuário"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={
                "idea": "com snapshot",
                "stack": "python",
                "mock_llm": True,
                "pipeline_id": pid,
                "snapshot": override,
            },
        )
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["snapshot"]["description"] == "editada pelo usuário"
        assert run["pipeline_id"] == pid
        # GET do run devolve o snapshot persistido
        r2 = await ac.get(f"/api/v1/runs/{run['id']}")
        assert r2.status_code == 200
        assert r2.json()["snapshot"]["description"] == "editada pelo usuário"


@pytest.mark.asyncio
async def test_snapshot_sem_pipeline_id():
    """Snapshot próprio sem template vinculado — run nasce com snapshot."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={"idea": "só snapshot", "stack": "python", "mock_llm": True, "snapshot": PIPELINE_BODY},
        )
        assert r.status_code == 201, r.text
        assert r.json()["snapshot"]["name"] == "snap-pipeline"


@pytest.mark.asyncio
async def test_snapshot_invalido_422():
    """Snapshot com ciclo → 422 (validação reutilizada do template)."""
    app = create_app()
    ciclico = {**PIPELINE_BODY, "edges": [
        {"source": "n1", "target": "n2", "type": "sequential", "condition": None, "max_retries": 0},
        {"source": "n2", "target": "n1", "type": "sequential", "condition": None, "max_retries": 0},
    ]}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={"idea": "ciclo", "stack": "python", "mock_llm": True, "snapshot": ciclico},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_sem_snapshot_deriva_template_regressao():
    """Regressão: sem snapshot + pipeline_id → snapshot do template."""
    app = create_app()
    pid = await _create_pipeline(app, PIPELINE_BODY)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={"idea": "sem override", "stack": "python", "mock_llm": True, "pipeline_id": pid},
        )
        assert r.status_code == 201, r.text
        assert r.json()["snapshot"]["description"] == "template"
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `pytest tests/test_api_snapshot.py -x`
Expected: FAIL (campo snapshot não existe)

- [ ] **Step 3: Implementar**

`schemas.py`:

```python
class RunCreate(BaseModel):
    idea: str = Field(..., description="Descrição da funcionalidade ou ideia")
    stack: str = Field("python", description="Stack de tecnologia")
    mock_llm: bool = Field(False, description="Usar modo LLM mock")
    routing_mode: RoutingMode = Field("full", description="Modo de roteamento: full ou fast")
    interactive: bool = Field(False, description="Pausar após nós para aprovação humana (HITL)")
    model: str | None = Field(None, description="Modelo LLM override para a run (vence env/config)")
    pipeline_id: str | None = Field(None, description="Pipeline a executar; ausente = montagem automática atual")
    # S3: override do snapshot do pipeline (válido no create). Ausente =
    # deriva do template (pipeline_id) ou montagem automática. Validação
    # semântica via validate_pipeline — 422 se inválido.
    snapshot: dict | None = Field(
        None,
        description="Snapshot do pipeline (name/description/nodes/edges) — override no create",
    )
```

`RunResponse` — adicionar campo aditivo (após `pipeline_name` :46):

```python
    # S3: snapshot imutável da run (pipeline_snapshot do PipelineRun) — a UI
    # mostra no detail o que foi executado de fato. Aditivo.
    # validation_alias: o ORM grava em `pipeline_snapshot`; RunResponse é
    # construído via model_validate(run) (from_attributes) — o alias garante
    # o mapeamento, mantendo o nome público `snapshot`.
    snapshot: dict | None = Field(default=None, validation_alias="pipeline_snapshot")
```

`app.py` — `_create_run_impl` (:309-371): usar o override quando presente. Substituir o bloco de derivação:

```python
        pipeline_snapshot: dict | None = None
        if payload.snapshot is not None:
            # Override do usuário no create-run: valida como pipeline real.
            pipeline = PipelineBase.model_validate(payload.snapshot)
            agents_result = await session.execute(select(AgentTemplate.id))
            known_agents = {row[0] for row in agents_result.all()} | SPECIAL_AGENT_IDS
            errors = validate_pipeline(pipeline, known_agents)
            if errors:
                raise HTTPException(status_code=422, detail=f"snapshot invalid: {', '.join(errors)}")
            pipeline_snapshot = pipeline.model_dump()
            if payload.pipeline_id:
                run.pipeline_id = payload.pipeline_id
        elif payload.pipeline_id:
            template = await session.get(PipelineTemplate, payload.pipeline_id)
            if template is None:
                raise HTTPException(status_code=404, detail="Pipeline not found")

            pipeline = PipelineBase(
                name=template.name,
                description=template.description,
                nodes=template.nodes,
                edges=template.edges,
            )
            agents_result = await session.execute(select(AgentTemplate.id))
            known_agents = {row[0] for row in agents_result.all()} | SPECIAL_AGENT_IDS
            errors = validate_pipeline(pipeline, known_agents)
            if errors:
                raise HTTPException(status_code=422, detail=f"pipeline invalid: {', '.join(errors)}")

            run.pipeline_id = payload.pipeline_id
            pipeline_snapshot = pipeline.model_dump()
```

Verificar se `PipelineBase` já está importado no app.py (está, usado em :329) — se `model_validate` exigir import de pydantic, já presente via PipelineBase.

- [ ] **Step 4: Rodar testes p/ passar**

Run: `pytest tests/test_api_snapshot.py && pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lf/api/schemas.py src/lf/api/app.py tests/test_api_snapshot.py
git commit -m "feat(api): RunCreate.snapshot override + RunResponse.snapshot (S3)"
```

---

### Task 2: Frontend — tipos `Run.snapshot` / `CreateRunInput.snapshot` + api client

**Files:**
- Modify: `web/loopforge-ade/frontend/src/shared/lib/types.ts` (Run :59-78, CreateRunInput :139-149)
- Modify: `web/loopforge-ade/frontend/src/shared/lib/api.ts` (createRun :159-165)
- Test: sem teste unitário dedicado (tipos); validado por build + testes de UI das Tasks 3-4

**Interfaces:**
- Consumes: `Pipeline`/`PipelineInput` (types.ts:579-590)
- Produces: `Run.snapshot?: PipelineInput | null`; `CreateRunInput.snapshot?: PipelineInput | null`

- [ ] **Step 1: Implementar**

`types.ts` — Run (:59-78), após `pipeline_name`:

```ts
  /** Snapshot imutável do pipeline executado (S3) — name/description/nodes/edges. */
  snapshot?: PipelineInput | null
```

`CreateRunInput` (:139-149), após `pipeline_id`:

```ts
  /** Override do snapshot do pipeline no create (S3) — validado no backend. */
  snapshot?: PipelineInput | null
```

`api.ts` — `createRun` (:159-165): nenhuma mudança necessária — o body já serializa `input` inteiro (`JSON.stringify({ mock_llm: false, ...input })`). Validar com `npm run build` (tsc).

- [ ] **Step 2: Rodar p/ validar**

Run: `npx tsc -b && npx vitest run src/features/runs/__tests__/NewRunForm.test.tsx`
Expected: PASS (tipos compilam; testes atuais passam — campo opcional)

- [ ] **Step 3: Commit**

```bash
git add src/shared/lib/types.ts
git commit -m "feat(ui): tipos de snapshot (Run/CreateRunInput)"
```

---

### Task 3: Frontend — modal pré-criação no NewRunForm (preview + params + descrição editável)

**Files:**
- Modify: `web/loopforge-ade/frontend/src/features/runs/NewRunForm.tsx`
- Test: `web/loopforge-ade/frontend/src/features/runs/__tests__/NewRunForm.test.tsx` (atualizar)

**Interfaces:**
- Consumes: `usePipelinesStore.pipelines` (Task pré-existente), `Modal` (shared/ui/Modal.tsx), `getPipeline` (api.ts:334), `CreateRunInput.snapshot` (Task 2)
- Produces: ao clicar "Run" com pipeline selecionado → modal abre com snapshot (nome, descrição, N nós/arestas), campos editáveis (idea/stack/model/routing/interactive/mock já no form + descrição do snapshot) → confirmar → POST com `snapshot` = pipeline com descrição editada

- [ ] **Step 1: Testes que falham**

Atualizar `NewRunForm.test.tsx` (padrão existente: mock `vi.mock('.../shared/lib/api')` + `usePipelinesStore.setState`):

```tsx
  it('com pipeline selecionado, Run abre modal de snapshot; confirmar envia snapshot', async () => {
    usePipelinesStore.setState({
      pipelines: [
        {
          id: 'p1',
          name: 'SnapPipe',
          description: 'desc original',
          nodes: [{ id: 'n1', type: 'agent', agent_id: null, config: {} }],
          edges: [],
          created_at: '',
          updated_at: '',
        },
      ],
    })
    render(<NewRunForm onCreated={onCreated} />)
    fireEvent.change(screen.getByLabelText('Idea'), { target: { value: 'minha ideia' } })
    fireEvent.change(screen.getByLabelText('Pipeline (optional)'), { target: { value: 'p1' } })
    fireEvent.click(screen.getByText('Run'))
    // Modal de snapshot aparece
    expect(await screen.findByText(/Snapshot do pipeline/i)).toBeTruthy()
    // Edita a descrição e confirma
    const desc = screen.getByLabelText('Descrição do snapshot')
    fireEvent.change(desc, { target: { value: 'desc editada' } })
    fireEvent.click(screen.getByText('Criar run'))
    await waitFor(() => {
      expect(mockedCreateRun).toHaveBeenCalledWith(
        expect.objectContaining({
          idea: 'minha ideia',
          pipeline_id: 'p1',
          snapshot: expect.objectContaining({ description: 'desc editada', name: 'SnapPipe' }),
        }),
      )
    })
  })

  it('sem pipeline selecionado, Run envia direto (sem modal, sem snapshot)', async () => {
    render(<NewRunForm onCreated={onCreated} />)
    fireEvent.change(screen.getByLabelText('Idea'), { target: { value: 'direta' } })
    fireEvent.click(screen.getByText('Run'))
    await waitFor(() => {
      expect(mockedCreateRun).toHaveBeenCalledWith(
        expect.not.objectContaining({ snapshot: expect.anything() }),
      )
    })
  })
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `npx vitest run src/features/runs/__tests__/NewRunForm.test.tsx`
Expected: FAIL (não há modal)

- [ ] **Step 3: Implementar**

`NewRunForm.tsx` — adicionar estado + modal. Após `const [showPresets, setShowPresets] = useState(false)` (:52):

```tsx
  const [snapshotDraft, setSnapshotDraft] = useState<{ name: string; description: string } | null>(null)
```

No `submit` (:96-107), interceptar quando `pipelineId` setado — em vez de mutar direto, abrir modal:

```tsx
  const submit = (e?: FormEvent) => {
    if (e) e.preventDefault()
    const text = idea.trim()
    if (!text || mutation.isPending) return
    if (pipelineId) {
      // Preview + edição do snapshot antes de criar (S3)
      setSnapshotDraft({
        name: selectedPipeline?.name ?? '',
        description: selectedPipeline?.description ?? '',
      })
      return
    }
    doCreate(null)
  }

  const doCreate = (snapshot: { name: string; description: string } | null) => {
    const payload: CreateRunInput = { idea: idea.trim(), stack, routing_mode: routingMode, interactive }
    const m = model.trim()
    if (m) payload.model = m
    if (pipelineId) payload.pipeline_id = pipelineId
    if (snapshot && selectedPipeline) {
      payload.snapshot = {
        name: snapshot.name,
        description: snapshot.description,
        nodes: selectedPipeline.nodes,
        edges: selectedPipeline.edges,
      }
    }
    mutation.mutate(payload)
  }
```

Modal (após o form, antes do bloco `showPresets` :239), usando o `Modal` compartilhado (padrão ApiKeyGate/BudgetPill):

```tsx
      {snapshotDraft && (
        <Modal open title="Snapshot do pipeline" maxWidth={480} onClose={() => setSnapshotDraft(null)}>
          <div className="flex flex-col gap-3 p-4">
            <h2 className="text-lg font-semibold text-[var(--text)]">Snapshot do pipeline</h2>
            <p className="text-sm text-[var(--text-dim)]">
              Este snapshot é copiado no momento da criação — a run executa SEMPRE esta
              versão, mesmo que o template mude depois.
            </p>
            <div className="rounded-md border border-[var(--border)] bg-[var(--bg-elev)]/50 px-2.5 py-1.5">
              <p className="text-(--text-2xs) font-semibold uppercase tracking-wide text-[var(--text-dim)]">
                {snapshotDraft.name} · {selectedPipeline?.nodes.length ?? 0} nós · {selectedPipeline?.edges.length ?? 0} arestas
              </p>
            </div>
            <label className="flex flex-col gap-0.5">
              <span className="text-(--text-2xs) font-medium uppercase tracking-wide text-[var(--text-dim)]">
                Descrição do snapshot
              </span>
              <Input
                aria-label="Descrição do snapshot"
                value={snapshotDraft.description}
                onChange={(e) => setSnapshotDraft((d) => (d ? { ...d, description: e.target.value } : d))}
                className="w-full"
              />
            </label>
            <div className="mt-1 flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setSnapshotDraft(null)}>
                Cancelar
              </Button>
              <Button size="sm" variant="primary" onClick={() => { doCreate(snapshotDraft); setSnapshotDraft(null) }}>
                Criar run
              </Button>
            </div>
          </div>
        </Modal>
      )}
```

Imports: `Modal` de `../../shared/ui/Modal`; `Input` já importado. Remover/ajustar a nota display-only (:227-237) — substituir por hint de que o Run abre o preview (ou manter a nota; a nota continua verdadeira; ajustar o texto se quiser "Run abre preview antes de criar").

- [ ] **Step 4: Rodar testes p/ passar**

Run: `npx vitest run src/features/runs/__tests__/NewRunForm.test.tsx && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/features/runs/NewRunForm.tsx src/features/runs/__tests__/NewRunForm.test.tsx
git commit -m "feat(ui): modal de snapshot no create-run (preview + edição)"
```

---

### Task 4: Frontend — RunInspector mostra snapshot persistido

**Files:**
- Modify: `web/loopforge-ade/frontend/src/features/dag/RunInspector.tsx`
- Test: `web/loopforge-ade/frontend/src/features/dag/__tests__/RunInspector.test.tsx` (verificar existência; criar se não houver)

**Interfaces:**
- Consumes: `Run.snapshot` (Task 2), `RunInspector` (RunInspector.tsx:37)
- Produces: seção "Pipeline snapshot" no Run details com nome/descrição/contagem de nós-arestas (read-only) quando `run.snapshot` presente

- [ ] **Step 1: Teste que falha**

`RunInspector.test.tsx` (padrão: mock de `useRunsStore` p/ setar run ativa; `getRunCost` mockado — ver mock de `../../shared/lib/api` nos testes existentes de RunInspector, se houver; caso contrário mockar query de custo desabilitada com run queued):

```tsx
  it('exibe seção de snapshot quando run tem snapshot', () => {
    useRunsStore.setState({
      runs: [
        {
          id: 'r1',
          idea: 'ideia',
          stack: 'python',
          status: 'completed',
          pipeline_id: 'p1',
          pipeline_name: 'SnapPipe',
          snapshot: {
            name: 'SnapPipe',
            description: 'desc snapshot',
            nodes: [{ id: 'n1', type: 'agent', agent_id: null, config: {} }],
            edges: [],
          },
        },
      ],
      activeRunId: 'r1',
    })
    render(<RunInspector />)
    expect(screen.getByText('Pipeline snapshot')).toBeTruthy()
    expect(screen.getByText('SnapPipe')).toBeTruthy()
    expect(screen.getByText(/desc snapshot/)).toBeTruthy()
  })
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `npx vitest run src/features/dag/__tests__/RunInspector.test.tsx`
Expected: FAIL (seção inexistente)

- [ ] **Step 3: Implementar**

`RunInspector.tsx` — dentro da seção "Run details" (:102-127), após o `<dl>` (:115-126):

```tsx
                {run.snapshot ? (
                  <div className="mt-3 rounded-md border border-[var(--border)] bg-[var(--bg-elev)]/50 px-2.5 py-2">
                    <SectionTitle className="mb-1">Pipeline snapshot</SectionTitle>
                    <p className="text-xs font-medium text-[var(--text)]">{run.snapshot.name}</p>
                    {run.snapshot.description ? (
                      <p className="mt-0.5 text-xs leading-4 text-[var(--text-dim)]">{run.snapshot.description}</p>
                    ) : null}
                    <p className="mt-1 text-(--text-2xs) text-[var(--text-dim)]">
                      {run.snapshot.nodes?.length ?? 0} nós · {run.snapshot.edges?.length ?? 0} arestas
                    </p>
                  </div>
                ) : null}
```

- [ ] **Step 4: Rodar testes p/ passar**

Run: `npx vitest run src/features/dag/__tests__/RunInspector.test.tsx && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/features/dag/RunInspector.tsx src/features/dag/__tests__/RunInspector.test.tsx
git commit -m "feat(ui): RunInspector exibe snapshot persistido da run"
```

---

### Task 5: E2E — create-run com snapshot (opcional, smoke)

**Files:**
- Create: `web/loopforge-ade/frontend/tests/snapshot.spec.ts`

**Interfaces:**
- Consumes: `window.__lfTest` (App.tsx:112-120), padrão dos specs existentes (`dismissApiKeyGate`, `runDemo`)

- [ ] **Step 1: Escrever o spec**

`tests/snapshot.spec.ts` (usar mock de pipelines via `window.__lfTest` ou `usePipelinesStore` — conferir como specs existentes mockam estado; padrão: `page.evaluate` com o hook):

```ts
import { expect, test } from '@playwright/test'

test('create-run com pipeline selecionado abre modal de snapshot', async ({ page }) => {
  await page.goto('/')
  // injeta pipeline no store via hook (ajustar ao mecanismo real do __lfTest)
  await page.evaluate(() => {
    const w = window as unknown as { __lfTest: Record<string, unknown> }
    w.__lfTest.pipelines = [
      { id: 'p1', name: 'SnapPipe', description: 'desc', nodes: [{ id: 'n1', type: 'agent', agent_id: null, config: {} }], edges: [], created_at: '', updated_at: '' },
    ]
  })
  await page.getByLabel('Idea').fill('e2e snapshot')
  await page.getByLabel('Pipeline (optional)').selectOption('p1')
  await page.getByText('Run', { exact: true }).click()
  await expect(page.getByText('Snapshot do pipeline').first()).toBeVisible()
  await page.getByLabel('Descrição do snapshot').fill('desc e2e')
  await page.getByText('Criar run').click()
})
```

- [ ] **Step 2: Rodar p/ passar**

Run: `npm run test:e2e -- --project=chromium tests/snapshot.spec.ts`
Expected: PASS (ajustar seletores ao DOM real se necessário)

- [ ] **Step 3: Suíte completa**

Run: `npm run test && npm run lint && npm run build && npm run test:e2e`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/snapshot.spec.ts
git commit -m "test(e2e): modal de snapshot no create-run"
```

---

### Task 6: Validação final da fase

- [ ] **Step 1: Engine**

Run (em `agentes/LoopForge`): `ruff check --select E,F,W,I,N,UP,SIM src/lf tests && mypy src/lf && pytest --cov=src/lf --cov-fail-under=75 tests/`
Expected: PASS

- [ ] **Step 2: SPA**

Run (em `web/loopforge-ade/frontend`): `npm run lint && npm run test && npm run build && npm run test:e2e`
Expected: PASS

- [ ] **Step 3: Smoke manual**

`make sync-dist` + `lf serve` → criar run com pipeline selecionado: modal aparece, editar descrição, confirmar → run detail mostra snapshot editado; editar template depois → run antiga mantém snapshot.
