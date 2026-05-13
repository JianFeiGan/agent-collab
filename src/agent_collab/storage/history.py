"""SQLite-based execution history persistence.

Stores workflow execution records and per-task execution details
in a local SQLite database for historical analysis and querying.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


_DEFAULT_DB_DIR = Path.home() / ".agent-collab"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "history.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS task_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    duration REAL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES executions(id)
);
"""


@dataclass
class ExecutionRecord:
    """A workflow execution record."""

    id: int
    workflow_name: str
    started_at: str
    finished_at: str | None
    status: str


@dataclass
class TaskExecutionRecord:
    """A task-level execution record."""

    id: int
    execution_id: int
    task_id: str
    agent: str
    status: str
    duration: float | None
    tokens_input: int
    tokens_output: int
    error_message: str | None
    created_at: str


@dataclass
class ExecutionHistory:
    """SQLite-backed execution history store.

    Manages workflow and task execution records in a local SQLite database.
    The database is created automatically on first use.

    Args:
        db_path: Path to the SQLite database file. Defaults to
            ``~/.agent-collab/history.db``.

    Example::

        history = ExecutionHistory()
        exec_id = history.save_execution("my-workflow")
        history.save_task_execution(
            execution_id=exec_id,
            task_id="task-1",
            agent="claude",
            status="success",
            duration=12.5,
            tokens_input=500,
            tokens_output=200,
        )
        history.finish_execution(exec_id, status="success")
        records = history.list_executions()
    """

    db_path: Path = field(default_factory=lambda: _DEFAULT_DB_PATH)
    _conn: sqlite3.Connection | None = field(default=None, repr=False, init=False)

    def __post_init__(self) -> None:
        """Ensure the database directory exists and initialise the schema."""
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a cached database connection, creating one if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't already exist."""
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def save_execution(self, workflow_name: str) -> int:
        """Create a new execution record and return its id.

        Args:
            workflow_name: Name/identifier of the workflow being executed.

        Returns:
            The auto-generated execution id.
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO executions (workflow_name, started_at, status) VALUES (?, ?, ?)",
            (workflow_name, now, "running"),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def finish_execution(self, execution_id: int, status: str = "success") -> None:
        """Mark an execution as finished.

        Args:
            execution_id: The execution record id.
            status: Final status (e.g. ``'success'``, ``'failed'``).
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE executions SET finished_at = ?, status = ? WHERE id = ?",
            (now, status, execution_id),
        )
        conn.commit()

    def save_task_execution(
        self,
        execution_id: int,
        task_id: str,
        agent: str,
        status: str,
        duration: float | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        error_message: str | None = None,
    ) -> int:
        """Save a task-level execution record.

        Args:
            execution_id: Parent execution id.
            task_id: Task identifier.
            agent: Agent name that executed the task.
            status: Task status (e.g. ``'success'``, ``'failed'``).
            duration: Execution duration in seconds.
            tokens_input: Input tokens consumed.
            tokens_output: Output tokens consumed.
            error_message: Error message if the task failed.

        Returns:
            The auto-generated task execution id.
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            """INSERT INTO task_executions
               (execution_id, task_id, agent, status, duration,
                tokens_input, tokens_output, error_message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (execution_id, task_id, agent, status, duration,
             tokens_input, tokens_output, error_message, now),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_execution(self, execution_id: int) -> ExecutionRecord | None:
        """Retrieve an execution record by id.

        Args:
            execution_id: The execution record id.

        Returns:
            An ExecutionRecord, or None if not found.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM executions WHERE id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        return ExecutionRecord(
            id=row["id"],
            workflow_name=row["workflow_name"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
        )

    def get_task_executions(self, execution_id: int) -> list[TaskExecutionRecord]:
        """Retrieve all task execution records for a given execution.

        Args:
            execution_id: Parent execution id.

        Returns:
            List of TaskExecutionRecord objects.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM task_executions WHERE execution_id = ? ORDER BY id",
            (execution_id,),
        ).fetchall()
        return [
            TaskExecutionRecord(
                id=row["id"],
                execution_id=row["execution_id"],
                task_id=row["task_id"],
                agent=row["agent"],
                status=row["status"],
                duration=row["duration"],
                tokens_input=row["tokens_input"],
                tokens_output=row["tokens_output"],
                error_message=row["error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_executions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionRecord]:
        """List execution records, most recent first.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of ExecutionRecord objects.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM executions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            ExecutionRecord(
                id=row["id"],
                workflow_name=row["workflow_name"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                status=row["status"],
            )
            for row in rows
        ]

    def get_task_stats(
        self,
        agent: str | None = None,
    ) -> list[dict[str, object]]:
        """Get aggregated task execution statistics.

        Groups task executions by task_id and agent, computing
        counts, average duration, and total token usage.

        Args:
            agent: Optional agent name to filter by.

        Returns:
            List of dictionaries with aggregated statistics.
        """
        conn = self._get_conn()
        if agent is not None:
            rows = conn.execute(
                """SELECT task_id, agent,
                          COUNT(*) as exec_count,
                          AVG(duration) as avg_duration,
                          SUM(tokens_input) as total_input,
                          SUM(tokens_output) as total_output
                   FROM task_executions
                   WHERE agent = ?
                   GROUP BY task_id, agent
                   ORDER BY task_id""",
                (agent,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT task_id, agent,
                          COUNT(*) as exec_count,
                          AVG(duration) as avg_duration,
                          SUM(tokens_input) as total_input,
                          SUM(tokens_output) as total_output
                   FROM task_executions
                   GROUP BY task_id, agent
                   ORDER BY task_id"""
            ).fetchall()

        return [
            {
                "task_id": row["task_id"],
                "agent": row["agent"],
                "exec_count": row["exec_count"],
                "avg_duration": round(row["avg_duration"], 3) if row["avg_duration"] else 0.0,
                "total_input_tokens": row["total_input"],
                "total_output_tokens": row["total_output"],
            }
            for row in rows
        ]
