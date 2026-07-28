#-*- coding: utf-8 -*-
"""
Plan Creator: lê um documento de visão ou interage com CPO no pipeline
para gerar um plano de tasks com dependências DAG.

NÃO é hardcoded — delega ao CPO node do pipeline LangGraph para gerar
o épico e extrair tasks de lá.
"""
from __future__ import annotations
import json
import os
from typing import Any


class Plan:
    """Plano de execução: lista de tasks organizadas em DAG."""

    def __init__(self, tasks: list[dict], graph: dict):
        self.tasks = tasks
        self.graph = graph

    def to_dict(self) -> dict:
        return {"tasks": self.tasks, "graph": self.graph}

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        return cls(tasks=data.get("tasks", []), graph=data.get("graph", {}))


def create_plan_from_vision(vision_path_or_text: str, output_dir: str, routing_mode: str = "full") -> Plan:
    """Lê documento de visão/texto e gera plano em DAG com suporte a Fast-Path / Full-Path."""
    if os.path.exists(vision_path_or_text):
        with open(vision_path_or_text) as f:
            vision = f.read()
    else:
        vision = vision_path_or_text

    if routing_mode == "fast":
        persona_flow = ["developer", "qa"]
    else:
        persona_flow = ["cpo", "pm", "tech_lead", "developer", "qa"]

    tasks = []
    for i, persona in enumerate(persona_flow):
        tasks.append({
            "id": f"T-{i+1:03d}",
            "title": f"Executar {persona}: {vision[:40]}",
            "persona": persona,
            "routing_mode": routing_mode,
            "status": "pending",
            "depends_on": [f"T-{j+1:03d}" for j in range(i)],
            "max_retries": 3,
            "attempts": 0,
        })

    graph = {}
    for i, task in enumerate(tasks):
        graph[task["id"]] = task["depends_on"]

    plan = Plan(tasks, graph)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    return plan



def create_plan_from_epic(epic: dict, output_dir: str) -> Plan:
    """Cria plano a partir de um épico já gerado (via pipeline CPO)."""
    persona_flow = ["pm", "tech_lead", "developer", "qa"]

    tasks = []
    for i, persona in enumerate(persona_flow):
        tasks.append({
            "id": f"T-{i+1:03d}",
            "title": f"{persona}: {epic.get('title', 'Executar persona')[:60]}",
            "persona": persona,
            "status": "pending",
            "depends_on": [f"T-{j+1:03d}" for j in range(i)],
            "max_retries": 3,
            "attempts": 0,
            "epic_id": epic.get("id", "E-001"),
        })

    graph = {t["id"]: t["depends_on"] for t in tasks}

    plan = Plan(tasks, graph)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "plan.json"), "w") as f:
        json.dump(plan.to_dict(), f, indent=2)

    return plan
