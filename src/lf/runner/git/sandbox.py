import os
import subprocess
from pathlib import Path


class GitSandbox:
    """Gerenciador de Worktrees do Git para execução isolada de tarefas (.slim/worktrees/)."""

    def __init__(self, repo_path: str | Path = "."):
        self.repo_path = Path(repo_path).resolve()
        self.worktree_dir = self.repo_path / ".slim" / "worktrees"

    def create_worktree(self, task_id: str) -> Path | None:
        """Cria uma Git Worktree isolada em .slim/worktrees/<task_id>."""
        os.makedirs(self.worktree_dir, exist_ok=True)
        target_path = self.worktree_dir / task_id
        branch_name = f"lf-worktree-{task_id}"

        if target_path.exists():
            self.cleanup_worktree(task_id)

        res = subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(target_path), "HEAD"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return target_path

        res_existing = subprocess.run(
            ["git", "worktree", "add", str(target_path), branch_name],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
        )
        if res_existing.returncode == 0:
            return target_path

        return None

    def merge_worktree(self, task_id: str, target_branch: str = "main") -> bool:
        """Faz o merge das alterações aprovadas na worktree para a branch principal."""
        branch_name = f"lf-worktree-{task_id}"
        res = subprocess.run(
            ["git", "merge", branch_name, "--no-ff", "-m", f"feat: merge worktree {task_id}"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
        )
        return res.returncode == 0

    def cleanup_worktree(self, task_id: str) -> bool:
        """Remove a worktree isolada e sua branch temporária."""
        target_path = self.worktree_dir / task_id
        branch_name = f"lf-worktree-{task_id}"
        subprocess.run(["git", "worktree", "remove", "--force", str(target_path)], cwd=str(self.repo_path), capture_output=True)
        subprocess.run(["git", "branch", "-D", branch_name], cwd=str(self.repo_path), capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=str(self.repo_path), capture_output=True)
        return not target_path.exists()

    def create_sandbox_branch(self, branch_name: str) -> bool:
        """Fallback legacy para branches simples."""
        res = subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.repo_path, capture_output=True)
        return res.returncode == 0

    def cleanup_branch(self, branch_name: str, target_branch: str = "main") -> bool:
        """Fallback legacy para exclusão de branch."""
        subprocess.run(["git", "checkout", target_branch], cwd=self.repo_path, capture_output=True)
        res = subprocess.run(["git", "branch", "-D", branch_name], cwd=self.repo_path, capture_output=True)
        return res.returncode == 0
