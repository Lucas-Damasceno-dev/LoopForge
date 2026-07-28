from unittest.mock import MagicMock, patch

from lf.runner.git.checkpoint import GitCheckpointManager
from lf.runner.git.pr import create_github_pr
from lf.runner.git.sandbox import GitSandbox


def test_git_checkpoint_manager(tmp_path):
    manager = GitCheckpointManager(repo_path=tmp_path)
    with patch("subprocess.run") as mock_run:
        # Mock rev-parse HEAD return
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123commit\n", stderr="")
        commit_hash = manager.create_checkpoint("test checkpoint")
        assert commit_hash == "abc123commit"
        assert mock_run.call_count == 3

        # Test rollback_to
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = manager.rollback_to("abc123commit")
        assert success is True


def test_create_github_pr(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/pr/1", stderr="")
        res = create_github_pr(
            title="Test PR",
            body="PR Description",
            labels=["foundry:status:completed"],
            repo_path=tmp_path,
        )
        assert res is True

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
        res_fail = create_github_pr(
            title="Test PR",
            body="PR Description",
            labels=[],
            repo_path=tmp_path,
        )
        assert res_fail is False


def test_git_sandbox(tmp_path):
    sandbox = GitSandbox(repo_path=tmp_path)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert sandbox.create_sandbox_branch("feature/test") is True
        assert sandbox.cleanup_branch("feature/test", target_branch="main") is True
