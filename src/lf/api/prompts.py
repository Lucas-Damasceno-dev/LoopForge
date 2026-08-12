"""Rotas Prompt Central (ADE — PromptPanel).

Endpoints:
  GET    /api/v1/prompts          → lista [{node, prompt}] do prompt EFETIVO
                                    (override se houver, senão default do nó)
  PATCH  /api/v1/prompts/{node}   → salva override do prompt do nó
  DELETE /api/v1/prompts/{node}   → remove override (404 se não existir)
Auth aplicada no include (app.py), padrão dos demais routers.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..pipeline.prompt_overrides import (
    PROMPT_NODES,
    delete_prompt_override,
    list_effective_prompts,
    set_prompt_override,
)

prompts_router = APIRouter(prefix="/api/v1/prompts", tags=["Prompts"])


# ─── Schemas ─────────────────────────────────────────────────────────────
class PromptOverride(BaseModel):
    """Payload para salvar um override de prompt (PATCH)."""

    prompt: str = Field(..., min_length=1, description="Novo prompt do nó (não pode ser vazio)")


class PromptEntry(BaseModel):
    """Prompt efetivo de um nó (GET)."""

    node: str = Field(..., description="Nome do nó da esteira")
    prompt: str = Field(..., description="Prompt efetivo (override ou default)")


# ─── Endpoints ───────────────────────────────────────────────────────────
@prompts_router.get("", response_model=list[PromptEntry])
def list_prompts() -> list[dict]:
    """Lista o prompt efetivo de cada nó (override ou default embutido)."""
    return list_effective_prompts()


@prompts_router.patch("/{node}", response_model=PromptEntry)
def save_prompt_override(node: str, payload: PromptOverride) -> dict:
    """Salva (ou sobrescreve) o override do prompt do nó."""
    if node not in PROMPT_NODES:
        raise HTTPException(status_code=404, detail=f"Nó desconhecido: '{node}'.")
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt não pode ser vazio.")
    set_prompt_override(node, prompt)
    return {"node": node, "prompt": prompt}


@prompts_router.delete("/{node}")
def remove_prompt_override(node: str) -> dict:
    """Remove o override do prompt do nó (volta ao default embutido)."""
    if node not in PROMPT_NODES:
        raise HTTPException(status_code=404, detail=f"Nó desconhecido: '{node}'.")
    if not delete_prompt_override(node):
        raise HTTPException(status_code=404, detail=f"Nenhum override para '{node}'.")
    return {"deleted": True}
