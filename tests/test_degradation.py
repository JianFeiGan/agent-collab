"""Unit tests for degradation policies."""

from __future__ import annotations

import asyncio

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.degradation import (
    DegradationHandler,
    DegradationPolicy,
    TaskDegradation,
)
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


# ── DegradationHandler tests ──────────────────────────────────────


def test_degradation_handler_record_failure():
    handler = DegradationHandler()
    assert handler.record_failure("t1") == 1
    assert handler.record_failure("t1") == 2
    assert handler.record_failure("t2") == 1


def test_degradation_handler_should_degrade():
    handler = DegradationHandler()
    deg = TaskDegradation(policy=DegradationPolicy.SKIP, max_failures=2)
    assert not handler.should_degrade("t1", deg)
    handler.record_failure("t1")
    assert not handler.should_degrade("t1", deg)
    handler.record_failure("t1")
    assert handler.should_degrade("t1", deg)


def test_degradation_handler_get_policy_below_threshold():
    handler = DegradationHandler()
    deg = TaskDegradation(policy=DegradationPolicy.ABORT, max_failures=3)
    handler.record_failure("t1")
    assert handler.get_policy("t1", deg) == DegradationPolicy.CONTINUE


def test_degradation_handler_get_policy_at_threshold():
    handler = DegradationHandler()
    deg = TaskDegradation(policy=DegradationPolicy.ABORT, max_failures=1)
    handler.record_failure("t1")
    assert handler.get_policy("t1", deg) == DegradationPolicy.ABORT


def test_degradation_policy_enum_values():
    assert DegradationPolicy.SKIP.value == "skip"
    assert DegradationPolicy.ABORT.value == "abort"
    assert DegradationPolicy.CONTINUE.value == "continue"


def test_task_degradation_defaults():
    deg = TaskDegradation()
    assert deg.policy == DegradationPolicy.ABORT
    assert deg.fallback_task_id is None
    assert deg.max_failures == 1


def test_task_degradation_with_fallback():
    deg = TaskDegradation(
        policy=DegradationPolicy.CONTINUE,
        fallback_task_id="fallback_task",
        max_failures=3,
    )
    assert deg.policy == DegradationPolicy.CONTINUE
    assert deg.fallback_task_id == "fallback_task"
    assert deg.max_failures == 3


# ── Executor degradation integration tests ────────────────────────


@pytest.mark.asyncio
async def test_executor_skip_degradation():
    """Task with SKIP degradation should return success=True on failure."""
    agent = _FakeAgent(output="boom", success=False)
    agents = {"w": agent}
    agent_configs = {"w": AgentConfig(type="fake")}
    strategy = StrategyConfig()
    executor = TaskExecutor(agents=agents, agent_configs=agent_configs, strategy=strategy)

    deg = TaskDegradation(policy=DegradationPolicy.SKIP, max_failures=1)
    task = TaskConfig(id="t1", agent="w", prompt="fail", degradation=deg)
    result = await executor.execute_task(task)

    # SKIP policy turns failure into success
    assert result.success
    assert "[degraded:skipped]" in result.output


@pytest.mark.asyncio
async def test_executor_abort_degradation():
    """Task with ABORT degradation should keep failure status."""
    agent = _FakeAgent(output="boom", success=False)
    agents = {"w": agent}
    agent_configs = {"w": AgentConfig(type="fake")}
    strategy = StrategyConfig()
    executor = TaskExecutor(agents=agents, agent_configs=agent_configs, strategy=strategy)

    deg = TaskDegradation(policy=DegradationPolicy.ABORT, max_failures=1)
    task = TaskConfig(id="t1", agent="w", prompt="fail", degradation=deg)
    result = await executor.execute_task(task)

    assert not result.success


@pytest.mark.asyncio
async def test_executor_continue_degradation():
    """Task with CONTINUE degradation should keep failure but mark it."""
    agent = _FakeAgent(output="boom", success=False)
    agents = {"w": agent}
    agent_configs = {"w": AgentConfig(type="fake")}
    strategy = StrategyConfig()
    executor = TaskExecutor(agents=agents, agent_configs=agent_configs, strategy=strategy)

    deg = TaskDegradation(policy=DegradationPolicy.CONTINUE, max_failures=1)
    task = TaskConfig(id="t1", agent="w", prompt="fail", degradation=deg)
    result = await executor.execute_task(task)

    assert not result.success
    assert "[degraded:continued]" in result.output


@pytest.mark.asyncio
async def test_executor_no_degradation_keeps_original():
    """Task without degradation should behave normally."""
    agent = _FakeAgent(output="boom", success=False)
    agents = {"w": agent}
    agent_configs = {"w": AgentConfig(type="fake")}
    strategy = StrategyConfig()
    executor = TaskExecutor(agents=agents, agent_configs=agent_configs, strategy=strategy)

    task = TaskConfig(id="t1", agent="w", prompt="fail")
    result = await executor.execute_task(task)

    assert not result.success
    assert result.output == "boom"
