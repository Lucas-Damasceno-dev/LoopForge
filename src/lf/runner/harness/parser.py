import re
from typing import TypedDict


class ParsedTestOutput(TypedDict):
    total: int
    passed: int
    failed: int
    errors: list[str]


_EXCEPTION_LINE_RE = re.compile(
    r"(?:ModuleNotFoundError|ImportError|AttributeError|NameError|SyntaxError|TypeError|"
    r"ValueError|OSError|RuntimeError|RecursionError|fixture)\S*:\s*.*",
    re.IGNORECASE,
)


def _find_exception_line(output: str, start: int) -> str:
    """Retorna a 1ª linha de exceção/fixture entre `start` e a próxima linha 'ERROR' (ou o fim).

    P1-3: a mensagem real do erro de coleta (ex.: 'ModuleNotFoundError: No module
    named ...') fica logo abaixo do bloco 'ERROR collecting tests/x.py'; o trecho
    entre esse match e o próximo 'ERROR' contém o traceback do pytest.
    """
    next_error = output.find("ERROR", start)
    window = output[start:] if next_error == -1 else output[start:next_error]
    for line in window.splitlines():
        line = line.strip()
        if not line:
            continue
        if _EXCEPTION_LINE_RE.match(line):
            return line
    return ""


def _extract_collection_errors(output: str) -> list[str]:
    """Extrai erros de coleta do pytest com a mensagem real (ex.: ModuleNotFoundError).

    Para cada linha 'ERROR ... .py':
    1. usa a mensagem inline quando presente (após o '-', ex.: 'ERROR tests/x.py - Msg');
    2. senão, procura a 1ª linha de exceção/fixture logo abaixo no traceback.
    Deduplica por módulo (1ª mensagem vence), preservando a ordem de aparição, e
    trunca cada mensagem em ~200 chars.
    """
    pattern = re.compile(r"ERROR(?:\s+collecting)?\s+(\S+\.py)(?:\s*-\s*(.+))?", re.IGNORECASE)
    seen: set[str] = set()
    errors: list[str] = []
    for match in pattern.finditer(output):
        module = match.group(1)
        if module in seen:
            continue
        message = match.group(2)
        if message is None or not message.strip():
            message = _find_exception_line(output, match.end())
        if message.strip():
            errors.append(f"{module}: {message.strip()[:200]}")
        else:
            errors.append(module)
        seen.add(module)
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
