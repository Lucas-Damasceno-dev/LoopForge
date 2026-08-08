import json
import re
from dataclasses import dataclass, field


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences e linhas de cabeçalho do stdout."""
    # Remove ANSI escape codes
    ansi_re = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_re.sub('', text)
    # Remove linhas de cabeçalho OpenCode (ex: "> orchestrator · model")
    text = re.sub(r'^>.*$', '', text, flags=re.MULTILINE)
    return text.strip()


@dataclass
class OpenCodeResult:
    exit_code: int
    stdout: str
    stderr: str
    changed_files: list[str] = field(default_factory=list)
    diff: str = ""
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def error(self) -> str | None:
        return self.stderr if self.stderr else None

    @property
    def clean_stdout(self) -> str:
        """Stdout sem ANSI codes e cabeçalhos."""
        return strip_ansi(self.stdout)

    def extract_json(self) -> dict | None:
        """Tenta extrair um JSON do stdout do OpenCode."""
        text = self.clean_stdout
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        return None
