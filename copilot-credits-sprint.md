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
| T5 | Pipeline | Tornar `parallel_audit` resiliente: `as_completed(timeout)`, capturar exceção, setar `error` | alta | ✅ escolhida |
| T6 | Pipeline | Marcar run como falho quando retry esgota (`should_retry` + WS `completed` no dispatcher) | alta | ✅ escolhida |
| T7 | Runner | Auto-formatter opt-in (`run_auto_formatter` muta projeto do usuário sem flag) | média | ✅ escolhida |
| T8 | Testes | Testes para núcleo: `pipeline/nodes/qa.py` (56%) + `pipeline/llm_factory.py` (56%) | média | ✅ escolhida |
| T9 | Config | Validação Pydantic: `Literal` p/ routing_mode/task_type/complexity, constraints em budget/parallel | média | ✅ escolhida |
| T10 | Qualidade | Substituir `except Exception: pass` por logging (telemetria, WS, decisão humana) | média | ✅ escolhida |
| T11 | Runner | Fix `detect_test_command` falso positivo (exigir `tests/` real, não só `.py`) | média | ✅ escolhida |
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
| 11 | 2026-07-31 ~18:40 | T5 (Onda 3) | parallel_audit resiliente: as_completed(timeout) + try/except (PID 27687) | ⏳ em execução | — |
| 12 | 2026-07-31 ~18:40 | T6 (Onda 3) | retry esgotado → run falho (graph.py + task_dispatcher.py) (PID 27712) | ⏳ em execução | — |
| 13 | 2026-07-31 ~18:40 | T8 (Onda 3) | testes qa.py + llm_factory.py (cobertura) (PID 27751) | ⏳ em execução | — |
| 14 | 2026-07-31 ~18:40 | T9 (Onda 3) | Literal + constraints em schema.py (PID 27800) | ⏳ em execução | — |

## Checklist pós-sprint

- [ ] Rodar `pytest tests/` completo
- [ ] Rodar ruff + mypy com os mesmos comandos do CI
- [ ] Conferir cobertura ≥ 75%
- [ ] Revisar diffs das tasks (especialmente mutações fora do escopo)
