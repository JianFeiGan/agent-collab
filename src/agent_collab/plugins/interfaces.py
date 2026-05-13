"""Plugin interface definitions.

All plugin types derive from :class:`BasePlugin` and implement one or more
abstract ``create_*`` / ``on_*`` / ``format_*`` methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_collab.agents.base import AgentResult, BaseAgent


class BasePlugin(ABC):
    """Base class shared by every plugin.

    Subclasses must set ``name`` and optionally ``description`` as class
    attributes or in ``__init__``.

    Attributes:
        name: Unique plugin identifier (kebab-case recommended).
        description: Human-readable one-liner.
    """

    name: str
    description: str = ""

    def __init__(self) -> None:
        """Initialise the plugin.  Subclasses may override."""


class AgentPlugin(BasePlugin):
    """Plugin that provides a new agent adapter.

    Example::

        class MyAgentPlugin(AgentPlugin):
            name = "my-agent"
            description = "Does cool things"

            def create_agent(self, **kwargs: object) -> BaseAgent:
                return MyAgent(**kwargs)
    """

    @abstractmethod
    def create_agent(self, **kwargs: object) -> BaseAgent:
        """Instantiate and return a :class:`BaseAgent` implementation.

        Args:
            **kwargs: Arbitrary keyword arguments forwarded to the agent
                constructor (e.g. ``resume_mode``, ``session_id``).

        Returns:
            A concrete :class:`BaseAgent` instance.
        """


class HookPlugin(BasePlugin):
    """Plugin that hooks into the task execution lifecycle.

    Override any of the three lifecycle methods. All are optional and default
    to a no-op.
    """

    async def on_before_task(
        self,
        task_id: str,
        prompt: str,
        agent_name: str,
        metadata: dict[str, object],
    ) -> None:
        """Called before a task is dispatched to an agent.

        Args:
            task_id: Identifier of the task about to run.
            prompt: The resolved prompt text.
            agent_name: Name of the agent that will execute the task.
            metadata: Mutable dict for cross-hook data sharing.
        """

    async def on_after_task(
        self,
        task_id: str,
        result: AgentResult,
        metadata: dict[str, object],
    ) -> None:
        """Called after a task completes successfully.

        Args:
            task_id: Identifier of the completed task.
            result: The :class:`AgentResult` returned by the agent.
            metadata: Mutable dict populated by earlier hooks.
        """

    async def on_task_failure(
        self,
        task_id: str,
        error: Exception | None,
        result: AgentResult | None,
        metadata: dict[str, object],
    ) -> None:
        """Called when a task fails (after all retries are exhausted).

        Args:
            task_id: Identifier of the failed task.
            error: The exception raised, if any.
            result: The last :class:`AgentResult` if available.
            metadata: Mutable dict populated by earlier hooks.
        """


class FormatterPlugin(BasePlugin):
    """Plugin that formats agent results for display or storage."""

    @abstractmethod
    def format_result(self, result: AgentResult) -> str:
        """Format an :class:`AgentResult` into a display string.

        Args:
            result: The result to format.

        Returns:
            A formatted string representation.
        """

    @abstractmethod
    def format_output(self, output: str) -> str:
        """Format raw agent output text.

        Args:
            output: The raw output string from an agent.

        Returns:
            The formatted output string.
        """
