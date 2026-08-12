"""
Nó Test Writer: gera suíte de testes-contrato a partir de user stories e critérios de aceitação.
"""

from __future__ import annotations

import os
from pathlib import Path

from ...pipeline.prompt_overrides import get_effective_prompt
from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode
from .developer import _parse_multi_file_response

DEFAULT_PROMPT = (
    "Você é um Engenheiro de Testes Sênior. Escreva UMA SÚITE DE TESTES UNITÁRIOS "
    "(somente testes, NUNCA código de implementação) que cubra cada acceptance criterion "
    "de cada user story. Para cada critério, deve existir pelo menos 1 teste que FALHA "
    "quando o requisito não está implementado. Use o framework de testes da stack: pytest "
    "(python), junit (java), cargotest (rust), gotest (go), vitest (js/ts). Responda no "
    "formato multi-arquivos '### FILE: tests/...' seguido por bloco de código."
)

# Primeiro segmento de imports que NÃO representa módulo interno da aplicação:
# stdlib e bibliotecas de terceiros comuns. Módulos fora desta denylist com >=2
# segmentos (ex.: `app.services.payment`) são considerados internos e entram
# no inventário declarado ao Developer via '### MODULES:'.
_IMPORT_DENYLIST = frozenset(
    {
        "os",
        "sys",
        "json",
        "re",
        "pathlib",
        "typing",
        "datetime",
        "uuid",
        "pytest",
        "unittest",
        "fastapi",
        "flask",
        "django",
        "numpy",
        "pydantic",
        "httpx",
        "requests",
        "time",
        "collections",
        "functools",
        "itertools",
        "enum",
        "dataclasses",
        "logging",
        "math",
        "random",
        "string",
        "secrets",
        "hashlib",
        "subprocess",
        "contextlib",
        "warnings",
        "abc",
        "inspect",
    }
)


def _extract_module_inventory(files_map: dict[str, str]) -> list[str]:
    """Extrai o inventário de módulos internos importados pelos testes-contrato.

    Heurística: inclui imports com >=2 segmentos cujo primeiro segmento NÃO está
    na denylist de stdlib/terceiros comuns; exclui imports relativos ('.').
    Deduplica preservando a ordem de aparição. O Developer usa essa lista para
    nomear módulos com os nomes EXATOS (evita plural/singular divergentes).
    """
    modules: list[str] = []
    seen: set[str] = set()

    def _add(module: str) -> None:
        if module not in seen:
            seen.add(module)
            modules.append(module)

    for content in files_map.values():
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("from "):
                head = stripped[5:].split(None, 1)
                module = head[0].strip() if head else ""
            elif stripped.startswith("import "):
                first = stripped[7:].strip().split(",", 1)[0].strip()
                module = first.split(None, 1)[0].strip() if first else ""
            else:
                continue
            if not module or module.startswith("."):
                continue
            segments = module.split(".")
            if len(segments) < 2:
                continue
            if segments[0] in _IMPORT_DENYLIST:
                continue
            _add(module)

    return modules


def test_writer(state: GraphState) -> dict:
    """Gera testes-contrato independentes e grava em output_dir/tests/."""
    print("---EXECUTANDO NÓ: Test Writer---")

    user_stories = state.get("user_stories", [])
    has_acceptance_criteria = any(
        isinstance(us.get("acceptance_criteria"), list) and len(us.get("acceptance_criteria")) > 0
        for us in user_stories
    )

    if not user_stories or not has_acceptance_criteria:
        print("--- INFO: Test Writer: sem critérios de aceitação, pulando geração de testes-contrato ---")
        return {**state, "next_agent": "developer", "contract_tests": ""}

    stack = str(state.get("stack", "python")).lower()
    tech_spec = str(state.get("tech_spec", ""))
    output_dir = state.get("output_dir") or "."

    stories_lines: list[str] = []
    for us in user_stories:
        criteria = us.get("acceptance_criteria")
        if isinstance(criteria, list) and criteria:
            stories_lines.append(f"- ID: {us.get('id', 'N/A')}")
            stories_lines.append(f"  Título: {us.get('title', '')}")
            stories_lines.append("  Critérios de aceitação:")
            for c in criteria:
                stories_lines.append(f"  - {c}")

    system_prompt = get_effective_prompt("test_writer", DEFAULT_PROMPT)
    user_prompt = (
        f"Stack: {stack}\n\n"
        f"User Stories com critérios:\n{chr(10).join(stories_lines)}\n\n"
        f"Tech Spec (truncada):\n{tech_spec[:2000]}"
    )

    try:
        raw = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
            project_root=output_dir,
        )
        if not isinstance(raw, str):
            raw = str(raw)
    except Exception as exc:
        print(f"--- AVISO: Test Writer falhou ao chamar LLM: {exc} ---")
        return {**state, "next_agent": "developer", "contract_tests": ""}

    try:
        files_map = _parse_multi_file_response(raw)
    except Exception as exc:
        print(f"--- AVISO: Test Writer falhou ao parsear resposta multi-arquivos: {exc} ---")
        return {**state, "next_agent": "developer", "contract_tests": ""}

    if not files_map:
        print("--- AVISO: Test Writer não encontrou arquivos de teste na resposta da LLM ---")
        return {**state, "next_agent": "developer", "contract_tests": ""}

    tests_root = Path(output_dir) / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)

    written_files: dict[str, str] = {}
    written = 0
    for rel_path, content in files_map.items():
        normalized = os.path.normpath(rel_path).replace("\\", "/")
        name_lower = Path(normalized).name.lower()
        if not normalized.startswith("tests/") and not normalized.startswith("tests\\"):
            continue
        if "test" not in name_lower:
            continue

        destination = Path(output_dir) / normalized
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        written_files[normalized] = content
        written += 1
        print(f"--- INFO: Test Writer salvou teste-contrato: {destination} ({len(content)} chars) ---")

    if written == 0:
        print("--- AVISO: Test Writer não gravou nenhum arquivo válido de teste-contrato ---")
        return {**state, "next_agent": "developer", "contract_tests": ""}

    # Declara o inventário de módulos internos importados pelos testes para o
    # Developer nomear módulos com os nomes EXATOS (respeitando singular/plural).
    modules = _extract_module_inventory(written_files)
    contract_tests = raw
    if modules:
        contract_tests = raw + "\n\n### MODULES: " + ", ".join(modules)

    return {**state, "next_agent": "developer", "contract_tests": contract_tests}


test_writer.__test__ = False
