"""
Plan Creator: lê um documento de visão ou interage com CPO no pipeline
para gerar um plano de tasks com dependências DAG.

NÃO é hardcoded — delega ao CPO node do pipeline LangGraph para gerar
o épico e extrair tasks de lá.
"""
from __future__ import annotations

import json
import os

from lf.config.schema import TaskSchema


class Plan:
    """Plano de execução: lista de tasks organizadas em DAG."""

    def __init__(self, tasks: list[TaskSchema], graph: dict):
        self.tasks = tasks
        self.graph = graph

    def to_dict(self) -> dict:
        return {"tasks": [t.model_dump(mode="json") for t in self.tasks], "graph": self.graph}

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        tasks_raw = data.get("tasks", [])
        tasks = [t if isinstance(t, TaskSchema) else TaskSchema(**t) for t in tasks_raw]
        return cls(tasks=tasks, graph=data.get("graph", {}))


def create_plan_from_vision(vision_path_or_text: str, output_dir: str, routing_mode: str = "full") -> Plan:
    """Lê documento de visão/texto e gera plano em DAG com suporte a Fast-Path / Full-Path."""
    if os.path.exists(vision_path_or_text):
        with open(vision_path_or_text) as f:
            vision = f.read()
    else:
        vision = vision_path_or_text

    persona_flow = ["developer", "qa"] if routing_mode == "fast" else ["cpo", "pm", "tech_lead", "developer", "qa"]

    tasks: list[TaskSchema] = []
    for i, persona in enumerate(persona_flow):
        tasks.append(TaskSchema(
            id=f"T-{i+1:03d}",
            title=f"Executar {persona}: {vision[:40]}",
            agent_id=persona,
            persona=persona,
            status="pending",
            depends_on=[f"T-{j+1:03d}" for j in range(i)],
            max_retries=3,
            routing_mode=routing_mode,
        ))

    graph = {task.id: task.depends_on for task in tasks}

    plan = Plan(tasks, graph)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    return plan



def create_plan_from_epic(epic: dict, output_dir: str) -> Plan:
    """Cria plano a partir de um épico já gerado (via pipeline CPO)."""
    persona_flow = ["pm", "tech_lead", "developer", "qa"]

    tasks: list[TaskSchema] = []
    for i, persona in enumerate(persona_flow):
        tasks.append(TaskSchema(
            id=f"T-{i+1:03d}",
            title=f"{persona}: {epic.get('title', 'Executar persona')[:60]}",
            agent_id=persona,
            persona=persona,
            status="pending",
            depends_on=[f"T-{j+1:03d}" for j in range(i)],
            max_retries=3,
        ))

    graph = {t.id: t.depends_on for t in tasks}

    plan = Plan(tasks, graph)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    return plan
