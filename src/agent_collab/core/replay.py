"""Workflow replay from checkpoints."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.checkpoint import Checkpoint, CheckpointManager
from agent_collab.core.degradation import DegradationPolicy
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.scheduler import TaskScheduler
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig, WorkflowConfig


class WorkflowReplayer:
    """Replays a workflow from a saved checkpoint.

    The replayer loads a checkpoint, skips already-completed tasks, and
    executes remaining tasks via the normal executor pipeline.

    Attributes:
        checkpoint_manager: Manager used to load and save checkpoints.
    """

    def __init__(self, checkpoint_manager: CheckpointManager | None = None) -> None:
        """Initialise the WorkflowReplayer.

        Args:
            checkpoint_manager: Optional checkpoint manager. If ``None``,
                a default manager using the standard directory is created.
        """
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all available checkpoints.

        Returns:
            A list of Checkpoint objects sorted by timestamp descending.
        """
        return self.checkpoint_manager.list_checkpoints()

    async def replay_from_checkpoint(
        self,
        checkpoint_id: str,
        config: WorkflowConfig,
        agents: dict[str, BaseAgent],
    ) -> dict[str, AgentResult]:
        """Resume workflow execution from a saved checkpoint.

        Tasks that already appear in the checkpoint's ``completed_tasks``
        are skipped.  The executor is seeded with the checkpoint's
        ``task_outputs`` so downstream ``${task.output}`` references
        resolve correctly.

        Args:
            checkpoint_id: The checkpoint to resume from.
            config: The full workflow configuration.
            agents: Map of agent name to agent instance.

        Returns:
            A map of task ID to AgentResult for tasks executed in this run.
        """
        checkpoint = self.checkpoint_manager.load(checkpoint_id)
        completed = set(checkpoint.completed_tasks)

        # Build executor with checkpoint state restored
        executor = TaskExecutor(
            agents=agents,
            agent_configs=config.agents,
            strategy=config.strategy,
        )
        executor.task_outputs = dict(checkpoint.task_outputs)

        scheduler = TaskScheduler(config.tasks)
        levels = scheduler.get_execution_order()

        results: dict[str, AgentResult] = {}

        for task_ids in levels:
            # Filter out already-completed tasks
            pending_ids = [tid for tid in task_ids if tid not in completed]
            if not pending_ids:
                continue

            tasks = [scheduler.tasks[tid] for tid in pending_ids]
            level_results = await executor.execute_level(tasks)
            results.update(level_results)

            # Update checkpoint after each level
            for task in tasks:
                if level_results[task.id].success:
                    checkpoint.completed_tasks.append(task.id)
                    checkpoint.task_outputs[task.id] = level_results[task.id].output

            checkpoint.checkpoint_id = f"{config.name}-{uuid.uuid4().hex[:8]}"
            self.checkpoint_manager.save(checkpoint)

        return results

    async def replay_task(
        self,
        task_id: str,
        config: WorkflowConfig,
        agents: dict[str, BaseAgent],
        task_outputs: dict[str, str] | None = None,
    ) -> AgentResult:
        """Replay a single task by ID.

        Args:
            task_id: The task identifier to replay.
            config: The full workflow configuration.
            agents: Map of agent name to agent instance.
            task_outputs: Optional map of prior task outputs for variable
                resolution.

        Returns:
            The AgentResult of the replayed task.

        Raises:
            ValueError: If the task ID is not found in the workflow.
        """
        task_map = {t.id: t for t in config.tasks}
        if task_id not in task_map:
            raise ValueError(f"Task '{task_id}' not found in workflow")

        executor = TaskExecutor(
            agents=agents,
            agent_configs=config.agents,
            strategy=config.strategy,
        )
        if task_outputs:
            executor.task_outputs = task_outputs

        return await executor.execute_task(task_map[task_id])
