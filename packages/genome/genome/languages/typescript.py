"""Scanner AST / regex fallback para arquivos TypeScript / JavaScript."""

import re
from typing import List
from genome.languages.base import BaseLanguageScanner
from genome.store.models import ModuleInfo, Symbol


class TypeScriptScanner(BaseLanguageScanner):
    @property
    def language_name(self) -> str:
        return "typescript"

    @property
    def extensions(self) -> List[str]:
        return [".ts", ".tsx", ".js", ".jsx"]

    def scan_file(self, file_path: str, code: str) -> ModuleInfo:
        lines = code.splitlines()
        lines_count = len(lines)
        exports: List[Symbol] = []
        imports: List[str] = []

        # Capturar imports: import { x } from 'mod' ou import x from 'mod' ou import 'mod'
        import_regex = re.compile(r"""import\s+(?:[\w\s{},*]+?\s+from\s+)?['"]([^'"]+)['"]""")
        for match in import_regex.finditer(code):
            imports.append(match.group(1))

        # Capturar exports: export function name / export class Name / export const x / export interface Name / export type Name
        export_func = re.compile(r"""export\s+(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)""")
        export_class = re.compile(r"""export\s+(?:abstract\s+)?class\s+([A-Za-z0-9_$]+)""")
        export_interface = re.compile(r"""export\s+interface\s+([A-Za-z0-9_$]+)""")
        export_type = re.compile(r"""export\s+type\s+([A-Za-z0-9_$]+)""")
        export_const = re.compile(r"""export\s+(?:const|let|var)\s+([A-Za-z0-9_$]+)""")

        for line_num, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str.startswith("export"):
                continue

            m = export_func.search(line_str)
            if m:
                exports.append(
                    Symbol(
                        name=m.group(1),
                        kind="function",
                        line=line_num,
                        exported=True,
                        signature=f"function {m.group(1)}({m.group(2)})",
                    )
                )
                continue

            m = export_class.search(line_str)
            if m:
                exports.append(
                    Symbol(
                        name=m.group(1),
                        kind="class",
                        line=line_num,
                        exported=True,
                        signature=f"class {m.group(1)}",
                    )
                )
                continue

            m = export_interface.search(line_str)
            if m:
                exports.append(
                    Symbol(
                        name=m.group(1),
                        kind="interface",
                        line=line_num,
                        exported=True,
                        signature=f"interface {m.group(1)}",
                    )
                )
                continue

            m = export_type.search(line_str)
            if m:
                exports.append(
                    Symbol(
                        name=m.group(1),
                        kind="type",
                        line=line_num,
                        exported=True,
                        signature=f"type {m.group(1)}",
                    )
                )
                continue

            m = export_const.search(line_str)
            if m:
                exports.append(
                    Symbol(
                        name=m.group(1),
                        kind="variable",
                        line=line_num,
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
