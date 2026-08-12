"""
Nó Tech Lead: valida user stories, decide a melhor stack tecnológica e gera especificação técnica.
Usa template tech_spec_template.md do The Foundry e Pydantic para feedback.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...pipeline.prompt_overrides import get_effective_prompt
from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


DEFAULT_PROMPT = """Você é um Tech Lead. Revise as user stories e recomende a melhor stack.

Analise o problema e recomende a melhor stack (linguagem + framework + ferramentas). Considere:
- Tipo de projeto e escopo
- Performance e segurança necessárias
- Ecossistema e produtividade

Responda com:
- needs_feedback: true se alguma história precisa de revisão
- feedback_message: feedback detalhado
- approved_stories: IDs das histórias aprovadas
- recommended_stack: linguagem ou stack recomendada (ex: python, rust, java, javascript, go)"""


def _truncate_template_at_section_boundary(tech_spec_template: str, max_chars: int = 1500) -> str:
    """Evita truncar o template no meio de seções Markdown para manter contexto coerente."""
    if len(tech_spec_template) <= max_chars:
        return tech_spec_template

    prefix = tech_spec_template[:max_chars]
    header_pattern = r"(?m)^\s{0,3}#{2,3}\s+"
    headers = list(__import__("re").finditer(header_pattern, prefix))

    if not headers:
        return prefix

    for header in reversed(headers):
        if header.start() == 0:
            continue
        next_header = __import__("re").search(header_pattern, tech_spec_template[header.start() + 1 :])
        section_end = len(tech_spec_template) if next_header is None else header.start() + 1 + next_header.start()
        if section_end <= max_chars:
            return tech_spec_template[:section_end]
    return tech_spec_template[: headers[-1].start()]


class ValidationResult(BaseModel):
    """Resultado da validação do Tech Lead sobre as user stories."""

    needs_feedback: bool = Field(..., description="True se user stories precisam de revisão")
    feedback_message: str = Field(..., description="Feedback detalhado para o PM")
    approved_stories: list[str] = Field(default_factory=list, description="IDs das histórias aprovadas")
    recommended_stack: str = Field("python", description="Stack recomendada (ex: python, rust, java, javascript, go)")
    stack_rationale: str = Field(
        "Stack selecionada com base no escopo e maturidade do ecossistema.",
        description="Justificativa técnica da escolha da stack",
    )


def _extract_stack_from_text(text: str) -> str:
    """Extrai a linguagem/stack principal recomendada no texto da tech spec."""
    import re

    text_lower = text.lower()

    # 1. Detecção de framework/stack específico primeiro (mais preciso).
    #    'typescript' antes do grupo JS para priorizá-lo quando presente.
    framework_map = [
        ("typescript", "typescript"),
        ("fastapi", "python"),
        ("django", "python"),
        ("flask", "python"),
        ("pandas", "python"),
        ("pytest", "python"),
        ("spring", "java"),
        ("junit", "java"),
        ("actix", "rust"),
        ("gin", "go"),
        ("express", "javascript"),
        ("react", "javascript"),
        ("next.js", "javascript"),
        ("node", "javascript"),
    ]
    for marker, stack in framework_map:
        if marker in text_lower:
            return stack

    # 2. Linguagens com match de palavra inteira (evita 'go' dentro de 'logout').
    for lang in ("rust", "python", "java", "javascript", "typescript", "go", "csharp", "ruby", "php"):
        if re.search(rf"\b{lang}\b", text_lower):
            return lang
    return "python"


def tech_lead(state: GraphState) -> dict:
    """Valida user stories, decide a stack do projeto e gera tech spec."""
    print("---EXECUTANDO NÓ: Tech Lead---")

    user_stories = state.get("user_stories", [])
    idea = state.get("idea", "")
    current_stack = state.get("stack")  # Se informado pelo usuário via CLI override

    # Reutiliza tech spec se já gerada em etapa anterior do plano
    if state.get("tech_spec"):
        print("--- INFO: Tech Lead reutilizando Tech Spec existente no estado ---")
        decided_stack = current_stack or _extract_stack_from_text(state["tech_spec"])
        return {**state, "stack": decided_stack, "next_agent": "test_writer"}

    now_iso = datetime.now(UTC).isoformat()
    now_date = now_iso.split("T")[0]

    # Carrega template tech_spec.md do Foundry se disponível
    template_path = (
        Path(state.get("ontology_path", "examples/the-foundry"))
        / "company_context/shared_knowledge/artifact_templates/tech_spec_template.md"
    )
    if template_path.exists():
        tech_spec_template = template_path.read_text(encoding="utf-8")
    else:
        tech_spec_template = "# Especificação Técnica: {title}\n\n## Visão Geral\n{description}\n\n## Arquitetura\n{architecture}\n\n## Stack Recomendada\n{stack}\n\n## User Stories\n{user_stories}\n\n## Decisões\n{decisions}"

    if state.get("mock_llm"):
        print("--- INFO: Tech Lead modo MOCK ---")
        decided_stack = current_stack or _extract_stack_from_text(idea) or "python"
        tech_spec = _mock_tech_spec(user_stories, tech_spec_template, now_date, decided_stack)
        return {**state, "stack": decided_stack, "tech_spec": tech_spec, "next_agent": "test_writer"}

    print("--- INFO: Tech Lead analisando problema e decidindo stack ---")

    stories_str = "\n".join(
        f"{us.get('id', 'N/A')}: {us.get('title', '')} — {us.get('as_a', '')} quer {us.get('i_want_to', '')} para {us.get('so_that', '')}"
        for us in user_stories
    )

    # Fase 1: Validar user stories e recomendar stack
    decided_stack = current_stack
    new_feedback = list(state.get("feedback_history", []))

    try:
        validation = call_llm_via_opencode(
            system_prompt=get_effective_prompt("tech_lead", DEFAULT_PROMPT),
            user_prompt=f"Ideia do Projeto: {idea}\n\nUser Stories:\n{stories_str}",
            schema_model=ValidationResult,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )

        if not decided_stack:
            decided_stack = validation.get("recommended_stack", "python")

        if validation.get("needs_feedback"):
            feedback_msg = validation.get("feedback_message", "")
            print("--- AVISO: Tech Lead solicita feedback: ---")
            print(f"--- {feedback_msg[:500]} ---")
            new_feedback.append({"from": "tech_lead", "message": feedback_msg, "timestamp": now_iso})
    except Exception as e:
        print(f"--- ERRO TL validação: {e} ---")
        if not decided_stack:
            decided_stack = _extract_stack_from_text(idea) or "python"

    # Fase 2: Gerar tech spec
    print(f"--- Gerando especificação técnica (Stack decidida pelo TL: {decided_stack}) ---")

    try:
        truncated_template = _truncate_template_at_section_boundary(tech_spec_template, 1500)
        truncated_stories = "\n".join(f"{us.get('id', '')}: {us.get('title', '')}" for us in user_stories[:5])
        # 🧠 Injeta lições da memória no Tech Lead
        memory_txt = ""
        try:
            from ...memory.manager import MemoryManager

            mem = MemoryManager()
            lessons = mem.search_relevant_lessons(query=idea, stack=decided_stack, limit=3)
            memory_txt = mem.format_lessons_for_prompt(lessons)
        except Exception:
            pass

        user_prompt_str = f"Ideia do Projeto: {idea}\nStack: {decided_stack}\n\nUser Stories:\n{truncated_stories}"
        if memory_txt:
            user_prompt_str += f"\n\n{memory_txt}"

        tech_spec = call_llm_via_opencode(
            system_prompt="""Você é um Tech Lead Sênior. Escreva uma especificação técnica (Tech Spec) completa e detalhada em Markdown.
