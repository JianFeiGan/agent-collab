"""Unit tests for SQLite ExecutionHistory."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_collab.storage.history import (
    ExecutionHistory,
    ExecutionRecord,
    TaskExecutionRecord,
)


class TestExecutionHistoryInit:
    """Tests for database initialization."""

    def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        history = ExecutionHistory(db_path=db_path)
        history.close()
        assert db_path.exists()

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "deep" / "test.db"
        history = ExecutionHistory(db_path=db_path)
        history.close()
        assert db_path.exists()

    def test_schema_persists_on_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        h1 = ExecutionHistory(db_path=db_path)
        exec_id = h1.save_execution("wf1")
        h1.close()

        h2 = ExecutionHistory(db_path=db_path)
        record = h2.get_execution(exec_id)
        h2.close()
        assert record is not None
        assert record.workflow_name == "wf1"


class TestSaveExecution:
    """Tests for save_execution and get_execution."""

    def test_save_and_get_execution(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("my-workflow")
            assert isinstance(exec_id, int)
            record = history.get_execution(exec_id)
            assert record is not None
            assert record.workflow_name == "my-workflow"
            assert record.status == "running"
            assert record.started_at is not None
            assert record.finished_at is None
        finally:
            history.close()

    def test_get_nonexistent_execution(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            assert history.get_execution(9999) is None
        finally:
            history.close()

    def test_finish_execution(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            history.finish_execution(exec_id, status="success")
            record = history.get_execution(exec_id)
            assert record is not None
            assert record.status == "success"
            assert record.finished_at is not None
        finally:
            history.close()

    def test_finish_execution_failed(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            history.finish_execution(exec_id, status="failed")
            record = history.get_execution(exec_id)
            assert record is not None
            assert record.status == "failed"
        finally:
            history.close()


class TestSaveTaskExecution:
    """Tests for save_task_execution."""

    def test_save_and_retrieve_task(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            task_id = history.save_task_execution(
                execution_id=exec_id,
                task_id="task-1",
                agent="claude",
                status="success",
                duration=12.5,
                tokens_input=500,
                tokens_output=200,
            )
            assert isinstance(task_id, int)
            tasks = history.get_task_executions(exec_id)
            assert len(tasks) == 1
            t = tasks[0]
            assert t.task_id == "task-1"
            assert t.agent == "claude"
            assert t.status == "success"
            assert t.duration == 12.5
            assert t.tokens_input == 500
            assert t.tokens_output == 200
            assert t.error_message is None
        finally:
            history.close()

    def test_save_task_with_error(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            history.save_task_execution(
                execution_id=exec_id,
                task_id="task-fail",
                agent="codex",
                status="failed",
                duration=5.0,
                error_message="Connection timeout",
            )
            tasks = history.get_task_executions(exec_id)
            assert len(tasks) == 1
            assert tasks[0].error_message == "Connection timeout"
        finally:
            history.close()

    def test_multiple_tasks_per_execution(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            for i in range(3):
                history.save_task_execution(
                    execution_id=exec_id,
                    task_id=f"task-{i}",
                    agent="claude",
                    status="success",
                    duration=float(i),
                )
            tasks = history.get_task_executions(exec_id)
            assert len(tasks) == 3
            assert [t.task_id for t in tasks] == ["task-0", "task-1", "task-2"]
        finally:
            history.close()


class TestListExecutions:
    """Tests for list_executions."""

    def test_list_empty(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            assert history.list_executions() == []
        finally:
            history.close()

    def test_list_returns_most_recent_first(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            id1 = history.save_execution("wf-a")
            id2 = history.save_execution("wf-b")
            id3 = history.save_execution("wf-c")
            records = history.list_executions()
            assert len(records) == 3
            assert records[0].id == id3
            assert records[1].id == id2
            assert records[2].id == id1
        finally:
            history.close()

    def test_list_with_limit(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            for i in range(5):
                history.save_execution(f"wf-{i}")
            records = history.list_executions(limit=2)
            assert len(records) == 2
        finally:
            history.close()

    def test_list_with_offset(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            ids = [history.save_execution(f"wf-{i}") for i in range(5)]
            records = history.list_executions(limit=2, offset=2)
            assert len(records) == 2
            # Most recent first, offset by 2
            assert records[0].id == ids[2]
            assert records[1].id == ids[1]
        finally:
            history.close()


class TestGetTaskStats:
    """Tests for get_task_stats."""

    def test_stats_empty(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            assert history.get_task_stats() == []
        finally:
            history.close()

    def test_stats_aggregate(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            history.save_task_execution(
                execution_id=exec_id, task_id="t1", agent="claude",
                status="success", duration=10.0, tokens_input=100, tokens_output=50,
            )
            history.save_task_execution(
                execution_id=exec_id, task_id="t1", agent="claude",
                status="success", duration=20.0, tokens_input=200, tokens_output=100,
            )
            stats = history.get_task_stats()
            assert len(stats) == 1
            s = stats[0]
            assert s["task_id"] == "t1"
            assert s["agent"] == "claude"
            assert s["exec_count"] == 2
            assert s["avg_duration"] == 15.0
            assert s["total_input_tokens"] == 300
            assert s["total_output_tokens"] == 150
        finally:
            history.close()

    def test_stats_filter_by_agent(self, tmp_path: Path) -> None:
        history = ExecutionHistory(db_path=tmp_path / "test.db")
        try:
            exec_id = history.save_execution("wf")
            history.save_task_execution(
                execution_id=exec_id, task_id="t1", agent="claude",
                status="success", duration=10.0,
            )
            history.save_task_execution(
                execution_id=exec_id, task_id="t2", agent="codex",
                status="success", duration=20.0,
            )
            stats = history.get_task_stats(agent="claude")
            assert len(stats) == 1
            assert stats[0]["agent"] == "claude"
        finally:
            history.close()


class TestExecutionHistoryRecordTypes:
    """Tests for record dataclass construction."""

    def test_execution_record_fields(self) -> None:
        record = ExecutionRecord(
            id=1, workflow_name="wf", started_at="2024-01-01",
            finished_at=None, status="running",
        )
        assert record.id == 1
        assert record.finished_at is None

    def test_task_execution_record_fields(self) -> None:
        record = TaskExecutionRecord(
            id=1, execution_id=1, task_id="t1", agent="claude",
            status="success", duration=5.0, tokens_input=100,
            tokens_output=50, error_message=None, created_at="2024-01-01",
        )
        assert record.tokens_input == 100
