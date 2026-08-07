"""Endpoints de provedores LLM (auto-descoberta)."""
from fastapi import APIRouter, HTTPException

from lf.config.loader import load_ade_config
from lf.pipeline.providers.ollama import OllamaProvider

providers_router = APIRouter(prefix="/api/v1/providers", tags=["Providers"])


@providers_router.get("/ollama/models")
async def ollama_models():
    base_url = load_ade_config().providers.ollama_base_url
    try:
        return OllamaProvider(base_url=base_url).discover_models()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama indisponível em {base_url}") from exc
