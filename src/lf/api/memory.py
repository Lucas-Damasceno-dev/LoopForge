"""API de memória e lições aprendidas (ADE — MemoryPanel).

Endpoints:
  GET    /api/v1/memory/lessons?stack=&query=&limit=  → lista + busca por palavras-chave
  POST   /api/v1/memory/lessons                       → cria nova lição
  PATCH  /api/v1/memory/lessons/{id}                  → atualiza campos opcionais
  DELETE /api/v1/memory/lessons/{id}                  → remove lição
Auth aplicada no include (app.py), padrão dos demais routers.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..memory.manager import MemoryManager, cross_project_enabled

memory_router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])


# ─── Schemas ─────────────────────────────────────────────────────────────
class LessonCreate(BaseModel):
    """Payload para criar uma lição aprendida."""

    run_id: str = Field(..., description="Id da execução que gerou a lição")
    stack: str = Field(..., description="Stack tecnológica (ex.: python)")
    idea: str = Field(..., description="Ideia/contexto da lição")
    lesson_text: str = Field(..., description="Texto da lição aprendida")


class LessonUpdate(BaseModel):
    """Payload para atualizar campos opcionais de uma lição (PATCH)."""

    stack: str | None = Field(default=None, description="Nova stack")
    idea: str | None = Field(default=None, description="Nova ideia")
    lesson_text: str | None = Field(default=None, description="Novo texto da lição")


class LessonResponse(BaseModel):
    """Lição aprendida como devolvida pela API."""

    id: int = Field(..., description="Id interno da lição")
    run_id: str = Field(..., description="Id da execução que gerou a lição")
    stack: str = Field(..., description="Stack tecnológica (minúsculas)")
    idea: str = Field(..., description="Ideia/contexto da lição")
    lesson_text: str = Field(..., description="Texto da lição aprendida")
    created_at: float = Field(..., description="Timestamp de criação (epoch seconds)")


# ─── Endpoints ───────────────────────────────────────────────────────────
@memory_router.get("/lessons", response_model=list[LessonResponse])
def list_lessons_endpoint(
    stack: str | None = None,
    query: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    """Lista lições aprendidas com filtro opcional por stack e busca por palavras-chave.

    Com `query` presente, a busca reutiliza o ranqueamento por relevância do
    MemoryManager (search_relevant_lessons); o resultado final é ordenado por
    created_at DESC para apresentação consistente no painel.
    """
    manager = MemoryManager()
    if query and query.strip():
        lessons = manager.search_relevant_lessons(
            query.strip(),
            stack=stack,
            limit=limit,
            only_relevant=True,
        )
        lessons.sort(key=lambda item: item["created_at"], reverse=True)
    else:
        lessons = manager.list_lessons(stack=stack, limit=limit)
    return lessons


@memory_router.post("/lessons", response_model=LessonResponse, status_code=201)
def create_lesson_endpoint(payload: LessonCreate) -> dict:
    """Cria uma nova lição aprendida a partir do payload."""
    manager = MemoryManager()
    lesson = manager.save_lesson(
        run_id=payload.run_id,
        stack=payload.stack,
        idea=payload.idea,
        lesson_text=payload.lesson_text,
    )
    if lesson is None:
        raise HTTPException(status_code=422, detail="lesson_text não pode ser vazio.")
    return lesson


@memory_router.patch("/lessons/{lesson_id}", response_model=LessonResponse)
def update_lesson_endpoint(lesson_id: int, payload: LessonUpdate) -> dict:
    """Atualiza apenas os campos informados de uma lição existente."""
    manager = MemoryManager()
    lesson = manager.update_lesson(
        lesson_id,
        stack=payload.stack,
        idea=payload.idea,
        lesson_text=payload.lesson_text,
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lição não encontrada.")
    return lesson


@memory_router.delete("/lessons/{lesson_id}")
def delete_lesson_endpoint(lesson_id: int) -> dict:
    """Remove uma lição aprendida pelo id."""
    manager = MemoryManager()
    if not manager.delete_lesson(lesson_id):
        raise HTTPException(status_code=404, detail="Lição não encontrada.")
    return {"deleted": True}
