"""Unit tests for checkpoint management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_collab.core.checkpoint import Checkpoint, CheckpointManager


@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for checkpoint storage."""
    return tmp_path / "checkpoints"


@pytest.fixture
def manager(checkpoint_dir: Path) -> CheckpointManager:
    """Return a CheckpointManager using a temporary directory."""
    return CheckpointManager(base_dir=checkpoint_dir)


def test_checkpoint_defaults():
    cp = Checkpoint(checkpoint_id="test-1", workflow_name="wf")
    assert cp.checkpoint_id == "test-1"
    assert cp.workflow_name == "wf"
    assert cp.completed_tasks == []
    assert cp.task_outputs == {}
    assert cp.timestamp == ""
    assert cp.metadata == {}


def test_manager_creates_directory(checkpoint_dir: Path):
    assert not checkpoint_dir.exists()
    CheckpointManager(base_dir=checkpoint_dir)
    assert checkpoint_dir.exists()


def test_save_and_load(manager: CheckpointManager):
    cp = Checkpoint(
        checkpoint_id="cp-1",
        workflow_name="my-workflow",
        completed_tasks=["t1", "t2"],
        task_outputs={"t1": "output1", "t2": "output2"},
    )
    manager.save(cp)

    loaded = manager.load("cp-1")
    assert loaded.checkpoint_id == "cp-1"
    assert loaded.workflow_name == "my-workflow"
    assert loaded.completed_tasks == ["t1", "t2"]
    assert loaded.task_outputs == {"t1": "output1", "t2": "output2"}
    assert loaded.timestamp != ""


def test_save_auto_sets_timestamp(manager: CheckpointManager):
    cp = Checkpoint(checkpoint_id="cp-ts", workflow_name="wf")
    assert cp.timestamp == ""
    manager.save(cp)
    loaded = manager.load("cp-ts")
    assert loaded.timestamp != ""


def test_save_preserves_existing_timestamp(manager: CheckpointManager):
    cp = Checkpoint(
        checkpoint_id="cp-explicit",
        workflow_name="wf",
        timestamp="2024-01-01T00:00:00+00:00",
    )
    manager.save(cp)
    loaded = manager.load("cp-explicit")
    assert loaded.timestamp == "2024-01-01T00:00:00+00:00"


def test_load_nonexistent_raises(manager: CheckpointManager):
    with pytest.raises(FileNotFoundError, match="Checkpoint not found: missing"):
        manager.load("missing")


def test_list_checkpoints_empty(manager: CheckpointManager):
    assert manager.list_checkpoints() == []


def test_list_checkpoints_sorted(manager: CheckpointManager):
    cp1 = Checkpoint(
        checkpoint_id="cp-1",
        workflow_name="wf",
        timestamp="2024-01-01T00:00:00+00:00",
    )
    cp2 = Checkpoint(
        checkpoint_id="cp-2",
        workflow_name="wf",
        timestamp="2024-06-01T00:00:00+00:00",
    )
    cp3 = Checkpoint(
        checkpoint_id="cp-3",
        workflow_name="wf",
        timestamp="2024-03-01T00:00:00+00:00",
    )
    manager.save(cp1)
    manager.save(cp2)
    manager.save(cp3)

    cps = manager.list_checkpoints()
    assert len(cps) == 3
    assert cps[0].checkpoint_id == "cp-2"  # Most recent first
    assert cps[1].checkpoint_id == "cp-3"
    assert cps[2].checkpoint_id == "cp-1"


def test_delete_existing(manager: CheckpointManager):
    cp = Checkpoint(checkpoint_id="cp-del", workflow_name="wf")
    manager.save(cp)
    assert manager.delete("cp-del") is True
    # Confirm deleted
    with pytest.raises(FileNotFoundError):
        manager.load("cp-del")


def test_delete_nonexistent(manager: CheckpointManager):
    assert manager.delete("no-such-cp") is False


def test_save_creates_json_file(manager: CheckpointManager, checkpoint_dir: Path):
    cp = Checkpoint(
        checkpoint_id="cp-json",
        workflow_name="wf",
        completed_tasks=["t1"],
        task_outputs={"t1": "hello"},
    )
    manager.save(cp)

    file_path = checkpoint_dir / "cp-json.json"
    assert file_path.exists()
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data["checkpoint_id"] == "cp-json"
    assert data["completed_tasks"] == ["t1"]
    assert data["task_outputs"] == {"t1": "hello"}


def test_list_checkpoints_skips_invalid_json(
    manager: CheckpointManager, checkpoint_dir: Path
):
    # Save a valid checkpoint
    cp = Checkpoint(checkpoint_id="cp-valid", workflow_name="wf")
    manager.save(cp)

    # Write invalid JSON
    bad_file = checkpoint_dir / "bad.json"
    bad_file.write_text("not valid json {{{", encoding="utf-8")

    cps = manager.list_checkpoints()
    assert len(cps) == 1
    assert cps[0].checkpoint_id == "cp-valid"
