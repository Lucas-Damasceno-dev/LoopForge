"""Router e analisador de AST e grafo de dependências do código gerado pela IA."""

import ast
import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.database import get_session
from lf.api.models import PipelineRun
from lf.api.schemas import (
    AstAnalysisResponse,
    AstEdge,
    AstModuleInfo,
    AstSymbolInfo,
)

logger = logging.getLogger(__name__)

ast_router = APIRouter(prefix="/api/v1/ast", tags=["AST & Dependencies"])

_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".genome", ".registry", "node_modules", "dist", "build", ".venv"}

_PY_STD_LIBS = {
    "sys", "os", "io", "re", "json", "math", "random", "time", "datetime", "typing", "collections",
    "functools", "itertools", "pathlib", "sqlite3", "asyncio", "logging", "unittest", "shutil",
    "dataclasses", "enum", "uuid", "copy", "socket", "http", "urllib", "threading", "subprocess",
}


def _find_run_dir(run_id: str) -> Path | None:
    d1 = Path(f"/tmp/loopforge/run_{run_id}")
    if d1.exists() and d1.is_dir():
        return d1
    d2 = Path(f".loopforge/worktrees/run_{run_id}")
    if d2.exists() and d2.is_dir():
        return d2
    return None


def _analyze_python_file(rel_path: str, content: str) -> AstModuleInfo:
    symbols: list[AstSymbolInfo] = []
    imports: list[str] = []
    total_lines = len(content.splitlines())

    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                symbols.append(AstSymbolInfo(
                    name=node.name,
                    kind="class",
                    line_number=node.lineno,
                    docstring=doc[:120] if doc else None,
                ))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                symbols.append(AstSymbolInfo(
                    name=node.name,
                    kind=kind,
                    line_number=node.lineno,
                    docstring=doc[:120] if doc else None,
                ))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except Exception:
        # Fallback regex se ast.parse falhar (ex: sintaxe incompleta)
        for idx, line in enumerate(content.splitlines(), start=1):
            if line.strip().startswith("def "):
                fn_name = line.strip().split("(")[0].replace("def ", "").strip()
                symbols.append(AstSymbolInfo(name=fn_name, kind="function", line_number=idx))
            elif line.strip().startswith("class "):
                cls_name = line.strip().split("(")[0].split(":")[0].replace("class ", "").strip()
                symbols.append(AstSymbolInfo(name=cls_name, kind="class", line_number=idx))
            elif line.strip().startswith("import ") or line.strip().startswith("from "):
                parts = line.strip().split()
                if len(parts) >= 2:
                    imports.append(parts[1])

    symbols.sort(key=lambda s: s.line_number)
    return AstModuleInfo(
        file_path=rel_path,
        language="python",
        total_lines=total_lines,
        symbols=symbols,
        imports=list(dict.fromkeys(imports)),
    )


def _analyze_generic_file(rel_path: str, content: str, lang: str) -> AstModuleInfo:
    symbols: list[AstSymbolInfo] = []
    imports: list[str] = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, start=1):
        sline = line.strip()
        # Imports
        if sline.startswith("import ") or sline.startswith("from ") or sline.startswith("use ") or sline.startswith("require("):
            match = re.search(r"['\"]([^'\"]+)['\"]", sline)
            if match:
                imports.append(match.group(1))
            else:
                parts = sline.replace(";", "").split()
                if len(parts) >= 2:
                    imports.append(parts[1])
        # Classes / Structs / Interfaces
        if re.search(r"\b(class|struct|interface|trait|enum)\s+([A-Za-z0-9_]+)", sline):
            match = re.search(r"\b(class|struct|interface|trait|enum)\s+([A-Za-z0-9_]+)", sline)
            if match:
                symbols.append(AstSymbolInfo(name=match.group(2), kind=match.group(1), line_number=idx))
        # Functions / Methods
        elif re.search(r"\b(def|fn|func|function|public\s+\w+|async\s+function)\s+([A-Za-z0-9_]+)\s*\(", sline):
            match = re.search(r"\b(def|fn|func|function|public\s+\w+|async\s+function)\s+([A-Za-z0-9_]+)\s*\(", sline)
            if match:
                symbols.append(AstSymbolInfo(name=match.group(2), kind="function", line_number=idx))

    return AstModuleInfo(
        file_path=rel_path,
        language=lang,
        total_lines=len(lines),
        symbols=symbols,
        imports=list(dict.fromkeys(imports)),
    )


@ast_router.get("/{run_id}", response_model=AstAnalysisResponse)
async def get_run_ast_and_dependencies(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> AstAnalysisResponse:
    """Extrai estrutura sintática (classes, funções), dependências e grafo de módulos."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = _find_run_dir(run_id)
    if not run_dir:
        return AstAnalysisResponse(run_id=run_id, modules=[], external_packages=[], dependency_graph=[])

    modules: list[AstModuleInfo] = []
    local_module_names: set[str] = set()

    # Coleta arquivos e mapeia nomes locais
    files_to_parse: list[tuple[str, Path, str]] = []
    for root, dirs, files in os.walk(run_dir):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(run_dir).as_posix()
            ext = full.suffix.lower()
            if ext == ".py":
                files_to_parse.append((rel, full, "python"))
                local_module_names.add(full.stem)
                local_module_names.add(rel.replace("/", ".").replace(".py", ""))
            elif ext in {".ts", ".tsx"}:
                files_to_parse.append((rel, full, "typescript"))
                local_module_names.add(full.stem)
            elif ext in {".js", ".jsx"}:
                files_to_parse.append((rel, full, "javascript"))
                local_module_names.add(full.stem)
            elif ext == ".java":
                files_to_parse.append((rel, full, "java"))
                local_module_names.add(full.stem)
            elif ext == ".rs":
                files_to_parse.append((rel, full, "rust"))
                local_module_names.add(full.stem)
            elif ext == ".go":
                files_to_parse.append((rel, full, "go"))
                local_module_names.add(full.stem)

    external_packages_set: set[str] = set()
    edges: list[AstEdge] = []

    for rel, full, lang in files_to_parse:
        try:
            content = full.read_text(encoding="utf-8")
        except Exception:
            continue

        if lang == "python":
            mod_info = _analyze_python_file(rel, content)
        else:
            mod_info = _analyze_generic_file(rel, content, lang)

        modules.append(mod_info)

        # Classifica imports entre internos e externos
        for imp in mod_info.imports:
            root_imp = imp.split(".")[0].replace("/", "")
            if root_imp in _PY_STD_LIBS:
                continue
            if root_imp in local_module_names or imp.startswith("."):
                edges.append(AstEdge(source_file=rel, target_module=imp, import_type="internal"))
            else:
                external_packages_set.add(root_imp)
                edges.append(AstEdge(source_file=rel, target_module=root_imp, import_type="external"))

    modules.sort(key=lambda m: m.file_path)

    return AstAnalysisResponse(
        run_id=run_id,
        modules=modules,
        external_packages=sorted(external_packages_set),
        dependency_graph=edges,
    )
