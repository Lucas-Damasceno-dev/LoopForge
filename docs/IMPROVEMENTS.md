# Sugestões de Melhorias (após 2 runs reais)

**Data**: 2026-08-01
**Base**: runs reais `examples/imp-valid` (Java/Spring, `--advanced`) e `examples/expense-split` (Python/FastAPI, `--advanced`) executados via OmniRoute local com modelo `oc/deepseek-v4-flash-free`.

---

## Bugs observados (críticos)

### P0-1 — Parser do harness não detecta erros de coleta do pytest

`src/lf/runner/harness/parser.py` (54 linhas) só aplica regex de `(\d+) passed` (linha 10) e `(\d+) failed` (linha 14), além dos formatos go/cargo/maven. Ele **não lê** `N errors during collection` nem as linhas `ERROR tests/...` do pytest. Quando a coleta falha, o parse retorna `passed=0, failed=0` e `success=False`.

Resultado: o QA converte isso em "Nenhum teste foi executado ou nenhum harness/compilador foi encontrado." (`src/lf/pipeline/nodes/qa.py:237`, com status FAIL decidido em `qa.py:83-86`), escondendo a falha real por trás de um ImportError de coleta.

**Sugestão**:
- Adicionar regex para `(\d+) errors?` e para linhas `ERROR .*\.py` no `parse_test_output`.
- Tratar erros de coleta como falha, populando `errors` com o nome do módulo que falhou.

---

### P0-2 — Naming contract TestWriter↔Developer quebrado

No run `expense-split`, o TestWriter gerou testes-contrato importando `app.services.payment`, `notification` e `balance` (singular); o Developer gerou `payments.py`, `notifications.py` e `balances.py` (plural). Resultado: 3 ImportError na coleta do pytest (confirmado com `pytest tests/ -q`: `ERROR tests/test_balances.py`, `test_notifications.py`, `test_payments.py — ModuleNotFoundError`). O run terminou com "QA retries exhausted" após 3 tentativas.

**Sugestão**:
- TestWriter declarar no `contract_tests` o inventário de módulos esperados (ex.: `### MODULES: app.services.payment, app.services.notification, app.services.balance`) para o Developer receber isso como contrato obrigatório.
- Alternativa: o QA executar os testes-contrato **antes** de aceitar qualquer código e reportar o nome exato do módulo faltante.

---

### P1-3 — Feedback de falha do harness não carrega o erro real pro Developer

`qa.py:83-86` marca `FAIL` quando `passed == 0`, mas o feedback que chega ao Developer é a mensagem genérica de `qa.py:237`. O Developer recebe "Nenhum teste foi executado" em vez dos ImportError reais e **regenera a arquitetura do zero a cada retry** (3 arquiteturas diferentes nas 3 tentativas do `expense-split`), nunca convergindo.

Os gates de cobertura de critérios (`qa.py:101-107`, regra 7) e de contrato de testes (`qa.py:111-116`) existem, mas não ajudam quando o harness não executa nada.

**Sugestão**:
- Quando a coleta falhar, capturar o stderr do pytest (já disponível em `harness_result["output"]`) e incluir as 3–5 primeiras linhas de erro no feedback.
- A melhoria R3 em `qa.py:141-166` extrai detalhes de `failed_tests_details`, mas o report não popula isso quando nada é executado — estender esse caminho para o caso de collection error.

---

### P1-4 — Contaminação cross-run no workdir compartilhado

`/tmp/loopforge/loopforge_project` acumulou `pom.xml`, `target/` e `test_reports/` do run Java dentro do projeto Python novo. O QA roda no diretório do produto (`output_dir`, `qa.py:26`), que é compartilhado entre runs.

`_cleanup_stale_project_dirs` (`developer.py:461`, definida em `developer.py:550`) só remove `{"cmd", "internal", "src", "pkg", "migrations"}` (linha 556) — não limpa `pom.xml`, `target/` nem `test_reports/`.

**Sugestão**:
- Workdir único por task (ex.: `/tmp/loopforge/{task_id}/`).
- Ou limpeza completa do diretório no início do run.

---

### P2-5 — Timeout default insuficiente para modelos de reasoning

`OPENROUTER_TIMEOUT` default é `120s` (`src/lf/pipeline/llm_factory.py:59`), com backoff `timeout_val = base_timeout * (1.0 + attempt * 0.5)` em `:64`. Prompts grandes do pipeline full + modelo de reasoning estouram os 120s.

Medição via OmniRoute: prompt pequeno ~1.4s; prompt médio ~54.2s para 6092 tokens de saída.

**Sugestão**:
- Detectar modelo de reasoning e elevar o timeout automaticamente.
- Ou elevar o default para `300s`.

---

## Oportunidades (validadas nos runs)

Melhorias que **funcionaram** e merecem destaque:

- **TestWriter gerando contrato real**: 8 arquivos de testes-contrato no `expense-split`.
- **Gates Q9 (cobertura de critérios) e R2 (contrato de testes)** presentes em `qa.py` (101-107 e 111-116) — mesmo que não tenham resolvido o caso de harness vazio.
- **Retry QA→Developer** com `attempt_count` e `feedback_history` acumulando entre tentativas.
- **Arquitetura gerada pelo Developer surpreendentemente boa**: hexagonal no `imp-valid` (Java), em camadas no `expense-split` (models/repositories/services/schemas/api/migrations).
- **`_extract_failing_snippets` (Q10)** para enriquecer retries com trechos reais de erro.

---

## Experiência de uso

- Runs full `--advanced` com modelo de reasoning: **minutos por nó** — não matar o processo; aumentar `OPENROUTER_TIMEOUT` se houver timeout.
- **Fast mode** recomendado para bugfix/refactor (`--stack <lang>` com routing fast).
- **Mock mode** para testar o fluxo do pipeline sem custo/latência.
- Documentar a expectativa de latência no guia de execução real.

---

## Priorização sugerida

1. **P0-1 e P0-2 primeiro**: sem detectar erros de coleta e sem contrato de módulos, o QA fica cego e o retry nunca converge.
2. **P1-3 e P1-4 em seguida**: feedback real pro Developer + isolamento do workdir.
3. **P2-5 por último**: ajuste de timeout (workaround imediato via env var).