Use o template fornecido como guia. Seja técnico, preciso e inclua decisões de arquitetura e modelo de dados.

DIRETRIZES ARQUITETURAIS LIMPAS (CLEAN ARCHITECTURE POR STACK):
Especifique obrigatoriamente a estrutura de diretórios sugerida no projeto conforme a stack:
- Rust: src/domain/, src/adapters/, src/ports/, src/entrypoints/, tests/
- Python (FastAPI): src/core/, src/services/, src/api/, src/repositories/, tests/
- TypeScript/Node: src/domain/, src/usecases/, src/infrastructure/, src/http/, tests/
- Go: internal/domain/, internal/service/, internal/handler/, internal/repository/, pkg/

Template (use como guia):
"""
            + truncated_template,
            user_prompt=user_prompt_str,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )
    except Exception as e:
        print(f"--- ERRO TL tech spec: {e} ---")
        tech_spec = _mock_tech_spec(user_stories, tech_spec_template, now_date, decided_stack)

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        epic_id = user_stories[0].get("epic_id", "UNKNOWN") if user_stories else "UNKNOWN"
        path = os.path.join(output_dir, f"tech_spec_{epic_id}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tech_spec)
        print(f"--- INFO: Tech spec salva em {path} ---")

    if "validation" in locals() and isinstance(validation, dict):
        rationale = validation.get(
            "stack_rationale", f"Stack '{decided_stack}' escolhida por adequação técnica aos requisitos."
        )
    else:
        rationale = f"Stack '{decided_stack}' selecionada por requisitos de arquitetura."

    return {
        **state,
        "stack": decided_stack,
        "stack_rationale": rationale,
        "tech_spec": tech_spec,
        "feedback_history": new_feedback,
        "next_agent": "test_writer",
    }


def _mock_tech_spec(user_stories: list[dict], template: str, date: str, stack: str = "python") -> str:
    epic_id = user_stories[0].get("epic_id", "UNKNOWN") if user_stories else "UNKNOWN"
    stories_list = "\n".join(f"- {us.get('id', '')}: {us.get('title', '')}" for us in user_stories)

    return (
        template.format(
            title=f"Especificação Técnica para Épico {epic_id}",
            description="Descrição técnica",
            architecture="Arquitetura a ser definida",
            stack=f"Stack decidida pelo Tech Lead: {stack}",
            user_stories=stories_list,
            decisions="Decisões arquiteturais",
        )
        if "{title}" in template
        else f"""# Especificação Técnica - {epic_id}

**Data:** {date}
**Status:** Approved

## User Stories
{stories_list}

## Stack Decidida pelo Tech Lead
- Linguagem/Framework: {stack}

## Decisões
- Implementar projeto multi-arquivo completo com testes automatizados.
"""
    )
