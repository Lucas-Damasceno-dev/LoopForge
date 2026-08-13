"""Router de terminal e execução ad-hoc de comandos no workspace da run."""

import asyncio
import logging
import shlex
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.database import get_session
from lf.api.models import PipelineRun
from lf.api.schemas import ExecCommandRequest, ExecCommandResponse, TerminalInfoResponse

logger = logging.getLogger(__name__)

terminal_router = APIRouter(prefix="/api/v1/terminal", tags=["Terminal"])

_FORBIDDEN_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "shutdown",
    "reboot",
    ":(){ :|:& };:",
}


def _find_run_dir(run_id: str) -> Path | None:
    d1 = Path(f"/tmp/loopforge/run_{run_id}")
    if d1.exists() and d1.is_dir():
        return d1
    d2 = Path(f".loopforge/worktrees/run_{run_id}")
    if d2.exists() and d2.is_dir():
        return d2
    return None


@terminal_router.get("/{run_id}/info", response_model=TerminalInfoResponse)
async def get_terminal_info(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> TerminalInfoResponse:
    """Retorna informações do workspace para o terminal da run."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = _find_run_dir(run_id)
    return TerminalInfoResponse(
        run_id=run_id,
        workspace_path=str(run_dir.resolve()) if run_dir else None,
        exists=run_dir is not None,
    )


@terminal_router.post("/{run_id}/exec", response_model=ExecCommandResponse)
async def exec_workspace_command(
    run_id: str,
    payload: ExecCommandRequest,
    session: AsyncSession = Depends(get_session),
) -> ExecCommandResponse:
    """Executa um comando não-interativo no diretório de trabalho da run."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = _find_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Workspace directory not found for this run")

    raw_cmd = payload.command.strip()
    if not raw_cmd:
        raise HTTPException(status_code=400, detail="Command cannot be empty")

    for forbidden in _FORBIDDEN_COMMANDS:
        if forbidden in raw_cmd:
            raise HTTPException(status_code=400, detail=f"Command '{forbidden}' is forbidden for security")

    start_time = time.time()
    try:
        proc = await asyncio.create_subprocess_shell(
            raw_cmd,
            cwd=str(run_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(payload.timeout_seconds),
            )
            stdout = stdout_bytes.decode(errors="replace")
            stderr = stderr_bytes.decode(errors="replace")
            exit_code = proc.returncode if proc.returncode is not None else -1
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            stdout = ""
            stderr = f"Command timed out after {payload.timeout_seconds} seconds."
            exit_code = 124
    except Exception as exc:
        stdout = ""
        stderr = f"Failed to start process: {exc}"
        exit_code = 1

    duration = round(time.time() - start_time, 3)

    return ExecCommandResponse(
        run_id=run_id,
        command=raw_cmd,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        duration_seconds=duration,
    )
