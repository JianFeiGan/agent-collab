"""Rich-based TUI progress display for workflow execution."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class ProgressDisplay:
    """Displays workflow progress using Rich terminal output."""

    def show_workflow_start(self, name: str, task_count: int, agent_count: int) -> None:
        """Print a banner at workflow start."""
        console.print(
            Panel(
                f"[bold]Workflow:[/] {name}\n"
                f"[bold]Tasks:[/] {task_count}  [bold]Agents:[/] {agent_count}",
                title="[bold blue]AgentCollab[/]",
                border_style="blue",
            )
        )

    def show_level_start(self, level: int, task_ids: list[str]) -> None:
        """Print the start of a parallel execution level."""
        ids = ", ".join(task_ids)
        console.print(f"\n[bold cyan]Level {level + 1}[/] — running: {ids}")

    def show_task_start(self, task_id: str, agent_name: str) -> None:
        """Print when a task begins execution."""
        console.print(f"  [yellow]>[/] {task_id} ({agent_name}) ...", end="")

    def show_task_complete(self, task_id: str, duration: float) -> None:
        """Print when a task finishes successfully."""
        console.print(f" [green]done[/] ({duration:.1f}s)")

    def show_task_failed(self, task_id: str, error: str) -> None:
        """Print when a task fails."""
        console.print(f" [red]FAILED[/]: {error}")

    def show_workflow_complete(self, total_tasks: int, failed: int, duration: float) -> None:
        """Print a summary panel at workflow end."""
        status = "[green]Success[/]" if failed == 0 else f"[red]{failed} task(s) failed[/]"
        table = Table(show_header=False, box=None)
        table.add_row("Status", status)
        table.add_row("Tasks", str(total_tasks))
        table.add_row("Duration", f"{duration:.1f}s")
        console.print(Panel(table, title="[bold blue]Workflow Complete[/]", border_style="blue"))

    def show_error(self, message: str) -> None:
        """Print an error message."""
        console.print(f"[bold red]Error:[/] {message}")
