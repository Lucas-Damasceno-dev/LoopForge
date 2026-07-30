"""Scanner AST para arquivos Python."""

import ast
from typing import List
from genome.languages.base import BaseLanguageScanner
from genome.store.models import ModuleInfo, Symbol


class PythonScanner(BaseLanguageScanner):
    @property
    def language_name(self) -> str:
        return "python"

    @property
    def extensions(self) -> List[str]:
        return [".py"]

    def scan_file(self, file_path: str, code: str) -> ModuleInfo:
        lines = code.splitlines()
        lines_count = len(lines)
        exports: List[Symbol] = []
        imports: List[str] = []

        try:
            tree = ast.parse(code, filename=file_path)
        except SyntaxError:
            return ModuleInfo(
                path=file_path,
                language=self.language_name,
                exports=[],
                imports=[],
                lines_count=lines_count,
            )

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if module:
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Se não começar com _, consideramos exportado/público
                is_exported = not node.name.startswith("_")
                args_list = [arg.arg for arg in node.args.args]
                sig = f"def {node.name}({', '.join(args_list)})"
                exports.append(
                    Symbol(
                        name=node.name,
                        kind="function",
                        line=node.lineno,
                        exported=is_exported,
                        signature=sig,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                is_exported = not node.name.startswith("_")
                exports.append(
                    Symbol(
                        name=node.name,
                        kind="class",
                        line=node.lineno,
                        exported=is_exported,
                        signature=f"class {node.name}",
                    )
                )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        # Variável / constante de nível superior
                        exports.append(
                            Symbol(
                                name=target.id,
                                kind="variable",
                                line=node.lineno,
                                exported=True,
                            )
                        )

        return ModuleInfo(
            path=file_path,
            language=self.language_name,
            exports=exports,
            imports=imports,
            lines_count=lines_count,
        )
