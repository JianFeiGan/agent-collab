"""Log manager for AgentCollab execution logs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExecutionLogEntry:
    """A single execution log entry."""

    task_id: str
    agent: str
    status: str
    duration: float
    output_summary: str
    timestamp: float
    tokens_used: int | None = None
    files_changed: list[str] = field(default_factory=list)
    attempt: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class LogManager:
    """Manages execution logs with persistence and querying capabilities."""

    def __init__(self, log_dir: str | Path = ".agent-collab/logs") -> None:
        """Initialize the LogManager.

        Args:
            log_dir: Directory to store log files.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_log: list[ExecutionLogEntry] = []
        self._session_id: str = f"session-{int(time.time())}"

    def add_entry(self, entry: ExecutionLogEntry) -> None:
        """Add a log entry to the current session.

        Args:
            entry: The log entry to add.
        """
        self._current_log.append(entry)

    def add_from_dict(self, data: dict[str, Any]) -> None:
        """Add a log entry from a dictionary.

        Args:
            data: Dictionary containing log entry data.
        """
        entry = ExecutionLogEntry(
            task_id=data.get("task_id", ""),
            agent=data.get("agent", ""),
            status=data.get("status", "unknown"),
            duration=data.get("duration", 0.0),
            output_summary=data.get("output_summary", ""),
            timestamp=data.get("timestamp", time.time()),
            tokens_used=data.get("tokens_used"),
            files_changed=data.get("files_changed", []),
            attempt=data.get("attempt", 1),
            metadata=data.get("metadata", {}),
        )
        self.add_entry(entry)

    def save_session(self, filename: str | None = None) -> Path:
        """Save the current session log to a JSON file.

        Args:
            filename: Optional filename. If not provided, uses session ID.

        Returns:
            Path to the saved log file.
        """
        if filename is None:
            filename = f"{self._session_id}.json"

        log_path = self.log_dir / filename
        log_data = {
            "session_id": self._session_id,
            "timestamp": time.time(),
            "entries": [
                {
                    "task_id": entry.task_id,
                    "agent": entry.agent,
                    "status": entry.status,
                    "duration": entry.duration,
                    "output_summary": entry.output_summary,
                    "timestamp": entry.timestamp,
                    "tokens_used": entry.tokens_used,
                    "files_changed": entry.files_changed,
                    "attempt": entry.attempt,
                    "metadata": entry.metadata,
                }
                for entry in self._current_log
            ],
        }

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        return log_path

    def load_session(self, filename: str) -> list[ExecutionLogEntry]:
        """Load a session log from a JSON file.

        Args:
            filename: The filename to load.

        Returns:
            List of log entries from the session.
        """
        log_path = self.log_dir / filename
        if not log_path.exists():
            return []

        with open(log_path, encoding="utf-8") as f:
            log_data = json.load(f)

        entries = []
        for entry_data in log_data.get("entries", []):
            entry = ExecutionLogEntry(
                task_id=entry_data.get("task_id", ""),
                agent=entry_data.get("agent", ""),
                status=entry_data.get("status", "unknown"),
                duration=entry_data.get("duration", 0.0),
                output_summary=entry_data.get("output_summary", ""),
                timestamp=entry_data.get("timestamp", 0.0),
                tokens_used=entry_data.get("tokens_used"),
                files_changed=entry_data.get("files_changed", []),
                attempt=entry_data.get("attempt", 1),
                metadata=entry_data.get("metadata", {}),
            )
            entries.append(entry)

        return entries

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all available log sessions.

        Returns:
            List of session information dictionaries.
        """
        sessions = []
        for log_file in self.log_dir.glob("*.json"):
            try:
                with open(log_file, encoding="utf-8") as f:
                    log_data = json.load(f)
                sessions.append({
                    "filename": log_file.name,
                    "session_id": log_data.get("session_id", ""),
                    "timestamp": log_data.get("timestamp", 0.0),
                    "entry_count": len(log_data.get("entries", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(sessions, key=lambda x: x["timestamp"], reverse=True)

    def get_statistics(self, entries: list[ExecutionLogEntry] | None = None) -> dict[str, Any]:
        """Get statistics from log entries.

        Args:
            entries: Optional list of entries. If not provided, uses current session.

        Returns:
            Dictionary containing statistics.
        """
        if entries is None:
            entries = self._current_log

        if not entries:
            return {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "total_duration": 0.0,
                "average_duration": 0.0,
                "total_tokens": 0,
                "agents_used": [],
            }

        successful = [e for e in entries if e.status == "success"]
        failed = [e for e in entries if e.status == "failed"]
        total_duration = sum(e.duration for e in entries)
        total_tokens = sum(e.tokens_used or 0 for e in entries)
        agents_used = list(set(e.agent for e in entries))

        return {
            "total_tasks": len(entries),
            "successful_tasks": len(successful),
            "failed_tasks": len(failed),
            "total_duration": round(total_duration, 3),
            "average_duration": round(total_duration / len(entries), 3) if entries else 0.0,
            "total_tokens": total_tokens,
            "agents_used": agents_used,
            "success_rate": round(len(successful) / len(entries) * 100, 2) if entries else 0.0,
        }

    def export_csv(self, filename: str, entries: list[ExecutionLogEntry] | None = None) -> Path:
        """Export log entries to CSV format.

        Args:
            filename: The filename for the CSV file.
            entries: Optional list of entries. If not provided, uses current session.

        Returns:
            Path to the exported CSV file.
        """
        import csv

        if entries is None:
            entries = self._current_log

        csv_path = self.log_dir / filename
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "task_id", "agent", "status", "duration", "timestamp",
                "tokens_used", "attempt", "output_summary"
            ])
            for entry in entries:
                writer.writerow([
                    entry.task_id,
                    entry.agent,
                    entry.status,
                    entry.duration,
                    entry.timestamp,
                    entry.tokens_used or "",
                    entry.attempt,
                    entry.output_summary[:100] if entry.output_summary else "",
                ])

        return csv_path

    def clear_session(self) -> None:
        """Clear the current session log."""
        self._current_log.clear()

    @property
    def current_entries(self) -> list[ExecutionLogEntry]:
        """Get the current session entries."""
        return list(self._current_log)
