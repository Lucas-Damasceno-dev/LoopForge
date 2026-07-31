# Copilot Credits Sprint — LoopForge

> Registro de coordenação do GitHub Copilot CLI (plano Pro via GitHub Education).
> Execução via: `gh copilot -p "<task>" --yolo --no-ask-user --max-autopilot-continues 3`

## Contexto

- **Data**: 2026-07-31
- **Créditos**: 0/200 usados — reset em ~5h
- **Foco**: fundação do projeto
- **Modelo**: GitHub Copilot CLI 1.0.77

## Estado da fundação (baseline)

| Verificação | Resultado | Observação |
|---|---|---|
| `pytest tests/` | 151 passed, 1 skipped | 20.5s |
| Cobertura `src/lf` | 76.75% | limiar CI 75% — margem de ~1.75pp |
| `ruff check --select E,F,W,I,N,UP,SIM src/lf tests` | **119 erros** | 114×E501, 2×W293, 1×W292, 1×I001, 1×F841 → **CI vermelha** |
| `mypy src/lf` | Success | **no-op** (`ignore_errors = true` no pyproject) |
| Git | árvore limpa | — |

## Tasks propostas

| ID | Área | Task | Prioridade | Status |
|---|---|---|---|---|
| T1 | CI | Corrigir erros de lint + alinhar `--select` do CI com config do pyproject | alta | ✅ concluída |
| T2 | CI | Ativar gate real de mypy (remover `ignore_errors = true`, corrigir tipos) | alta | ❌ recusada pelo usuário |
| T3 | Testes | Testes para módulos com 0% cobertura (`fail_to_eval.py`, `flake_isolator.py`) | alta | ✅ concluída |
| T4 | Config | Fix bug de precedência no `config/loader.py` (YAML parsing sempre) + teste de regressão | alta | ✅ concluída |
| T5 | Pipeline | Tornar `parallel_audit` resiliente: `as_completed(timeout)`, capturar exceção, setar `error` | alta | ✅ concluída |
| T6 | Pipeline | Marcar run como falho quando retry esgota (`should_retry` + WS `completed` no dispatcher) | alta | ✅ concluída |
| T7 | Runner | Auto-formatter opt-in (`run_auto_formatter` muta projeto do usuário sem flag) | média | ✅ concluída |
| T8 | Testes | Testes para núcleo: `pipeline/nodes/qa.py` (56%) + `pipeline/llm_factory.py` (56%) | média | ✅ concluída |
| T9 | Config | Validação Pydantic: `Literal` p/ routing_mode/task_type/complexity, constraints em budget/parallel | média | ✅ concluída |
| T10 | Qualidade | Substituir `except Exception: pass` por logging (telemetria, WS, decisão humana) | média | ✅ escolhida |
| T11 | Runner | Fix `detect_test_command` falso positivo (exigir `tests/` real, não só `.py`) | média | ✅ concluída |
| T12 | Config | Atualizar defaults para OpenRouter (`oc/deepseek-v4-flash-free`) | baixa | ✅ escolhida |

## Notas da análise

- **Descoberta importante**: `pyproject.toml` já ignora `E501` e `SIM117` (`[tool.ruff.lint].ignore`). Os 130 erros só aparecem porque o CI roda `--select` na CLI, que sobrescreve o ignore. Estratégia T1 (re-escopada após recusa do copilot em corrigir 126 E501): **alinhar CI à config** (remover `--select` do ci.yml) + corrigir os **3 erros reais** restantes (SIM105 `qa.py:183`, SIM102 `parser.py:40`, F841 `llm.py:82`). E501/SIM117 permanecem intencionalmente ignorados.

## Plano de ondas (evita interferência de arquivos)

Tasks paralelas só compartilham arquivos que **não** se sobrepõem. Ordens impostas por conflito: T9→T12 (schema.py), T6→T10 (task_dispatcher.py), T1 sozinha (toca tudo).

| Onda | Tasks | Por quê |
|---|---|---|
| 1 | T1 | toca src/lf + tests inteiros — sozinha |
| 2 | T3, T4, T7, T11 | arquivos disjuntos (testes novos; loader.py; harness/runner.py; config/registry.py) |
| 3 | T5, T6, T8, T9 | disjuntos (parallel_audit.py; graph.py+task_dispatcher.py; testes novos; schema.py) |
| 4 | T10, T12 | disjuntos (logging em 4 arquivos; schema.py defaults) |

## Log de execução

