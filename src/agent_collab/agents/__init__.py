"""Agent adapters."""

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.agents.aider import AiderAgent
from agent_collab.agents.claude_code import ClaudeCodeAgent
from agent_collab.agents.codex import CodexAgent
from agent_collab.agents.opencode import OpenCodeAgent

__all__ = [
    "AgentResult",
    "BaseAgent",
    "AiderAgent",
    "ClaudeCodeAgent",
    "CodexAgent",
    "OpenCodeAgent",
]
