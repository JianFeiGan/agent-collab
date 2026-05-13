"""Unit tests for TokenTracker."""

from __future__ import annotations

import json

import pytest

from agent_collab.observability.token_tracker import TokenTracker, TokenUsage


class TestTokenTrackerRecord:
    """Tests for recording token usage."""

    def test_record_single_task(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        assert len(tracker.usages) == 1
        usage = tracker.usages[0]
        assert usage.task_id == "t1"
        assert usage.agent == "claude"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_record_multiple_tasks(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        tracker.record("t2", "codex", input_tokens=200, output_tokens=80)
        tracker.record("t3", "claude", input_tokens=150, output_tokens=60)
        assert len(tracker.usages) == 3


class TestTokenUsageDataclass:
    """Tests for TokenUsage dataclass."""

    def test_total_tokens_property(self) -> None:
        usage = TokenUsage(task_id="t1", agent="a", input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_total_tokens_zero(self) -> None:
        usage = TokenUsage(task_id="t1", agent="a", input_tokens=0, output_tokens=0)
        assert usage.total_tokens == 0


class TestTokenTrackerGetTaskUsage:
    """Tests for get_task_usage method."""

    def test_returns_usage_for_existing_task(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        usage = tracker.get_task_usage("t1")
        assert usage is not None
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_returns_none_for_missing_task(self) -> None:
        tracker = TokenTracker()
        assert tracker.get_task_usage("nonexistent") is None

    def test_returns_first_matching_task(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        tracker.record("t1", "codex", input_tokens=200, output_tokens=80)
        usage = tracker.get_task_usage("t1")
        assert usage is not None
        assert usage.agent == "claude"


class TestTokenTrackerAgentSummary:
    """Tests for get_agent_summary method."""

    def test_empty_tracker(self) -> None:
        tracker = TokenTracker()
        assert tracker.get_agent_summary() == {}

    def test_single_agent(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        tracker.record("t2", "claude", input_tokens=200, output_tokens=80)
        summary = tracker.get_agent_summary()
        assert "claude" in summary
        assert summary["claude"]["input_tokens"] == 300
        assert summary["claude"]["output_tokens"] == 130
        assert summary["claude"]["total_tokens"] == 430
        assert summary["claude"]["task_count"] == 2

    def test_multiple_agents(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        tracker.record("t2", "codex", input_tokens=200, output_tokens=80)
        summary = tracker.get_agent_summary()
        assert len(summary) == 2
        assert summary["claude"]["task_count"] == 1
        assert summary["codex"]["task_count"] == 1


class TestTokenTrackerOverallSummary:
    """Tests for get_overall_summary method."""

    def test_empty_tracker(self) -> None:
        tracker = TokenTracker()
        result = tracker.get_overall_summary()
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["total_tokens"] == 0
        assert result["task_count"] == 0

    def test_with_records(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        tracker.record("t2", "codex", input_tokens=200, output_tokens=80)
        result = tracker.get_overall_summary()
        assert result["input_tokens"] == 300
        assert result["output_tokens"] == 130
        assert result["total_tokens"] == 430
        assert result["task_count"] == 2


class TestTokenTrackerRender:
    """Tests for Rich table rendering."""

    def test_render_table_returns_table(self) -> None:
        from rich.table import Table
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        table = tracker.render_table()
        assert isinstance(table, Table)
        assert len(table.columns) == 5

    def test_render_agent_summary_table_returns_table(self) -> None:
        from rich.table import Table
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        table = tracker.render_agent_summary_table()
        assert isinstance(table, Table)


class TestTokenTrackerExport:
    """Tests for data export."""

    def test_export_data_empty(self) -> None:
        tracker = TokenTracker()
        assert tracker.export_data() == []

    def test_export_data_with_records(self) -> None:
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        data = tracker.export_data()
        assert len(data) == 1
        assert data[0]["task_id"] == "t1"
        assert data[0]["input_tokens"] == 100
        assert data[0]["output_tokens"] == 50
        assert data[0]["total_tokens"] == 150

    def test_export_json_creates_file(self, tmp_path: object) -> None:
        from pathlib import Path
        tracker = TokenTracker()
        tracker.record("t1", "claude", input_tokens=100, output_tokens=50)
        tracker.record("t2", "codex", input_tokens=200, output_tokens=80)
        json_path = Path(str(tmp_path)) / "tokens.json"
        tracker.export_json(json_path)
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "tasks" in data
        assert "by_agent" in data
        assert "overall" in data
        assert len(data["tasks"]) == 2
        assert data["overall"]["total_tokens"] == 430
