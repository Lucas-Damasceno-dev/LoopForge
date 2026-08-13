"""
Slice de entrega incremental por user story (milestone v7 item 5.1).

Um "slice" é UMA user story com seu contrato de testes e metadados de
progresso. O pipeline gera/valida um slice por vez; o contrato de testes do
slice é escrito em ``tests/slices/slice_{NN}/`` para o QA classificar falhas
do slice corrente vs. regressão (falhas de slices anteriores).
"""

from __future__ import annotations

from typing import Any


def build_slices(user_stories: list, contract_map: dict | None = None, max_slices: int = 8) -> list[dict]:
    """Deriva a lista de slices incrementais a partir das user stories.

    Cada slice = ``{"story": <dict da story>, "modules": [...], "contract_tests":
    "", "status": "pending", "attempts": 0, "test_report": {}}``.

    ``contract_map`` (opcional) permite semear o contrato de testes por story_id
    (ex.: resume de uma run em andamento). ``max_slices`` capa a derivação
    (AdePipeline.max_slices, default 8) — stories além do limite ficam fora.
    """
    slices: list[dict[str, Any]] = []
    for us in (user_stories or [])[:max_slices]:
        story = dict(us)
        contract_tests = ""
        if contract_map:
            contract_tests = str(contract_map.get(story.get("id"), "") or "")
        slices.append(
            {
                "story": story,
                "modules": [],
                "contract_tests": contract_tests,
                "status": "pending",
                "attempts": 0,
                "test_report": {},
            }
        )
    return slices


def slice_dir_name(slice_index: int) -> str:
    """Nome do diretório do slice (``slice_00``, ``slice_01``, ...)."""
    return f"slice_{int(slice_index):02d}"
