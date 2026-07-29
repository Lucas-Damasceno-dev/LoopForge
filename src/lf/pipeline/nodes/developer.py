"""
Nó Developer: recebe tech spec e gera código REAL via chamada direta à API OpenRouter.
"""
from __future__ import annotations

import os
from pathlib import Path

from ...pipeline.state import GraphState


def _ensure_openrouter_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError("OPENROUTER_API_KEY não configurada")
    return key


def _call_openrouter(prompt: str, system: str, model: str) -> str:
    import httpx

    key = _ensure_openrouter_key()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://loopforge.dev",
        "X-Title": "LoopForge AI Engine",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }

    response = httpx.post(url, headers=headers, json=payload, timeout=120.0)
    if response.status_code != 200:
        raise RuntimeError(f"LLM API error ({response.status_code}): {response.text}")

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("LLM API: resposta vazia")
    return choices[0]["message"]["content"]


STACK_CONFIGS = {
    "java": {
        "lang": "Java",
        "ext": ".java",
        "instruction": "You are a Java developer. Generate ONLY Java code.",
        "rules": [
            "Write a SINGLE compilable Java class with a main(String[] args) method",
            "Include import statements",
            "Do NOT include test code in the same file",
            "Exactly one class per file — the class name MUST match the filename (Main)",
            "No markdown fences, no explanations, no backticks",
        ],
        "entry": "import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        \n    }\n}",
    },
    "python": {
        "lang": "Python",
        "ext": ".py",
        "instruction": "You are a Python developer. Generate ONLY Python code.",
        "rules": [
            "Write a complete, runnable Python program",
            "Include a main() function and if __name__ guard",
            "No markdown fences, no explanations, no backticks",
            "Just the raw code",
        ],
        "entry": 'def main():\n    pass\n\nif __name__ == "__main__":\n    main()',
    },
    "javascript": {
        "lang": "JavaScript",
        "ext": ".js",
        "instruction": "You are a JavaScript developer. Generate ONLY JavaScript code.",
        "rules": ["Write a complete Node.js program", "No markdown fences, no explanations", "Just the raw code"],
        "entry": "function main() {\n    \n}\n\nmain();",
    },
    "go": {
        "lang": "Go",
        "ext": ".go",
        "instruction": "You are a Go developer. Generate ONLY Go code.",
        "rules": ["Write a complete Go program with package main", "Include func main()", "No markdown fences", "Just the raw code"],
        "entry": 'package main\n\nimport "fmt"\n\nfunc main() {\n    \n}',
    },
    "rust": {
        "lang": "Rust",
        "ext": ".rs",
        "instruction": "You are a Rust developer. Generate ONLY Rust code.",
        "rules": ["Write a complete Rust program with fn main()", "No markdown fences", "Just the raw code"],
        "entry": "fn main() {\n    \n}",
    },
}


def developer(state: GraphState) -> dict:
    """Recebe tech spec e gera código via OpenRouter API"""
    print("---EXECUTANDO NÓ: Developer---")

    if state.get("mock_llm"):
        print("--- INFO: Developer modo MOCK ---")
        return {
            **state,
            "code": "# Mock generated code\nprint('mock')",
            "next_agent": "qa",
            "error": None,
        }

    tech_spec = state.get("tech_spec", "")
    idea = state.get("idea", "")
    user_stories = state.get("user_stories", [])
    stack_lang = str(state.get("stack", "python")).lower()
    model_name = os.environ.get("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash:free")

    sc = STACK_CONFIGS.get(stack_lang, STACK_CONFIGS["python"])

    # Build user prompt with context
    story_lines = []
    for us in user_stories[:3]:
        sid = us.get("id", "")
        title = us.get("title", "")
        desc = us.get("description", "")[:150]
        story_lines.append(f"- {sid}: {title} — {desc}")

    user_prompt = f"""Implemente em {sc['lang']}:

Ideia: {idea}

Tech Spec:
{tech_spec[:2000]}

User Stories:
{chr(10).join(story_lines) if story_lines else 'N/A'}"""

    system_prompt = f"""{sc['instruction']}

REGRAS:
{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(sc['rules']))}

Exemplo de entry point:
{sc['entry']}
"""

    print(f"--- Chamando OpenRouter API (model: {model_name})... ---")
    try:
        raw = _call_openrouter(user_prompt, system_prompt, model_name)
    except Exception as e:
        err_msg = f"OpenRouter API falhou: {e}"
        print(f"--- AVISO: {err_msg} ---")
        state.setdefault("feedback_history", []).append(
            {"from": "developer", "message": err_msg, "attempt": state.get("attempt_count", 0)}
        )
        return {**state, "code": "", "next_agent": "qa", "error": err_msg}

    # Clean up markdown fences if present
    code = raw.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[-1] if "\n" in code else code[3:]
    if code.endswith("```"):
        code = code[:-3].strip()
    # Remove leading language tag like java, python
    first_line = code.split("\n", 1)[0].strip()
    if first_line.lower() in ("java", "python", "javascript", "go", "rust", "typescript"):
        code = code.split("\n", 1)[-1] if "\n" in code else code
    code = code.strip()

    # Save to file
    ext = sc["ext"]
    output_dir = state.get("output_dir", ".")
    os.makedirs(output_dir, exist_ok=True)
    code_path = os.path.join(output_dir, f"generated_code{ext}")
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"--- INFO: Código salvo em {code_path} ({len(code)} chars) ---")

    return {
        **state,
        "code": code,
        "next_agent": "qa",
        "error": None,
    }
