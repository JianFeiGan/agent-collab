"""Unit tests for task executor — execution log and export."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig


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


def _make_executor(agent: BaseAgent | None = None) -> TaskExecutor:
    agents = {"w": agent or _FakeAgent()}
    agent_configs = {"w": AgentConfig(type="fake")}
    strategy = StrategyConfig()
    return TaskExecutor(agents=agents, agent_configs=agent_configs, strategy=strategy)


@pytest.mark.asyncio
async def test_execution_log_records_task_result():
    executor = _make_executor(_FakeAgent(output="hello world"))
    task = TaskConfig(id="t1", agent="w", prompt="do it")
    result = await executor.execute_task(task)
    assert result.success
    log = executor.get_execution_log()
    assert len(log) == 1
    entry = log[0]
    assert entry["task_id"] == "t1"
    assert entry["agent"] == "w"
    assert entry["status"] == "success"
    assert isinstance(entry["duration"], float)
    assert entry["output_summary"] == "hello world"


@pytest.mark.asyncio
async def test_execution_log_records_failure():
    executor = _make_executor(_FakeAgent(output="error occurred", success=False))
    task = TaskConfig(id="t2", agent="w", prompt="fail")
    result = await executor.execute_task(task)
    assert not result.success
    log = executor.get_execution_log()
    assert len(log) == 1
    assert log[0]["status"] == "failed"
    assert log[0]["output_summary"] == "error occurred"


@pytest.mark.asyncio
async def test_execution_log_truncates_long_output():
    long_output = "x" * 500
    executor = _make_executor(_FakeAgent(output=long_output))
    task = TaskConfig(id="t3", agent="w", prompt="long")
    await executor.execute_task(task)
    log = executor.get_execution_log()
    assert len(log[0]["output_summary"]) == 200


@pytest.mark.asyncio
async def test_execution_log_multiple_tasks():
    executor = _make_executor()
    for i in range(3):
        task = TaskConfig(id=f"t{i}", agent="w", prompt=f"task {i}")
        await executor.execute_task(task)
    log = executor.get_execution_log()
    assert len(log) == 3
    assert [e["task_id"] for e in log] == ["t0", "t1", "t2"]


def test_get_execution_log_returns_copy():
    executor = _make_executor()
    log1 = executor.get_execution_log()
    log1.append({"fake": True})
    log2 = executor.get_execution_log()
    assert log2 == []


@pytest.mark.asyncio
async def test_export_log_creates_json_file(tmp_path):
    executor = _make_executor(_FakeAgent(output="done"))
    task = TaskConfig(id="t1", agent="w", prompt="go")
    await executor.execute_task(task)

    export_path = str(tmp_path / "log.json")
    executor.export_log(export_path)

    with open(export_path) as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["task_id"] == "t1"
    assert data[0]["status"] == "success"
