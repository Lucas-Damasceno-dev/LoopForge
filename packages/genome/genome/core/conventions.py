"""Indução de convenções semânticas do repositório."""

from typing import List
from genome.store.models import ConventionDetail, Conventions, ModuleInfo


def infer_conventions(modules: List[ModuleInfo]) -> Conventions:
    testing_info = {}
    error_handling = None

    pytest_count = 0
    vitest_count = 0

    for mod in modules:
        if "test" in mod.path or "spec" in mod.path:
            if mod.language == "python":
                pytest_count += 1
            elif mod.language == "typescript":
                vitest_count += 1

    if pytest_count > 0:
        testing_info = {"framework": "pytest", "location": "tests/"}
    elif vitest_count > 0:
        testing_info = {"framework": "vitest", "location": "__tests__/"}

    # Inferência simples de tratamento de erro
    error_handling = ConventionDetail(pattern="standard-exceptions", usage_rate=0.90)

    return Conventions(
        error_handling=error_handling,
        testing=testing_info if testing_info else None,
    )
