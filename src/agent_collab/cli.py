"""Typer CLI entry point for AgentCollab."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from agent_collab import __version__
from agent_collab.core.checkpoint import CheckpointManager
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.replay import WorkflowReplayer
from agent_collab.core.scheduler import TaskScheduler
from agent_collab.core.workflow import WorkflowParser
from agent_collab.display.progress import ProgressDisplay

if TYPE_CHECKING:
    from agent_collab.agents.base import BaseAgent

app = typer.Typer(
    name="agent-collab",
    help="Multi-Agent Orchestration Engine — orchestrate Claude Code, Codex, Aider to collaborate on projects.",
    no_args_is_help=True,
)
console = Console()
progress = ProgressDisplay()


# ── Version callback ──────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def _version(
    version: bool = typer.Option(False, "--version", "-v", is_eager=True),
) -> None:
    """Agent Collab CLI."""
    if version:
        console.print(f"agent-collab {__version__}")
        raise typer.Exit()


# ── Agent registry (lazy initialization) ─────────────────────────────

_AGENT_REGISTRY: dict[str, BaseAgent] | None = None


def _get_agent_registry() -> dict[str, BaseAgent]:
    """Get or create the agent registry with lazy initialization."""
    global _AGENT_REGISTRY
    if _AGENT_REGISTRY is None:
        from agent_collab.agents.aider import AiderAgent
        from agent_collab.agents.claude_code import ClaudeCodeAgent
        from agent_collab.agents.codex import CodexAgent
        from agent_collab.agents.opencode import OpenCodeAgent

        _AGENT_REGISTRY = {
            "claude-code": ClaudeCodeAgent(),
            "codex": CodexAgent(),
            "aider": AiderAgent(),
            "opencode": OpenCodeAgent(),
        }
    return _AGENT_REGISTRY


# For backward compatibility, expose as property-like access
class _RegistryProxy:
    """Proxy that provides dict-like access to the lazy registry."""

    def __getitem__(self, key: str) -> BaseAgent:
        return _get_agent_registry()[key]

    def __contains__(self, key: str) -> bool:
        return key in _get_agent_registry()

    def get(self, key: str, default=None) -> BaseAgent | None:
        return _get_agent_registry().get(key, default)

    def items(self):
        return _get_agent_registry().items()

    def keys(self):
        return _get_agent_registry().keys()

    def values(self):
        return _get_agent_registry().values()


AGENT_REGISTRY = _RegistryProxy()


# ── Commands ────────────────────────────────────────────────────────


async def _run_workflow(config, scheduler, levels) -> tuple[int, int, TaskExecutor]:
    """Execute all workflow levels asynchronously.

    Returns:
        Tuple of (total_tasks, total_failed, executor).
    """
    # Build agent map: config name -> agent instance
    agent_map: dict[str, BaseAgent] = {}
    for cfg_name, cfg in config.agents.items():
        if cfg.type not in AGENT_REGISTRY:
            raise ValueError(f"Unknown agent type '{cfg.type}' for agent '{cfg_name}'")
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
        if executor.is_cancelled():
            progress.show_workflow_cancelled()
            break

        progress.show_level_start(level_idx, task_ids)
        tasks = [scheduler.tasks[tid] for tid in task_ids]
        results = await executor.execute_level(tasks)

        for task in tasks:
            result = results.get(task.id)
            if result is None:
                continue
            progress.show_task_start(task.id, task.agent)
            total_tasks += 1
            if result.success:
                progress.show_task_complete(task.id, result.duration_seconds)
            else:
                total_failed += 1
                progress.show_task_failed(task.id, result.output)

    elapsed = time.monotonic() - start_time
    progress.show_workflow_complete(total_tasks, total_failed, elapsed)

    return total_tasks, total_failed, executor


def _save_execution_log(
    executor: TaskExecutor,
    workflow_name: str,
) -> str | None:
    """Save the execution log to a JSON file in .agent-collab/logs/.

    Args:
        executor: The TaskExecutor whose log to save.
        workflow_name: Name of the workflow for the filename.

    Returns:
        The path the log was saved to, or None on failure.
    """
    import json
    from datetime import datetime

    log_dir = Path(".agent-collab/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = workflow_name.replace(" ", "_").replace("/", "_")
    log_path = log_dir / f"{safe_name}_{timestamp}.json"

    try:
        executor.export_log(str(log_path))
        return str(log_path)
    except OSError as exc:
        progress.show_error(f"Failed to save execution log: {exc}")
        return None


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

    # Shared container so KeyboardInterrupt handler can access the executor
    executor_container: list[TaskExecutor | None] = [None]

    try:
        total_tasks, total_failed, executor = asyncio.run(
            _run_workflow(config, scheduler, levels)
        )
        executor_container[0] = executor

        # Auto-save execution log
        log_path = _save_execution_log(executor, config.name)
        if log_path:
            console.print(f"[dim]Execution log saved to {log_path}[/dim]")

        if executor.is_cancelled():
            active = executor.active_task_count
            console.print(
                f"[yellow]⚠[/] Workflow cancelled. "
                f"Completed: {total_tasks}, still running: {active}"
            )
            raise typer.Exit(code=130) from None

        if total_failed > 0:
            raise typer.Exit(code=1)
    except ValueError as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        exec_ = executor_container[0]
        if exec_ is not None:
            # Trigger cancellation
            exec_.cancel_all()
            # Try to wait briefly for running tasks
            try:
                pending = asyncio.run(exec_.graceful_shutdown(timeout=2.0))
            except (RuntimeError, asyncio.CancelledError):
                pending = exec_.active_task_count
            # Save whatever log we have
            log_path = _save_execution_log(exec_, config.name)
            msg = "\n[yellow]⚠[/] Workflow cancelled by user"
            if log_path:
                msg += f"\n[dim]Execution log saved to {log_path}[/dim]"
            msg += f"\n[dim]{pending} task(s) still running at exit[/dim]"
            console.print(msg)
        else:
            console.print("\n[yellow]⚠[/] Workflow cancelled by user")
        raise typer.Exit(code=130) from None


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


async def _replay_workflow(config, agent_map, checkpoint_id) -> dict:
    """Replay workflow from checkpoint asynchronously.

    Returns:
        Dict of task_id -> AgentResult.
    """
    replayer = WorkflowReplayer()
    return await replayer.replay_from_checkpoint(checkpoint_id, config, agent_map)


@app.command(name="replay")
def replay_workflow(
    checkpoint_id: str = typer.Argument(..., help="Checkpoint ID to resume from."),
    workflow_file: Path = typer.Argument(
        ..., help="Path to the workflow YAML file.", exists=True, readable=True
    ),
) -> None:
    """Resume workflow execution from a checkpoint."""
    try:
        config = WorkflowParser.parse(workflow_file)
    except (FileNotFoundError, ValueError) as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc

    # Build agent map
    agent_map: dict[str, BaseAgent] = {}
    for cfg_name, cfg in config.agents.items():
        if cfg.type not in AGENT_REGISTRY:
            progress.show_error(f"Unknown agent type '{cfg.type}' for agent '{cfg_name}'")
            raise typer.Exit(code=1)
        agent_map[cfg_name] = AGENT_REGISTRY[cfg.type]

    try:
        results = asyncio.run(_replay_workflow(config, agent_map, checkpoint_id))
    except FileNotFoundError as exc:
        progress.show_error(str(exc))
        raise typer.Exit(code=1) from exc

    total_failed = 0
    for task_id, result in results.items():
        if result.success:
            console.print(f"  [green]✓[/] {task_id}")
        else:
            total_failed += 1
            console.print(f"  [red]✗[/] {task_id}: {result.output[:100]}")

    if total_failed > 0:
        console.print(f"\n[red]{total_failed} task(s) failed during replay.[/]")
        raise typer.Exit(code=1)
    else:
        console.print(
            f"\n[green]Replay completed successfully. {len(results)} task(s) executed.[/]"
        )


@app.command(name="checkpoints")
def checkpoints(
    action: str = typer.Argument("list", help="Action: 'list' or 'delete'."),
    checkpoint_id: str | None = typer.Argument(None, help="Checkpoint ID (required for 'delete')."),
) -> None:
    """Manage workflow checkpoints."""
    manager = CheckpointManager()

    if action == "list":
        cps = manager.list_checkpoints()
        if not cps:
            console.print("[yellow]No checkpoints found.[/]")
            return
        table = Table(title="Checkpoints")
        table.add_column("ID", style="cyan")
        table.add_column("Workflow")
        table.add_column("Completed Tasks")
        table.add_column("Timestamp")
        for cp in cps:
            table.add_row(
                cp.checkpoint_id,
                cp.workflow_name,
                ", ".join(cp.completed_tasks) if cp.completed_tasks else "none",
                cp.timestamp,
            )
        console.print(table)

    elif action == "delete":
        if checkpoint_id is None:
            progress.show_error("checkpoint_id is required for 'delete' action.")
            raise typer.Exit(code=1)
        deleted = manager.delete(checkpoint_id)
        if deleted:
            console.print(f"[green]Deleted checkpoint '{checkpoint_id}'.[/]")
        else:
            console.print(f"[yellow]Checkpoint '{checkpoint_id}' not found.[/]")
            raise typer.Exit(code=1)
    else:
        progress.show_error(f"Unknown action '{action}'. Use 'list' or 'delete'.")
        raise typer.Exit(code=1)


# ── Security commands ────────────────────────────────────────────────


@app.command()
def security_create_user(
    username: str = typer.Argument(..., help="Username."),
    password: str = typer.Argument(..., help="Plain-text password."),
    role: str = typer.Option("developer", help="Role: admin, manager, developer, viewer."),
    tenant_id: str = typer.Option("default", help="Tenant ID."),
) -> None:
    """Create a new user account."""
    from agent_collab.security import (
        User,
        UserRole,
        hash_password,
    )
    from agent_collab.security.providers import InMemoryAuthProvider

    provider = InMemoryAuthProvider()

    try:
        user_role = UserRole(role)
    except ValueError:
        progress.show_error(
            f"Invalid role '{role}'. Choose from: admin, manager, developer, viewer."
        )
        raise typer.Exit(code=1)

    import asyncio

    async def _create() -> None:
        user = User(
            username=username,
            hashed_password=hash_password(password),
            role=user_role,
            tenant_id=tenant_id,
        )
        await provider.create_user(user)
        console.print(f"[green]User '{username}' created with role '{role}' (id={user.id}).[/]")
        # Generate token immediately
        from agent_collab.security import generate_token

        token = generate_token(user)
        console.print(f"[cyan]Access token:[/] {token.access_token}")

    asyncio.run(_create())


@app.command()
def security_login(
    username: str = typer.Argument(..., help="Username."),
    password: str = typer.Argument(..., help="Password."),
) -> None:
    """Authenticate and return an access token."""
    import asyncio

    from agent_collab.security import generate_token
    from agent_collab.security.providers import InMemoryAuthProvider

    provider = InMemoryAuthProvider()

    async def _login() -> None:
        user = await provider.authenticate(username, password)
        if user is None:
            progress.show_error("Authentication failed: invalid username or password.")
            raise typer.Exit(code=1)
        token = generate_token(user)
        console.print(f"[green]Authenticated as '{username}'[/]")
        console.print(f"[cyan]Access token:[/] {token.access_token}")
        console.print(f"[dim]Expires in:[/] {token.expires_in}s")

    asyncio.run(_login())


@app.command()
def security_verify_token(
    token: str = typer.Argument(..., help="JWT access token to verify."),
) -> None:
    """Verify an access token and print its payload."""
    from agent_collab.security import verify_token

    payload = verify_token(token)
    if payload is None:
        progress.show_error("Token is invalid or expired.")
        raise typer.Exit(code=1)

    console.print("[green]Token is valid.[/]")
    table = Table(title="Token Payload")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(str(key), str(value))
    console.print(table)


# ── Distributed commands ─────────────────────────────────────────────


@app.command()
def distributed_status() -> None:
    """Show distributed execution status (workers & queue)."""
    import asyncio

    from agent_collab.distributed.queue import InMemoryTaskQueue, InMemoryWorkerManager

    queue = InMemoryTaskQueue()
    wm = InMemoryWorkerManager()

    async def _status() -> None:
        qsize = await queue.get_queue_size()
        stats = await wm.get_worker_stats()

        table = Table(title="Distributed Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Queue Size", str(qsize))
        table.add_row("Total Workers", str(stats.get("total_workers", 0)))
        table.add_row("Idle Workers", str(stats.get("idle_workers", 0)))
        table.add_row("Busy Workers", str(stats.get("busy_workers", 0)))
        table.add_row("Total Capacity", str(stats.get("total_capacity", 0)))
        table.add_row("Current Tasks", str(stats.get("current_tasks", 0)))
        console.print(table)

    asyncio.run(_status())


# ── HITL commands ────────────────────────────────────────────────────


@app.command()
def hitl_pending() -> None:
    """List pending approval and input requests."""
    import asyncio

    from agent_collab.hitl import InMemoryProvider
    from agent_collab.hitl.nodes import HITLManager

    provider = InMemoryProvider()
    manager = HITLManager(provider)

    async def _list() -> None:
        approvals = manager.get_pending_approvals()
        inputs = manager.get_pending_inputs()

        if not approvals and not inputs:
            console.print("[yellow]No pending HITL requests.[/]")
            return

        if approvals:
            table = Table(title="Pending Approvals")
            table.add_column("ID", style="cyan")
            table.add_column("Task ID")
            table.add_column("Title")
            table.add_column("Status")
            for req in approvals:
                table.add_row(req.id[:8], req.task_id, req.title, req.status.value)
            console.print(table)

        if inputs:
            table = Table(title="Pending Inputs")
            table.add_column("ID", style="cyan")
            table.add_column("Task ID")
            table.add_column("Title")
            table.add_column("Type")
            table.add_column("Status")
            for req in inputs:
                table.add_row(
                    req.id[:8], req.task_id, req.title, req.input_type.value, req.status.value
                )
            console.print(table)

    asyncio.run(_list())
