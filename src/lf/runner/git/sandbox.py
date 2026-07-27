from pathlib import Path
import subprocess


class GitSandbox:
    def __init__(self, repo_path: str | Path = "."):
        self.repo_path = Path(repo_path)

    def create_sandbox_branch(self, branch_name: str) -> bool:
        res = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.repo_path,
            capture_output=True,
        )
        return res.returncode == 0

    def cleanup_branch(self, branch_name: str, target_branch: str = "main") -> bool:
        subprocess.run(["git", "checkout", target_branch], cwd=self.repo_path, capture_output=True)
        res = subprocess.run(["git", "branch", "-D", branch_name], cwd=self.repo_path, capture_output=True)
        return res.returncode == 0
