import re


def parse_test_output(output: str) -> dict[str, int]:
    """Extract passed/failed test counts from pytest/npm test output."""
    passed = 0
    failed = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    return {
        "total": passed + failed,
        "passed": passed,
        "failed": failed,
    }
