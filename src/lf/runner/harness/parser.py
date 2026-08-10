import re
from typing import TypedDict


class ParsedTestOutput(TypedDict):
    total: int
    passed: int
    failed: int
    errors: list[str]


def _extract_collection_errors(output: str) -> list[str]:
    """Extrai módulos com erro de coleta das linhas 'ERROR ... .py' do pytest.

    Captura tanto 'ERROR collecting tests/x.py' quanto 'ERROR tests/x.py - ...'.
    Deduplica preservando a ordem de aparição (um mesmo módulo pode aparecer
    nas duas formas no mesmo run).
    """
    raw_matches = re.findall(r"ERROR(?:\s+collecting)?\s+(\S+\.py)", output, re.IGNORECASE)
    seen: set[str] = set()
    errors: list[str] = []
    for module in raw_matches:
        if module not in seen:
            seen.add(module)
            errors.append(module)
    return errors


def parse_test_output(output: str) -> ParsedTestOutput:
    """Extrai contagem de testes passados/falhados de pytest, vitest, jest, go test, cargo test.

    Também detecta erros de coleta do pytest (linhas 'ERROR ... .py' + resumo
    'N errors'): cada erro conta como falha e a lista de módulos é exposta na
    chave `errors` para o QA reportar a causa real (ex.: ModuleNotFoundError)
    em vez do genérico "nenhum teste foi executado".
    """
    passed = 0
    failed = 0

    # 1. Pytest / Vitest / Jest: (\d+) passed, (\d+) failed
    p_match = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
    if p_match:
        passed += int(p_match.group(1))

    f_match = re.search(r"(\d+)\s+failed", output, re.IGNORECASE)
    if f_match:
        failed += int(f_match.group(1))

    # 2. Go test: "--- PASS:", "--- FAIL:"
    go_passes = len(re.findall(r"--- PASS:", output))
    go_fails = len(re.findall(r"--- FAIL:", output))
    if go_passes > 0 or go_fails > 0:
        passed = max(passed, go_passes)
        failed = max(failed, go_fails)

    # 3. Cargo test: "test result: ok. X passed; Y failed"
    cargo_match = re.search(r"test result: \w+\.\s+(\d+)\s+passed;\s+(\d+)\s+failed", output)
    if cargo_match:
        passed = int(cargo_match.group(1))
        failed = int(cargo_match.group(2))

    # 4. Maven / JUnit: Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
    mvn_match = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", output)
    mvn_errors = 0
    if mvn_match:
        total = int(mvn_match.group(1))
        fails = int(mvn_match.group(2)) + int(mvn_match.group(3))
        mvn_errors = int(mvn_match.group(3))
        passed = max(passed, total - fails)
        failed = max(failed, fails)

    # 5. Build/Compilation Failure Detection (Go, Rust, TS/JS, Python)
    if (
        passed == 0
        and failed == 0
        and (
            re.search(r"FAIL\s+\S+\s+\[build failed\]", output)
            or re.search(r"#\s+\S+[\r\n]+.*(?:error|undefined|cannot|imported and not used)", output, re.IGNORECASE)
            or "build failed" in output.lower()
            or "compilation failed" in output.lower()
            or "cannot find module" in output.lower()
            or "no required module" in output.lower()
        )
    ):
        failed = 1

    # 6. Erros de coleta do pytest: cada erro conta como falha (o QA decide FAIL
    #    com failed > 0). Nunca retorna passed=0/failed=0 quando há `errors`.
    errors = _extract_collection_errors(output)
    errors_match = re.search(r"(\d+)\s+errors?\b", output, re.IGNORECASE)
    summary_errors = int(errors_match.group(1)) if errors_match else 0
    # Maven já soma Errors no bloco 4; evita dupla contagem.
    summary_errors = max(0, summary_errors - mvn_errors)
    failed += summary_errors
    if errors:
        failed = max(failed, len(errors))

    return {
        "total": passed + failed,
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }
