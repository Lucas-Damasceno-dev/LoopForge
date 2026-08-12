"""API de avaliações (evals) da telemetria de benchmarks (ADE — EvalsPanel).

Scaffold: router vazio, implementado pela lane de evals (engine + ADE).
Contrato previsto:
  GET /api/v1/evals/summary  → métricas agregadas (runs, pass rate, custo, ELO)
  GET /api/v1/evals/leaderboard → ranking de agentes/benchmarks
Auth aplicada no include (app.py), padrão dos demais routers.
"""

from fastapi import APIRouter

evals_router = APIRouter(prefix="/api/v1/evals", tags=["Evals"])
