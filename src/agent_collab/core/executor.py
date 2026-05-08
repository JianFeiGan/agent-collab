"""Async task executor that dispatches work to agent adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig
from agent_collab.locks.file_lock import FileLockManager


@dataclass
class ExecutionResult:
    """Aggregated result of running a full workflow."""

    task_results: dict[str, AgentResult] = field(default_factory=dict)
    failed_tasks: list[str] = field(default_factory=list)


class TaskExecutor:
    """Executes workflow tasks using the appropriate agent adapters."""

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        agent_configs: dict[str, AgentConfig],
        strategy: StrategyConfig,
        lock_manager: FileLockManager | None = None,
    ) -> None:
        self.agents = agents
        self.agent_configs = agent_configs
        self.strategy = strategy
        self.lock_manager = lock_manager or FileLockManager()

    async def execute_task(self, task: TaskConfig) -> AgentResult:
        """Execute a single task with retry logic."""
        agent_cfg = self.agent_configs[task.agent]
        agent = self.agents[task.agent]

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
            result = await self._run_with_retries(
                agent=agent,
                prompt=task.prompt,
                workdir=agent_cfg.workdir,
                allowed_tools=agent_cfg.allowed_tools,
                timeout=self.strategy.timeout_per_task,
            )
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
    ) -> AgentResult:
        max_attempts = 1 + (self.strategy.max_retries if self.strategy.retry_on_failure else 0)
        last_result: AgentResult | None = None

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

        return last_result  # type: ignore[return-value]

    async def execute_level(self, tasks: list[TaskConfig]) -> dict[str, AgentResult]:
        """Execute a group of independent tasks in parallel."""
        semaphore = asyncio.Semaphore(self.strategy.max_parallel)

        async def _run(task: TaskConfig) -> tuple[str, AgentResult]:
            async with semaphore:
                result = await self.execute_task(task)
                return task.id, result

        results = await asyncio.gather(*(_run(t) for t in tasks))
        return dict(results)
