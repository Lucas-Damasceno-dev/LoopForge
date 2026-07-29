import re


def parse_test_output(output: str) -> dict[str, int]:
    """Extrai contagem de testes passados/falhados de pytest, vitest, jest, go test, cargo test."""
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

    if passed == 0 and failed == 0 and "ok" in output.lower():
        passed = 1

    return {
        "total": passed + failed,
        "passed": passed,
        "failed": failed,
    }
