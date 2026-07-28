import subprocess
from pathlib import Path


class GitCheckpointManager:
    def __init__(self, repo_path: str | Path = "."):
        self.repo_path = Path(repo_path)

    def create_checkpoint(self, message: str) -> str:
        """Creates git commit checkpoint."""
        subprocess.run(["git", "add", "."], cwd=self.repo_path, capture_output=True)
        res = subprocess.run(
            ["git", "commit", "-m", f"checkpoint: {message}"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        # Return commit hash
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return rev.stdout.strip()

    def rollback_to(self, commit_hash: str) -> bool:
        res = subprocess.run(
            ["git", "reset", "--hard", commit_hash],
            cwd=self.repo_path,
            capture_output=True,
        )
        return res.returncode == 0
