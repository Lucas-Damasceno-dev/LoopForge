from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


@dataclass
class OpenCodeResult:
    exit_code: int
    stdout: str
    stderr: str
    changed_files: list[str] = field(default_factory=list)
    diff: str = ""
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def error(self) -> str | None:
        return self.stderr if self.stderr else None

    def extract_json(self) -> dict | None:
        """Tenta extrair um JSON do stdout do OpenCode.
        OpenCode tende a wrappar JSON em ```json ... ``` ou ``` ... ```."""
        text = self.stdout
        # Tenta bloco ```json ... ```
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Tenta parsear o texto inteiro como JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        return None


DEFAULT_OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "openrouter/openrouter/free")


class OpenCodeRunner:
    """Gerencia execução de instâncias OpenCode via subprocesso.

    Uso correto: opencode run "mensagem" --dir /caminho
    O prompt é um argumento posicional, não --prompt.
    """

    def __init__(self, timeout_seconds: int = 600):
        self.timeout = timeout_seconds

    def run(self, prompt: str, project_root: str | Path = ".", model: str | None = None) -> OpenCodeResult:
        model_to_use = model or os.environ.get("OPENCODE_MODEL", "openrouter/openrouter/free")
        root = Path(project_root).resolve()
        start_time = time.time()


        is_mock = os.environ.get("OPENCODE_MOCK", "0") == "1" or not shutil.which("opencode")

        if is_mock:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=0,
                stdout=f"[MOCK OPENCODE] Executed prompt: {prompt[:120]}...",
                stderr="",
                changed_files=[],
                diff="[Mock diff: 0 files changed]",
                duration_seconds=duration,
            )

        # O comando correto: opencode run "prompt" --dir /path
        # O prompt é argumento posicional, não --prompt
        # --dir faz OpenCode carregar contexto do projeto, o que adiciona ~19k tokens
        # Para chamadas LLM puras, evitamos para reduzir latência
        cmd = ["opencode", "run", prompt]
        if model_to_use:
            cmd.extend(["-m", model_to_use])


        try:
            res = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=os.environ.copy(),
            )
            duration = time.time() - start_time
            changed_files = detect_changed_files(root, start_time)
            return OpenCodeResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                changed_files=changed_files,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=f"OpenCode execution timed out after {self.timeout}s",
                duration_seconds=duration,
            )
        except Exception as exc:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=1,
                stdout="",
                stderr=str(exc),
                duration_seconds=duration,
            )


def detect_changed_files(project_root: str | Path, start_time: float) -> list[str]:
    """Detecta arquivos criados ou modificados no project_root após start_time."""
    root = Path(project_root).resolve()
    ignored_parts = {
        ".git", ".loopforge", "__pycache__", ".pytest_cache", "node_modules",
        "venv", ".venv", ".mypy_cache", ".gemini"
    }
    ignored_files = {
        "generated_code.py", ".loopforge.json", "llm_cache.sqlite", ".users.json", "loop.lock"
    }

    changed: list[str] = []

    # 1. Tenta git status se for um repositório git
    git_dir = root / ".git"
    if git_dir.exists():
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        rel_path = parts[1].strip('"')
                        file_path = root / rel_path
                        if any(part in ignored_parts for part in file_path.parts):
                            continue
                        if file_path.name in ignored_files or file_path.name.startswith("test_report_"):
                            continue
                        if file_path.is_file():
                            changed.append(str(file_path))
        except Exception:
            pass

    # 2. Fallback / Complemento: verificação de mtime
    if not changed and root.exists():
        try:
            for p in root.rglob("*"):
                if p.is_file():
                    if any(part in ignored_parts for part in p.parts):
                        continue
                    if p.name in ignored_files or p.name.startswith("test_report_"):
                        continue
                    try:
                        if p.stat().st_mtime >= start_time - 1.0:
                            changed.append(str(p))
                    except OSError:
                        pass
        except Exception:
            pass

    return changed



# ---- Utilitário compartilhado para nós que só precisam de LLM via OpenCode ----

_SQLITE_CACHE: dict = {}


def _get_cache(db_path: str = ".loopforge/llm_cache.sqlite") -> tuple:
    """Retorna (conn, cursor) lazy-init."""
    global _SQLITE_CACHE
    if "conn" not in _SQLITE_CACHE:
        import sqlite3
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(p)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "prompt_hash TEXT PRIMARY KEY, response TEXT NOT NULL,"
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        _SQLITE_CACHE["conn"] = conn
    return _SQLITE_CACHE["conn"], _SQLITE_CACHE["conn"].cursor()


