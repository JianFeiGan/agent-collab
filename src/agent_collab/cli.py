"""Typer CLI entry point for AgentCollab."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agent_collab.agents.aider import AiderAgent
from agent_collab.agents.base import BaseAgent
from agent_collab.agents.claude_code import ClaudeCodeAgent
from agent_collab.agents.codex import CodexAgent
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.scheduler import TaskScheduler
from agent_collab.core.workflow import WorkflowParser
from agent_collab.display.progress import ProgressDisplay

app = typer.Typer(
    name="agent-collab",
    help="Multi-Agent Orchestration Engine — orchestrate Claude Code, Codex, Aider to collaborate on projects.",
    no_args_is_help=True,
)
console = Console()
progress = ProgressDisplay()

# ── Agent registry ──────────────────────────────────────────────────

AGENT_REGISTRY: dict[str, BaseAgent] = {
    "claude-code": ClaudeCodeAgent(),
    "codex": CodexAgent(),
    "aider": AiderAgent(),
}


# ── Commands ────────────────────────────────────────────────────────


@app.command()
def run(
    workflow_file: Path = typer.Argument(
        ..., help="Path to the workflow YAML file.", exists=True, readable=True
    ),
) -> None:
    """Execute a workflow defined in a YAML file."""
    try:
        config = WorkflowParser.parse(workflow_file)
    except (FileNotFoundError, ValueError) as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc

    scheduler = TaskScheduler(config.tasks)
    try:
        levels = scheduler.get_execution_order()
    except ValueError as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc

    # Build agent map: config name -> agent instance
    agent_map: dict[str, BaseAgent] = {}
    for cfg_name, cfg in config.agents.items():
        if cfg.type not in AGENT_REGISTRY:
            progress.show_error(f"Unknown agent type '{cfg.type}' for agent '{cfg_name}'")
            raise typer.Exit(code=1)
        agent_map[cfg_name] = AGENT_REGISTRY[cfg.type]

    executor = TaskExecutor(
        agents=agent_map,
        agent_configs=config.agents,
        strategy=config.strategy,
    )

    progress.show_workflow_start(
        name=config.name,
        task_count=len(config.tasks),
        agent_count=len(config.agents),
    )

    start_time = time.monotonic()
    total_failed = 0
    total_tasks = 0

    for level_idx, task_ids in enumerate(levels):
        progress.show_level_start(level_idx, task_ids)
        tasks = [scheduler.tasks[tid] for tid in task_ids]
        results = asyncio.run(executor.execute_level(tasks))

        for task in tasks:
            result = results[task.id]
            progress.show_task_start(task.id, task.agent)
            total_tasks += 1
            if result.success:
                progress.show_task_complete(task.id, result.duration_seconds)
            else:
                total_failed += 1
                progress.show_task_failed(task.id, result.output)

    elapsed = time.monotonic() - start_time
    progress.show_workflow_complete(total_tasks, total_failed, elapsed)

    if total_failed > 0:
        raise typer.Exit(code=1)


@app.command(name="validate")
def validate_workflow(
    workflow_file: Path = typer.Argument(
        ..., help="Path to the workflow YAML file.", exists=True, readable=True
    ),
) -> None:
    """Validate a workflow YAML file without executing it."""
    try:
        config = WorkflowParser.parse(workflow_file)
    except FileNotFoundError as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc

    scheduler = TaskScheduler(config.tasks)
    try:
        levels = scheduler.get_execution_order()
    except ValueError as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc

    # Report validation success
    console.print(f"[green]✓[/] Workflow '{config.name}' is valid.")
    console.print(f"  Tasks: {len(config.tasks)}")
    console.print(f"  Agents: {', '.join(config.agents.keys())}")
    console.print(f"  Execution levels: {len(levels)}")

    # Warn about unavailable agents
    for name, cfg in config.agents.items():
        agent = AGENT_REGISTRY.get(cfg.type)
        if agent is None:
            console.print(f"  [yellow]⚠[/] Agent '{name}' uses unknown type '{cfg.type}'")
        elif not agent.is_available():
            console.print(f"  [yellow]⚠[/] Agent '{name}' ({cfg.type}) CLI is not installed")


@app.command(name="list-agents")
def list_agents() -> None:
    """Show available agents and their installation status."""
    table = Table(title="Registered Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("CLI Tool")

    cli_names = {
        "claude-code": "claude",
        "codex": "codex",
        "aider": "aider",
    }

    for name, agent in AGENT_REGISTRY.items():
        available = agent.is_available()
        status = "[green]available[/]" if available else "[red]not found[/]"
        table.add_row(name, status, cli_names.get(name, "—"))

    console.print(table)
