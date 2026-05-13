"""SQLite-based execution history storage.

Persists workflow execution records and per-task execution details
to a local SQLite database for historical analysis.
"""

from __future__ import annotations

from agent_collab.storage.history import ExecutionHistory

__all__ = ["ExecutionHistory"]
