"""Sample agent adapter plugin.

Demonstrates how to create a plugin that provides a new agent adapter.
Register via entry-point or ``PluginManager.register_plugin()``.
"""

from __future__ import annotations

import asyncio
import time

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.plugins.interfaces import AgentPlugin


class EchoAgent(BaseAgent):
    """Trivial agent that echoes the prompt back as output.

    Useful for testing and demonstration purposes.
    """

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        start = time.monotonic()
        # Simulate a small amount of work
        await asyncio.sleep(0)
        elapsed = time.monotonic() - start
        return AgentResult(
            success=True,
            output=f"[echo] {prompt}",
            duration_seconds=elapsed,
        )

    def name(self) -> str:
        return "echo"

    def is_available(self) -> bool:
        return True


class EchoAgentPlugin(AgentPlugin):
    """Plugin that registers the :class:`EchoAgent` adapter."""

    name: str = "echo-agent"
    description: str = "Echo agent — returns the prompt as output"

    def create_agent(self, **kwargs: object) -> BaseAgent:
        """Create an :class:`EchoAgent` instance.

        Args:
            **kwargs: Forwarded to :class:`EchoAgent`.

        Returns:
            An :class:`EchoAgent` instance.
        """
        return EchoAgent(**kwargs)  # type: ignore[arg-type]
