"""Performance tests for AgentCollab workflow execution."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.scheduler import TaskScheduler
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig


class FastAgent(BaseAgent):
    """Fast agent for performance testing."""

    def __init__(self, name: str = "fast", delay: float = 0.01) -> None:
        super().__init__()
        self._name = name
        self._delay = delay

    async def execute(self, prompt, workdir, allowed_tools, timeout=600):
        await asyncio.sleep(self._delay)
        return AgentResult(success=True, output=f"Executed: {prompt}")

    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def get_cli_version(self) -> str | None:
        return "1.0.0"

    def get_supported_arguments(self) -> list[str]:
        return []

    def check_api_key(self) -> tuple[bool, str]:
        return True, "Mock API key"


@dataclass
class PerformanceResult:
    """Performance test result."""

    total_tasks: int
    total_duration: float
    tasks_per_second: float
    average_task_duration: float
    max_concurrency: int


@pytest.mark.asyncio
async def test_parallel_execution_performance():
    """Test performance of parallel task execution."""
    agent = FastAgent(delay=0.01)
    agents = {"fast": agent}
    agent_configs = {
        "fast": AgentConfig(
            type="fast",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }

    # Test with different concurrency levels
    concurrency_levels = [1, 2, 4, 8]
    results: list[PerformanceResult] = []

    for max_parallel in concurrency_levels:
        strategy = StrategyConfig(max_parallel=max_parallel)
        executor = TaskExecutor(
            agents=agents,
            agent_configs=agent_configs,
            strategy=strategy,
        )

        # Create 20 tasks
        tasks = [
            TaskConfig(id=f"task-{i}", agent="fast", prompt=f"Task {i}")
            for i in range(20)
        ]

        start_time = time.monotonic()
        await executor.execute_level(tasks)
        duration = time.monotonic() - start_time

        result = PerformanceResult(
            total_tasks=20,
            total_duration=duration,
            tasks_per_second=20 / duration,
            average_task_duration=duration / 20,
            max_concurrency=max_parallel,
        )
        results.append(result)

    # Verify that higher concurrency leads to better performance
    assert results[1].total_duration < results[0].total_duration
    assert results[2].total_duration < results[1].total_duration
    assert results[3].total_duration < results[2].total_duration


@pytest.mark.asyncio
async def test_scheduler_performance():
    """Test scheduler performance with large task graphs."""
    # Create a large task graph
    tasks = []
    for i in range(100):
        depends_on = [f"task-{i-1}"] if i > 0 else []
        tasks.append(
            TaskConfig(
                id=f"task-{i}",
                agent="fast",
                prompt=f"Task {i}",
                depends_on=depends_on,
            )
        )

    start_time = time.monotonic()
    scheduler = TaskScheduler(tasks)
    levels = scheduler.get_execution_order()
    duration = time.monotonic() - start_time

    assert len(levels) == 100  # Each level has one task
    assert duration < 1.0  # Should complete in less than 1 second


@pytest.mark.asyncio
async def test_large_workflow_execution():
    """Test executing a large workflow."""
    agent = FastAgent(delay=0.001)
    agents = {"fast": agent}
    agent_configs = {
        "fast": AgentConfig(
            type="fast",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=10)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    # Create 50 tasks
    tasks = [
        TaskConfig(id=f"task-{i}", agent="fast", prompt=f"Task {i}")
        for i in range(50)
    ]

    start_time = time.monotonic()
    results = await executor.execute_level(tasks)
    duration = time.monotonic() - start_time

    assert len(results) == 50
    assert all(r.success for r in results.values())
    assert duration < 5.0  # Should complete in less than 5 seconds


@pytest.mark.asyncio
async def test_memory_usage():
    """Test memory usage with large task lists."""
    import sys

    # Create a large number of tasks
    tasks = [
        TaskConfig(id=f"task-{i}", agent="fast", prompt=f"Task {i}")
        for i in range(1000)
    ]

    scheduler = TaskScheduler(tasks)

    # Get initial memory usage
    initial_size = sys.getsizeof(scheduler)

    # Execute the scheduler
    levels = scheduler.get_execution_order()

    # Get final memory usage
    final_size = sys.getsizeof(scheduler)

    # Memory usage should be reasonable
    assert initial_size < 1024 * 1024  # Less than 1MB
    assert final_size < 1024 * 1024  # Less than 1MB


@pytest.mark.asyncio
async def test_log_manager_performance():
    """Test LogManager performance with many entries."""
    from agent_collab.storage.log_manager import LogManager

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        log_manager = LogManager(log_dir=tmpdir)

        # Add many entries
        start_time = time.monotonic()
        for i in range(1000):
            log_manager.add_from_dict({
                "task_id": f"task-{i}",
                "agent": "fast",
                "status": "success",
                "duration": 0.1,
                "output_summary": f"Task {i} completed",
                "timestamp": time.time(),
            })
        add_duration = time.monotonic() - start_time

        # Get statistics
        start_time = time.monotonic()
        stats = log_manager.get_statistics()
        stats_duration = time.monotonic() - start_time

        # Save session
        start_time = time.monotonic()
        log_path = log_manager.save_session("performance-test.json")
        save_duration = time.monotonic() - start_time

        # Load session
        start_time = time.monotonic()
        entries = log_manager.load_session("performance-test.json")
        load_duration = time.monotonic() - start_time

        # Verify performance
        assert add_duration < 1.0  # Adding 1000 entries should take less than 1 second
        assert stats_duration < 0.1  # Getting statistics should be fast
        assert save_duration < 1.0  # Saving should take less than 1 second
        assert load_duration < 1.0  # Loading should take less than 1 second

        # Verify data
        assert len(entries) == 1000
        assert stats["total_tasks"] == 1000


@pytest.mark.asyncio
async def test_cancellation_performance():
    """Test that cancellation is fast."""
    agent = FastAgent(delay=1.0)  # Slow agent
    agents = {"fast": agent}
    agent_configs = {
        "fast": AgentConfig(
            type="fast",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=10)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    # Create many tasks
    tasks = [
        TaskConfig(id=f"task-{i}", agent="fast", prompt=f"Task {i}")
        for i in range(100)
    ]

    # Start execution
    async def run_workflow():
        return await executor.execute_level(tasks)

    # Cancel after a short delay
    async def cancel_after_delay():
        await asyncio.sleep(0.1)
        start_time = time.monotonic()
        executor.cancel_all()
        cancel_duration = time.monotonic() - start_time
        return cancel_duration

    # Run both concurrently
    results, cancel_duration = await asyncio.gather(
        run_workflow(),
        cancel_after_delay(),
    )

    # Cancellation should be fast
    assert cancel_duration < 0.1  # Should cancel in less than 100ms
    assert executor.is_cancelled()


@pytest.mark.asyncio
async def test_concurrent_executor_creation():
    """Test creating multiple executors concurrently."""
    agent = FastAgent(delay=0.01)
    agents = {"fast": agent}
    agent_configs = {
        "fast": AgentConfig(
            type="fast",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=2)

    async def create_and_run(executor_id: int):
        executor = TaskExecutor(
            agents=agents,
            agent_configs=agent_configs,
            strategy=strategy,
        )
        tasks = [
            TaskConfig(id=f"task-{executor_id}-{i}", agent="fast", prompt=f"Task {i}")
            for i in range(5)
        ]
        results = await executor.execute_level(tasks)
        return len(results)

    # Create multiple executors concurrently
    start_time = time.monotonic()
    results = await asyncio.gather(*[create_and_run(i) for i in range(10)])
    duration = time.monotonic() - start_time

    # All executors should complete
    assert all(r == 5 for r in results)
    assert duration < 5.0  # Should complete in less than 5 seconds


@pytest.mark.asyncio
async def test_statistics_performance():
    """Test statistics calculation performance."""
    from agent_collab.core.scheduler import TaskScheduler

    # Create scheduler with many tasks
    tasks = [
        TaskConfig(id=f"task-{i}", agent="fast", prompt=f"Task {i}")
        for i in range(100)
    ]

    scheduler = TaskScheduler(tasks)

    # Record many executions
    start_time = time.monotonic()
    for i in range(1000):
        scheduler.record_task_execution(f"task-{i % 100}", 0.1, i % 2 == 0)
    record_duration = time.monotonic() - start_time

    # Get statistics
    start_time = time.monotonic()
    stats = scheduler.get_task_statistics()
    stats_duration = time.monotonic() - start_time

    # Verify performance
    assert record_duration < 1.0  # Recording should be fast
    assert stats_duration < 0.1  # Getting statistics should be fast

    # Verify data
    assert len(stats) == 100
