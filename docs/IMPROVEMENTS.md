# Sugestões de Melhorias (após 2 runs reais)

**Data**: 2026-08-01
**Última auditoria**: 2026-08-12 (todos os itens verificados no código real)
**Base**: runs reais `examples/imp-valid` (Java/Spring, `--advanced`) e `examples/expense-split` (Python/FastAPI, `--advanced`) executados via OmniRoute local com modelo `oc/deepseek-v4-flash-free`.

---

## Bugs observados (críticos)

### P0-1 — Parser do harness não detecta erros de coleta do pytest

**✅ FIXADO (auditoria 2026-08-12)** — `src/lf/runner/harness/parser.py` agora:

- `_find_exception_line` (parser.py:19-34) captura a 1ª linha de exceção (ex.: `ModuleNotFoundError`) logo abaixo do bloco `ERROR`.
- `_extract_collection_errors` (parser.py:37-61) aplica regex nas linhas `ERROR ... .py` com mensagem inline opcional, deduplica por módulo (1ª mensagem vence) e trunca em 200 chars.
- Bloco 6 (parser.py:122-131): cada erro de coleta conta como falha (`failed += summary_errors`; `failed = max(failed, len(errors))`). Nunca retorna `passed=0, failed=0` quando existem erros. Erros Maven são descontados para evitar dupla contagem com o bloco 4 (parser.py:127).

Sintoma original: `src/lf/runner/harness/parser.py` (54 linhas) só aplicava regex de `(\d+) passed` (linha 10) e `(\d+) failed` (linha 14), além dos formatos go/cargo/maven. Não lia `N errors during collection` nem as linhas `ERROR tests/...` do pytest. Quando a coleta falhava, o parse retornava `passed=0, failed=0` e `success=False`, escondendo a falha real por trás de um ImportError de coleta.

---

### P0-2 — Naming contract TestWriter↔Developer quebrado

