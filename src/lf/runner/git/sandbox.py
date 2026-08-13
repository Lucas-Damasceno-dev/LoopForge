import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Timeouts dos subprocessos git (roadmap 4.1): 60s padrão; commit usa 120s
# (git pode demorar em repos grandes / hooks).
_GIT_TIMEOUT = 60
_GIT_COMMIT_TIMEOUT = 120

# .gitignore gravado na worktree antes do commit — artefatos regeneráveis
# nunca entram no commit de merge.
_GITIGNORE_CONTENT = (
    ".venv/\nnode_modules/\n__pycache__/\ntarget/\ntest_reports/\nhtmlcov/\n.pytest_cache/\n.loopforge/\n"
)


class GitSandbox:
    """Gerenciador de Worktrees do Git para execução isolada de tarefas (.slim/worktrees/)."""

    def __init__(self, repo_path: str | Path = "."):
        self.repo_path = Path(repo_path).resolve()
        self.worktree_dir = self.repo_path / ".slim" / "worktrees"

    @staticmethod
    def is_git_repo(repo_path: str | Path) -> bool:
        """True se o caminho está dentro de um repo git válido (git rev-parse)."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(Path(repo_path).resolve()),
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return False
        return res.returncode == 0 and res.stdout.strip() == "true"

    def create_worktree(self, task_id: str) -> Path | None:
        """Cria uma Git Worktree isolada em .slim/worktrees/<task_id>."""
        os.makedirs(self.worktree_dir, exist_ok=True)
        target_path = self.worktree_dir / task_id
        branch_name = f"lf-worktree-{task_id}"

        # Remove registros administrativos órfãos de worktrees já removidas —
        # sem o prune, `worktree add` do MESMO path falha com "already exists".
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(self.repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )

        if target_path.exists():
            self.cleanup_worktree(task_id)

        res = subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(target_path), "HEAD"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if res.returncode == 0:
            return target_path

        res_existing = subprocess.run(
            ["git", "worktree", "add", str(target_path), branch_name],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if res_existing.returncode == 0:
            return target_path

        logger.warning("Falha ao criar worktree %s: %s", target_path, (res.stderr or "").strip())
        return None

    def _current_branch(self) -> str | None:
        """Branch corrente do repo (None em detached HEAD)."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT,
            )
        except Exception:
            return None
        if res.returncode != 0:
            return None
        branch = res.stdout.strip()
        return branch if branch != "HEAD" else None

    def commit_worktree(self, task_id: str, message: str) -> bool:
        """Commita as alterações da worktree (cwd = worktree path).

        Grava .gitignore (artefatos regeneráveis fora do commit) antes do
        add/commit. Se não houver nada para commitar (working tree limpa),
        retorna True com log — não é falha.
        """
        target_path = self.worktree_dir / task_id
        if not target_path.exists():
            logger.warning("commit_worktree: worktree %s não existe.", target_path)
            return False

        (target_path / ".gitignore").write_text(_GITIGNORE_CONTENT, encoding="utf-8")

        add = subprocess.run(
            ["git", "add", "-A"],
            cwd=str(target_path),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if add.returncode != 0:
            logger.warning("commit_worktree: git add falhou em %s: %s", target_path, (add.stderr or "").strip())
            return False

        res = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(target_path),
            capture_output=True,
            text=True,
            timeout=_GIT_COMMIT_TIMEOUT,
        )
        if res.returncode == 0:
            return True

        combined = (res.stdout or "") + (res.stderr or "")
        if "nothing to commit" in combined or "nothing added to commit" in combined:
            logger.info("commit_worktree: nada a commitar em %s (working tree limpa).", target_path)
            return True
        logger.warning("commit_worktree: git commit falhou em %s: %s", target_path, combined.strip())
        return False

    def merge_worktree(self, task_id: str, target_branch: str = "main") -> bool:
        """Faz o merge das alterações aprovadas na worktree para a branch alvo.

        Faz checkout de ``target_branch`` antes do merge e retorna à branch
        original ao final, preservando o estado do workdir de trabalho. Em
        FALHA de merge (ex.: conflito), executa ``git merge --abort`` e
        restaura a branch original — o repo nunca fica em estado MERGING.
        """
        branch_name = f"lf-worktree-{task_id}"
        original_branch = self._current_branch()

        if original_branch != target_branch:
            checkout = subprocess.run(
                ["git", "checkout", target_branch],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT,
            )
            if checkout.returncode != 0:
                return False

        res = subprocess.run(
            ["git", "merge", branch_name, "--no-ff", "-m", f"feat: merge worktree {task_id}"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )

        if res.returncode != 0:
            # Falha (ex.: conflito ou arquivo untracked colidindo): aborta o
            # merge e volta para a branch original antes de reportar falha.
            logger.warning("merge_worktree: merge de %s falhou: %s", branch_name, (res.stderr or "").strip())
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT,
            )
            if original_branch is not None and original_branch != target_branch:
                subprocess.run(
                    ["git", "checkout", original_branch],
                    cwd=str(self.repo_path),
                    capture_output=True,
                    text=True,
                    timeout=_GIT_TIMEOUT,
                )
            return False

        if original_branch is not None and original_branch != target_branch:
            subprocess.run(
                ["git", "checkout", original_branch],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT,
            )

        return True

    def cleanup_worktree(self, task_id: str) -> bool:
        """Remove a worktree isolada e sua branch temporária."""
        target_path = self.worktree_dir / task_id
        branch_name = f"lf-worktree-{task_id}"
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target_path)],
            cwd=str(self.repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=str(self.repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(self.repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        return not target_path.exists()

    def create_sandbox_branch(self, branch_name: str) -> bool:
        """Fallback legacy para branches simples."""
        res = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.repo_path,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        return res.returncode == 0

    def cleanup_branch(self, branch_name: str, target_branch: str = "main") -> bool:
        """Fallback legacy para exclusão de branch."""
        subprocess.run(
            ["git", "checkout", target_branch],
            cwd=self.repo_path,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        res = subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=self.repo_path,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        return res.returncode == 0
