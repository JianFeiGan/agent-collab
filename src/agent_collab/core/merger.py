"""Git-based result merging for multi-agent task outputs."""

from __future__ import annotations

import subprocess
from pathlib import Path


class ResultMerger:
    """Merges task output branches back into the working branch."""

    def __init__(self, repo_dir: str | Path = ".") -> None:
        self.repo_dir = Path(repo_dir)

    def create_task_branch(self, task_id: str, base_branch: str = "HEAD") -> str:
        """Create a new branch for a task's output.

        Args:
            task_id: Identifier used in the branch name.
            base_branch: Ref to branch from.

        Returns:
            The new branch name.
        """
        branch = f"agent-collab/{task_id}"
        self._git("checkout", "-b", branch, base_branch)
        return branch

    def commit_task_output(self, task_id: str, files: list[str]) -> None:
        """Stage and commit changed files for a task.

        Args:
            task_id: Used in the commit message.
            files: List of file paths to stage.
        """
        for f in files:
            self._git("add", f)
        self._git("commit", "-m", f"[agent-collab] {task_id}")

    def merge_task_branch(self, task_id: str, target_branch: str = "main") -> None:
        """Merge a task branch into the target branch.

        Args:
            task_id: Identifies the branch to merge.
            target_branch: Branch to merge into.
        """
        branch = f"agent-collab/{task_id}"
        self._git("checkout", target_branch)
        self._git("merge", "--no-ff", "-m", f"Merge {branch}", branch)

    def cleanup_branch(self, task_id: str) -> None:
        """Delete the task branch after successful merge."""
        branch = f"agent-collab/{task_id}"
        self._git("branch", "-d", branch)

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