def call_llm_via_opencode(
    system_prompt: str,
    user_prompt: str,
    schema_model=None,
    model: str | None = None,
    temperature: float = 0.3,
    mock: bool = False,
    cache: bool = True,
) -> str | dict | list:
    model_to_use = model or os.environ.get("OPENCODE_MODEL", "openrouter/openrouter/free")

    """Chama OpenCode como LLM para geração de texto/estruturado.

    Args:
        system_prompt: Instruções de sistema (papel, formato, regras)
        user_prompt: O conteúdo variável (ideia, épico, user stories, etc.)
        schema_model: Classe Pydantic opcional para validar saída JSON
        model: Modelo OpenCode
        temperature: Não usado via subprocesso, mantido para compatibilidade
        mock: Se True, retorna mock
        cache: Se True, usa cache SQLite

    Returns:
        str se não tiver schema_model, dict se tiver schema_model
    """
    from hashlib import sha256

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    prompt_hash = sha256(full_prompt.encode()).hexdigest()

    # Cache check
    if cache and not mock:
        conn, cur = _get_cache()
        cur.execute("SELECT response FROM cache WHERE prompt_hash = ?", (prompt_hash,))
        row = cur.fetchone()
        if row:
            cached = row[0]
            if schema_model:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass
            return cached

    if mock:
        mock_text = f"[MOCK] Resposta para: {user_prompt[:80]}..."
        if schema_model:
            return _mock_response(schema_model)
        return mock_text

    # Monta prompt final com instrução de formato
    if schema_model:
        schema_json = json.dumps(schema_model.model_json_schema(), indent=2, ensure_ascii=False)
        format_instruction = f"""
Responda APENAS com um JSON válido que corresponda a este schema:

{schema_json}

NÃO inclua texto explicativo, markdown, ou comentários.
Responda SOMENTE o objeto JSON puro."""
        final_prompt = full_prompt + format_instruction
    else:
        final_prompt = full_prompt

    runner = OpenCodeRunner(timeout_seconds=300)  # 5min for free model
    result = runner.run(final_prompt, project_root=os.getcwd(), model=model_to_use)


    if not result.success:
        raise RuntimeError(f"OpenCode LLM call failed: {result.stderr}")

    # Tenta extrair JSON
    if schema_model:
        parsed = result.extract_json()
        if parsed is None:
            # Fallback: tenta parsear o stdout inteiro
            try:
                parsed = json.loads(result.stdout.strip())
            except (json.JSONDecodeError, TypeError):
                raise RuntimeError(
                    f"OpenCode não retornou JSON válido para {schema_model.__name__}. "
                    f"Stdout: {result.stdout[:500]}"
                )
        # Valida contra schema
        validated = schema_model(**parsed)
        result_dict = validated.model_dump()

        # Salva no cache
        if cache:
            conn, cur = _get_cache()
            conn.execute(
                "INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
                (prompt_hash, json.dumps(result_dict, default=str)),
            )
            conn.commit()

        return result_dict

    # Não tem schema — retorna texto puro
    text = result.stdout

    if cache:
        conn, cur = _get_cache()
        conn.execute(
            "INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
            (prompt_hash, text),
        )
        conn.commit()

    return text


def _mock_response(schema_model) -> dict:
    """Gera resposta mock baseada no schema Pydantic."""
    import inspect
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    mock = {}
    for name, field in schema_model.model_fields.items():
        ann = field.annotation
        if ann is None:
            mock[name] = None
        elif hasattr(ann, "__origin__"):
            origin = ann.__origin__
            if origin is list:
                mock[name] = [f"mock_{name}_item"]
            elif origin is dict:
                mock[name] = {"mock_key": "mock_value"}
            else:
                mock[name] = f"mock_{name}"
        elif ann is str:
            mock[name] = f"mock_{name}"
        elif ann is int:
            mock[name] = 0
        elif ann is float:
            mock[name] = 0.0
        elif ann is bool:
            mock[name] = False
        else:
            mock[name] = f"mock_{name}"
    mock["id"] = "MOCK-001"
    mock["dates"] = {"created_at": now}
    if hasattr(schema_model, "model_dump"):
        return schema_model(**mock).model_dump()
    return mock
