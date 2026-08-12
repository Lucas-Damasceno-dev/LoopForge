import json
import os
from collections.abc import Callable
from datetime import UTC
from pathlib import Path

from rich.console import Console

from ...pipeline.cache import SQLiteLLMCache
from .runner import DEFAULT_OPENCODE_MODEL, OpenCodeRunner

_console = Console()

# Marcadores de erro de modelo/servidor que NÃO são resposta LLM válida. O
# wrapper `script` mascara o exit code do subprocesso (success=True mesmo com
# falha), então o gate precisa checar o TEXTO da resposta, não o código de saída.
_LLM_ERROR_MARKERS = ("Model not found", "UnknownError", "Unexpected server error", "model_not_found")


def _raise_if_llm_error_marker(raw_response_text: str, result=None) -> None:
    """Gate: resposta LLM contendo marcador de erro vira RuntimeError.

    Roda MESMO quando `result.success` é True — o wrapper `script` mascara o
    exit code e texto de erro ("Model not found"/"UnknownError") chegava como
    resposta válida, fazendo o Developer seguir para QA com código vazio.
    """
    haystack = raw_response_text or ""
    if result is not None:
        haystack += "\n" + (getattr(result, "stdout", "") or "") + "\n" + (getattr(result, "stderr", "") or "")
    for marker in _LLM_ERROR_MARKERS:
        if marker in haystack:
            raise RuntimeError(
                "LLM Engine falhou: resposta contém erro de modelo/servidor. "
                "Verifique OPENROUTER_MODEL / OPENCODE_MODEL / .loopforge.json "
                f"(ex.: 'oc/deepseek-v4-flash-free'). Resposta: {raw_response_text[:300]}"
            )


