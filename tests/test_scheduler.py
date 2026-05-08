"""Unit tests for task scheduler."""

from __future__ import annotations

import pytest

from agent_collab.core.scheduler import TaskScheduler
from agent_collab.core.workflow import AgentConfig, TaskConfig, WorkflowConfig


def _make_config(tasks_def: list[dict]) -> WorkflowConfig:
    """Helper: build a WorkflowConfig from simplified task dicts."""
    agents = {"worker": AgentConfig(type="claude-code")}
    tasks = []
    for td in tasks_def:
        tasks.append(
            TaskConfig(
                id=td["id"],
                agent="worker",
                prompt="",
                depends_on=td.get("depends_on", []),
                when=td.get("when"),
            )
        )
    return WorkflowConfig(name="test", agents=agents, tasks=tasks)


# ── Linear chain ────────────────────────────────────────────────────


def test_linear_chain():
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["b"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    order = scheduler.get_execution_order()
    assert order == [["a"], ["b"], ["c"]]


# ── Diamond pattern ─────────────────────────────────────────────────


def test_diamond_pattern():
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["a"]},
        {"id": "d", "depends_on": ["b", "c"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    order = scheduler.get_execution_order()
    assert order[0] == ["a"]
    assert set(order[1]) == {"b", "c"}
    assert order[2] == ["d"]


# ── All independent ─────────────────────────────────────────────────


def test_all_independent():
    config = _make_config([{"id": "x"}, {"id": "y"}, {"id": "z"}])
    scheduler = TaskScheduler(config.tasks)
    order = scheduler.get_execution_order()
    assert len(order) == 1
    assert set(order[0]) == {"x", "y", "z"}


# ── Single task ─────────────────────────────────────────────────────


def test_single_task():
    config = _make_config([{"id": "only"}])
    scheduler = TaskScheduler(config.tasks)
    assert scheduler.get_execution_order() == [["only"]]


# ── Cycle detection ─────────────────────────────────────────────────


def test_detect_direct_cycle():
    config = _make_config([
        {"id": "a", "depends_on": ["b"]},
        {"id": "b", "depends_on": ["a"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    assert scheduler.detect_cycles() is not None


def test_detect_indirect_cycle():
    config = _make_config([
        {"id": "a", "depends_on": ["c"]},
        {"id": "b", "depends_on": ["a"]},
        {"id": "c", "depends_on": ["b"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    assert scheduler.detect_cycles() is not None


def test_no_cycle_returns_none():
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    assert scheduler.detect_cycles() is None


def test_execution_order_raises_on_cycle():
    config = _make_config([
        {"id": "a", "depends_on": ["b"]},
        {"id": "b", "depends_on": ["a"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    with pytest.raises(ValueError, match="dependency cycle"):
        scheduler.get_execution_order()


# ── Complex graph ───────────────────────────────────────────────────


def test_complex_graph():
    """Two independent chains that merge at the end."""
    config = _make_config([
        {"id": "a1"},
        {"id": "a2", "depends_on": ["a1"]},
        {"id": "b1"},
        {"id": "b2", "depends_on": ["b1"]},
        {"id": "merge", "depends_on": ["a2", "b2"]},
    ])
    scheduler = TaskScheduler(config.tasks)
    order = scheduler.get_execution_order()

    assert set(order[0]) == {"a1", "b1"}
    assert set(order[1]) == {"a2", "b2"}
    assert order[2] == ["merge"]


# ── when-conditional tasks ───────────────────────────────────────────


def test_when_task_skipped():
    """Task with unsatisfied when clause is excluded."""
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"], "when": "deploy"},
    ])
    scheduler = TaskScheduler(config.tasks, context={"ENV": "test"})
    order = scheduler.get_execution_order()
    all_ids = [tid for level in order for tid in level]
    assert "a" in all_ids
    assert "b" not in all_ids


def test_when_task_runs_when_satisfied():
    """Task with satisfied when clause is included."""
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"], "when": "deploy"},
    ])
    scheduler = TaskScheduler(config.tasks, context={"ENV": "deploy"})
    order = scheduler.get_execution_order()
    all_ids = [tid for level in order for tid in level]
    assert "a" in all_ids
    assert "b" in all_ids


def test_when_none_always_runs():
    """Task without when clause always runs."""
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"]},
    ])
    scheduler = TaskScheduler(config.tasks, context={"ENV": "whatever"})
    order = scheduler.get_execution_order()
    all_ids = [tid for level in order for tid in level]
    assert "a" in all_ids
    assert "b" in all_ids


def test_skipped_task_does_not_block_downstream():
    """A skipped conditional task doesn't block its dependents."""
    config = _make_config([
        {"id": "a"},
        {"id": "b", "depends_on": ["a"], "when": "never"},
        {"id": "c", "depends_on": ["b"]},
    ])
    scheduler = TaskScheduler(config.tasks, context={"ENV": "prod"})
    order = scheduler.get_execution_order()
    all_ids = [tid for level in order for tid in level]
    assert "a" in all_ids
    assert "b" not in all_ids
    assert "c" in all_ids


# ── Priority sorting ─────────────────────────────────────────────────


def test_priority_higher_first():
    """Higher priority tasks appear first within a parallel level."""
    agents = {"worker": AgentConfig(type="claude-code")}
    tasks = [
        TaskConfig(id="low", agent="worker", prompt="", priority=0),
        TaskConfig(id="mid", agent="worker", prompt="", priority=5),
        TaskConfig(id="high", agent="worker", prompt="", priority=10),
    ]
    config = WorkflowConfig(name="test", agents=agents, tasks=tasks)
    scheduler = TaskScheduler(config.tasks)
    order = scheduler.get_execution_order()
    assert len(order) == 1
    assert order[0] == ["high", "mid", "low"]


def test_priority_does_not_break_dependencies():
    """Priority ordering respects dependency levels."""
    agents = {"worker": AgentConfig(type="claude-code")}
    tasks = [
        TaskConfig(id="dep", agent="worker", prompt="", priority=0),
        TaskConfig(id="a", agent="worker", prompt="", priority=10, depends_on=["dep"]),
        TaskConfig(id="b", agent="worker", prompt="", priority=20, depends_on=["dep"]),
    ]
    config = WorkflowConfig(name="test", agents=agents, tasks=tasks)
    scheduler = TaskScheduler(config.tasks)
    order = scheduler.get_execution_order()
    assert order[0] == ["dep"]
    assert order[1] == ["b", "a"]  # b has higher priority than a


# ── Cancel ───────────────────────────────────────────────────────────


def test_cancel_all_returns_empty():
    """After cancel_all(), get_execution_order returns an empty list."""
    config = _make_config([{"id": "a"}, {"id": "b"}])
    scheduler = TaskScheduler(config.tasks)
    scheduler.cancel_all()
    assert scheduler.get_execution_order() == []
