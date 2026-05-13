"""Sample hook plugin.

Demonstrates how to create a plugin that hooks into the task lifecycle.
Register via entry-point or ``PluginManager.register_plugin()``.
"""

from __future__ import annotations

from agent_collab.agents.base import AgentResult
from agent_collab.plugins.interfaces import HookPlugin


class LoggingHookPlugin(HookPlugin):
    """Hook plugin that records lifecycle events into an in-memory log.

    Useful for testing, debugging, and demonstration. In production you
    would typically forward events to a logging framework or metrics system.
    """

    name: str = "logging-hook"
    description: str = "Records task lifecycle events into an in-memory list"

    def __init__(self) -> None:
        # Avoid calling super().__init__ with required fields by setting
        # attributes directly.
        self.name = "logging-hook"
        self.description = "Records task lifecycle events into an in-memory list"
        self.events: list[dict[str, object]] = []

    async def on_before_task(
        self,
        task_id: str,
        prompt: str,
        agent_name: str,
        metadata: dict[str, object],
    ) -> None:
        """Record a before-task event.

        Args:
            task_id: Identifier of the task about to run.
            prompt: The resolved prompt text.
            agent_name: Name of the agent that will execute the task.
            metadata: Mutable dict for cross-hook data sharing.
        """
        self.events.append({
            "event": "before_task",
            "task_id": task_id,
            "agent": agent_name,
        })

    async def on_after_task(
        self,
        task_id: str,
        result: AgentResult,
        metadata: dict[str, object],
    ) -> None:
        """Record an after-task event.

        Args:
            task_id: Identifier of the completed task.
            result: The :class:`AgentResult` returned by the agent.
            metadata: Mutable dict populated by earlier hooks.
        """
        self.events.append({
            "event": "after_task",
            "task_id": task_id,
            "success": result.success,
        })

    async def on_task_failure(
        self,
        task_id: str,
        error: Exception | None,
        result: AgentResult | None,
        metadata: dict[str, object],
    ) -> None:
        """Record a task-failure event.

        Args:
            task_id: Identifier of the failed task.
            error: The exception raised, if any.
            result: The last :class:`AgentResult` if available.
            metadata: Mutable dict populated by earlier hooks.
        """
        self.events.append({
            "event": "task_failure",
            "task_id": task_id,
            "error": str(error) if error else None,
        })
