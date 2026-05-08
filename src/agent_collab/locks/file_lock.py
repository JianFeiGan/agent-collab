"""File-level locking for concurrent agent access."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path


class FileLockManager:
    """Manages file locks to prevent concurrent writes by multiple agents."""

    def __init__(self, lock_dir: str | Path = ".agent-collab/locks") -> None:
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._held_locks: dict[str, int] = {}

    def acquire(self, file_path: str, task_id: str) -> bool:
        """Try to acquire a lock for *file_path* on behalf of *task_id*.

        Returns True if the lock was acquired, False if already held.
        """
        lock_file = self._lock_path(file_path)
        try:
            fd = open(lock_file, "w")  # noqa: SIM115
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd.write(json.dumps({"task_id": task_id, "file": file_path}))
            fd.flush()
            self._held_locks[file_path] = fd
            return True
        except OSError:
            return False

    def release(self, file_path: str) -> None:
        """Release the lock for *file_path*."""
        fd = self._held_locks.pop(file_path, None)
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()
        lock_file = self._lock_path(file_path)
        if lock_file.exists():
            lock_file.unlink(missing_ok=True)

    def list_locked_files(self) -> list[str]:
        """Return file paths currently locked by this manager."""
        return list(self._held_locks.keys())

    def _lock_path(self, file_path: str) -> Path:
        safe_name = Path(file_path).name.replace("/", "_").replace("\\", "_")
        return self.lock_dir / f"{safe_name}.lock"
