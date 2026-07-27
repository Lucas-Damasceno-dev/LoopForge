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


class OpenCodeRunner:
    """Gerencia execução de instâncias OpenCode via subprocesso.

    Uso correto: opencode run "mensagem" --dir /caminho
    O prompt é um argumento posicional, não --prompt.
    """

    def __init__(self, timeout_seconds: int = 300):
        self.timeout = timeout_seconds

    def run(self, prompt: str, project_root: str | Path = ".", model: str = "opencode/deepseek-v4-flash-free") -> OpenCodeResult:
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
        cmd = ["opencode", "run", prompt, "--dir", str(root)]
        if model:
            cmd.extend(["-m", model])

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
            return OpenCodeResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
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
    model: str = "opencode/deepseek-v4-flash-free",
    temperature: float = 0.3,
    mock: bool = False,
    cache: bool = True,
) -> str | dict | list:
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

    runner = OpenCodeRunner(timeout_seconds=120)
    result = runner.run(final_prompt, project_root=os.getcwd(), model=model)

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