**✅ FIXADO (auditoria 2026-08-12)** — `src/lf/pipeline/nodes/test_writer.py:195` agora declara no `contract_tests` o inventário de módulos esperados via `### MODULES: ` + `, `.join(modules)`. O QA valida o contrato no gate `qa.py:132-142` (procura `test_*.py`/`*_test.py` em `tests/`), evitando ImportError por plural/singular.

Sintoma original: no run `expense-split`, o TestWriter gerou testes-contrato importando `app.services.payment`, `notification` e `balance` (singular); o Developer gerou `payments.py`, `notifications.py` e `balances.py` (plural). Resultado: 3 ImportError na coleta do pytest. O run terminou com "QA retries exhausted" após 3 tentativas.

---

### P1-3 — Feedback de falha do harness não carrega o erro real pro Developer

**✅ FIXADO (auditoria 2026-08-12)** — `src/lf/pipeline/nodes/qa.py` agora:

- Caso `no_tests_found` (qa.py:164-180): feedback inclui mensagem + `raw_output[-500:]` anexado.
- Caso erros reais (qa.py:183-213): feedback estruturado com `err_list[:3]`, `failed_tests_details` e `raw_output[-800:]`.

Sintoma original: `qa.py:83-86` marcava `FAIL` quando `passed == 0`, mas o feedback que chegava ao Developer era a mensagem genérica de `qa.py:237`. O Developer recebia "Nenhum teste foi executado" em vez dos ImportError reais e **regenerava a arquitetura do zero a cada retry** (3 arquiteturas diferentes nas 3 tentativas do `expense-split`), nunca convergindo.

---

### P1-4 — Contaminação cross-run no workdir compartilhado

**✅ FIXADO (auditoria 2026-08-12)** — `src/lf/orchestrator/task_dispatcher.py`:

- `_task_dir_suffix` (task_dispatcher.py:50-55): id único por task (sufixo sanitizado com prefixo do projeto removido).
- `output_dir` (task_dispatcher.py:169-175): `/tmp/loopforge/{project_id}/{suffix}` — workdir único por task, eliminando contaminação cross-run.
- `_cleanup_stale_project_dirs` (developer.py:777) ampliado: remove `target/`, `build/`, `dist/`, `test_reports/`, `.pytest_cache/`, `htmlcov/` além de `cmd/internal/src/pkg/migrations`. `.venv/` e `node_modules/` são preservados. Proteção dogfooding (developer.py:802, 835): nunca limpa o repo LoopForge ou diretórios dentro dele.

Sintoma original: `/tmp/loopforge/loopforge_project` acumulava `pom.xml`, `target/` e `test_reports/` do run Java dentro do projeto Python novo. `_cleanup_stale_project_dirs` (developer.py:461, definida em `developer.py:550`) só removia `{"cmd", "internal", "src", "pkg", "migrations"}` (linha 556).

---

### P2-5 — Timeout default insuficiente para modelos de reasoning

**✅ FIXADO (auditoria 2026-08-12)** — `src/lf/pipeline/llm_factory.py`:

- `DEFAULT_LLM_TIMEOUT = 300.0` (llm_factory.py:31), `REASONING_TIMEOUT = 600.0` (:33).
- `_is_reasoning_model` (:41-44) detecta modelos reasoning via `_REASONING_MODEL_MARKERS` (:36-38: reasoner, reasoning, thinking, r1, o1, o3, deepseek-r, kimi, glm-4.5).
- `_resolve_timeout` (:47-58): **ENV > reasoning > default**, nunca retorna `None`.
- Backoff preservado: `timeout_val = base_timeout * (1.0 + attempt * 0.5)` (:116).
- Complementar: `subprocess_timeout_seconds` configurável via `ade.yaml runner.subprocess_timeout_seconds` (task_dispatcher.py:119-127), antes hardcoded em 120s.

Sintoma original: `OPENROUTER_TIMEOUT` default era `120s` (`src/lf/pipeline/llm_factory.py:59`). Prompts grandes do pipeline full + modelo de reasoning estouravam os 120s.

---

## Oportunidades (validadas nos runs)

Melhorias que **funcionaram** e merecem destaque:

- **TestWriter gerando contrato real**: 8 arquivos de testes-contrato no `expense-split`.
- **Gates Q9 (cobertura de critérios) e R2 (contrato de testes)** presentes em `qa.py` (101-107 e 132-142).
- **Retry QA→Developer** com `attempt_count` e `feedback_history` acumulando entre tentativas.
- **Arquitetura gerada pelo Developer surpreendentemente boa**: hexagonal no `imp-valid` (Java), em camadas no `expense-split` (models/repositories/services/schemas/api/migrations).
- **`_extract_failing_snippets` (Q10)** para enriquecer retries com trechos reais de erro.

---

## Experiência de uso

- Runs full `--advanced` com modelo de reasoning: **minutos por nó** — não matar o processo; ajustar `OPENROUTER_TIMEOUT` ou `ade.yaml runner.subprocess_timeout_seconds` se houver timeout.
- **Fast mode** recomendado para bugfix/refactor (`--stack <lang>` com routing fast).
- **Mock mode** para testar o fluxo do pipeline sem custo/latência.
- Documentar a expectativa de latência no guia de execução real.

---

## Pendências reais (verificadas em 2026-08-12)

Itens que ainda NÃO estão implementados (detalhes no `ROADMAP_CHECKLIST.md`):

1. **Worktree Sandbox isolado (4.1, parcial)**: `WorktreeSandbox` existe em `src/lf/runner/git/sandbox.py`, mas não é referenciado pelo `TaskDispatcher` nem pela CLI — falta wiring no `dispatch()`.
2. **Diff side-by-side no HITL (4.4, parcial)**: `lf diff` standalone existe (`src/lf/cli/commands/diff.py:21,33,58`), mas não integrado ao `lf run -i`.
3. **Entrega incremental por User Story (5.1)**: nenhum trecho de slice incremental encontrado no código; topologia atual é whole-feature.

---

## Priorização sugerida

1. **P0-1 e P0-2** → **Resolvidos.**
2. **P1-3 e P1-4** → **Resolvidos.**
3. **P2-5** → **Resolvido.**
4. **Próximo ciclo**: 4.1 (wire do worktree sandbox), 4.4 (diff no HITL), 5.1 (incremental slices).
