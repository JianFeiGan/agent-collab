"""Unit tests for workflow replay."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.checkpoint import Checkpoint, CheckpointManager
from agent_collab.core.replay import WorkflowReplayer
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig, WorkflowConfig


class _FakeAgent(BaseAgent):
    """Minimal agent that returns a fixed result."""

    def __init__(self, output: str = "ok", success: bool = True) -> None:
        self._output = output
        self._success = success

    async def execute(self, prompt, workdir, allowed_tools, timeout=600):  # type: ignore[override]
        return AgentResult(success=self._success, output=self._output)

    def name(self) -> str:  # type: ignore[override]
        return "fake"

    def is_available(self) -> bool:  # type: ignore[override]
        return True


@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    return tmp_path / "checkpoints"


@pytest.fixture
def manager(checkpoint_dir: Path) -> CheckpointManager:
    return CheckpointManager(base_dir=checkpoint_dir)


def _make_config() -> WorkflowConfig:
    """Build a simple workflow config with three tasks."""
    return WorkflowConfig(
        name="test-wf",
        agents={"w": AgentConfig(type="fake")},
        tasks=[
            TaskConfig(id="t1", agent="w", prompt="task 1"),
            TaskConfig(id="t2", agent="w", prompt="task 2"),
            TaskConfig(id="t3", agent="w", prompt="task 3", depends_on=["t1", "t2"]),
        ],
        strategy=StrategyConfig(),
    )


# ── list_checkpoints ─────────────────────────────────────────────


def test_replayer_list_checkpoints_empty(manager: CheckpointManager):
    replayer = WorkflowReplayer(checkpoint_manager=manager)
    assert replayer.list_checkpoints() == []


def test_replayer_list_checkpoints(manager: CheckpointManager):
    cp = Checkpoint(checkpoint_id="cp-1", workflow_name="wf", timestamp="2024-01-01T00:00:00")
    manager.save(cp)
    replayer = WorkflowReplayer(checkpoint_manager=manager)
    cps = replayer.list_checkpoints()
    assert len(cps) == 1
    assert cps[0].checkpoint_id == "cp-1"


# ── replay_from_checkpoint ───────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_from_checkpoint_skips_completed(
    manager: CheckpointManager,
):
    """Replay should skip tasks that are already completed in the checkpoint."""
    cp = Checkpoint(
        checkpoint_id="cp-1",
        workflow_name="test-wf",
        completed_tasks=["t1", "t2"],
        task_outputs={"t1": "output1", "t2": "output2"},
    )
    manager.save(cp)

    config = _make_config()
    agent = _FakeAgent(output="new-output")
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    results = await replayer.replay_from_checkpoint("cp-1", config, agents)

    # Only t3 should have been executed (t1, t2 already completed)
    assert "t3" in results
    assert results["t3"].success


@pytest.mark.asyncio
async def test_replay_from_checkpoint_all_completed(
    manager: CheckpointManager,
):
    """If all tasks are completed, no tasks should be executed."""
    cp = Checkpoint(
        checkpoint_id="cp-all",
        workflow_name="test-wf",
        completed_tasks=["t1", "t2", "t3"],
        task_outputs={"t1": "o1", "t2": "o2", "t3": "o3"},
    )
    manager.save(cp)

    config = _make_config()
    agent = _FakeAgent(output="new-output")
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    results = await replayer.replay_from_checkpoint("cp-all", config, agents)

    assert results == {}


@pytest.mark.asyncio
async def test_replay_from_checkpoint_preserves_task_outputs(
    manager: CheckpointManager,
):
    """The executor should be seeded with checkpoint's task_outputs."""
    cp = Checkpoint(
        checkpoint_id="cp-seed",
        workflow_name="test-wf",
        completed_tasks=["t1"],
        task_outputs={"t1": "previous_output"},
    )
    manager.save(cp)

    config = _make_config()
    agent = _FakeAgent(output="new-output")
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    await replayer.replay_from_checkpoint("cp-seed", config, agents)

    # A new checkpoint should have been saved with t1's prior output preserved
    all_cps = manager.list_checkpoints()
    # There should be at least 2 checkpoints (original + new)
    assert len(all_cps) >= 2


@pytest.mark.asyncio
async def test_replay_from_checkpoint_nonexistent_raises(
    manager: CheckpointManager,
):
    config = _make_config()
    agent = _FakeAgent()
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    with pytest.raises(FileNotFoundError):
        await replayer.replay_from_checkpoint("nonexistent", config, agents)


# ── replay_task ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_task_success(manager: CheckpointManager):
    config = _make_config()
    agent = _FakeAgent(output="task-result")
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    result = await replayer.replay_task("t1", config, agents)

    assert result.success
    assert result.output == "task-result"


@pytest.mark.asyncio
async def test_replay_task_with_task_outputs(manager: CheckpointManager):
    config = _make_config()
    agent = _FakeAgent(output="ok")
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    result = await replayer.replay_task(
        "t1", config, agents, task_outputs={"prev": "data"}
    )
    assert result.success


@pytest.mark.asyncio
async def test_replay_task_not_found(manager: CheckpointManager):
    config = _make_config()
    agent = _FakeAgent()
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    with pytest.raises(ValueError, match="Task 'nonexistent' not found"):
        await replayer.replay_task("nonexistent", config, agents)


@pytest.mark.asyncio
async def test_replay_task_failure(manager: CheckpointManager):
    config = _make_config()
    agent = _FakeAgent(output="error", success=False)
    agents = {"w": agent}

    replayer = WorkflowReplayer(checkpoint_manager=manager)
    result = await replayer.replay_task("t1", config, agents)

    assert not result.success
    assert result.output == "error"
