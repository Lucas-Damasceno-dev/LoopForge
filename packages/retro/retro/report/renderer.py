"""Renderizador de relatórios Markdown (retro.md)."""

import os
from retro.store.models import LearningItem, PatternItem, RetroReport, SessionRecord


class RetroRenderer:
    def render(self, session: SessionRecord, patterns: list[PatternItem], learnings: list[LearningItem]) -> RetroReport:
        duration_sec = session.duration_ms / 1000.0 if session.duration_ms else 0.0
        dur_fmt = f"{duration_sec:.1f}s" if duration_sec < 60 else f"{duration_sec / 60:.1f}min"
        cost_fmt = f"${session.cost:.2f}"

        pat_lines = []
        if patterns:
            for p in patterns:
                pat_lines.append(f"- **{p.pattern}** (impacto: {p.impact}): {p.context}")
        else:
            pat_lines.append("- Nenhum padrão de erro crítico detectado.")

        learn_lines = []
        if learnings:
            for l in learnings:
                override_str = f" → Override: `{l.prompt_override}`" if l.prompt_override else ""
                learn_lines.append(f"- [{l.category.upper()} / {l.stack}]: {l.recommendation}{override_str}")
        else:
            learn_lines.append("- Nenhum novo aprendizado registrado.")

        summary_md = f"""# 🧠 Agentic Retro — Relatório de Sessão

**Sessão**: `{session.session_id}`  
**Objetivo**: `{session.goal}`  
**Resultado**: `{session.status}` | **Duração**: `{dur_fmt}` | **Custo**: `{cost_fmt}`

---

## 📊 Métricas da Execução
- **Tentativas / Retries**: {session.attempts}
- **Eventos Registrados**: {len(session.events)}

---

## 🔍 Padrões & Causas Raiz Detectados
{chr(10).join(pat_lines)}

---

## 💡 Aprendizados Realimentáveis
{chr(10).join(learn_lines)}
"""
        return RetroReport(
            session_id=session.session_id,
            goal=session.goal,
            status=session.status,
            duration_formatted=dur_fmt,
            cost_formatted=cost_fmt,
            summary_md=summary_md,
            patterns=patterns,
            learnings=learnings,
        )
