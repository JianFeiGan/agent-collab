"""Token consumption tracking for agent task executions.

Records per-task input/output token usage and provides aggregated
statistics grouped by agent, with Rich table rendering and JSON export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table


@dataclass
class TokenUsage:
    """Token usage record for a single task execution."""

    task_id: str
    agent: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (input + output)."""
        return self.input_tokens + self.output_tokens


@dataclass
class TokenTracker:
    """Tracks and aggregates token consumption across task executions.

    Collects per-task token usage and provides summary statistics
    grouped by agent, with Rich table rendering and JSON export.

    Example::

        tracker = TokenTracker()
        tracker.record("task-1", "claude", input_tokens=500, output_tokens=200)
        tracker.record("task-2", "claude", input_tokens=300, output_tokens=100)
        print(tracker.get_agent_summary())
        tracker.render_table()
    """

    usages: list[TokenUsage] = field(default_factory=list)
    _console: Console = field(default_factory=Console, repr=False)

    def record(
        self,
        task_id: str,
        agent: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage for a task execution.

        Args:
            task_id: Unique task identifier.
            agent: Agent name that executed the task.
            input_tokens: Number of input (prompt) tokens consumed.
            output_tokens: Number of output (completion) tokens consumed.
        """
        self.usages.append(TokenUsage(
            task_id=task_id,
            agent=agent,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ))

    def get_task_usage(self, task_id: str) -> TokenUsage | None:
        """Get the token usage record for a specific task.

        Args:
            task_id: Task identifier to look up.

        Returns:
            The TokenUsage for the task, or None if not found.
        """
        for u in self.usages:
            if u.task_id == task_id:
                return u
        return None

    def get_agent_summary(self) -> dict[str, dict[str, int]]:
        """Get token usage summary grouped by agent.

        Returns:
            Dictionary mapping agent names to their token summaries
            with keys ``input_tokens``, ``output_tokens``, ``total_tokens``,
            and ``task_count``.
        """
        agents: dict[str, list[TokenUsage]] = {}
        for u in self.usages:
            agents.setdefault(u.agent, []).append(u)

        result: dict[str, dict[str, int]] = {}
        for agent, usages in agents.items():
            result[agent] = {
                "input_tokens": sum(u.input_tokens for u in usages),
                "output_tokens": sum(u.output_tokens for u in usages),
                "total_tokens": sum(u.total_tokens for u in usages),
                "task_count": len(usages),
            }
        return result

    def get_overall_summary(self) -> dict[str, int]:
        """Get overall token usage summary for all tasks.

        Returns:
            Dictionary with ``input_tokens``, ``output_tokens``,
            ``total_tokens``, and ``task_count``.
        """
        return {
            "input_tokens": sum(u.input_tokens for u in self.usages),
            "output_tokens": sum(u.output_tokens for u in self.usages),
            "total_tokens": sum(u.total_tokens for u in self.usages),
            "task_count": len(self.usages),
        }

    def render_table(self) -> Table:
        """Render token usage as a Rich table.

        Returns:
            A Rich Table with per-task token usage details.
        """
        table = Table(title="Token Usage", show_lines=True)
        table.add_column("Task", style="cyan", no_wrap=True)
        table.add_column("Agent", style="magenta")
        table.add_column("Input Tokens", justify="right", style="green")
        table.add_column("Output Tokens", justify="right", style="green")
        table.add_column("Total Tokens", justify="right", style="bold green")

        for u in self.usages:
            table.add_row(
                u.task_id,
                u.agent,
                f"{u.input_tokens:,}",
                f"{u.output_tokens:,}",
                f"{u.total_tokens:,}",
            )

        # Add summary row
        summary = self.get_overall_summary()
        if summary["task_count"] > 0:
            table.add_row(
                "[bold]TOTAL[/bold]",
                "",
                f"[bold]{summary['input_tokens']:,}[/bold]",
                f"[bold]{summary['output_tokens']:,}[/bold]",
                f"[bold]{summary['total_tokens']:,}[/bold]",
            )

        return table

    def render_agent_summary_table(self) -> Table:
        """Render agent-level token summary as a Rich table.

        Returns:
            A Rich Table with per-agent aggregated token usage.
        """
        table = Table(title="Token Usage by Agent", show_lines=True)
        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("Tasks", justify="right", style="magenta")
        table.add_column("Input Tokens", justify="right", style="green")
        table.add_column("Output Tokens", justify="right", style="green")
        table.add_column("Total Tokens", justify="right", style="bold green")

        for agent, summary in self.get_agent_summary().items():
            table.add_row(
                agent,
                str(summary["task_count"]),
                f"{summary['input_tokens']:,}",
                f"{summary['output_tokens']:,}",
                f"{summary['total_tokens']:,}",
            )

        return table

    def export_data(self) -> list[dict[str, int | str]]:
        """Export all token usage data as a list of dictionaries.

        Returns:
            List of dictionaries suitable for JSON serialization.
        """
        return [
            {
                "task_id": u.task_id,
                "agent": u.agent,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "total_tokens": u.total_tokens,
            }
            for u in self.usages
        ]

    def export_json(self, path: str | Path) -> None:
        """Export token usage data to a JSON file.

        Args:
            path: Filesystem path where the JSON file will be written.
        """
        path = Path(path)
        data = {
            "tasks": self.export_data(),
            "by_agent": self.get_agent_summary(),
            "overall": self.get_overall_summary(),
        }
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
