"""Plugin system for AgentCollab."""

from __future__ import annotations

from agent_collab.plugins.hooks import HookContext, HookRegistry
from agent_collab.plugins.interfaces import (
    AgentPlugin,
    FormatterPlugin,
    HookPlugin,
)
from agent_collab.plugins.manager import PluginManager

__all__ = [
    "AgentPlugin",
    "FormatterPlugin",
    "HookContext",
    "HookPlugin",
    "HookRegistry",
    "PluginManager",
]
