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
import os


# ── Model construction ──────────────────────────────────────────────


def test_task_config_defaults():
    t = TaskConfig(id="t1", agent="a1", prompt="do stuff")
    assert t.depends_on == []
    assert t.outputs == []
    assert t.merge_strategy is None
    assert t.when is None
    assert t.priority == 0


def test_task_config_priority():
    t = TaskConfig(id="t1", agent="a1", prompt="do stuff", priority=10)
    assert t.priority == 10


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
    assert config.variables == {}


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
        "variables": {"ENV": "staging"},
    }
    path = tmp_path / "workflow.yaml"
    path.write_text(yaml.dump(yaml_content))

    config = WorkflowParser.parse(path)
    assert config.name == "example"
    assert len(config.tasks) == 2
    assert config.strategy.max_parallel == 2
    assert config.variables["ENV"] == "staging"


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


# ── resolve_variables ────────────────────────────────────────────────


def test_resolve_basic_variable():
    result = WorkflowParser.resolve_variables("Hello ${NAME}", {"NAME": "World"})
    assert result == "Hello World"


def test_resolve_default_value():
    result = WorkflowParser.resolve_variables("Hello ${NAME:-stranger}", {})
    assert result == "Hello stranger"


def test_resolve_explicit_overrides_default():
    result = WorkflowParser.resolve_variables("Hello ${NAME:-stranger}", {"NAME": "Alice"})
    assert result == "Hello Alice"


def test_resolve_env_fallback(monkeypatch):
    monkeypatch.setenv("TEST_AC_VAR", "from_env")
    result = WorkflowParser.resolve_variables("Value is ${TEST_AC_VAR}", {})
    assert result == "Value is from_env"


def test_resolve_dict_overrides_env(monkeypatch):
    monkeypatch.setenv("TEST_AC_VAR2", "from_env")
    result = WorkflowParser.resolve_variables("Value is ${TEST_AC_VAR2}", {"TEST_AC_VAR2": "from_dict"})
    assert result == "Value is from_dict"


def test_resolve_unresolved_without_default():
    result = WorkflowParser.resolve_variables("Value is ${MISSING}", {})
    assert result == "Value is "


def test_resolve_multiple_vars():
    result = WorkflowParser.resolve_variables("${A}-${B}", {"A": "x", "B": "y"})
    assert result == "x-y"


def test_parse_workflow_with_when(tmp_path):
    yaml_content = {
        "name": "cond",
        "agents": {"w": {"type": "claude-code"}},
        "tasks": [
            {"id": "t1", "agent": "w", "prompt": "hi", "when": "deploy"},
            {"id": "t2", "agent": "w", "prompt": "yo"},
        ],
    }
    path = tmp_path / "wf.yaml"
    path.write_text(yaml.dump(yaml_content))
    config = WorkflowParser.parse(path)
    assert config.tasks[0].when == "deploy"
    assert config.tasks[1].when is None


# ── resolve_task_outputs ─────────────────────────────────────────────


def test_resolve_task_outputs_basic():
    result = WorkflowParser.resolve_task_outputs(
        "Previous result: ${t1.output}", {"t1": "hello world"}
    )
    assert result == "Previous result: hello world"


def test_resolve_task_outputs_multiple():
    result = WorkflowParser.resolve_task_outputs(
        "${a.output} and ${b.output}", {"a": "first", "b": "second"}
    )
    assert result == "first and second"


def test_resolve_task_outputs_unresolved():
    result = WorkflowParser.resolve_task_outputs(
        "${missing.output} stays", {}
    )
    assert result == "${missing.output} stays"


def test_resolve_task_outputs_empty():
    result = WorkflowParser.resolve_task_outputs("no placeholders here", {})
    assert result == "no placeholders here"


# ── TaskConfig outputs field ──────────────────────────────────────────


def test_task_config_outputs_default():
    t = TaskConfig(id="t1", agent="a1", prompt="do stuff")
    assert t.outputs == []


def test_task_config_outputs_custom():
    t = TaskConfig(id="t1", agent="a1", prompt="do stuff", outputs=["file.txt"])
    assert t.outputs == ["file.txt"]


# ── include support ───────────────────────────────────────────────────


def test_parse_workflow_with_include(tmp_path):
    # Create included workflow
    inc_content = {
        "name": "included",
        "agents": {"helper": {"type": "claude-code"}},
        "tasks": [
            {"id": "inc_t1", "agent": "helper", "prompt": "help me"},
        ],
    }
    inc_path = tmp_path / "shared.yaml"
    inc_path.write_text(yaml.dump(inc_content))

    # Create main workflow that includes the above
    main_content = {
        "name": "main",
        "agents": {"main_agent": {"type": "claude-code"}},
        "tasks": [
            {"id": "t1", "agent": "main_agent", "prompt": "main task"},
        ],
        "include": ["shared.yaml"],
    }
    main_path = tmp_path / "workflow.yaml"
    main_path.write_text(yaml.dump(main_content))

    config = WorkflowParser.parse(main_path)
    task_ids = [t.id for t in config.tasks]
    assert "t1" in task_ids
    assert "inc_t1" in task_ids
    assert "helper" in config.agents
    assert "main_agent" in config.agents


def test_parse_workflow_include_missing_file(tmp_path):
    main_content = {
        "name": "main",
        "agents": {"a1": {"type": "claude-code"}},
        "tasks": [{"id": "t1", "agent": "a1", "prompt": "go"}],
        "include": ["nonexistent.yaml"],
    }
    main_path = tmp_path / "workflow.yaml"
    main_path.write_text(yaml.dump(main_content))

    with pytest.raises(FileNotFoundError, match="Included workflow file not found"):
        WorkflowParser.parse(main_path)


def test_workflow_config_include_default():
    config = WorkflowConfig(
        name="test",
        agents={"a1": AgentConfig(type="claude-code")},
        tasks=[TaskConfig(id="t1", agent="a1", prompt="go")],
    )
    assert config.include == []
