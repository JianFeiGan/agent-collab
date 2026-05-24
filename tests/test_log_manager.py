"""Tests for log manager module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_collab.storage.log_manager import ExecutionLogEntry, LogManager


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    """Create a temporary log directory."""
    return tmp_path / "logs"


@pytest.fixture
def manager(log_dir: Path) -> LogManager:
    """Create a LogManager instance."""
    return LogManager(log_dir=log_dir)


@pytest.fixture
def sample_entry() -> ExecutionLogEntry:
    """Create a sample log entry."""
    return ExecutionLogEntry(
        task_id="task1",
        agent="claude-code",
        status="success",
        duration=1.5,
        output_summary="Task completed successfully",
        timestamp=1234567890.0,
        tokens_used=100,
        files_changed=["file1.py", "file2.py"],
        attempt=1,
        metadata={"key": "value"},
    )


class TestExecutionLogEntry:
    """Tests for ExecutionLogEntry dataclass."""

    def test_init(self) -> None:
        """Test ExecutionLogEntry initialization."""
        entry = ExecutionLogEntry(
            task_id="task1",
            agent="claude-code",
            status="success",
            duration=1.5,
            output_summary="Test",
            timestamp=1234567890.0,
        )
        assert entry.task_id == "task1"
        assert entry.agent == "claude-code"
        assert entry.status == "success"
        assert entry.duration == 1.5
        assert entry.output_summary == "Test"
        assert entry.timestamp == 1234567890.0
        assert entry.tokens_used is None
        assert entry.files_changed == []
        assert entry.attempt == 1
        assert entry.metadata == {}

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        entry = ExecutionLogEntry(
            task_id="task1",
            agent="claude-code",
            status="success",
            duration=1.5,
            output_summary="Test",
            timestamp=1234567890.0,
            tokens_used=100,
            files_changed=["file.py"],
            attempt=2,
            metadata={"key": "value"},
        )
        assert entry.tokens_used == 100
        assert entry.files_changed == ["file.py"]
        assert entry.attempt == 2
        assert entry.metadata == {"key": "value"}


class TestLogManager:
    """Tests for LogManager class."""

    def test_init(self, log_dir: Path) -> None:
        """Test LogManager initialization."""
        manager = LogManager(log_dir=log_dir)
        assert manager.log_dir == log_dir
        assert log_dir.exists()
        assert manager._current_log == []
        assert manager._session_id.startswith("session-")

    def test_init_default(self) -> None:
        """Test LogManager initialization with default directory."""
        manager = LogManager()
        assert manager.log_dir == Path(".agent-collab/logs")

    def test_add_entry(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test adding a log entry."""
        manager.add_entry(sample_entry)
        assert len(manager._current_log) == 1
        assert manager._current_log[0] is sample_entry

    def test_add_multiple_entries(self, manager: LogManager) -> None:
        """Test adding multiple log entries."""
        entry1 = ExecutionLogEntry(
            task_id="task1",
            agent="claude-code",
            status="success",
            duration=1.0,
            output_summary="Test 1",
            timestamp=1234567890.0,
        )
        entry2 = ExecutionLogEntry(
            task_id="task2",
            agent="codex",
            status="failed",
            duration=2.0,
            output_summary="Test 2",
            timestamp=1234567891.0,
        )
        manager.add_entry(entry1)
        manager.add_entry(entry2)
        assert len(manager._current_log) == 2

    def test_add_from_dict(self, manager: LogManager) -> None:
        """Test adding a log entry from dictionary."""
        data = {
            "task_id": "task1",
            "agent": "claude-code",
            "status": "success",
            "duration": 1.5,
            "output_summary": "Test",
            "timestamp": 1234567890.0,
            "tokens_used": 100,
            "files_changed": ["file.py"],
            "attempt": 2,
            "metadata": {"key": "value"},
        }
        manager.add_from_dict(data)
        assert len(manager._current_log) == 1
        entry = manager._current_log[0]
        assert entry.task_id == "task1"
        assert entry.agent == "claude-code"
        assert entry.status == "success"
        assert entry.duration == 1.5
        assert entry.tokens_used == 100
        assert entry.files_changed == ["file.py"]
        assert entry.attempt == 2
        assert entry.metadata == {"key": "value"}

    def test_add_from_dict_defaults(self, manager: LogManager) -> None:
        """Test adding a log entry from dictionary with defaults."""
        data = {"task_id": "task1"}
        manager.add_from_dict(data)
        entry = manager._current_log[0]
        assert entry.task_id == "task1"
        assert entry.agent == ""
        assert entry.status == "unknown"
        assert entry.duration == 0.0
        assert entry.output_summary == ""
        assert entry.tokens_used is None
        assert entry.files_changed == []
        assert entry.attempt == 1
        assert entry.metadata == {}

    def test_save_session(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test saving session to file."""
        manager.add_entry(sample_entry)
        log_path = manager.save_session()
        assert log_path.exists()
        assert log_path.suffix == ".json"

        with open(log_path) as f:
            data = json.load(f)
        assert "session_id" in data
        assert "timestamp" in data
        assert "entries" in data
        assert len(data["entries"]) == 1

    def test_save_session_custom_filename(
        self, manager: LogManager, sample_entry: ExecutionLogEntry
    ) -> None:
        """Test saving session with custom filename."""
        manager.add_entry(sample_entry)
        log_path = manager.save_session(filename="custom.json")
        assert log_path.name == "custom.json"

    def test_save_session_empty(self, manager: LogManager) -> None:
        """Test saving empty session."""
        log_path = manager.save_session()
        assert log_path.exists()
        with open(log_path) as f:
            data = json.load(f)
        assert data["entries"] == []

    def test_load_session(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test loading session from file."""
        manager.add_entry(sample_entry)
        log_path = manager.save_session()

        loaded_entries = manager.load_session(log_path.name)
        assert len(loaded_entries) == 1
        loaded = loaded_entries[0]
        assert loaded.task_id == sample_entry.task_id
        assert loaded.agent == sample_entry.agent
        assert loaded.status == sample_entry.status
        assert loaded.duration == sample_entry.duration
        assert loaded.tokens_used == sample_entry.tokens_used
        assert loaded.files_changed == sample_entry.files_changed
        assert loaded.attempt == sample_entry.attempt
        assert loaded.metadata == sample_entry.metadata

    def test_load_session_nonexistent(self, manager: LogManager) -> None:
        """Test loading nonexistent session."""
        entries = manager.load_session("nonexistent.json")
        assert entries == []

    def test_list_sessions(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test listing sessions."""
        manager.add_entry(sample_entry)
        manager.save_session(filename="session1.json")
        manager.save_session(filename="session2.json")

        sessions = manager.list_sessions()
        assert len(sessions) == 2
        for session in sessions:
            assert "filename" in session
            assert "session_id" in session
            assert "timestamp" in session
            assert "entry_count" in session

    def test_list_sessions_empty(self, manager: LogManager) -> None:
        """Test listing sessions with no logs."""
        sessions = manager.list_sessions()
        assert sessions == []

    def test_get_statistics_empty(self, manager: LogManager) -> None:
        """Test getting statistics with no entries."""
        stats = manager.get_statistics()
        assert stats == {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "total_duration": 0.0,
            "average_duration": 0.0,
            "total_tokens": 0,
            "agents_used": [],
        }

    def test_get_statistics(self, manager: LogManager) -> None:
        """Test getting statistics with entries."""
        entries = [
            ExecutionLogEntry(
                task_id="task1",
                agent="claude-code",
                status="success",
                duration=1.0,
                output_summary="Test 1",
                timestamp=1234567890.0,
                tokens_used=100,
            ),
            ExecutionLogEntry(
                task_id="task2",
                agent="codex",
                status="failed",
                duration=2.0,
                output_summary="Test 2",
                timestamp=1234567891.0,
                tokens_used=200,
            ),
            ExecutionLogEntry(
                task_id="task3",
                agent="claude-code",
                status="success",
                duration=3.0,
                output_summary="Test 3",
                timestamp=1234567892.0,
                tokens_used=300,
            ),
        ]

        stats = manager.get_statistics(entries)
        assert stats["total_tasks"] == 3
        assert stats["successful_tasks"] == 2
        assert stats["failed_tasks"] == 1
        assert stats["total_duration"] == 6.0
        assert stats["average_duration"] == 2.0
        assert stats["total_tokens"] == 600
        assert set(stats["agents_used"]) == {"claude-code", "codex"}
        assert stats["success_rate"] == pytest.approx(66.67, rel=1e-2)

    def test_get_statistics_current_session(self, manager: LogManager) -> None:
        """Test getting statistics from current session."""
        entry = ExecutionLogEntry(
            task_id="task1",
            agent="claude-code",
            status="success",
            duration=1.0,
            output_summary="Test",
            timestamp=1234567890.0,
        )
        manager.add_entry(entry)

        stats = manager.get_statistics()
        assert stats["total_tasks"] == 1
        assert stats["successful_tasks"] == 1
        assert stats["failed_tasks"] == 0

    def test_export_csv(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test exporting to CSV."""
        manager.add_entry(sample_entry)
        csv_path = manager.export_csv("test.csv")
        assert csv_path.exists()
        assert csv_path.suffix == ".csv"

        with open(csv_path) as f:
            content = f.read()
        assert "task_id,agent,status,duration" in content
        assert "task1,claude-code,success" in content

    def test_export_csv_empty(self, manager: LogManager) -> None:
        """Test exporting empty log to CSV."""
        csv_path = manager.export_csv("empty.csv")
        assert csv_path.exists()
        with open(csv_path) as f:
            content = f.read()
        assert "task_id,agent,status,duration" in content

    def test_clear_session(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test clearing session."""
        manager.add_entry(sample_entry)
        assert len(manager._current_log) == 1
        manager.clear_session()
        assert len(manager._current_log) == 0

    def test_current_entries(self, manager: LogManager, sample_entry: ExecutionLogEntry) -> None:
        """Test getting current entries."""
        manager.add_entry(sample_entry)
        entries = manager.current_entries
        assert len(entries) == 1
        assert entries[0] is sample_entry
        # Should return a copy
        entries.append(sample_entry)
        assert len(manager._current_log) == 1
