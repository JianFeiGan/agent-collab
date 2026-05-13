"""Tests for the PluginManager."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.plugins.interfaces import (
    AgentPlugin,
    FormatterPlugin,
    HookPlugin,
)
from agent_collab.plugins.manager import PluginManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubAgent(BaseAgent):
    """Minimal agent for testing."""

    async def execute(self, prompt, workdir, allowed_tools, timeout=600):  # type: ignore[override]
        return AgentResult(success=True, output="stub")

    def name(self) -> str:
        return "stub"

    def is_available(self) -> bool:
        return True


class _StubAgentPlugin(AgentPlugin):
    name: str = "stub-agent"
    description: str = "A stub agent plugin"

    def create_agent(self, **kwargs: object) -> BaseAgent:
        return _StubAgent(**kwargs)  # type: ignore[arg-type]


class _StubHookPlugin(HookPlugin):
    def __init__(self) -> None:
        self.name = "stub-hook"
        self.description = "A stub hook plugin"
        self.called_before = False
        self.called_after = False
        self.called_failure = False

    async def on_before_task(self, task_id, prompt, agent_name, metadata):  # type: ignore[override]
        self.called_before = True

    async def on_after_task(self, task_id, result, metadata):  # type: ignore[override]
        self.called_after = True

    async def on_task_failure(self, task_id, error, result, metadata):  # type: ignore[override]
        self.called_failure = True


class _StubFormatterPlugin(FormatterPlugin):
    name: str = "stub-formatter"
    description: str = "A stub formatter plugin"

    def format_result(self, result: AgentResult) -> str:
        return f"formatted: {result.output}"

    def format_output(self, output: str) -> str:
        return f"[{output}]"


# ---------------------------------------------------------------------------
# Tests — registration
# ---------------------------------------------------------------------------


def test_register_agent_plugin() -> None:
    pm = PluginManager()
    plugin = _StubAgentPlugin()
    pm.register_plugin(plugin)
    assert pm.get_agent_plugins() == [plugin]


def test_register_hook_plugin() -> None:
    pm = PluginManager()
    plugin = _StubHookPlugin()
    pm.register_plugin(plugin)
    assert pm.get_hook_plugins() == [plugin]


def test_register_formatter_plugin() -> None:
    pm = PluginManager()
    plugin = _StubFormatterPlugin()
    pm.register_plugin(plugin)
    assert pm.get_formatter_plugins() == [plugin]


def test_register_unknown_type_raises() -> None:
    pm = PluginManager()
    with pytest.raises(TypeError, match="not an AgentPlugin"):
        pm.register_plugin("not a plugin")  # type: ignore[arg-type]


def test_register_multiple_plugins() -> None:
    pm = PluginManager()
    pm.register_plugin(_StubAgentPlugin())
    pm.register_plugin(_StubHookPlugin())
    pm.register_plugin(_StubFormatterPlugin())
    assert len(pm.get_agent_plugins()) == 1
    assert len(pm.get_hook_plugins()) == 1
    assert len(pm.get_formatter_plugins()) == 1


def test_get_agent_plugin_by_name() -> None:
    pm = PluginManager()
    plugin = _StubAgentPlugin()
    pm.register_plugin(plugin)
    assert pm.get_agent_plugin("stub-agent") is plugin
    assert pm.get_agent_plugin("nonexistent") is None


def test_get_formatter_plugin_by_name() -> None:
    pm = PluginManager()
    plugin = _StubFormatterPlugin()
    pm.register_plugin(plugin)
    assert pm.get_formatter_plugin("stub-formatter") is plugin
    assert pm.get_formatter_plugin("nonexistent") is None


# ---------------------------------------------------------------------------
# Tests — agent creation
# ---------------------------------------------------------------------------


def test_agent_plugin_create_agent() -> None:
    pm = PluginManager()
    pm.register_plugin(_StubAgentPlugin())
    plugin = pm.get_agent_plugin("stub-agent")
    assert plugin is not None
    agent = plugin.create_agent()
    assert isinstance(agent, BaseAgent)
    assert agent.name() == "stub"


# ---------------------------------------------------------------------------
# Tests — formatter
# ---------------------------------------------------------------------------


def test_formatter_format_result() -> None:
    pm = PluginManager()
    pm.register_plugin(_StubFormatterPlugin())
    plugin = pm.get_formatter_plugin("stub-formatter")
    assert plugin is not None
    result = AgentResult(success=True, output="hello")
    assert plugin.format_result(result) == "formatted: hello"


def test_formatter_format_output() -> None:
    pm = PluginManager()
    pm.register_plugin(_StubFormatterPlugin())
    plugin = pm.get_formatter_plugin("stub-formatter")
    assert plugin is not None
    assert plugin.format_output("world") == "[world]"


# ---------------------------------------------------------------------------
# Tests — hook registry wiring
# ---------------------------------------------------------------------------


def test_hook_plugin_wired_to_registry() -> None:
    pm = PluginManager()
    plugin = _StubHookPlugin()
    pm.register_plugin(plugin)
    registry = pm.hook_registry
    # The hook methods should be registered
    assert len(registry.before_hooks) >= 1
    assert len(registry.after_hooks) >= 1
    assert len(registry.failure_hooks) >= 1


# ---------------------------------------------------------------------------
# Tests — hook triggers via PluginManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_before_task() -> None:
    pm = PluginManager()
    hook = _StubHookPlugin()
    pm.register_plugin(hook)
    metadata = await pm.trigger_before_task("t1", "prompt", "agent")
    assert hook.called_before
    assert isinstance(metadata, dict)


@pytest.mark.asyncio
async def test_trigger_after_task() -> None:
    pm = PluginManager()
    hook = _StubHookPlugin()
    pm.register_plugin(hook)
    result = AgentResult(success=True, output="ok")
    metadata = await pm.trigger_after_task("t1", result)
    assert hook.called_after


@pytest.mark.asyncio
async def test_trigger_on_failure() -> None:
    pm = PluginManager()
    hook = _StubHookPlugin()
    pm.register_plugin(hook)
    metadata = await pm.trigger_on_failure("t1", error=ValueError("oops"))
    assert hook.called_failure


# ---------------------------------------------------------------------------
# Tests — load_plugins (empty — no real entry points installed)
# ---------------------------------------------------------------------------


def test_load_plugins_returns_zero_with_no_entry_points() -> None:
    pm = PluginManager()
    count = pm.load_plugins()
    assert count == 0
