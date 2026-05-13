"""Task timing statistics and bar chart rendering.

Tracks per-task execution times and renders summary statistics
with Rich bar charts for visual comparison.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text


@dataclass
class TaskTiming:
    """Timing data for a single task execution."""

    task_id: str
    agent: str
    duration: float
    status: str
    attempt: int = 1


@dataclass
class TimingStats:
    """Aggregated timing statistics for workflow execution.

    Collects timing data from task executions and provides
    statistical summaries and visual bar charts.
    """

    timings: list[TaskTiming] = field(default_factory=list)
    _console: Console = field(default_factory=Console, repr=False)

    def record(self, task_id: str, agent: str, duration: float, status: str, attempt: int = 1) -> None:
        """Record timing for a task execution.

        Args:
            task_id: Unique task identifier.
            agent: Agent name that executed the task.
            duration: Execution duration in seconds.
            status: Task status (success/failed/skipped).
            attempt: Attempt number (1 for first try).
        """
        self.timings.append(TaskTiming(
            task_id=task_id,
            agent=agent,
            duration=duration,
            status=status,
            attempt=attempt,
        ))

    def get_task_summary(self, task_id: str) -> dict[str, float | int]:
        """Get timing summary for a specific task across all attempts.

        Args:
            task_id: Task identifier to summarize.

        Returns:
            Dictionary with min, max, avg, total, count, last values.
        """
        task_timings = [t for t in self.timings if t.task_id == task_id]
        if not task_timings:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "total": 0.0, "count": 0, "last": 0.0}

        durations = [t.duration for t in task_timings]
        return {
            "min": min(durations),
            "max": max(durations),
            "avg": statistics.mean(durations),
            "total": sum(durations),
            "count": len(durations),
            "last": durations[-1],
        }

    def get_overall_summary(self) -> dict[str, float | int]:
        """Get overall timing summary for all tasks.

        Returns:
            Dictionary with total_time, task_count, success_count,
            failed_count, avg_time, median_time, p95_time values.
        """
        if not self.timings:
            return {
                "total_time": 0.0,
                "task_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "avg_time": 0.0,
                "median_time": 0.0,
                "p95_time": 0.0,
            }

        durations = [t.duration for t in self.timings]
        success_count = sum(1 for t in self.timings if t.status == "success")
        failed_count = sum(1 for t in self.timings if t.status == "failed")

        sorted_durations = sorted(durations)
        p95_idx = int(len(sorted_durations) * 0.95)
        p95_idx = min(p95_idx, len(sorted_durations) - 1)

        return {
            "total_time": sum(durations),
            "task_count": len(set(t.task_id for t in self.timings)),
            "success_count": success_count,
            "failed_count": failed_count,
            "avg_time": statistics.mean(durations),
            "median_time": statistics.median(durations),
            "p95_time": sorted_durations[p95_idx],
        }

    def get_agent_summary(self) -> dict[str, dict[str, float | int]]:
        """Get timing summary grouped by agent.

        Returns:
            Dictionary mapping agent names to their timing summaries.
        """
        agents: dict[str, list[float]] = {}
        for t in self.timings:
            agents.setdefault(t.agent, []).append(t.duration)

        result: dict[str, dict[str, float | int]] = {}
        for agent, durations in agents.items():
            sorted_d = sorted(durations)
            p95_idx = min(int(len(sorted_d) * 0.95), len(sorted_d) - 1)
            result[agent] = {
                "count": len(durations),
                "total": sum(durations),
                "avg": statistics.mean(durations),
                "median": statistics.median(durations),
                "p95": sorted_d[p95_idx],
            }
        return result

    def render_table(self) -> Table:
        """Render timing statistics as a Rich table.

        Returns:
            A Rich Table with task timing details.
        """
        table = Table(title="Task Timing Statistics", show_lines=True)
        table.add_column("Task", style="cyan", no_wrap=True)
        table.add_column("Agent", style="magenta")
        table.add_column("Duration", justify="right", style="green")
        table.add_column("Status", justify="center")
        table.add_column("Attempts", justify="right")

        task_ids_seen: set[str] = set()
        for t in self.timings:
            if t.task_id in task_ids_seen:
                continue
            task_ids_seen.add(t.task_id)
            summary = self.get_task_summary(t.task_id)
            status_style = "green" if t.status == "success" else "red"
            table.add_row(
                t.task_id,
                t.agent,
                f"{summary['avg']:.1f}s",
                f"[{status_style}]{t.status}[/]",
                str(summary["count"]),
            )

        return table

    def render_bar_chart(self, max_width: int = 40) -> Text:
        """Render a horizontal bar chart of task durations.

        Args:
            max_width: Maximum width of the bar in characters.

        Returns:
            Rich Text object with the rendered bar chart.
        """
        if not self.timings:
            return Text("No timing data available.")

        # Deduplicate by task_id (use last timing for each)
        task_durations: dict[str, float] = {}
        task_agents: dict[str, str] = {}
        for t in self.timings:
            task_durations[t.task_id] = t.duration
            task_agents[t.task_id] = t.agent

        if not task_durations:
            return Text("No timing data available.")

        max_dur = max(task_durations.values())
        if max_dur == 0:
            max_dur = 1.0

        lines: list[str] = []
        for tid, dur in sorted(task_durations.items(), key=lambda x: -x[1]):
            bar_len = int((dur / max_dur) * max_width)
            bar = "█" * bar_len
            agent = task_agents.get(tid, "")
            lines.append(f"  {tid:<15s} {bar} {dur:.1f}s ({agent})")

        text = Text.from_markup("\n".join(lines))
        return text

    def export_data(self) -> list[dict[str, object]]:
        """Export all timing data as a list of dictionaries.

        Returns:
            List of dictionaries suitable for JSON serialization.
        """
        return [
            {
                "task_id": t.task_id,
                "agent": t.agent,
                "duration": round(t.duration, 3),
                "status": t.status,
                "attempt": t.attempt,
            }
            for t in self.timings
        ]
