"""Gerador de recomendações acionáveis e otimizações de prompt."""

from typing import List
from retro.store.models import LearningItem, PatternItem, SessionRecord


class Recommender:
    def recommend(self, session: SessionRecord, patterns: List[PatternItem]) -> List[LearningItem]:
        learnings: List[LearningItem] = []

        stack = "python"
        if "rust" in session.goal.lower():
            stack = "rust"
        elif "go" in session.goal.lower():
            stack = "go"
        elif "java" in session.goal.lower():
            stack = "java"
        elif "js" in session.goal.lower() or "ts" in session.goal.lower():
            stack = "typescript"

        for pat in patterns:
            if pat.pattern == "qa-db-mock":
                learnings.append(
                    LearningItem(
                        category="testing",
                        stack=stack,
                        recommendation="Injetar precondição de Mock DB / Mock Fixtures no nó Developer e QA",
                        prompt_override="Garantir que todos os testes de integração usem mocks isolados para banco de dados.",
                    )
                )
            elif pat.pattern == "typing-mismatch":
                learnings.append(
                    LearningItem(
                        category="code-style",
                        stack=stack,
                        recommendation="Reforçar checagem de tipos estáticos antes de salvar os arquivos",
                        prompt_override="Utilizar typings rigorosos e verificar correspondência com contratos de interface.",
                    )
                )
            elif pat.pattern == "excessive-retries":
                learnings.append(
                    LearningItem(
                        category="workflow",
                        stack=stack,
                        recommendation="Adicionar checklist de auto-revisão no nó Developer antes do envio para QA",
                        prompt_override="Revise seu próprio código para erros sintáticos e de importação antes de concluir.",
                    )
                )

        if not learnings:
            learnings.append(
                LearningItem(
                    category="baseline",
                    stack=stack,
                    recommendation="Manter configuração atual do pipeline (desempenho limpo)",
                )
            )

        return learnings
