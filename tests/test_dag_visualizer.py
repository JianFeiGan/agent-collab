"""Tests for DAG visualizer module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from rich.console import Console
from rich.tree import Tree

from agent_collab.core.workflow import TaskConfig
from agent_collab.observability.dag_visualizer import DAGVisualizer


@pytest.fixture
def console() -> Console:
    """Create a mock console for testing."""
    return MagicMock(spec=Console)


@pytest.fixture
def visualizer(console: Console) -> DAGVisualizer:
    """Create a DAGVisualizer instance."""
    return DAGVisualizer(console=console)


@pytest.fixture
def sample_tasks() -> list[TaskConfig]:
    """Create sample tasks for testing."""
    return [
        TaskConfig(id="task1", agent="claude-code", prompt="Do something"),
        TaskConfig(id="task2", agent="codex", prompt="Do something else", depends_on=["task1"]),
        TaskConfig(id="task3", agent="aider", prompt="Final task", depends_on=["task2"]),
    ]


class TestDAGVisualizer:
    """Tests for DAGVisualizer class."""

    def test_init(self, console: Console) -> None:
        """Test initialization."""
        viz = DAGVisualizer(console=console)
        assert viz.console is console
        assert viz._tree is None
        assert viz._tasks == {}
        assert viz._statuses == {}
        assert viz._durations == {}
        assert viz._agents == {}

    def test_build_simple_dag(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig]
    ) -> None:
        """Test building a simple DAG."""
        tree = visualizer.build(sample_tasks)
        assert isinstance(tree, Tree)
        assert visualizer._tree is tree
        assert len(visualizer._tasks) == 3

    def test_build_with_statuses(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig]
    ) -> None:
        """Test building DAG with status information."""
        statuses = {"task1": "success", "task2": "running", "task3": "pending"}
        tree = visualizer.build(sample_tasks, statuses=statuses)
        assert isinstance(tree, Tree)
        assert visualizer._statuses == statuses

    def test_build_with_durations(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig]
    ) -> None:
        """Test building DAG with duration information."""
        durations = {"task1": 1.5, "task2": 2.0, "task3": 0.5}
        tree = visualizer.build(sample_tasks, durations=durations)
        assert isinstance(tree, Tree)
        assert visualizer._durations == durations

    def test_build_with_agents(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig]
    ) -> None:
        """Test building DAG with agent information."""
        agents = {"task1": "claude-code", "task2": "codex", "task3": "aider"}
        tree = visualizer.build(sample_tasks, agents=agents)
        assert isinstance(tree, Tree)
        assert visualizer._agents == agents

    def test_build_empty_tasks(self, visualizer: DAGVisualizer) -> None:
        """Test building DAG with empty task list."""
        tree = visualizer.build([])
        assert isinstance(tree, Tree)
        assert len(visualizer._tasks) == 0

    def test_build_with_cycle(self, visualizer: DAGVisualizer) -> None:
        """Test building DAG with circular dependencies."""
        tasks = [
            TaskConfig(
                id="task1", agent="claude-code", prompt="Do something", depends_on=["task3"]
            ),
            TaskConfig(id="task2", agent="codex", prompt="Do something else", depends_on=["task1"]),
            TaskConfig(id="task3", agent="aider", prompt="Final task", depends_on=["task2"]),
        ]
        # Should handle cycles gracefully
        tree = visualizer.build(tasks)
        assert isinstance(tree, Tree)

    def test_render_without_build(self, visualizer: DAGVisualizer, console: MagicMock) -> None:
        """Test rendering without building first."""
        visualizer.render()
        console.print.assert_called_once_with("[yellow]No DAG to render. Call build() first.[/]")

    def test_render_with_title(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig], console: MagicMock
    ) -> None:
        """Test rendering with a title."""
        visualizer.build(sample_tasks)
        visualizer.render(title="Test Workflow")
        # Should call console.print with a Panel
        assert console.print.called

    def test_render_without_title(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig], console: MagicMock
    ) -> None:
        """Test rendering without a title."""
        visualizer.build(sample_tasks)
        visualizer.render()
        # Should call console.print with the tree
        assert console.print.called

    def test_get_execution_levels(
        self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig]
    ) -> None:
        """Test getting execution levels."""
        levels = visualizer.get_execution_levels(sample_tasks)
        assert len(levels) == 3
        assert levels[0] == ["task1"]
        assert levels[1] == ["task2"]
        assert levels[2] == ["task3"]

    def test_get_execution_levels_parallel(self, visualizer: DAGVisualizer) -> None:
        """Test getting execution levels with parallel tasks."""
        tasks = [
            TaskConfig(id="task1", agent="claude-code", prompt="Do something"),
            TaskConfig(id="task2", agent="codex", prompt="Do something else"),
            TaskConfig(
                id="task3", agent="aider", prompt="Final task", depends_on=["task1", "task2"]
            ),
        ]
        levels = visualizer.get_execution_levels(tasks)
        assert len(levels) == 2
        assert set(levels[0]) == {"task1", "task2"}
        assert levels[1] == ["task3"]

    def test_get_execution_levels_empty(self, visualizer: DAGVisualizer) -> None:
        """Test getting execution levels with empty tasks."""
        levels = visualizer.get_execution_levels([])
        assert levels == []

    def test_to_dict(self, visualizer: DAGVisualizer, sample_tasks: list[TaskConfig]) -> None:
        """Test exporting DAG to dictionary."""
        statuses = {"task1": "success", "task2": "running"}
        durations = {"task1": 1.5, "task2": 2.0}
        visualizer.build(sample_tasks, statuses=statuses, durations=durations)

        result = visualizer.to_dict(sample_tasks)
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2

    def test_to_dict_empty(self, visualizer: DAGVisualizer) -> None:
        """Test exporting empty DAG to dictionary."""
        result = visualizer.to_dict([])
        assert result == {"nodes": [], "edges": []}

    def test_format_task_label_with_agent(self, visualizer: DAGVisualizer) -> None:
        """Test formatting task label with agent information."""
        task = TaskConfig(id="task1", agent="claude-code", prompt="test")
        visualizer._tasks = {"task1": task}
        visualizer._statuses = {"task1": "success"}
        visualizer._agents = {"task1": "claude-code"}
        visualizer._durations = {"task1": 1.5}

        label = visualizer._format_task_label("task1")
        assert "task1" in label
        assert "claude-code" in label
        assert "1.5s" in label

    def test_format_task_label_without_agent(self, visualizer: DAGVisualizer) -> None:
        """Test formatting task label without agent information."""
        task = TaskConfig(id="task1", agent="claude-code", prompt="test")
        visualizer._tasks = {"task1": task}
        visualizer._statuses = {"task1": "pending"}

        label = visualizer._format_task_label("task1")
        assert "task1" in label
        assert "claude-code" not in label

    def test_format_root_label_all_success(self, visualizer: DAGVisualizer) -> None:
        """Test formatting root label when all tasks are successful."""
        task1 = TaskConfig(id="task1", agent="claude-code", prompt="test")
        task2 = TaskConfig(id="task2", agent="codex", prompt="test")
        visualizer._tasks = {"task1": task1, "task2": task2}
        visualizer._statuses = {"task1": "success", "task2": "success"}

        label = visualizer._format_root_label()
        assert "2/2 done" in label
        assert "failed" not in label

    def test_format_root_label_with_failures(self, visualizer: DAGVisualizer) -> None:
        """Test formatting root label when some tasks failed."""
        task1 = TaskConfig(id="task1", agent="claude-code", prompt="test")
        task2 = TaskConfig(id="task2", agent="codex", prompt="test")
        task3 = TaskConfig(id="task3", agent="aider", prompt="test")
        visualizer._tasks = {"task1": task1, "task2": task2, "task3": task3}
        visualizer._statuses = {"task1": "success", "task2": "failed", "task3": "pending"}

        label = visualizer._format_root_label()
        assert "1/3 done" in label
        assert "1 failed" in label

    def test_format_root_label_no_tasks(self, visualizer: DAGVisualizer) -> None:
        """Test formatting root label with no tasks."""
        visualizer._tasks = {}
        visualizer._statuses = {}

        label = visualizer._format_root_label()
        assert "0/0 done" in label
