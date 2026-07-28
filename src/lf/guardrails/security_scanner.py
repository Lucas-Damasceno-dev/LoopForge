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
    PATTERNS = [
        (r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][A-Za-z0-9/\+=]{16,}['\"]", "SEC-001", "Hardcoded API Key or Secret"),
        (r"eval\(", "SEC-002", "Use of dangerous eval() function"),
        (r"exec\(", "SEC-003", "Use of dangerous exec() function"),
    ]

    def scan_directory(self, root_dir: str | Path = ".") -> list[Vulnerability]:
        root = Path(root_dir)
        vulnerabilities = []

        for p in root.rglob("*.py"):
            if ".venv" in p.parts or "node_modules" in p.parts:
                continue
            try:
                content = p.read_text(encoding="utf-8")
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
            except Exception:
                continue

        return vulnerabilities

    def fix_vulnerabilities(self, root_dir: str | Path = ".") -> int:
        """Autocorrige vulnerabilidades simples encontradas nos arquivos."""
        root = Path(root_dir)
        fixed_count = 0

        for p in root.rglob("*.py"):
            if ".venv" in p.parts or "node_modules" in p.parts:
                continue
            try:
                content = p.read_text(encoding="utf-8")
                new_lines = []
                modified = False
                for line in content.splitlines():
                    # Neutraliza eval/exec com warning comment
                    if "eval(" in line and "# SEC-FIX" not in line:
                        line = line.replace("eval(", "# SEC-FIX: eval neutralized\n# eval(")
                        modified = True
                        fixed_count += 1
                    elif "exec(" in line and "# SEC-FIX" not in line:
                        line = line.replace("exec(", "# SEC-FIX: exec neutralized\n# exec(")
                        modified = True
                        fixed_count += 1
                    new_lines.append(line)

                if modified:
                    p.write_text("\n".join(new_lines), encoding="utf-8")
            except Exception:
                continue

        return fixed_count

