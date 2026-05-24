"""Tests for result merger module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_collab.core.merger import ResultMerger


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    """Create a temporary repository directory."""
    return tmp_path / "repo"


@pytest.fixture
def merger(repo_dir: Path) -> ResultMerger:
    """Create a ResultMerger instance."""
    return ResultMerger(repo_dir=repo_dir)


class TestResultMerger:
    """Tests for ResultMerger class."""

    def test_init(self, repo_dir: Path) -> None:
        """Test initialization."""
        merger = ResultMerger(repo_dir=repo_dir)
        assert merger.repo_dir == repo_dir

    def test_init_default(self) -> None:
        """Test initialization with default directory."""
        merger = ResultMerger()
        assert merger.repo_dir == Path(".")

    def test_create_task_branch(self, merger: ResultMerger) -> None:
        """Test creating a task branch."""
        with patch.object(merger, "_git") as mock_git:
            branch = merger.create_task_branch("task1")
            assert branch == "agent-collab/task1"
            mock_git.assert_called_once_with("checkout", "-b", "agent-collab/task1", "HEAD")

    def test_create_task_branch_custom_base(self, merger: ResultMerger) -> None:
        """Test creating a task branch with custom base."""
        with patch.object(merger, "_git") as mock_git:
            branch = merger.create_task_branch("task1", base_branch="develop")
            assert branch == "agent-collab/task1"
            mock_git.assert_called_once_with("checkout", "-b", "agent-collab/task1", "develop")

    def test_commit_task_output(self, merger: ResultMerger) -> None:
        """Test committing task output."""
        with patch.object(merger, "_git") as mock_git:
            merger.commit_task_output("task1", ["file1.py", "file2.py"])
            assert mock_git.call_count == 3
            mock_git.assert_any_call("add", "file1.py")
            mock_git.assert_any_call("add", "file2.py")
            mock_git.assert_any_call("commit", "-m", "[agent-collab] task1")

    def test_commit_task_output_empty_files(self, merger: ResultMerger) -> None:
        """Test committing with empty file list."""
        with patch.object(merger, "_git") as mock_git:
            merger.commit_task_output("task1", [])
            mock_git.assert_called_once_with("commit", "-m", "[agent-collab] task1")

    def test_merge_task_branch(self, merger: ResultMerger) -> None:
        """Test merging a task branch."""
        with patch.object(merger, "_git") as mock_git:
            merger.merge_task_branch("task1")
            assert mock_git.call_count == 2
            mock_git.assert_any_call("checkout", "main")
            mock_git.assert_any_call("merge", "--no-ff", "-m", "Merge agent-collab/task1", "agent-collab/task1")

    def test_merge_task_branch_custom_target(self, merger: ResultMerger) -> None:
        """Test merging a task branch with custom target."""
        with patch.object(merger, "_git") as mock_git:
            merger.merge_task_branch("task1", target_branch="develop")
            assert mock_git.call_count == 2
            mock_git.assert_any_call("checkout", "develop")
            mock_git.assert_any_call("merge", "--no-ff", "-m", "Merge agent-collab/task1", "agent-collab/task1")

    def test_cleanup_branch(self, merger: ResultMerger) -> None:
        """Test cleaning up a task branch."""
        with patch.object(merger, "_git") as mock_git:
            merger.cleanup_branch("task1")
            mock_git.assert_called_once_with("branch", "-d", "agent-collab/task1")

    def test_git_success(self, merger: ResultMerger) -> None:
        """Test successful git command execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = merger._git("status")
            assert result.returncode == 0
            mock_run.assert_called_once_with(
                ["git", "status"],
                cwd=merger.repo_dir,
                capture_output=True,
                text=True,
                check=True,
            )

    def test_git_failure(self, merger: ResultMerger) -> None:
        """Test git command failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Git command failed")
            with pytest.raises(Exception, match="Git command failed"):
                merger._git("status")

    def test_git_with_multiple_args(self, merger: ResultMerger) -> None:
        """Test git command with multiple arguments."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            merger._git("commit", "-m", "test message")
            mock_run.assert_called_once_with(
                ["git", "commit", "-m", "test message"],
                cwd=merger.repo_dir,
                capture_output=True,
                text=True,
                check=True,
            )