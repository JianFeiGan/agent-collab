"""DAG tree visualization using Rich for terminal output.

Renders the task dependency graph as a tree structure, showing
execution status, timing, and relationships between tasks.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from agent_collab.core.workflow import TaskConfig


# Status symbols for tree rendering
_STATUS_SYMBOLS: dict[str, str] = {
    "pending": "○",
    "running": "●",
    "success": "✓",
    "failed": "✗",
    "skipped": "⊘",
    "retrying": "↻",
}

_STATUS_STYLES: dict[str, str] = {
    "pending": "dim",
    "running": "yellow",
    "success": "green",
    "failed": "red",
    "skipped": "dim",
    "retrying": "cyan",
}


class DAGVisualizer:
    """Renders a DAG task graph as a Rich tree in the terminal.

    Usage::

        viz = DAGVisualizer()
        viz.build(tasks, statuses={"t1": "success", "t2": "running"})
        viz.render()
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._tree: Tree[str] | None = None
        self._tasks: dict[str, TaskConfig] = {}
        self._statuses: dict[str, str] = {}
        self._durations: dict[str, float] = {}
        self._agents: dict[str, str] = {}

    def build(
        self,
        tasks: list[TaskConfig],
        statuses: dict[str, str] | None = None,
        durations: dict[str, float] | None = None,
        agents: dict[str, str] | None = None,
    ) -> Tree[str]:
        """Build the tree structure from task configurations.

        Args:
            tasks: List of task configurations defining the DAG.
            statuses: Mapping of task_id -> status string
                (pending/running/success/failed/skipped/retrying).
            durations: Mapping of task_id -> duration in seconds.
            agents: Mapping of task_id -> agent name.

        Returns:
            The root Rich Tree object.
        """
        self._tasks = {t.id: t for t in tasks}
        self._statuses = statuses or {}
        self._durations = durations or {}
        self._agents = agents or {}

        # Find root tasks (no dependencies)
        roots = [t for t in tasks if not t.depends_on]
        if not roots and tasks:
            # Fallback: pick tasks that nothing depends on
            depended_on: set[str] = set()
            for t in tasks:
                depended_on.update(t.depends_on)
            roots = [t for t in tasks if t.id not in depended_on]

        root_label = self._format_root_label()
        self._tree = Tree(root_label)

        # Build children map: parent -> list of children
        children_map: dict[str, list[str]] = {t.id: [] for t in tasks}
        for t in tasks:
            for dep in t.depends_on:
                if dep in children_map:
                    children_map[dep].append(t.id)

        visited: set[str] = set()

        def _add_children(parent_tree: Tree[str], task_id: str) -> None:
            if task_id in visited:
                return
            visited.add(task_id)
            for child_id in children_map.get(task_id, []):
                child_task = self._tasks.get(child_id)
                if child_task is None:
                    continue
                label = self._format_task_label(child_id)
                child_branch = parent_tree.add(label)
                _add_children(child_branch, child_id)

        for root_task in roots:
            label = self._format_task_label(root_task.id)
            branch = self._tree.add(label)
            _add_children(branch, root_task.id)

        return self._tree

    def render(self, title: str | None = None) -> None:
        """Render the built tree to the console.

        Args:
            title: Optional title for the panel.
        """
        if self._tree is None:
            self.console.print("[yellow]No DAG to render. Call build() first.[/]")
            return

        if title:
            self.console.print(Panel(self._tree, title=title, border_style="blue"))
        else:
            self.console.print(self._tree)

    def get_execution_levels(self, tasks: list[TaskConfig]) -> list[list[str]]:
        """Return task IDs grouped by execution level (BFS topological sort).

        Args:
            tasks: List of task configurations.

        Returns:
            List of levels, each level is a list of task IDs.
        """
        from collections import defaultdict, deque

        children: dict[str, set[str]] = defaultdict(set)
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}

        for t in tasks:
            for dep in t.depends_on:
                children[dep].add(t.id)
                in_degree[t.id] += 1

        queue = deque(tid for tid, d in in_degree.items() if d == 0)
        levels: list[list[str]] = []

        while queue:
            level = list(queue)
            levels.append(level)
            next_queue: deque[str] = deque()
            for node in level:
                for child in children.get(node, set()):
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_queue.append(child)
            queue = next_queue

        return levels

    def _format_task_label(self, task_id: str) -> str:
        """Format a single task's label with status and metadata."""
        status = self._statuses.get(task_id, "pending")
        symbol = _STATUS_SYMBOLS.get(status, "?")
        style = _STATUS_STYLES.get(status, "")

        parts = [f"[{style}]{symbol}[/] [{style}]{task_id}[/]"]

        agent = self._agents.get(task_id)
        if agent:
            parts.append(f"[dim]({agent})[/]")

        duration = self._durations.get(task_id)
        if duration is not None:
            parts.append(f"[dim]{duration:.1f}s[/]")

        return " ".join(parts)

    def _format_root_label(self) -> str:
        """Format the root label of the tree."""
        total = len(self._tasks)
        completed = sum(1 for s in self._statuses.values() if s == "success")
        failed = sum(1 for s in self._statuses.values() if s == "failed")
        if failed:
            return f"[bold blue]workflow[/] [dim]({completed}/{total} done, {failed} failed)[/]"
        return f"[bold blue]workflow[/] [dim]({completed}/{total} done)[/]"

    def to_dict(self, tasks: list[TaskConfig]) -> dict[str, Any]:
        """Export DAG structure as a plain dictionary for JSON serialization.

        Args:
            tasks: List of task configurations.

        Returns:
            Dictionary with nodes and edges representation.
        """
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []

        for t in tasks:
            nodes.append({
                "id": t.id,
                "agent": t.agent,
                "status": self._statuses.get(t.id, "pending"),
                "duration": self._durations.get(t.id),
            })
            for dep in t.depends_on:
                edges.append({"from": dep, "to": t.id})

        return {"nodes": nodes, "edges": edges}
