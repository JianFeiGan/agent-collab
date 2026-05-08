"""Base agent adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Result returned by an agent after executing a task."""

    success: bool
    output: str
    files_changed: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    tokens_used: int | None = None


class BaseAgent(ABC):
    """Abstract base class for all agent adapters."""

    def __init__(
        self,
        resume_mode: str = "none",
        session_id: str | None = None,
    ) -> None:
        """Initialise a BaseAgent.

        Args:
            resume_mode: Resume strategy. One of ``'none'``, ``'continue'``, or
                ``'resume'``.
            session_id: Session identifier used when *resume_mode* is ``'resume'``.
        """
        self.resume_mode: str = resume_mode
        self.session_id: str | None = session_id

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        """Execute a prompt and return the result.

        Args:
            prompt: The instruction to send to the agent.
            workdir: Working directory for the agent.
            allowed_tools: List of tools the agent may use.
            timeout: Maximum execution time in seconds.

        Returns:
            AgentResult with execution details.
        """

    @abstractmethod
    def name(self) -> str:
        """Return the human-readable name of this agent."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this agent's CLI tool is installed and accessible."""
