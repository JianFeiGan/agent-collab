"""Async task executor that dispatches work to agent adapters."""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
import uuid
from dataclasses import dataclass, field

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.checkpoint import Checkpoint, CheckpointManager
from agent_collab.core.degradation import DegradationHandler, DegradationPolicy, TaskDegradation
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig, WorkflowParser
from agent_collab.locks.file_lock import FileLockManager

try:
    from agent_collab.observability.token_tracker import TokenTracker
except ImportError:  # pragma: no cover
    TokenTracker = None  # type: ignore[assignment,misc]

try:
    from agent_collab.storage.history import ExecutionHistory
except ImportError:  # pragma: no cover
    ExecutionHistory = None  # type: ignore[assignment,misc]


@dataclass
class ExecutionResult:
    """Aggregated result of running a full workflow."""

    task_results: dict[str, AgentResult] = field(default_factory=dict)
    failed_tasks: list[str] = field(default_factory=list)


class TaskExecutor:
    """Executes workflow tasks using the appropriate agent adapters.

    Supports exponential backoff retries, degradation policies,
    checkpoint persistence, optional token tracking and SQLite
    execution history persistence.
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        agent_configs: dict[str, AgentConfig],
        strategy: StrategyConfig,
        lock_manager: FileLockManager | None = None,
        variables: dict[str, str] | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        workflow_name: str = "",
    ) -> None:
        self.agents = agents
        self.agent_configs = agent_configs
        self.strategy = strategy
        self.lock_manager = lock_manager or FileLockManager()
        self.variables = variables or {}
        self.execution_log: list[dict[str, object]] = []
        self.task_outputs: dict[str, str] = {}
        self.checkpoint_manager = checkpoint_manager
        self.workflow_name = workflow_name
        self.degradation_handler = DegradationHandler()
        self._execution_id: int | None = None

    async def execute_task(self, task: TaskConfig) -> AgentResult:
        """Execute a single task with retry logic and degradation support."""
        agent_cfg = self.agent_configs[task.agent]
        agent = self.agents[task.agent]

        # Resolve variables in prompt: workflow variables + os.environ
        merged: dict[str, str] = {**os.environ, **self.variables}
        resolved_prompt = WorkflowParser.resolve_variables(task.prompt, merged)
        # Resolve ${task_id.output} references from upstream tasks
        resolved_prompt = WorkflowParser.resolve_task_outputs(
            resolved_prompt, self.task_outputs
        )

        # Acquire locks for output files
        locked: list[str] = []
        for output in task.outputs:
            if self.lock_manager.acquire(output, task.id):
                locked.append(output)
            else:
                # Release already-held locks and fail
                for f in locked:
                    self.lock_manager.release(f)
                return AgentResult(
                    success=False,
                    output=f"Could not acquire lock for {output}",
                )

        try:
            start = time.monotonic()
            result = await self._run_with_retries(
                agent=agent,
                prompt=resolved_prompt,
                workdir=agent_cfg.workdir,
                allowed_tools=agent_cfg.allowed_tools,
                timeout=self.strategy.timeout_per_task,
                task=task,
            )
            duration = time.monotonic() - start
            # Store output for downstream task resolution
            if result.success:
                self.task_outputs[task.id] = result.output

            self.execution_log.append({
                "task_id": task.id,
                "agent": task.agent,
                "status": "success" if result.success else "failed",
                "duration": round(duration, 3),
                "output_summary": result.output[:200] if result.output else "",
            })

            # Apply degradation policy on failure
            if not result.success and task.degradation is not None:
                result = self._apply_degradation(task, result)

            # Auto-save checkpoint after successful task
            if result.success and self.strategy.checkpoint_enabled and self.checkpoint_manager:
                self._save_checkpoint()

            return result
        finally:
            for f in locked:
                self.lock_manager.release(f)

    async def _run_with_retries(
        self,
        agent: BaseAgent,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int,
        task: TaskConfig | None = None,
    ) -> AgentResult:
        """Run an agent with exponential backoff retry logic.

        Uses exponential backoff with jitter: ``base_delay * (2 ** attempt)``
        capped at 60 seconds, with a random jitter of ±25%.
        """
        max_attempts = 1 + (self.strategy.max_retries if self.strategy.retry_on_failure else 0)
        last_result: AgentResult | None = None
        base_delay = self.strategy.retry_delay

        for attempt in range(max_attempts):
            result = await agent.execute(
                prompt=prompt,
                workdir=workdir,
                allowed_tools=allowed_tools,
                timeout=timeout,
            )
            if result.success:
                return result
            last_result = result

            # Wait with exponential backoff + jitter before next retry
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2 ** attempt), 60.0)
                jitter = delay * 0.25
                delay = delay + random.uniform(-jitter, jitter)
                delay = max(0.1, delay)  # Ensure positive delay
                await asyncio.sleep(delay)

        return last_result  # type: ignore[return-value]

    def _apply_degradation(
        self, task: TaskConfig, result: AgentResult
    ) -> AgentResult:
        """Apply degradation policy after a task failure.

        Args:
            task: The failed task configuration.
            result: The failure result.

        Returns:
            The original result, or a modified result based on the policy.
        """
        degradation = task.degradation
        if degradation is None:
            return result

        self.degradation_handler.record_failure(task.id)
        policy = self.degradation_handler.get_policy(task.id, degradation)

        if policy == DegradationPolicy.SKIP:
            return AgentResult(
                success=True,
                output=f"[degraded:skipped] Original error: {result.output}",
            )

        if policy == DegradationPolicy.ABORT:
            return result

        # CONTINUE — mark as continued despite failure
        return AgentResult(
            success=False,
            output=f"[degraded:continued] {result.output}",
        )

    async def execute_level(self, tasks: list[TaskConfig]) -> dict[str, AgentResult]:
        """Execute a group of independent tasks in parallel."""
        semaphore = asyncio.Semaphore(self.strategy.max_parallel)

        async def _run(task: TaskConfig) -> tuple[str, AgentResult]:
            async with semaphore:
                result = await self.execute_task(task)
                return task.id, result

        results = await asyncio.gather(*(_run(t) for t in tasks))
        return dict(results)

    def get_execution_log(self) -> list[dict[str, object]]:
        """Return the full execution log recorded so far."""
        return list(self.execution_log)

    def export_log(self, path: str) -> None:
        """Export the execution log to a JSON file.

        Args:
            path: Filesystem path where the JSON file will be written.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.execution_log, f, indent=2, ensure_ascii=False)

    def _save_checkpoint(self) -> str:
        """Save a checkpoint of the current execution state.

        Returns:
            The checkpoint ID.
        """
        if self.checkpoint_manager is None:
            return ""
        checkpoint_id = f"{self.workflow_name}-{uuid.uuid4().hex[:8]}"
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            workflow_name=self.workflow_name,
            completed_tasks=list(self.task_outputs.keys()),
            task_outputs=dict(self.task_outputs),
        )
        return self.checkpoint_manager.save(checkpoint)
