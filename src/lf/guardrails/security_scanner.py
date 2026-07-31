import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Vulnerability:
    file_path: str
    line_number: int
    rule_id: str
    message: str


class SecurityScanner:
    SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".env", ".yml", ".yaml", ".json")

    PATTERNS = [
        (r"(?i)(api[_-]?key|secret|password|private[_-]?key|token)\s*[:=]\s*['\"][A-Za-z0-9/\+=_-]{16,}['\"]", "SEC-001", "Hardcoded API Key, Secret or Token"),
        (r"(?i)(eval\(|Function\(|exec\()", "SEC-002", "Use of dangerous dynamic code evaluation (eval/exec)"),
        (r"(?i)(os\.system\(|subprocess\.Popen\(.*shell\s*=\s*True|Runtime\.getRuntime\(\)\.exec\(|child_process\.exec\()", "SEC-003", "Potential OS Command Injection"),
        (r"(?i)(verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true)", "SEC-004", "Insecure TLS/SSL verification disabled"),
        (r"(?i)http://(?!localhost|127\.0\.0\.1)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "SEC-005", "Insecure Plaintext HTTP protocol URL"),
    ]

    def scan_directory(self, root_dir: str | Path = ".") -> list[Vulnerability]:
        root = Path(root_dir)
        vulnerabilities = []

        ignore_dirs = {".venv", "node_modules", ".git", ".genome", ".loopforge", "target", "vendor", "dist", "build"}

        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in ignore_dirs for part in p.parts):
                continue
            if p.suffix.lower() not in self.SUPPORTED_EXTENSIONS and p.name.lower() not in (".env", ".env.local"):
                continue

            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                for line_idx, line in enumerate(lines, 1):
                    for pattern, rule_id, msg in self.PATTERNS:
                        if re.search(pattern, line):
                            vulnerabilities.append(
                                Vulnerability(
                                    file_path=str(p.relative_to(root)),
                                    line_number=line_idx,
                                    rule_id=rule_id,
                                    message=msg,
                                )
                            )
            except Exception as e:
                print(f"--- AVISO: Erro ao escanear arquivo {p}: {e} ---")
                continue

        return vulnerabilities

    def fix_vulnerabilities(self, root_dir: str | Path = ".") -> int:
        """Autocorrige vulnerabilidades identificadas via análise estática segura com AST."""
        root = Path(root_dir)
        fixed_count = 0

        for p in root.rglob("*.py"):
            if any(part in {".venv", "node_modules", ".git", ".loopforge"} for part in p.parts):
                continue
            try:
                content = p.read_text(encoding="utf-8")
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue

                lines = content.splitlines()
                dangerous_lines = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in ("eval", "exec"):
                            dangerous_lines.add(node.lineno)

                if not dangerous_lines:
                    continue

                new_lines = []
                modified = False
                for idx, line in enumerate(lines, 1):
                    if idx in dangerous_lines and "# SEC-FIX" not in line:
                        new_lines.append(f"# SEC-FIX: dangerous call on line {idx} neutralized")
                        new_lines.append(f"# {line}")
                        modified = True
                        fixed_count += 1
                    else:
                        new_lines.append(line)

                if modified:
                    p.write_text("\n".join(new_lines), encoding="utf-8")
            except Exception as e:
                print(f"--- AVISO: Erro ao corrigir arquivo {p}: {e} ---")
                continue

        return fixed_count

