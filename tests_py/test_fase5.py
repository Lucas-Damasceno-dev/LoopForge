from pathlib import Path
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.guardrails.loop_lock import LoopLock
from lf.guardrails.security_scanner import SecurityScanner
from lf.telemetry.store import TelemetryStore


def test_circuit_breaker():
    cb = CircuitBreaker(max_consecutive_failures=2, max_total_cost=1.0)
    assert cb.can_proceed()

    cb.record_failure()
    assert cb.can_proceed()

    cb.record_failure()
    assert not cb.can_proceed()


def test_loop_lock(tmp_path: Path):
    lock_file = tmp_path / "test.lock"
    lock = LoopLock(lock_file)

    assert lock.acquire("session-1")
    assert not lock.acquire("session-2")
    assert lock.release()
    assert lock.acquire("session-2")
    lock.release()


def test_telemetry_store(tmp_path: Path):
    db_file = tmp_path / "telemetry.sqlite"
    store = TelemetryStore(db_file)
    store.log_event("sess1", "task1", "cpo", "done", duration=1.5, cost=0.01)

    events = store.fetch_all()
    assert len(events) == 1
    assert events[0]["node"] == "cpo"


def test_security_scanner(tmp_path: Path):
    vuln_file = tmp_path / "bad.py"
    vuln_file.write_text("API_KEY = '12345678901234567890'\neval('1+1')\n")

    scanner = SecurityScanner()
    vulns = scanner.scan_directory(tmp_path)
    assert len(vulns) >= 2
