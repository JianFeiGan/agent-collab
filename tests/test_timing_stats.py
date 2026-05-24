"""Tests for timing stats module."""

from __future__ import annotations

import pytest
from rich.console import Console
from rich.table import Table
from rich.text import Text

from agent_collab.observability.timing_stats import TaskTiming, TimingStats


@pytest.fixture
def stats() -> TimingStats:
    """Create a TimingStats instance."""
    return TimingStats()


@pytest.fixture
def sample_timings() -> list[TaskTiming]:
    """Create sample timing data."""
    return [
        TaskTiming(task_id="task1", agent="claude-code", duration=1.5, status="success"),
        TaskTiming(task_id="task2", agent="codex", duration=2.0, status="success"),
        TaskTiming(task_id="task3", agent="aider", duration=0.5, status="failed"),
    ]


class TestTaskTiming:
    """Tests for TaskTiming dataclass."""

    def test_init(self) -> None:
        """Test TaskTiming initialization."""
        timing = TaskTiming(
            task_id="task1",
            agent="claude-code",
            duration=1.5,
            status="success",
            attempt=2,
        )
        assert timing.task_id == "task1"
        assert timing.agent == "claude-code"
        assert timing.duration == 1.5
        assert timing.status == "success"
        assert timing.attempt == 2

    def test_default_attempt(self) -> None:
        """Test default attempt value."""
        timing = TaskTiming(
            task_id="task1",
            agent="claude-code",
            duration=1.5,
            status="success",
        )
        assert timing.attempt == 1