def call_llm_via_opencode(
    system_prompt: str,
    user_prompt: str,
    schema_model=None,
    model: str | None = None,
    temperature: float = 0.3,
    mock: bool = False,
    cache: bool = True,
    circuit_breaker=None,
    project_root: str | Path | None = None,
    on_token_delta: Callable[[str], None] | None = None,
) -> str | dict | list:
    """Chama OpenCode como LLM para geração de texto/estruturado.

    Args:
        system_prompt: Instruções de sistema (papel, formato, regras)
        user_prompt: O conteúdo variável (ideia, épico, user stories, etc.)
        schema_model: Classe Pydantic opcional para validar saída JSON
        model: Modelo OpenCode
        temperature: Não usado via subprocesso, mantido para compatibilidade
        mock: Se True, retorna mock
        cache: Se True, usa cache SQLite (SQLiteLLMCache de llm_factory)
        circuit_breaker: CircuitBreaker opcional para preemptar subprocessos
        project_root: Diretório da run (cwd do subprocesso opencode). Default:
            os.getcwd(). Subprocessos opencode herdam PWD, então passar o dir
            correto impede que o agente escreva no repo real.
        on_token_delta: Callback opcional p/ streaming token a token
            (V1.1/ADR-0007). Repassado ao provider HTTP quando a API key
            OpenRouter está disponível; o caminho subprocesso ignora (sem
            incremento incremental — fallback silencioso).

    Returns:
        str se não tiver schema_model, dict se tiver schema_model
    """
    model_to_use = model or os.environ.get("OPENCODE_MODEL", DEFAULT_OPENCODE_MODEL)

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # Cache check
    if cache and not mock:
        llm_cache = SQLiteLLMCache()
        cached = llm_cache.get(full_prompt)
        if cached:
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

    # Circuit breaker check antes de spawnar subprocesso
    if circuit_breaker is not None:
        # M-08: o estado do grafo carrega o CircuitBreaker como SNAPSHOT (dict)
        # serializável (canal `circuit_breaker` do GraphState). Reconstrói a
        # instância para o can_proceed() funcionar — antes o dict chegava aqui
        # e o enforcement do CB ficava morto nos nós.
        if isinstance(circuit_breaker, dict):
            from ...guardrails.circuit_breaker import CircuitBreaker

            circuit_breaker = CircuitBreaker.from_snapshot(circuit_breaker)
        if not circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker is open - cannot proceed")

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

    from ...pipeline.llm_factory import (
        _DEFAULT_OPENROUTER_BASE_URL,
        DEFAULT_OPENROUTER_KEY,
        DEFAULT_OPENROUTER_MODEL,
        call_openrouter_api,
    )

    openrouter_key = os.environ.get("OPENROUTER_API_KEY") or DEFAULT_OPENROUTER_KEY

    display_model = (
        model or os.environ.get("OPENROUTER_MODEL") or os.environ.get("OPENCODE_MODEL") or DEFAULT_OPENCODE_MODEL
    )

    raw_response_text = ""
    used_subprocess = False
    run_root = project_root or os.getcwd()
    with _console.status(f"⏳ Consultando LLM ({display_model})...", spinner="dots"):
        if openrouter_key:
            model_name = model or DEFAULT_OPENROUTER_MODEL
            user_content = user_prompt + (format_instruction if schema_model else "")
            try:
                raw_response_text, _ = call_openrouter_api(
                    user_content,
                    model=model_name,
                    api_key=openrouter_key,
                    system_prompt=system_prompt,
                    on_token_delta=on_token_delta,
                )
            except RuntimeError:
                # Gate já levantou (erro de modelo/servidor) — não cai no
                # fallback: propaga como erro de LLM, não como falha de API.
                raise
            except Exception as e:
                print(
                    f"--- AVISO: LLM API ({model_name}) falhou após retentativas ({e}). Executando OpenCodeRunner fallback ---"
                )
                runner = OpenCodeRunner()
                result = runner.run(
                    final_prompt, project_root=run_root, model=model_to_use, circuit_breaker=circuit_breaker
                )
                if not result.success:
                    raise RuntimeError(f"OpenCode LLM call failed: {result.stderr}")
                raw_response_text = result.clean_stdout
                _raise_if_llm_error_marker(raw_response_text, result)
                used_subprocess = True
            # Gate do path OpenRouter direto: roda fora do try para o RuntimeError
            # não ser confundido com falha da API e capturado pelo fallback.
            _raise_if_llm_error_marker(raw_response_text)
        else:
            runner = OpenCodeRunner()
            result = runner.run(
                final_prompt, project_root=run_root, model=model_to_use, circuit_breaker=circuit_breaker
            )
            if not result.success:
                raise RuntimeError(f"OpenCode LLM call failed: {result.stderr}")
            raw_response_text = result.clean_stdout
            _raise_if_llm_error_marker(raw_response_text, result)
            used_subprocess = True

    # M-09: custo ESTIMADO do path OpenCode subprocess (não havia registro —
    # o hard-stop de budget ficava cego exatamente quando mais importa). Usa o
    # mesmo padrão do CostTracker (tiktoken/chars fallback) com estimated=True.
    # Falha de tracking nunca quebra a chamada LLM (contextlib.suppress).
    if used_subprocess:
        try:
            from ...pipeline.llm_factory import CostTracker

            CostTracker().track(
                model=display_model,
                prompt_text=full_prompt,
                response_text=raw_response_text,
                estimated=True,
            )
        except Exception:
            pass

    # Tenta extrair JSON
    if schema_model:
        parsed = _extract_json_from_text(raw_response_text)
        if parsed is None:
            raise RuntimeError(
                f"LLM não retornou JSON válido para {schema_model.__name__}. Resposta: {raw_response_text[:500]}"
            )
        if isinstance(parsed, dict):
            validated = schema_model(**parsed)
        elif isinstance(parsed, list):
            try:
                validated = schema_model.model_validate(parsed)
            except Exception:
                if len(parsed) > 0 and isinstance(parsed[0], dict):
                    validated = schema_model(**parsed[0])
                else:
                    raise TypeError(f"Não foi possível converter lista para {schema_model.__name__}")
        else:
            raise TypeError(f"Formato JSON inesperado para {schema_model.__name__}: {type(parsed)}")
        result_dict = validated.model_dump()

        if cache:
            llm_cache = SQLiteLLMCache()
            llm_cache.set(full_prompt, json.dumps(result_dict, default=str))

        return result_dict

    # Não tem schema — retorna texto puro
    if cache:
        llm_cache = SQLiteLLMCache()
        llm_cache.set(full_prompt, raw_response_text)

    return raw_response_text


def _extract_json_from_text(text: str) -> dict | list | None:
    import re

    if not text:
        return None
    # Direct parse attempt
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    # Markdown code block extraction (flexible: tolera conteúdo após o bloco)
    # Pattern: ```json \n ... \n ```  ou ```json \n ... ```
    for pattern in [
        r"```(?:json)?\s*\n(.+?)\n```",
        r"```(?:json)?\s*\n(.+)```",
    ]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass

    # Brace/bracket depth tracking: extrai o primeiro objeto/array JSON completo
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except Exception:
                        # Se o primeiro objeto falhou, continua para achar outro
                        break
    return None


def _mock_response(schema_model) -> dict:
    """Gera resposta mock baseada no schema Pydantic."""
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
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
