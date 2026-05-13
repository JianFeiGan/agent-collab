"""Plugin manager — discovers, registers, and queries plugins."""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Any

from agent_collab.agents.base import AgentResult
from agent_collab.plugins.hooks import HookRegistry
from agent_collab.plugins.interfaces import (
    AgentPlugin,
    FormatterPlugin,
    HookPlugin,
)

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "agent_collab.plugins"


class PluginManager:
    """Central registry for all loaded plugins.

    Plugins can be loaded two ways:

    1. **Entry-points** — call :meth:`load_plugins` to discover third-party
       plugins declared via ``[project.entry-points."agent_collab.plugins"]``.
    2. **Manual registration** — call :meth:`register_plugin` with an
       instance of :class:`AgentPlugin`, :class:`HookPlugin`, or
       :class:`FormatterPlugin`.
    """

    def __init__(self) -> None:
        self._agent_plugins: dict[str, AgentPlugin] = {}
        self._hook_plugins: dict[str, HookPlugin] = {}
        self._formatter_plugins: dict[str, FormatterPlugin] = {}
        self._hook_registry = HookRegistry()

    # -- discovery -----------------------------------------------------------

    def load_plugins(self) -> int:
        """Discover and load plugins via ``importlib.metadata.entry_points``.

        Looks for the ``agent_collab.plugins`` entry-point group. Each
        entry-point must resolve to a callable (class or factory) that returns
        a plugin instance.

        Returns:
            The number of plugins successfully loaded.
        """
        eps = entry_points()
        # Python 3.12 returns SelectableGroups; 3.11 may return a dict-like.
        group_eps = eps.select(group=_ENTRY_POINT_GROUP) if hasattr(eps, "select") else eps.get(_ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]
        count = 0
        for ep in group_eps:
            try:
                plugin_cls = ep.load()
                plugin = plugin_cls() if callable(plugin_cls) else plugin_cls  # type: ignore[call-arg]
                self.register_plugin(plugin)  # type: ignore[arg-type]
                count += 1
            except Exception:
                logger.exception("Failed to load plugin entry-point %s", ep.name)
        return count

    # -- registration --------------------------------------------------------

    def register_plugin(self, plugin: AgentPlugin | HookPlugin | FormatterPlugin) -> None:
        """Register a single plugin instance.

        The plugin is routed to the correct internal registry based on its
        class hierarchy.  A plugin that implements multiple interfaces will be
        registered under each one.

        Args:
            plugin: An :class:`AgentPlugin`, :class:`HookPlugin`, or
                :class:`FormatterPlugin` instance.

        Raises:
            TypeError: If *plugin* is not a recognised plugin type.
        """
        registered = False

        if isinstance(plugin, AgentPlugin):
            self._agent_plugins[plugin.name] = plugin
            registered = True

        if isinstance(plugin, HookPlugin):
            self._hook_plugins[plugin.name] = plugin
            # Wire lifecycle methods into the hook registry
            self._hook_registry.register_before(plugin.on_before_task)
            self._hook_registry.register_after(plugin.on_after_task)
            self._hook_registry.register_failure(plugin.on_task_failure)
            registered = True

        if isinstance(plugin, FormatterPlugin):
            self._formatter_plugins[plugin.name] = plugin
            registered = True

        if not registered:
            raise TypeError(
                f"Plugin {plugin!r} is not an AgentPlugin, HookPlugin, "
                "or FormatterPlugin"
            )

    # -- queries -------------------------------------------------------------

    def get_agent_plugins(self) -> list[AgentPlugin]:
        """Return all registered :class:`AgentPlugin` instances."""
        return list(self._agent_plugins.values())

    def get_hook_plugins(self) -> list[HookPlugin]:
        """Return all registered :class:`HookPlugin` instances."""
        return list(self._hook_plugins.values())

    def get_formatter_plugins(self) -> list[FormatterPlugin]:
        """Return all registered :class:`FormatterPlugin` instances."""
        return list(self._formatter_plugins.values())

    def get_agent_plugin(self, name: str) -> AgentPlugin | None:
        """Look up an :class:`AgentPlugin` by *name*."""
        return self._agent_plugins.get(name)

    def get_formatter_plugin(self, name: str) -> FormatterPlugin | None:
        """Look up a :class:`FormatterPlugin` by *name*."""
        return self._formatter_plugins.get(name)

    @property
    def hook_registry(self) -> HookRegistry:
        """Return the underlying :class:`HookRegistry`."""
        return self._hook_registry

    # -- hook triggers -------------------------------------------------------

    async def trigger_before_task(
        self,
        task_id: str,
        prompt: str,
        agent_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger all registered before-task hooks.

        Args:
            task_id: Identifier of the task about to run.
            prompt: The resolved prompt text.
            agent_name: Name of the agent that will execute the task.
            metadata: Optional mutable dict for cross-hook data sharing.

        Returns:
            The (possibly mutated) metadata dict.
        """
        ctx = await self._hook_registry.trigger_before(
            task_id, prompt, agent_name, metadata
        )
        return ctx.metadata

    async def trigger_after_task(
        self,
        task_id: str,
        result: AgentResult,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger all registered after-task hooks.

        Args:
            task_id: Identifier of the completed task.
            result: The :class:`AgentResult` from the agent.
            metadata: Optional mutable dict populated by earlier hooks.

        Returns:
            The (possibly mutated) metadata dict.
        """
        ctx = await self._hook_registry.trigger_after(task_id, result, metadata)
        return ctx.metadata

    async def trigger_on_failure(
        self,
        task_id: str,
        error: Exception | None = None,
        result: AgentResult | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger all registered on-failure hooks.

        Args:
            task_id: Identifier of the failed task.
            error: The exception raised, if any.
            result: The last :class:`AgentResult`, if available.
            metadata: Optional mutable dict populated by earlier hooks.

        Returns:
            The (possibly mutated) metadata dict.
        """
        ctx = await self._hook_registry.trigger_failure(
            task_id, error, result, metadata
        )
        return ctx.metadata
