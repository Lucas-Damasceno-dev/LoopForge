"""Módulo da SPA React do LoopForge (M-16/B4).

O dist compilado da SPA é embutido no pacote na tarefa B5
(``src/lf/ade/static/``); este módulo localiza esse dist em call-time e monta
``/app`` (StaticFiles com ``html=True``) quando disponível, incluindo o
fallback SPA para deep-links. Sem dist, o dashboard legado continua sendo o
único front-end servido e nada quebra (apenas um warning no log).
"""

import importlib.util
import logging
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

logger = logging.getLogger(__name__)


class _SPAStaticFiles(StaticFiles):
    """StaticFiles com fallback SPA.

    ``html=True`` puro do Starlette só serve ``index.html`` para diretórios e
    ``404.html`` para not found — rotas deep-link da SPA (ex.: /app/runs/xyz)
    dariam 404. Esta subclasse devolve o ``index.html`` para qualquer rota não
    encontrada (comportamento esperado de uma SPA client-side).
    """

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def resolve_spa_dist() -> Path | None:
    """Localiza o dist da SPA compilada, nesta ordem:

    1. Env ``LF_SPA_DIST`` (path absoluto) — override de desenvolvimento;
    2. Pacote embutido ``lf.ade.static.dist`` se importável (B5);
    3. ``None`` — nenhum dist disponível (ex.: install sem a SPA).
    """
    env_dist = os.getenv("LF_SPA_DIST")
    if env_dist:
        return Path(env_dist).resolve()

    try:
        spec = importlib.util.find_spec("lf.ade.static.dist")
    except (ImportError, ValueError):
        spec = None
    if spec is not None and spec.submodule_search_locations:
        return Path(list(spec.submodule_search_locations)[0]).resolve()

    return None


def mount_spa(app) -> str | None:
    """Monta o dist da SPA em ``/app`` se existir; retorna o path ou ``None``.

    Cria o mount ``/app`` (rotas GET ``/app`` e ``/app/{path:path}``) com
    StaticFiles(html=True) + fallback SPA para deep-links. Sem dist (env
    ausente/inválido e pacote embutido inexistente), loga warning e NÃO monta —
    o backend segue íntegro (GET /app → 404).
    """
    dist = resolve_spa_dist()
    if dist is None or not dist.is_dir():
        logger.warning(
            "SPA dist não encontrado — /app não montado (defina LF_SPA_DIST "
            "ou embuta o pacote lf.ade.static.dist na tarefa B5)"
        )
        return None

    app.mount("/app", _SPAStaticFiles(directory=str(dist), html=True), name="spa")
    return str(dist)
