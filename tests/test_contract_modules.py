"""P0-2: contrato de nomenclatura TestWriter↔Developer.

O TestWriter gera testes-contrato que importam módulos internos (ex.:
`app.services.payment`). O Developer precisa conhecer esses nomes EXATOS para
não inventar variações plurais/singulares (`payments.py` vs `payment.py`) que
quebram a coleta do pytest. Estes testes cobrem o helper de inventário de
módulos e o fluxo do contrato entre os dois nós.
"""

from unittest.mock import patch

from lf.pipeline.nodes.developer import developer
from lf.pipeline.nodes.test_writer import _extract_module_inventory, test_writer


def test_extract_module_inventory_filtra_stdlib_e_um_segmento():
    """Filtra os/pytest (denylist) e imports de 1 segmento; mantém módulos internos."""
    files_map = {
        "tests/test_payment.py": (
            "from app.services.payment import PaymentProcessor\n"
            "from app.services.notification import Notifier\n"
            "import os\n"
            "import pytest\n"
        )
    }

    modules = _extract_module_inventory(files_map)

    assert modules == ["app.services.payment", "app.services.notification"]


def test_extract_module_inventory_import_sem_from_e_dedup():
    """`import app.models` sem `from` é capturado; repetição vira 1 entrada."""
    files_map = {
        "tests/test_models.py": (
            "import app.models\n"
            "from app.models import User\n"
            "from app.services.payment import PaymentProcessor\n"
            "import numpy as np\n"
        )
    }

    modules = _extract_module_inventory(files_map)

    assert modules == ["app.models", "app.services.payment"]


def test_extract_module_inventory_ignora_import_relativo():
    """Imports relativos ('.modelo') não são tratados como módulos da aplicação."""
    files_map = {"tests/test_helper.py": "from .helpers import make_client\nfrom app.core.config import Settings\n"}

    modules = _extract_module_inventory(files_map)

    assert modules == ["app.core.config"]


def test_test_writer_contrato_inclui_linha_modules(tmp_path, monkeypatch):
    """O contract_tests retornado declara '### MODULES:' com os módulos importados."""
    llm_response = """### FILE: tests/test_payment.py
```python
from app.services.payment import PaymentProcessor

def test_pagamento_valido():
    assert True
```
"""
    state = {
        "user_stories": [
            {
                "id": "US-1",
                "title": "Processar pagamento",
                "acceptance_criteria": ["Deve processar pagamento válido"],
            }
        ],
        "stack": "python",
        "tech_spec": "Tech spec de exemplo",
        "output_dir": str(tmp_path),
        "mock_llm": True,
    }
    monkeypatch.setattr(
        "lf.pipeline.nodes.test_writer.call_llm_via_opencode",
        lambda **kwargs: llm_response,
    )

    result = test_writer(state)

    assert "### MODULES:" in result["contract_tests"]
    assert "app.services.payment" in result["contract_tests"]


def test_developer_prompt_inclui_modulos_obrigatorios(tmp_path):
    """O Developer injeta no prompt os módulos obrigatórios do contrato de testes."""
    captured = {}

    def _fake_call_llm(**kwargs):
        captured["user_prompt"] = kwargs.get("user_prompt", "")
        return "### FILE: generated_code.py\n```python\ndef main():\n    pass\n```"

    state = {
        "idea": "App de pagamentos",
        "tech_spec": "# Spec\nImplement code",
        "user_stories": [{"id": "US-001", "title": "Implement feature", "acceptance_criteria": ["c1"]}],
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "mock_llm": False,
        "contract_tests": (
            "def test_pagamento():\n    assert True\n\n### MODULES: app.services.payment, app.services.notification"
        ),
    }

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_call_llm):
        developer(state)

    user_prompt = captured["user_prompt"]
    assert "app.services.payment" in user_prompt
    assert "app.services.notification" in user_prompt
    assert "MÓDULOS OBRIGATÓRIOS" in user_prompt
