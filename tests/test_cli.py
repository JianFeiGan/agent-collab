"""Tests for the CLI commands."""

from __future__ import annotations

import pytest
import yaml
from typer.testing import CliRunner

from agent_collab.agents.base import AgentResult
from agent_collab.cli import AGENT_REGISTRY, app

runner = CliRunner()


# ── Helpers ─────────────────────────────────────────────────────────


def _write_workflow(path, *, tasks=None, agents=None):
    """Write a minimal valid workflow YAML and return its path."""
    data = {
        "name": "test-workflow",
        "agents": agents or {"worker": {"type": "claude-code"}},
        "tasks": tasks or [{"id": "t1", "agent": "worker", "prompt": "hello"}],
    }
    p = path / "workflow.yaml"
    p.write_text(yaml.dump(data))
    return p


# ── validate command ────────────────────────────────────────────────


class TestValidateCommand:
    def test_valid_workflow(self, tmp_path):
        path = _write_workflow(tmp_path)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()
        assert "test-workflow" in result.output

    def test_valid_workflow_shows_details(self, tmp_path):
        tasks = [
            {"id": "t1", "agent": "worker", "prompt": "a"},
            {"id": "t2", "agent": "worker", "prompt": "b", "depends_on": ["t1"]},
        ]
        path = _write_workflow(tmp_path, tasks=tasks)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code == 0
        assert "Tasks: 2" in result.output
        assert "Execution levels: 2" in result.output

    def test_missing_file(self, tmp_path):
        result = runner.invoke(app, ["validate", str(tmp_path / "nope.yaml")])
        assert result.exit_code != 0

    def test_unknown_agent(self, tmp_path):
        tasks = [{"id": "t1", "agent": "ghost", "prompt": "go"}]
        path = _write_workflow(tmp_path, tasks=tasks)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code != 0

    def test_unknown_dependency(self, tmp_path):
        tasks = [
            {"id": "t1", "agent": "worker", "prompt": "go", "depends_on": ["missing"]},
        ]
        path = _write_workflow(tmp_path, tasks=tasks)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code != 0

    def test_cyclic_dependency(self, tmp_path):
        tasks = [
            {"id": "a", "agent": "worker", "prompt": "", "depends_on": ["b"]},
            {"id": "b", "agent": "worker", "prompt": "", "depends_on": ["a"]},
        ]
        path = _write_workflow(tmp_path, tasks=tasks)
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code != 0

    def test_invalid_yaml_syntax(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("not: [valid: yaml: {{")
        result = runner.invoke(app, ["validate", str(path)])
        assert result.exit_code != 0


# ── list-agents command ─────────────────────────────────────────────


class TestListAgentsCommand:
    def test_shows_all_agents(self):
        result = runner.invoke(app, ["list-agents"])
        assert result.exit_code == 0
        assert "claude-code" in result.output
        assert "codex" in result.output
        assert "aider" in result.output

    def test_shows_status_column(self):
        result = runner.invoke(app, ["list-agents"])
        assert result.exit_code == 0
        # Should show either "available" or "not found" for each agent
        assert "available" in result.output or "not found" in result.output


# ── run command ─────────────────────────────────────────────────────


class TestRunCommand:
    def test_successful_run(self, tmp_path, monkeypatch):
        """Run a single-task workflow with a mocked agent."""
        path = _write_workflow(tmp_path)

        async def fake_execute(prompt, workdir, allowed_tools, timeout=600):
            return AgentResult(success=True, output="done", duration_seconds=0.1)

        monkeypatch.setattr(AGENT_REGISTRY["claude-code"], "execute", fake_execute)

        result = runner.invoke(app, ["run", str(path)])
        assert result.exit_code == 0
        assert "test-workflow" in result.output
        assert "done" in result.output

    def test_failed_task_exits_nonzero(self, tmp_path, monkeypatch):
        """A failing task should cause exit code 1."""
        path = _write_workflow(tmp_path)

        async def fake_execute(prompt, workdir, allowed_tools, timeout=600):
            return AgentResult(success=False, output="boom", duration_seconds=0.1)

        monkeypatch.setattr(AGENT_REGISTRY["claude-code"], "execute", fake_execute)

        result = runner.invoke(app, ["run", str(path)])
        assert result.exit_code == 1
        assert "FAILED" in result.output

    def test_parallel_tasks(self, tmp_path, monkeypatch):
        """Two independent tasks should both run."""
        tasks = [
            {"id": "t1", "agent": "worker", "prompt": "a"},
            {"id": "t2", "agent": "worker", "prompt": "b"},
        ]
        path = _write_workflow(tmp_path, tasks=tasks)

        call_log: list[str] = []

        async def fake_execute(prompt, workdir, allowed_tools, timeout=600):
            call_log.append(prompt)
            return AgentResult(success=True, output="ok", duration_seconds=0.05)

        monkeypatch.setattr(AGENT_REGISTRY["claude-code"], "execute", fake_execute)

        result = runner.invoke(app, ["run", str(path)])
        assert result.exit_code == 0
        assert len(call_log) == 2

    def test_sequential_dependency(self, tmp_path, monkeypatch):
        """Tasks with dependencies run in correct order."""
        tasks = [
            {"id": "t1", "agent": "worker", "prompt": "first"},
            {"id": "t2", "agent": "worker", "prompt": "second", "depends_on": ["t1"]},
        ]
        path = _write_workflow(tmp_path, tasks=tasks)
        order: list[str] = []

        async def fake_execute(prompt, workdir, allowed_tools, timeout=600):
            order.append(prompt)
            return AgentResult(success=True, output="ok", duration_seconds=0.05)

        monkeypatch.setattr(AGENT_REGISTRY["claude-code"], "execute", fake_execute)

        result = runner.invoke(app, ["run", str(path)])
        assert result.exit_code == 0
        assert order == ["first", "second"]

    def test_missing_workflow_file(self):
        result = runner.invoke(app, ["run", "/nonexistent/workflow.yaml"])
        assert result.exit_code != 0


# ── no-args shows help ──────────────────────────────────────────────


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # Typer exits with 2 (usage) when no_args_is_help triggers
    assert "agent-collab" in result.output.lower()
