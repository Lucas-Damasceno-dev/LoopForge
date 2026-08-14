"""Testes de schema de agentes (S2 — CRUD de agentes).

Cobre AgentBase/AgentCreate/AgentUpdate/AgentResponse (validação pydantic v2)
e o modelo ORM AgentTemplate (colunas espelhando AgentBase, unique em name).
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lf.api.agents import AgentCreate, AgentResponse, AgentUpdate
from lf.api.models import AgentTemplate, Base


# ─── AgentCreate: validação ───────────────────────────────────────────────
def test_name_vazio_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="", prompt="rode o pipeline")


def test_prompt_vazio_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="dev", prompt="")


def test_temperature_negativa_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="dev", prompt="x", temperature=-0.1)


def test_temperature_acima_do_limite_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="dev", prompt="x", temperature=2.1)


def test_timeout_zero_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="dev", prompt="x", timeout_seconds=0)


def test_max_retries_negativo_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="dev", prompt="x", max_retries=-1)


def test_budget_negativo_falha():
    with pytest.raises(ValidationError):
        AgentCreate(name="dev", prompt="x", budget_usd=-0.01)


# ─── AgentCreate: defaults ────────────────────────────────────────────────
def test_defaults_corretos():
    agent = AgentCreate(name="dev", prompt="rode o pipeline")
    assert agent.description == ""
    assert agent.model == "default"
    assert agent.temperature == 0.7
    assert agent.max_retries == 2
    assert agent.timeout_seconds == 300
    assert agent.env_vars == {}
    assert agent.tools_allowlist == []
    assert agent.permissions == []
    assert agent.stack == "python"
    assert agent.budget_usd == 0.0


def test_valores_explicitos_aceitos():
    agent = AgentCreate(
        name="dev",
        prompt="x",
        description="agente dev",
        model="openrouter/auto",
        temperature=1.5,
        max_retries=5,
        timeout_seconds=120,
        env_vars={"OPENROUTER_MODEL": "x"},
        tools_allowlist=["bash"],
        permissions=["run"],
        stack="node",
        budget_usd=3.5,
    )
    assert agent.temperature == 1.5
    assert agent.max_retries == 5
    assert agent.env_vars == {"OPENROUTER_MODEL": "x"}


def test_temperature_no_limite_aceito():
    assert AgentCreate(name="dev", prompt="x", temperature=0.0).temperature == 0.0
    assert AgentCreate(name="dev", prompt="x", temperature=2.0).temperature == 2.0


# ─── AgentUpdate: PATCH-style (PUT com campos omitidos) ───────────────────
def test_update_todos_campos_none_valido():
    update = AgentUpdate()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_campos_parciais():
    update = AgentUpdate(temperature=1.1, permissions=["approve"])
    assert update.temperature == 1.1
    assert update.permissions == ["approve"]
    assert update.name is None
    assert update.prompt is None


def test_update_valida_campos_preenchidos():
    with pytest.raises(ValidationError):
        AgentUpdate(name="")
    with pytest.raises(ValidationError):
        AgentUpdate(temperature=3.0)


# ─── AgentResponse: id + timestamps ───────────────────────────────────────
def test_response_inclui_id_e_timestamps():
    now = datetime.now(UTC)
    resp = AgentResponse(
        id="abc-123",
        name="dev",
        prompt="x",
        created_at=now,
        updated_at=now,
    )
    assert resp.id == "abc-123"
    assert resp.created_at == now
    assert resp.updated_at == now
    assert isinstance(resp.created_at, datetime)


def test_response_model_validate_de_dict():
    now = datetime.now(UTC)
    data = {
        "id": "abc-123",
        "name": "dev",
        "prompt": "x",
        "created_at": now,
        "updated_at": now,
    }
    resp = AgentResponse.model_validate(data)
    assert resp.name == "dev"
    assert resp.temperature == 0.7  # default propagado via AgentBase
    assert resp.permissions == []


# ─── AgentTemplate: ORM ───────────────────────────────────────────────────
def test_agent_template_registrado_no_metadata():
    assert "agent_templates" in Base.metadata.tables
    table = Base.metadata.tables["agent_templates"]
    assert AgentTemplate.__tablename__ == "agent_templates"
    for col in (
        "id",
        "name",
        "description",
        "prompt",
        "model",
        "temperature",
        "max_retries",
        "timeout_seconds",
        "env_vars",
        "tools_allowlist",
        "permissions",
        "stack",
        "budget_usd",
        "created_at",
        "updated_at",
    ):
        assert col in table.columns, f"coluna ausente: {col}"


def test_agent_template_name_unique():
    table = Base.metadata.tables["agent_templates"]
    name_col = table.columns["name"]
    assert name_col.unique is True
