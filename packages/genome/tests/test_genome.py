"""Suíte de testes automatizados para o Codebase Genome."""

import os
import tempfile
import pytest

from genome.core.bus_factor import calculate_bus_factor
from genome.core.diff import diff_genomes
from genome.core.graph import build_dependency_graph, compute_metrics, detect_circular_dependencies
from genome.core.renderers import render_json, render_markdown, render_summary
from genome.core.scanner import GenomeScanner
from genome.languages.python import PythonScanner
from genome.languages.typescript import TypeScriptScanner
from genome.resolvers.py_resolver import PythonSymbolResolver
from genome.resolvers.ts_resolver import TypeScriptSymbolResolver
from genome.store.models import ModuleInfo
from genome.store.sqlite import GenomeStore


def test_python_scanner():
    scanner = PythonScanner()
    code = """import os
from math import sqrt

def calculate_sum(a: int, b: int) -> int:
    return a + b

class Helper:
    pass

_private_var = 10
PUBLIC_CONST = 100
"""
    mod = scanner.scan_file("test.py", code)
    assert mod.path == "test.py"
    assert mod.language == "python"
    assert "os" in mod.imports
    assert "math.sqrt" in mod.imports

    exports_dict = {e.name: e for e in mod.exports}
    assert "calculate_sum" in exports_dict
    assert exports_dict["calculate_sum"].kind == "function"
    assert exports_dict["calculate_sum"].exported is True
    assert "Helper" in exports_dict
    assert exports_dict["Helper"].kind == "class"
    assert "PUBLIC_CONST" in exports_dict


def test_typescript_scanner():
    scanner = TypeScriptScanner()
    code = """import { useState } from 'react';
import { api } from '@/services/api';

export function Header(props: any) {
    return null;
}

export interface User {
    id: string;
}

export type UserRole = 'admin' | 'user';

export class AuthController {}
"""
    mod = scanner.scan_file("src/Header.tsx", code)
    assert mod.path == "src/Header.tsx"
    assert mod.language == "typescript"
    assert "react" in mod.imports
    assert "@/services/api" in mod.imports

    exports_dict = {e.name: e for e in mod.exports}
    assert "Header" in exports_dict
    assert exports_dict["Header"].kind == "function"
    assert "User" in exports_dict
    assert exports_dict["User"].kind == "interface"
    assert "UserRole" in exports_dict
    assert exports_dict["UserRole"].kind == "type"
    assert "AuthController" in exports_dict
    assert exports_dict["AuthController"].kind == "class"


def test_symbol_resolvers():
    py_resolver = PythonSymbolResolver()
    mod = ModuleInfo(
        path="src/main.py",
        language="python",
        imports=["lf.core.engine", "utils"],
    )
    known = {"src/lf/core/engine.py", "utils.py"}
    deps = py_resolver.resolve_dependencies(mod, repo_root=".", known_files=known)
    assert "src/lf/core/engine.py" in deps
    assert "utils.py" in deps


def test_graph_and_bus_factor():
    mod_a = ModuleInfo(path="src/a.py", language="python", dependencies=["src/b.py"])
    mod_b = ModuleInfo(path="src/b.py", language="python", dependencies=[])

    graph = build_dependency_graph([mod_a, mod_b])
    updated_mods = compute_metrics(graph, [mod_a, mod_b])

    mod_b_updated = next(m for m in updated_mods if m.path == "src/b.py")
    assert "src/a.py" in mod_b_updated.dependents

    bf = calculate_bus_factor(graph, updated_mods, high_risk_threshold=1)
    assert len(bf.high_risk_files) == 1
    assert bf.high_risk_files[0].path == "src/b.py"


def test_full_genome_scanner():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Criar fixture de repositório
        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
        with open(os.path.join(tmpdir, "src", "db.py"), "w") as f:
            f.write("def connect(): pass\n")

        with open(os.path.join(tmpdir, "src", "app.py"), "w") as f:
            f.write("from src.db import connect\ndef main(): connect()\n")

        scanner = GenomeScanner(tmpdir)
        genome = scanner.scan()

        assert genome.repo.total_files == 2
        assert genome.repo.total_lines > 0

        # Verificar renderers
        md = render_markdown(genome)
        assert "# 🧬 Codebase Genome" in md
        assert "`src/db.py`" in md or "`src/app.py`" in md

        summary = render_summary(genome)
        assert "[GENOME SUMMARY]" in summary

        js = render_json(genome)
        assert '"version": "1.0.0"' in js

        # Testar SQLite Store
        store = GenomeStore(tmpdir)
        loaded = store.load_genome()
        assert loaded is not None
        assert loaded.repo.total_files == 2