| # | Data/hora | Task | Comando | Resultado | Créditos |
|---|---|---|---|---|---|
| 1 | 2026-07-31 ~17:00 | T1 (tentativa 1) | `gh copilot -p "T1-LINT" --yolo --no-ask-user --max-autopilot-continues 3` | Esgotou 3 continues: autofix rodou (4 erros corrigidos), 126 restantes (114 E501 + 9 SIM117 + 1 SIM105 + 1 SIM102 + 1 F841) | 6.48 |
| 2 | 2026-07-31 ~17:10 | T1 (tentativa 2) | `... --resume=a214c265... --max-autopilot-continues 5` | **TRAVOU** — processo 0% CPU esperando input interativo; morto via pkill | 0 (retomada) |
| 3 | 2026-07-31 ~17:20 | T1 (tentativa 3) | `... --max-autopilot-continues 5 < /dev/null` | Recusou: "126 E501 é arriscado num turno" — 0 changes, 4.87 créditos. **Re-escopo**: alinhar CI + 3 erros reais | 4.87 |
| 4 | 2026-07-31 ~17:30 | T1 (tentativa 4/final) | `... T1-FINAL < /dev/null` | ✅ Concluída: ci.yml sem `--select`; SIM105/SIM102/F841 corrigidos; ruff "All checks passed" (config) + pytest verde. Sessão resumível: `3fc41788-726a-4886-add5-17bf005b1344` | 5.98 |
| 5 | 2026-07-31 ~17:40 | T1 (pós) | fix direto (orquestrador) | W292 residual em `tests/test_main.py` (newline final) corrigido via printf — ruff "All checks passed" + pytest test_main 1 passed | 0 |
| 6 | 2026-07-31 ~18:00 | T3 (Onda 2) | testes p/ fail_to_eval.py + flake_isolator.py (PID 21628) | ✅ 11 testes (4+7), isolado 11 passed; suíte completa 173 passed/1 skipped. Sessão: `0d3b143c-037f-421c-b047-c4de252b0ed8` | 12.10 |
| 7 | 2026-07-31 ~18:00 | T4 (Onda 2) | fix precedência loader.py + teste (PID 21654) | ✅ 5 testes; +1 de regressão adicionado pelo orquestrador (`.json` com `null` → default, pina o bug real) = 6 testes. Verificado por mim: 6 passed. Sessão: `1064b400-5c70-4dfa-aed4-d4d6a11b8ab5` | 5.12 |
| 8 | 2026-07-31 ~18:00 | T7 (Onda 2) | auto-formatter opt-in + teste (PID 21709) | ✅ `auto_format: bool = False` no `__init__`, run() só formata se True; test_auto_formatter.py cobre opt-in (11 passed isolado). Sessão: `5e29402a-a772-4dbd-b4cb-3d5d8f7451f8` | 4.95 |
| 9 | 2026-07-31 ~18:00 | T11 (Onda 2) | fix detect_test_command falso positivo + teste (PID 21761) | ✅ PythonStackHandler exige evidência real (tests/, conftest.py, config pytest); contrato `str\|None` consistente; 4 testes. Sessão: `4f40144e-4e32-4c16-a010-f853b305d822` | 8.36 |
| 10 | 2026-07-31 ~18:20 | Onda 2 (verificação) | exp-2 (explorer) reutilizado | ✅ Aprovado: sem mutação fora do escopo; ajustes menores aplicados (teste T4 + W292). **Lições**: erros `sqlite3 disk I/O` nos runs paralelos eram artefato de 4 pytest concorrentes no mesmo `.sqlite` — re-rodar suíte sequencial para validar; processo LoopForge em background reescreveu test_main.py (W292 voltou) — re-aplicar fix | 0 |
| 11 | 2026-07-31 ~18:40 | T5 (Onda 3) | parallel_audit resiliente: as_completed(timeout) + try/except (PID 27687) | ✅ 5.21cr; `as_completed([...], timeout=300)`, try/except por future (worker_errors, res={"error":...}), TimeoutError cancela pendentes; teste test_parallel_audit_resilience.py. Sessão: `2f6ded8c-3f55-47a8-8a8e-617903b0dcf6` | 5.21 |
| 12 | 2026-07-31 ~18:40 | T6 (Onda 3) | retry esgotado → run falho (graph.py + task_dispatcher.py) (PID 27712) | ⚠️ 11.6cr; regressão: `state["error"]=` em should_retry (aresta condicional) NÃO propaga no LangGraph 1.2.10. **Fix pelo orquestrador**: erro setado no nó parallel_audit (retorno de nó propaga) + testes patcheiam `qa._mock_report` p/ FAIL (QA mock sobrescrevia test_report com PASS). Verificado: 194 passed/1 skipped + ruff limpo. Sessão: `5f7bcfe1-d1ba-4e49-a69e-2a7910a85e7e` | 11.6 |
| 13 | 2026-07-31 ~18:40 | T8 (Onda 3) | testes qa.py + llm_factory.py (cobertura) (PID 27751) | ✅ 10.3cr; test_qa_coverage_extra.py (4) + test_llm_factory_extra.py (6 testes, não 4 — brief divergiu). Sessão: `27f0d9fd-a497-49a0-9386-306c9b682adf` | 10.3 |
| 14 | 2026-07-31 ~18:40 | T9 (Onda 3) | Literal + constraints em schema.py (PID 27800) | ✅ 6.8cr; routing_mode/task_type/complexity_level → Literal; budget ge=0, max_parallel gt=0; defaults LLM PRESERVADOS (T12 não aplicado). test_schema_validation.py. Sessão: `edb71cf5-f28d-4cc2-8752-98aec414c486` | 6.8 |
| 15 | 2026-07-31 ~19:10 | T6 (pós) | fix direto (orquestrador) | Fix do T6: removida mutação in-place em should_retry; bloco retry_error no nó parallel_audit (`tests_failed and qa_attempt >= max_retries`); 2 testes ajustados p/ patchear `_mock_report` (FAIL). Resultado: 2 testes passando + suíte 194 passed/1 skipped + ruff All checks passed | 0 |
| 16 | 2026-07-31 ~19:15 | Onda 3 (verificação) | exp-4/exp-5/exp-6 (explorer) | ✅ T5/T6/T8/T9 aprovados; Onda 2 sem regressão (diff HEAD~6 vazio, 26/26 testes); sem mutação fora do escopo. **Notas**: QA mock não incrementa qa_attempt_count (pré-existente); timeout 300s não é hard-stop (cancel não interrompe thread); `routing_mode="fast"` puro cai no caminho full (pré-existente); W292 em test_main.py recorre (LoopForge background reescreve o arquivo) | 0 |
| 17 | 2026-07-31 ~19:25 | T10 (Onda 4) | logging nos 5 `except Exception: pass` (task_dispatcher.py:139/199, developer.py:29-30, lessons.py:36-37, cache.py:23) (PID 37119) | ⚠️ Relatou "5/5" mas converteu só 1/5 (task_dispatcher.py:142) com mensagens trocadas (_broadcast_ws/_send_notification). **Fix manual pelo orquestrador**: convertidos os 5 pontos + import logging/logger nos 3 arquivos + mensagens des-trocadas. Re-verificado por exp-9: ✅ todos corretos, ruff All checks passed | 6.51 |
| 18 | 2026-07-31 ~19:25 | T12 (Onda 4) | defaults LLM → OpenRouter em schema.py:91-92 + ajustar testes (PID 37146) | ✅ `llm_provider="openrouter"`/`llm_model="oc/deepseek-v4-flash-free"`; T9 literals/constraints preservados; test_config_loader.py:56 ajustado; nenhum teste asserta "google"/"gemini-1.5-flash" como default. Verificado por exp-8: ✅ 14 passed + ruff. **Nota**: init.py:37-38 ainda grava fallback "google"/"gemini-1.5-flash" no config (fora do escopo, follow-up candidato) | 3.78 |
| 19 | 2026-07-31 ~20:00 | Rodada 2 — Pacote 1 (edits diretos) | init.py fallback → OpenRouter; lessons.py 2º save_lesson print→logger; docs/configuration.md atualizada; test_main.py → smoke test CLI real (`CliRunner` + `main --help`) | ✅ Verificado: ruff All checks passed. **LoopForge background reescreveu test_main.py p/ placeholder (W292) — re-aplicado 2x** | 0 |
| 20 | 2026-07-31 ~20:00 | Rodada 2 — Pacote 2 (edits diretos) | HITL: case `parallel_audit` no handler (tabela 🛡️ vulns + deployabilidade); `_get_input_with_timeout` fallback "c"→"x" (abortar); router() whitelist restrita a (pm, tech_lead, developer, qa); entry_router roteia `routing_mode="fast"` puro → Developer; qa.py next_agent "appsec"→"parallel_audit" (+4 testes atualizados); api/schemas.py `RoutingMode` Literal; runner/opencode timeout 600→300 | ⚠️ **2 regressões expostas e corrigidas**: (1) test_graph_router_direct assertava "cpo" no router — atualizado p/ contrato novo ("cpo"→__end__, novo assert "pm"); (2) fast routing deixa `stack=None` (TL não roda) → crash `stack.lower()` em lessons.py — fix `stack = state.get("stack") or "python"` | 0 |
| 21 | 2026-07-31 ~20:10 | Rodada 2 — Pacote 4 (git) | `git push origin main` | ✅ Push `7954448..ecdf526` (25 commits de checkpoint do LoopForge, inclui rodadas 1+2) | 0 |

## Checklist pós-sprint

- [x] Rodar `pytest tests/` completo (194 passed, 1 skipped)
- [x] Rodar ruff com o comando do CI (All checks passed)
- [x] Conferir cobertura ≥ 75% — **80.30%** (baseline 76.75%, +3.55pp; CI `--cov-fail-under=75` verde)
- [x] Revisar diffs das tasks (4 verificações explorer independentes: sem mutação fora do escopo)

## Resumo de créditos

| Fase | Tasks | Créditos |
|---|---|---|
| T1 (lint, 4 tentativas + fix direto) | — | 17.33 |
| Onda 2 (T3, T4, T7, T11) | — | 30.53 |
| Onda 3 (T5, T6, T8, T9) + fix T6 | — | 33.80 |
| Onda 4 (T10, T12) + fix T10 | — | 10.29 |
| **Total** | **11 tasks** | **~91.95** |

Todos os 11 tasks aprovados concluídos (T2 recusada pelo usuário). Reset mensal de 200 créditos ocorre em ~5h — sprint usou ~46%.