class TestTimingStats:
    """Tests for TimingStats class."""

    def test_init(self) -> None:
        """Test TimingStats initialization."""
        stats = TimingStats()
        assert stats.timings == []
        assert isinstance(stats._console, Console)

    def test_record(self, stats: TimingStats) -> None:
        """Test recording timing data."""
        stats.record("task1", "claude-code", 1.5, "success", 1)
        assert len(stats.timings) == 1
        timing = stats.timings[0]
        assert timing.task_id == "task1"
        assert timing.agent == "claude-code"
        assert timing.duration == 1.5
        assert timing.status == "success"
        assert timing.attempt == 1

    def test_record_multiple(self, stats: TimingStats) -> None:
        """Test recording multiple timing entries."""
        stats.record("task1", "claude-code", 1.5, "success")
        stats.record("task2", "codex", 2.0, "success")
        stats.record("task3", "aider", 0.5, "failed")
        assert len(stats.timings) == 3

    def test_get_task_summary_empty(self, stats: TimingStats) -> None:
        """Test getting task summary with no data."""
        summary = stats.get_task_summary("task1")
        assert summary == {
            "min": 0.0,
            "max": 0.0,
            "avg": 0.0,
            "total": 0.0,
            "count": 0,
            "last": 0.0,
        }

    def test_get_task_summary_single(self, stats: TimingStats) -> None:
        """Test getting task summary with single entry."""
        stats.record("task1", "claude-code", 1.5, "success")
        summary = stats.get_task_summary("task1")
        assert summary["min"] == 1.5
        assert summary["max"] == 1.5
        assert summary["avg"] == 1.5
        assert summary["total"] == 1.5
        assert summary["count"] == 1
        assert summary["last"] == 1.5

    def test_get_task_summary_multiple(self, stats: TimingStats) -> None:
        """Test getting task summary with multiple entries."""
        stats.record("task1", "claude-code", 1.0, "success")
        stats.record("task1", "claude-code", 2.0, "success")
        stats.record("task1", "claude-code", 3.0, "success")
        summary = stats.get_task_summary("task1")
        assert summary["min"] == 1.0
        assert summary["max"] == 3.0
        assert summary["avg"] == 2.0
        assert summary["total"] == 6.0
        assert summary["count"] == 3
        assert summary["last"] == 3.0

    def test_get_task_summary_nonexistent(self, stats: TimingStats) -> None:
        """Test getting task summary for nonexistent task."""
        stats.record("task1", "claude-code", 1.5, "success")
        summary = stats.get_task_summary("task2")
        assert summary == {
            "min": 0.0,
            "max": 0.0,
            "avg": 0.0,
            "total": 0.0,
            "count": 0,
            "last": 0.0,
        }

    def test_get_overall_summary_empty(self, stats: TimingStats) -> None:
        """Test getting overall summary with no data."""
        summary = stats.get_overall_summary()
        assert summary == {
            "total_time": 0.0,
            "task_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "avg_time": 0.0,
            "median_time": 0.0,
            "p95_time": 0.0,
        }

    def test_get_overall_summary(
        self, stats: TimingStats, sample_timings: list[TaskTiming]
    ) -> None:
        """Test getting overall summary with sample data."""
        for t in sample_timings:
            stats.record(t.task_id, t.agent, t.duration, t.status)

        summary = stats.get_overall_summary()
        assert summary["total_time"] == 4.0
        assert summary["task_count"] == 3
        assert summary["success_count"] == 2
        assert summary["failed_count"] == 1
        assert summary["avg_time"] == pytest.approx(1.333, rel=1e-2)
        assert summary["median_time"] == 1.5
        assert summary["p95_time"] == 2.0

    def test_get_agent_summary_empty(self, stats: TimingStats) -> None:
        """Test getting agent summary with no data."""
        summary = stats.get_agent_summary()
        assert summary == {}

    def test_get_agent_summary(self, stats: TimingStats, sample_timings: list[TaskTiming]) -> None:
        """Test getting agent summary with sample data."""
        for t in sample_timings:
            stats.record(t.task_id, t.agent, t.duration, t.status)

        summary = stats.get_agent_summary()
        assert "claude-code" in summary
        assert "codex" in summary
        assert "aider" in summary

        assert summary["claude-code"]["count"] == 1
        assert summary["claude-code"]["total"] == 1.5
        assert summary["codex"]["count"] == 1
        assert summary["codex"]["total"] == 2.0
        assert summary["aider"]["count"] == 1
        assert summary["aider"]["total"] == 0.5

    def test_render_table_empty(self, stats: TimingStats) -> None:
        """Test rendering table with no data."""
        table = stats.render_table()
        assert isinstance(table, Table)
        assert table.title == "Task Timing Statistics"

    def test_render_table(self, stats: TimingStats, sample_timings: list[TaskTiming]) -> None:
        """Test rendering table with sample data."""
        for t in sample_timings:
            stats.record(t.task_id, t.agent, t.duration, t.status)

        table = stats.render_table()
        assert isinstance(table, Table)
        # Table should have rows for each unique task
        assert len(table.columns) == 5

    def test_render_bar_chart_empty(self, stats: TimingStats) -> None:
        """Test rendering bar chart with no data."""
        text = stats.render_bar_chart()
        assert isinstance(text, Text)
        assert "No timing data available" in text.plain

    def test_render_bar_chart(self, stats: TimingStats, sample_timings: list[TaskTiming]) -> None:
        """Test rendering bar chart with sample data."""
        for t in sample_timings:
            stats.record(t.task_id, t.agent, t.duration, t.status)

        text = stats.render_bar_chart()
        assert isinstance(text, Text)
        assert "task1" in text.plain
        assert "task2" in text.plain
        assert "task3" in text.plain

    def test_render_bar_chart_custom_width(self, stats: TimingStats) -> None:
        """Test rendering bar chart with custom width."""
        stats.record("task1", "claude-code", 1.5, "success")
        text = stats.render_bar_chart(max_width=20)
        assert isinstance(text, Text)

    def test_export_data_empty(self, stats: TimingStats) -> None:
        """Test exporting data with no timings."""
        data = stats.export_data()
        assert data == []

    def test_export_data(self, stats: TimingStats, sample_timings: list[TaskTiming]) -> None:
        """Test exporting data with sample timings."""
        for t in sample_timings:
            stats.record(t.task_id, t.agent, t.duration, t.status)

        data = stats.export_data()
        assert len(data) == 3
        assert data[0]["task_id"] == "task1"
        assert data[0]["agent"] == "claude-code"
        assert data[0]["duration"] == 1.5
        assert data[0]["status"] == "success"
        assert data[0]["attempt"] == 1

    def test_export_data_rounding(self, stats: TimingStats) -> None:
        """Test that exported data rounds duration to 3 decimal places."""
        stats.record("task1", "claude-code", 1.123456789, "success")
        data = stats.export_data()
        assert data[0]["duration"] == 1.123
