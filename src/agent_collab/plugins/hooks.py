"""Hook system for task lifecycle events."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agent_collab.agents.base import AgentResult

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """Context object passed to hook callbacks.

    Attributes:
        task_id: Identifier of the task being executed.
        result: The :class:`AgentResult` (populated after execution).
        error: Exception raised during execution, if any.
        metadata: Mutable dict for passing data between hooks.
    """

    task_id: str = ""
    result: AgentResult | None = None
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Type alias for hook callback signatures
BeforeHook = Any  # async (task_id, prompt, agent_name, metadata) -> None
AfterHook = Any  # async (task_id, result, metadata) -> None
FailureHook = Any  # async (task_id, error, result, metadata) -> None


class HookRegistry:
    """Registry that stores and triggers lifecycle hooks.

    Hooks are registered via :meth:`register_before`, :meth:`register_after`,
    and :meth:`register_failure`.  They are triggered in registration order.
    """

    def __init__(self) -> None:
        self._before: list[BeforeHook] = []
        self._after: list[AfterHook] = []
        self._failure: list[FailureHook] = []

    # -- registration --------------------------------------------------------

    def register_before(self, hook: BeforeHook) -> None:
        """Register a *before-task* hook.

        Args:
            hook: An async callable with signature
                ``(task_id, prompt, agent_name, metadata) -> None``.
        """
        self._before.append(hook)

    def register_after(self, hook: AfterHook) -> None:
        """Register an *after-task* hook.

        Args:
            hook: An async callable with signature
                ``(task_id, result, metadata) -> None``.
        """
        self._after.append(hook)

    def register_failure(self, hook: FailureHook) -> None:
        """Register an *on-failure* hook.

        Args:
            hook: An async callable with signature
                ``(task_id, error, result, metadata) -> None``.
        """
        self._failure.append(hook)

    # -- accessors -----------------------------------------------------------

    @property
    def before_hooks(self) -> list[BeforeHook]:
        """Return the list of registered before-task hooks."""
        return list(self._before)

    @property
    def after_hooks(self) -> list[AfterHook]:
        """Return the list of registered after-task hooks."""
        return list(self._after)

    @property
    def failure_hooks(self) -> list[FailureHook]:
        """Return the list of registered on-failure hooks."""
        return list(self._failure)

    # -- triggers ------------------------------------------------------------

    async def trigger_before(
        self,
        task_id: str,
        prompt: str,
        agent_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> HookContext:
        """Trigger all before-task hooks.

        Args:
            task_id: Identifier of the task about to run.
            prompt: The resolved prompt text.
            agent_name: Name of the agent that will execute the task.
            metadata: Optional mutable dict for cross-hook data sharing.

        Returns:
            A :class:`HookContext` capturing the invocation context.
        """
        ctx = HookContext(task_id=task_id, metadata=metadata or {})
        for hook in self._before:
            try:
                await hook(task_id, prompt, agent_name, ctx.metadata)
            except Exception:
                logger.exception("before-task hook %r raised", hook)
        return ctx

    async def trigger_after(
        self,
        task_id: str,
        result: AgentResult,
        metadata: dict[str, Any] | None = None,
    ) -> HookContext:
        """Trigger all after-task hooks.

        Args:
            task_id: Identifier of the completed task.
            result: The :class:`AgentResult` returned by the agent.
            metadata: Optional mutable dict populated by earlier hooks.

        Returns:
            A :class:`HookContext` capturing the invocation context.
        """
        ctx = HookContext(task_id=task_id, result=result, metadata=metadata or {})
        for hook in self._after:
            try:
                await hook(task_id, result, ctx.metadata)
            except Exception:
                logger.exception("after-task hook %r raised", hook)
        return ctx

    async def trigger_failure(
        self,
        task_id: str,
        error: Exception | None = None,
        result: AgentResult | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HookContext:
        """Trigger all on-failure hooks.

        Args:
            task_id: Identifier of the failed task.
            error: The exception raised, if any.
            result: The last :class:`AgentResult`, if available.
            metadata: Optional mutable dict populated by earlier hooks.

        Returns:
            A :class:`HookContext` capturing the invocation context.
        """
        ctx = HookContext(
            task_id=task_id, error=error, result=result, metadata=metadata or {}
        )
        for hook in self._failure:
            try:
                await hook(task_id, error, result, ctx.metadata)
            except Exception:
                logger.exception("on-failure hook %r raised", hook)
        return ctx
