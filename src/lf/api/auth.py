"""Autenticação e RBAC (Tier2) para a API do LoopForge.

Suporta HTTP Basic e header ``X-API-Key``. O principal é resolvido a partir
de uma store de keys: env ``LF_API_KEY`` (→ single key admin, BC) + bloco
``api_keys`` do ``ade.yaml`` (``AdeConfig.api_keys``, com roles por key).

A autorização é centralizada aqui (nada de editar routers): ``verify_authentication``
recebe o ``Request`` e checa método+path contra a matriz de roles abaixo.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from lf.api.config import APISettings
from lf.config.loader import load_ade_config

security_basic = HTTPBasic(auto_error=False)
security_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


# ─── Roles RBAC ──────────────────────────────────────────────────────
# Hierarquia: admin > runner > viewer.
_ROLE_LEVEL: dict[str, int] = {"viewer": 0, "runner": 1, "admin": 2}


@dataclass(frozen=True)
class Principal:
    """Identidade resolvida de uma API key (name + roles)."""

    name: str
    roles: tuple[str, ...]

    def has_role(self, required: str) -> bool:
        """True se o principal atende a role mínima exigida."""
        required_level = _ROLE_LEVEL.get(required, 0)
        return max(_ROLE_LEVEL.get(r, 0) for r in self.roles) >= required_level


# ─── Matriz de roles (path-prefix → role mínima) ─────────────────────
# Ordem importa: primeira regra que casar vence.
#
# ADMIN
#   - /api/v1/config        (GET/PATCH)   — administração de config
#   - /api/v1/mcp           (todos)       — administração/invocação de MCP
#   - .../cost e .../override (todos)     — custos + override de custo
#   - /api/v1/prompts       (PATCH/DELETE) — override/remoção de prompt
#   - /api/v1/memory        (DELETE)      — remoção de lesson
#   - /api/runs/*           (DELETE)      — remoção de run
# RUNNER
#   - /api/v1/runs, /api/runs (POST)      — criação de run
#   - .../resume, .../execute, .../decide (POST) — controle de run
#   - /api/runs/*           (PATCH)       — atualização de run
#   - /api/v1/trajectories  (POST import/fork)
#   - /api/v1/memory        (POST/PATCH)  — escrita de lessons
#   - /api/v1/prompts       (POST)
# VIEWER (default seguro)
#   - GET/HEAD/OPTIONS em qualquer rota autenticada (evals, git, providers,
#     timeline, checkpoints, export, listagens)
def _normalize_path(path: str) -> str:
    stripped = path.rstrip("/")
    return stripped or "/"


def _required_role(method: str, path: str) -> str:
    """Resolve a role mínima exigida para ``(method, path)``."""
    m = method.upper()
    p = _normalize_path(path)

    # ADMIN
    if m == "DELETE" and (p.startswith("/api/runs") or p.startswith("/api/v1/memory")):
        return "admin"
    if p.startswith("/api/v1/config"):
        return "admin"
    if p.startswith("/api/v1/mcp"):
        return "admin"
    if p.startswith("/api/v1/costs") or "/cost" in p:
        return "admin"
    if p.startswith("/api/v1/prompts") and m in ("PATCH", "DELETE"):
        return "admin"

    # RUNNER
    if p.startswith("/api/v1/memory") and m in ("POST", "PATCH"):
        return "runner"
    if p.startswith("/api/v1/prompts") and m in ("POST", "PUT"):
        return "runner"
    if m == "POST" and p in ("/api/v1/runs", "/api/runs"):
        return "runner"
    if m == "POST" and (p.endswith("/resume") or p.endswith("/execute") or p.endswith("/decide")):
        return "runner"
    if m == "PATCH" and p.startswith("/api/runs"):
        return "runner"
    if m == "POST" and p.startswith("/api/v1/trajectories") and (p.endswith("/import") or p.endswith("/fork")):
        return "runner"

    # VIEWER (default): leituras liberadas; escrita desconhecida exige runner.
    if m in ("GET", "HEAD", "OPTIONS"):
        return "viewer"
    return "runner"


# ─── Store de keys ───────────────────────────────────────────────────
def _key_store(settings: APISettings) -> dict[str, Principal]:
    """Monta a store key → Principal (env LF_API_KEY + ade.yaml api_keys).

    BC: env ``LF_API_KEY`` vira a única key admin. Se auth está ativa mas
    nenhuma key foi configurada, mantém o fallback legado ``"secret"`` (admin).
    """
    store: dict[str, Principal] = {}

    if settings.api_key:
        store[settings.api_key] = Principal(name="api-key-env", roles=("admin",))

    for item in load_ade_config().api_keys:
        # Keys do ade.yaml não sobrescrevem o env (env = admin canônico).
        store.setdefault(item.key, Principal(name=item.name, roles=tuple(item.roles)))

    if not store:
        store["secret"] = Principal(name="fallback", roles=("admin",))

    return store


def _auth_enabled(settings: APISettings) -> bool:
    """Auth ativa se require_auth, env key ou api_keys do ade.yaml existirem."""
    if settings.require_auth or settings.api_key:
        return True
    return bool(load_ade_config().api_keys)


def _resolve_principal(key: str | None, settings: APISettings) -> Principal | None:
    """Resolve ``key`` → Principal, ou None se desconhecida."""
    if key is None:
        return None
    return _key_store(settings).get(key)


def get_principal(api_key: str | None, settings: APISettings | None = None) -> Principal | None:
    """Helper público: resolve uma API key para o Principal (name + roles)."""
    return _resolve_principal(api_key, settings or APISettings())


def verify_authentication(
    request: Request,
    credentials: HTTPBasicCredentials | None = Security(security_basic),
    api_key_header: str | None = Security(security_api_key),
) -> bool:
    """Verifica autenticação (Basic ou X-API-Key) e aplica RBAC por método+path."""
    settings = APISettings()

    if not _auth_enabled(settings):
        return True

    # Resolve o principal: header X-API-Key primeiro; Basic aceita key no
    # username ou password (BC legado).
    principal = _resolve_principal(api_key_header, settings)
    if principal is None and credentials is not None:
        principal = _resolve_principal(credentials.username, settings)
        if principal is None:
            principal = _resolve_principal(credentials.password, settings)

    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas ou ausentes.",
            headers={"WWW-Authenticate": "Basic"},
        )

    required = _required_role(request.method, request.url.path)
    if not principal.has_role(required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Permissão insuficiente: role '{required}' exigida para "
                f"{request.method} {request.url.path} (principal '{principal.name}')."
            ),
        )

    return True
