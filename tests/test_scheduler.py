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
