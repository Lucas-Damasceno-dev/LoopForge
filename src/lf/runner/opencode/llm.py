import json
import os
from datetime import UTC

from ...pipeline.cache import SQLiteLLMCache
from .runner import DEFAULT_OPENCODE_MODEL, OpenCodeRunner


def call_llm_via_opencode(
    system_prompt: str,
    user_prompt: str,
    schema_model=None,
    model: str | None = None,
    temperature: float = 0.3,
    mock: bool = False,
    cache: bool = True,
    circuit_breaker=None,
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
    if circuit_breaker is not None and not circuit_breaker.can_proceed():
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
    base_url = os.environ.get("OPENROUTER_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL)
    is_default_or = base_url.rstrip("/") == _DEFAULT_OPENROUTER_BASE_URL

    raw_response_text = ""
    if openrouter_key:
        model_name = model or DEFAULT_OPENROUTER_MODEL
        try:
            raw_response_text, _ = call_openrouter_api(
                final_prompt, model=model_name, api_key=openrouter_key,
                system_prompt=system_prompt,
            )
        except Exception as e:
            print(f"--- AVISO: LLM API ({model_name}) falhou após retentativas ({e}). Executando OpenCodeRunner fallback ---")
            runner = OpenCodeRunner(timeout_seconds=300)
            result = runner.run(final_prompt, project_root=os.getcwd(), model=model_to_use, circuit_breaker=circuit_breaker)
            if not result.success:
                raise RuntimeError(f"OpenCode LLM call failed: {result.stderr}")
            raw_response_text = result.clean_stdout
    else:
        runner = OpenCodeRunner(timeout_seconds=300)
        result = runner.run(final_prompt, project_root=os.getcwd(), model=model_to_use, circuit_breaker=circuit_breaker)
        if not result.success:
            raise RuntimeError(f"OpenCode LLM call failed: {result.stderr}")
        raw_response_text = result.clean_stdout

    # Tenta extrair JSON
    if schema_model:
        parsed = _extract_json_from_text(raw_response_text)
        if parsed is None:
            raise RuntimeError(
                f"LLM não retornou JSON válido para {schema_model.__name__}. "
                f"Resposta: {raw_response_text[:500]}"
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
                        return json.loads(text[start:i + 1])
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
