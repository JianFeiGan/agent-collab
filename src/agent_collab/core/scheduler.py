"""DAG-based task scheduler with topological sort."""

from __future__ import annotations

from collections import defaultdict, deque

from agent_collab.core.workflow import TaskConfig


class TaskScheduler:
    """Schedules tasks using topological sort, grouping parallelizable tasks."""

    def __init__(self, tasks: list[TaskConfig]) -> None:
        self.tasks: dict[str, TaskConfig] = {t.id: t for t in tasks}
        self.graph: dict[str, set[str]] = self._build_dag(tasks)

    @staticmethod
    def _build_dag(tasks: list[TaskConfig]) -> dict[str, set[str]]:
        """Build adjacency list: parent -> set of children."""
        graph: dict[str, set[str]] = defaultdict(set)
        for task in tasks:
            graph.setdefault(task.id, set())
            for dep in task.depends_on:
                graph[dep].add(task.id)
        return graph

    def detect_cycles(self) -> list[str] | None:
        """Return the first cycle found, or None if the graph is acyclic.

        Uses Kahn's algorithm — if not all nodes are processed, there's a cycle.
        Returns the cycle path as a list of task IDs, or None.
        """
        in_degree: dict[str, int] = {tid: 0 for tid in self.tasks}
        for task in self.tasks.values():
            for dep in task.depends_on:
                in_degree[task.id] += 1

        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        visited: list[str] = []

        while queue:
            node = queue.popleft()
            visited.append(node)
            for child in self.graph.get(node, set()):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(visited) != len(self.tasks):
            # Find a node involved in the cycle via DFS
            remaining = set(self.tasks) - set(visited)
            return self._find_cycle_path(remaining)
        return None

    def _find_cycle_path(self, remaining: set[str]) -> list[str]:
        """DFS to extract an actual cycle path from remaining nodes."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {tid: WHITE for tid in remaining}
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            path.append(node)
            for child in self.graph.get(node, set()):
                if child in remaining:
                    if color[child] == GRAY:
                        idx = path.index(child)
                        return path[idx:] + [child]
                    if color[child] == WHITE:
                        result = dfs(child)
                        if result is not None:
                            return result
            path.pop()
            color[node] = BLACK
            return None

        for tid in remaining:
            if color[tid] == WHITE:
                result = dfs(tid)
                if result is not None:
                    return result
        return list(remaining)

    def get_execution_order(self) -> list[list[str]]:
        """Return tasks grouped by execution level (BFS-based topological sort).

        Each inner list contains task IDs that can run in parallel.
        Raises ValueError if a cycle is detected.
        """
        cycle = self.detect_cycles()
        if cycle is not None:
            raise ValueError(
                f"Cannot schedule: dependency cycle detected: {' -> '.join(cycle)}"
            )

        in_degree: dict[str, int] = {tid: 0 for tid in self.tasks}
        for task in self.tasks.values():
            for dep in task.depends_on:
                in_degree[task.id] += 1

        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        levels: list[list[str]] = []

        while queue:
            level = list(queue)
            levels.append(level)
            next_queue: deque[str] = deque()
            for node in level:
                for child in self.graph.get(node, set()):
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_queue.append(child)
            queue = next_queue

        return levels
