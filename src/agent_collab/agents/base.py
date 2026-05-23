"""Base agent adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Result returned by an agent after executing a task."""

    success: bool
    output: str
    files_changed: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    tokens_used: int | None = None


class BaseAgent(ABC):
    """Abstract base class for all agent adapters with capability detection."""

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
        self._capabilities_cache: dict[str, Any] | None = None

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

    @abstractmethod
    def get_cli_version(self) -> str | None:
        """Get the CLI tool version.

        Returns:
            Version string if available, None otherwise.
        """

    @abstractmethod
    def get_supported_arguments(self) -> list[str]:
        """Get list of supported CLI arguments.

        Returns:
            List of supported argument strings.
        """

    @abstractmethod
    def check_api_key(self) -> tuple[bool, str]:
        """Check if required API keys are configured.

        Returns:
            Tuple of (is_configured, message) where message describes
            the configuration status or what's missing.
        """

    def get_capabilities(self) -> dict[str, Any]:
        """Get detailed capability information about this agent.

        Returns:
            Dictionary with capability details including:
            - name: Agent name
            - available: Whether CLI is installed
            - version: CLI version if available
            - api_key_configured: Whether API key is set
            - api_key_message: Details about API key status
            - supported_arguments: List of supported CLI args
            - resume_modes: Supported resume modes
            - supports_json_output: Whether agent supports JSON output
            - supports_model_selection: Whether agent supports model selection
            - supports_multi_file_editing: Whether agent supports multi-file editing
            - max_concurrent_tasks: Maximum concurrent tasks (None for unlimited)
        """
        if self._capabilities_cache is not None:
            return self._capabilities_cache

        version = self.get_cli_version() if self.is_available() else None
        api_configured, api_message = self.check_api_key()
        arguments = self.get_supported_arguments() if self.is_available() else []

        capabilities: dict[str, Any] = {
            "name": self.name(),
            "available": self.is_available(),
            "version": version,
            "api_key_configured": api_configured,
            "api_key_message": api_message,
            "supported_arguments": arguments,
            "resume_modes": self._get_resume_modes(),
            "supports_json_output": self._supports_json_output(),
            "supports_model_selection": self._supports_model_selection(),
            "supports_multi_file_editing": self._supports_multi_file_editing(),
            "max_concurrent_tasks": self._get_max_concurrent_tasks(),
        }

        self._capabilities_cache = capabilities
        return capabilities

    def _get_resume_modes(self) -> list[str]:
        """Get supported resume modes.

        Returns:
            List of supported resume mode strings.
        """
        return ["none"]

    def _supports_json_output(self) -> bool:
        """Check if agent supports JSON output format.

        Returns:
            True if JSON output is supported, False otherwise.
        """
        return False

    def _supports_model_selection(self) -> bool:
        """Check if agent supports model selection.

        Returns:
            True if model selection is supported, False otherwise.
        """
        return False

    def _supports_multi_file_editing(self) -> bool:
        """Check if agent supports multi-file editing.

        Returns:
            True if multi-file editing is supported, False otherwise.
        """
        return False

    def _get_max_concurrent_tasks(self) -> int | None:
        """Get maximum concurrent tasks for this agent.

        Returns:
            Maximum number of concurrent tasks, or None for unlimited.
        """
        return None
