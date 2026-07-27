def format_test_summary(total: int, passed: int, failed: int) -> str:
    if failed == 0:
        return f"✅ PASSED ({passed}/{total} tests passed)"
    return f"❌ FAILED ({failed}/{total} tests failed)"
