"""Analisador de padrões de erro e causas raiz de sessões de agentes."""

from typing import List, Tuple
from retro.store.models import PatternItem, SessionRecord


class SessionAnalyzer:
    def analyze(self, session: SessionRecord) -> List[PatternItem]:
        patterns: List[PatternItem] = []

        error_counts = {}
        for ev in session.events:
            if ev.type in ("node_error", "node_retry") and ev.error:
                err_text = ev.error.lower()
                category = "general-error"
                if "mock" in err_text or "database" in err_text or "db" in err_text:
                    category = "qa-db-mock"
                elif "import" in err_text or "module" in err_text:
                    category = "missing-import"
                elif "syntax" in err_text or "parse" in err_text:
                    category = "syntax-error"
                elif "type" in err_text or "attribute" in err_text:
                    category = "typing-mismatch"

                error_counts[category] = error_counts.get(category, 0) + 1

        for cat, freq in error_counts.items():
            impact = "high" if freq >= 2 else "medium"
            patterns.append(
                PatternItem(
                    pattern=cat,
                    frequency=freq,
                    impact=impact,
                    context=f"Ocorreu {freq}x durante os nós da sessão",
                )
            )

        if session.attempts > 2:
            patterns.append(
                PatternItem(
                    pattern="excessive-retries",
                    frequency=session.attempts,
                    impact="high",
                    context=f"Sessão exigiu {session.attempts} tentativas para aprovação",
                )
            )

        return patterns
