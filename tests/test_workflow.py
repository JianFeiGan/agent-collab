"""Unit tests for workflow parser."""

from __future__ import annotations

import pytest
import yaml

from agent_collab.core.workflow import (
    AgentConfig,
    StrategyConfig,
    TaskConfig,
    WorkflowConfig,
    WorkflowParser,
)


# ── Model construction ──────────────────────────────────────────────


def test_task_config_defaults():
    t = TaskConfig(id="t1", agent="a1", prompt="do stuff")
    assert t.depends_on == []
    assert t.outputs == []
    assert t.merge_strategy is None


def test_agent_config_defaults():
    a = AgentConfig(type="claude-code")
    assert a.model == "sonnet"
    assert a.workdir == "."
    assert a.allowed_tools == []


def test_strategy_config_defaults():
    s = StrategyConfig()
    assert s.max_parallel == 4
    assert s.retry_on_failure is False
    assert s.max_retries == 0
    assert s.timeout_per_task == 600


def test_workflow_config_construction():
    config = WorkflowConfig(
        name="test",
        agents={"a1": AgentConfig(type="claude-code")},
        tasks=[TaskConfig(id="t1", agent="a1", prompt="go")],
    )
    assert config.name == "test"
    assert config.description == ""
    assert isinstance(config.strategy, StrategyConfig)


# ── Validation ──────────────────────────────────────────────────────


def test_unknown_agent_raises():
    with pytest.raises(ValueError, match="unknown agent 'ghost'"):
        WorkflowConfig(
            name="bad",
            agents={"a1": AgentConfig(type="claude-code")},
            tasks=[TaskConfig(id="t1", agent="ghost", prompt="go")],
        )


def test_unknown_dependency_raises():
    with pytest.raises(ValueError, match="unknown task 'missing'"):
        WorkflowConfig(
            name="bad",
            agents={"a1": AgentConfig(type="claude-code")},
            tasks=[
                TaskConfig(id="t1", agent="a1", prompt="go", depends_on=["missing"]),
            ],
        )


# ── Cycle detection ─────────────────────────────────────────────────


def test_cycle_detection_direct():
    tasks = [
        TaskConfig(id="a", agent="x", prompt="", depends_on=["b"]),
        TaskConfig(id="b", agent="x", prompt="", depends_on=["a"]),
    ]
    with pytest.raises(ValueError, match="Dependency cycle"):
        WorkflowParser._check_cycles(tasks)


def test_cycle_detection_indirect():
    tasks = [
        TaskConfig(id="a", agent="x", prompt="", depends_on=["b"]),
        TaskConfig(id="b", agent="x", prompt="", depends_on=["c"]),
        TaskConfig(id="c", agent="x", prompt="", depends_on=["a"]),
    ]
    with pytest.raises(ValueError, match="Dependency cycle"):
        WorkflowParser._check_cycles(tasks)


def test_no_cycle_passes():
    tasks = [
        TaskConfig(id="a", agent="x", prompt=""),
        TaskConfig(id="b", agent="x", prompt="", depends_on=["a"]),
        TaskConfig(id="c", agent="x", prompt="", depends_on=["a"]),
        TaskConfig(id="d", agent="x", prompt="", depends_on=["b", "c"]),
    ]
    WorkflowParser._check_cycles(tasks)  # should not raise


# ── YAML parsing ────────────────────────────────────────────────────


def test_parse_valid_yaml(tmp_path):
    yaml_content = {
        "name": "example",
        "description": "test workflow",
        "agents": {
            "worker": {"type": "claude-code", "model": "sonnet"},
        },
        "tasks": [
            {"id": "t1", "agent": "worker", "prompt": "hello"},
            {"id": "t2", "agent": "worker", "prompt": "world", "depends_on": ["t1"]},
        ],
        "strategy": {"max_parallel": 2},
    }
    path = tmp_path / "workflow.yaml"
    path.write_text(yaml.dump(yaml_content))

    config = WorkflowParser.parse(path)
    assert config.name == "example"
    assert len(config.tasks) == 2
    assert config.strategy.max_parallel == 2


def test_parse_missing_file():
    with pytest.raises(FileNotFoundError):
        WorkflowParser.parse("/nonexistent/workflow.yaml")


def test_parse_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("not: [valid: yaml: {{")

    # yaml.safe_load may or may not raise depending on content;
    # this specific content raises a YAML error
    with pytest.raises(Exception):
        WorkflowParser.parse(path)


def test_parse_non_dict_yaml(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text(yaml.dump([1, 2, 3]))
    with pytest.raises(ValueError, match="Invalid workflow file"):
        WorkflowParser.parse(path)
