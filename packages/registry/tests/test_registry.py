"""Suíte de testes automatizados para o Agentic Interface Registry."""

import os
import tempfile
import pytest

from registry.core.analyzer import analyze_signature_change, check_breaking_changes
from registry.core.checker import RegistryChecker
from registry.core.scanner import InterfaceScanner
from registry.store.models import InterfaceItem, RegistrySchema
from registry.store.sqlite import RegistryStore


def test_analyze_signature_change():
    # Sem alteração
    is_breaking, ctype, details = analyze_signature_change("(a: int)", "(a: int)")
    assert is_breaking is False

    # Parâmetro opcional adicionado (não quebra)
    is_breaking, ctype, details = analyze_signature_change("(a: int)", "(a: int, b: int = 0)")
    assert is_breaking is False
    assert ctype == "additive_change"

    # Parâmetro obrigatório adicionado (quebra)
    is_breaking, ctype, details = analyze_signature_change("(a: int)", "(a: int, b: int)")
    assert is_breaking is True
    assert ctype == "parameter_added_without_default"

    # Parâmetro removido (quebra)
    is_breaking, ctype, details = analyze_signature_change("(a: int, b: int)", "(a: int)")
    assert is_breaking is True
    assert ctype == "parameter_removed"


def test_interface_scanner_and_consumers():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Criar módulo produtor
        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
        prod_path = os.path.join(tmpdir, "src", "billing.py")
        with open(prod_path, "w") as f:
            f.write("def calculate_total(items):\n    return 100.0\n")

        # Criar consumidor (teste QA)
        tests_dir = os.path.join(tmpdir, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        cons_path = os.path.join(tests_dir, "test_billing.py")
        with open(cons_path, "w") as f:
            f.write("from src.billing import calculate_total\ndef test_total():\n    assert calculate_total([]) == 100.0\n")

        scanner = InterfaceScanner(tmpdir)
        schema = scanner.scan(current_agent="developer")

        assert len(schema.interfaces) >= 1
        item = next(i for i in schema.interfaces if i.name == "calculate_total")
        assert item.module == "src/billing.py"
        assert len(item.consumers) >= 1
        assert any(c.file == "tests/test_billing.py" for c in item.consumers)


def test_registry_checker_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Estado v1
        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "tests"), exist_ok=True)

        prod_path = os.path.join(tmpdir, "src", "billing.py")
        with open(prod_path, "w") as f:
            f.write("def calculate_total(items):\n    return 100.0\n")

        cons_path = os.path.join(tmpdir, "tests", "test_billing.py")
        with open(cons_path, "w") as f:
            f.write("from src.billing import calculate_total\ndef test_total():\n    assert calculate_total([]) == 100.0\n")

        # Salvar snapshot inicial
        scanner = InterfaceScanner(tmpdir)
        initial_schema = scanner.scan(current_agent="developer")
        store = RegistryStore(tmpdir)
        store.save(initial_schema)

        # 2. Modificar assinatura do produtor (adicionar parâmetro sem default)
        with open(prod_path, "w") as f:
            f.write("def calculate_total(items, discount):\n    return 100.0 - discount\n")

        checker = RegistryChecker(tmpdir)
        breaking = checker.check()

        assert len(breaking) == 1
        assert breaking[0].interface_name == "calculate_total"
        assert breaking[0].change_type == "parameter_added_without_default"
        assert len(breaking[0].impacted_consumers) >= 1
        assert any(c.file == "tests/test_billing.py" for c in breaking[0].impacted_consumers)
