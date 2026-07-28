import subprocess
from pathlib import Path


def create_github_pr(title: str, body: str, labels: list[str], repo_path: str | Path = ".") -> bool:
    """Creates a GitHub PR using `gh pr create` CLI if available."""
    cmd = ["gh", "pr", "create", "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])

    res = subprocess.run(cmd, cwd=Path(repo_path), capture_output=True, text=True)
    return res.returncode == 0
