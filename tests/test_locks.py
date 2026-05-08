"""Tests for the file lock manager."""

from __future__ import annotations

import pytest

from agent_collab.locks.file_lock import FileLockManager


@pytest.fixture
def lock_mgr(tmp_path):  # type: ignore[no-untyped-def]
    return FileLockManager(lock_dir=tmp_path / "locks")


def test_acquire_and_release(lock_mgr: FileLockManager) -> None:
    assert lock_mgr.acquire("src/main.py", "task-1")
    assert "src/main.py" in lock_mgr.list_locked_files()
    lock_mgr.release("src/main.py")
    assert "src/main.py" not in lock_mgr.list_locked_files()


def test_double_acquire_fails(lock_mgr: FileLockManager) -> None:
    assert lock_mgr.acquire("src/main.py", "task-1")
    assert not lock_mgr.acquire("src/main.py", "task-2")
    lock_mgr.release("src/main.py")


def test_release_then_acquire(lock_mgr: FileLockManager) -> None:
    lock_mgr.acquire("a.py", "t1")
    lock_mgr.release("a.py")
    assert lock_mgr.acquire("a.py", "t2")


def test_multiple_files(lock_mgr: FileLockManager) -> None:
    assert lock_mgr.acquire("a.py", "t1")
    assert lock_mgr.acquire("b.py", "t2")
    assert set(lock_mgr.list_locked_files()) == {"a.py", "b.py"}


def test_release_nonexistent_is_noop(lock_mgr: FileLockManager) -> None:
    lock_mgr.release("ghost.py")  # should not raise
