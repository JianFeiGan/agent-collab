"""Tests for the hook system (HookRegistry and HookContext)."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from agent_collab.agents.base import AgentResult
from agent_collab.plugins.hooks import HookContext, HookRegistry


# ---------------------------------------------------------------------------
# HookContext
# ---------------------------------------------------------------------------


def test_hook_context_defaults() -> None:
    ctx = HookContext()
    assert ctx.task_id == ""
    assert ctx.result is None
    assert ctx.error is None
    assert ctx.metadata == {}


def test_hook_context_with_values() -> None:
    result = AgentResult(success=True, output="ok")
    ctx = HookContext(task_id="t1", result=result, metadata={"k": "v"})
    assert ctx.task_id == "t1"
    assert ctx.result is result
    assert ctx.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# HookRegistry — registration
# ---------------------------------------------------------------------------


def test_register_before_hook() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_before(hook)
    assert registry.before_hooks == [hook]


def test_register_after_hook() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_after(hook)
    assert registry.after_hooks == [hook]


def test_register_failure_hook() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_failure(hook)
    assert registry.failure_hooks == [hook]


def test_hooks_lists_are_copies() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_before(hook)
    hooks = registry.before_hooks
    hooks.append(AsyncMock())
    assert len(registry.before_hooks) == 1


# ---------------------------------------------------------------------------
# HookRegistry — triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_before_calls_hook() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_before(hook)
    ctx = await registry.trigger_before("t1", "hello", "agent-a")
    hook.assert_awaited_once_with("t1", "hello", "agent-a", {})
    assert ctx.task_id == "t1"


@pytest.mark.asyncio
async def test_trigger_before_passes_metadata() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_before(hook)
    meta = {"existing": "data"}
    ctx = await registry.trigger_before("t1", "hello", "agent-a", metadata=meta)
    hook.assert_awaited_once_with("t1", "hello", "agent-a", meta)
    assert ctx.metadata is meta


@pytest.mark.asyncio
async def test_trigger_before_multiple_hooks() -> None:
    registry = HookRegistry()
    h1 = AsyncMock()
    h2 = AsyncMock()
    registry.register_before(h1)
    registry.register_before(h2)
    await registry.trigger_before("t1", "prompt", "agent")
    h1.assert_awaited_once()
    h2.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_after_calls_hook() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_after(hook)
    result = AgentResult(success=True, output="done")
    ctx = await registry.trigger_after("t1", result)
    hook.assert_awaited_once_with("t1", result, {})
    assert ctx.result is result


@pytest.mark.asyncio
async def test_trigger_failure_calls_hook() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_failure(hook)
    error = ValueError("boom")
    ctx = await registry.trigger_failure("t1", error=error)
    hook.assert_awaited_once_with("t1", error, None, {})
    assert ctx.error is error


@pytest.mark.asyncio
async def test_trigger_failure_with_result() -> None:
    registry = HookRegistry()
    hook = AsyncMock()
    registry.register_failure(hook)
    result = AgentResult(success=False, output="err")
    ctx = await registry.trigger_failure("t1", error=None, result=result)
    hook.assert_awaited_once_with("t1", None, result, {})
    assert ctx.result is result


@pytest.mark.asyncio
async def test_trigger_hooks_not_called_when_empty() -> None:
    registry = HookRegistry()
    ctx = await registry.trigger_before("t1", "prompt", "agent")
    assert ctx.task_id == "t1"
    ctx = await registry.trigger_after("t1", AgentResult(success=True, output=""))
    assert ctx.task_id == "t1"
    ctx = await registry.trigger_failure("t1")
    assert ctx.task_id == "t1"


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_before_survives_hook_exception(caplog: pytest.LogCaptureFixture) -> None:
    """If a hook raises, the others should still run."""
    registry = HookRegistry()

    async def _bad_hook(task_id, prompt, agent_name, metadata):  # type: ignore[no-untyped-def]
        raise RuntimeError("oops")

    good_hook = AsyncMock()
    registry.register_before(_bad_hook)
    registry.register_before(good_hook)

    with caplog.at_level(logging.ERROR):
        ctx = await registry.trigger_before("t1", "p", "a")

    good_hook.assert_awaited_once()
    assert ctx.task_id == "t1"
    assert "before-task hook" in caplog.text


@pytest.mark.asyncio
async def test_trigger_after_survives_hook_exception(caplog: pytest.LogCaptureFixture) -> None:
    registry = HookRegistry()

    async def _bad_hook(task_id, result, metadata):  # type: ignore[no-untyped-def]
        raise RuntimeError("oops")

    good_hook = AsyncMock()
    registry.register_after(_bad_hook)
    registry.register_after(good_hook)

    result = AgentResult(success=True, output="ok")
    with caplog.at_level(logging.ERROR):
        await registry.trigger_after("t1", result)

    good_hook.assert_awaited_once()
    assert "after-task hook" in caplog.text


@pytest.mark.asyncio
async def test_trigger_failure_survives_hook_exception(caplog: pytest.LogCaptureFixture) -> None:
    registry = HookRegistry()

    async def _bad_hook(task_id, error, result, metadata):  # type: ignore[no-untyped-def]
        raise RuntimeError("oops")

    good_hook = AsyncMock()
    registry.register_failure(_bad_hook)
    registry.register_failure(good_hook)

    with caplog.at_level(logging.ERROR):
        await registry.trigger_failure("t1", error=ValueError("x"))

    good_hook.assert_awaited_once()
    assert "on-failure hook" in caplog.text
