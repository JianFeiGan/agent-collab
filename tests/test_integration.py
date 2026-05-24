"""Integration tests for AgentCollab workflow execution."""

from __future__ import annotations

import asyncio
import tempfile

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.scheduler import TaskScheduler
from agent_collab.core.workflow import AgentConfig, StrategyConfig, TaskConfig, WorkflowParser


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    def __init__(self, name: str = "mock", delay: float = 0.1) -> None:
        super().__init__()
        self._name = name
        self._delay = delay
        self.executed_prompts: list[str] = []

    async def execute(self, prompt, workdir, allowed_tools, timeout=600):
        self.executed_prompts.append(prompt)
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


class FailingAgent(BaseAgent):
    """Agent that always fails."""

    def __init__(self, name: str = "failing") -> None:
        super().__init__()
        self._name = name

    async def execute(self, prompt, workdir, allowed_tools, timeout=600):
        return AgentResult(success=False, output="Agent failed")

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


@pytest.mark.asyncio
async def test_simple_workflow_execution():
    """Test executing a simple workflow with one task."""
    agent = MockAgent()
    agents = {"mock": agent}
    agent_configs = {
        "mock": AgentConfig(
            type="mock",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=1)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    tasks = [
        TaskConfig(
            id="task-1",
            agent="mock",
            prompt="Test prompt",
        )
    ]

    results = await executor.execute_level(tasks)
    assert len(results) == 1
    assert results["task-1"].success
    assert "Executed: Test prompt" in results["task-1"].output


@pytest.mark.asyncio
async def test_parallel_workflow_execution():
    """Test executing multiple tasks in parallel."""
    agent = MockAgent(delay=0.1)
    agents = {"mock": agent}
    agent_configs = {
        "mock": AgentConfig(
            type="mock",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=2)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    tasks = [
        TaskConfig(id="task-1", agent="mock", prompt="Task 1"),
        TaskConfig(id="task-2", agent="mock", prompt="Task 2"),
        TaskConfig(id="task-3", agent="mock", prompt="Task 3"),
    ]

    results = await executor.execute_level(tasks)
    assert len(results) == 3
    assert all(r.success for r in results.values())


@pytest.mark.asyncio
async def test_task_cancellation():
    """Test that tasks can be cancelled."""
    agent = MockAgent(delay=1.0)
    agents = {"mock": agent}
    agent_configs = {
        "mock": AgentConfig(
            type="mock",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=1)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    tasks = [
        TaskConfig(id="task-1", agent="mock", prompt="Task 1"),
        TaskConfig(id="task-2", agent="mock", prompt="Task 2"),
    ]

    # Start execution in background
    async def run_workflow():
        return await executor.execute_level(tasks)

    # Cancel after a short delay
    async def cancel_after_delay():
        await asyncio.sleep(0.2)
        executor.cancel_all()

    # Run both concurrently
    results, _ = await asyncio.gather(
        run_workflow(),
        cancel_after_delay(),
        return_exceptions=True,
    )

    # Check that cancellation was handled
    assert executor.is_cancelled()


@pytest.mark.asyncio
async def test_task_with_degradation():
    """Test task execution with degradation policy."""
    agent = FailingAgent()
    agents = {"failing": agent}
    agent_configs = {
        "failing": AgentConfig(
            type="failing",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=1)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    tasks = [
        TaskConfig(
            id="task-1",
            agent="failing",
            prompt="Test prompt",
            degradation={"policy": "skip"},
        )
    ]

    results = await executor.execute_level(tasks)
    assert len(results) == 1
    # With skip degradation, the task should be marked as successful
    assert results["task-1"].success
    assert "[degraded:skipped]" in results["task-1"].output


@pytest.mark.asyncio
async def test_execution_log_persistence():
    """Test that execution logs are persisted."""
    agent = MockAgent()
    agents = {"mock": agent}
    agent_configs = {
        "mock": AgentConfig(
            type="mock",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=1)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    tasks = [
        TaskConfig(id="task-1", agent="mock", prompt="Test prompt"),
    ]

    await executor.execute_level(tasks)

    # Check that execution log was recorded
    log = executor.get_execution_log()
    assert len(log) == 1
    assert log[0]["task_id"] == "task-1"
    assert log[0]["status"] == "success"
    assert "duration" in log[0]
    assert "timestamp" in log[0]


@pytest.mark.asyncio
async def test_scheduler_statistics():
    """Test scheduler statistics recording."""
    tasks = [
        TaskConfig(id="task-1", agent="mock", prompt="Task 1"),
        TaskConfig(id="task-2", agent="mock", prompt="Task 2", depends_on=["task-1"]),
    ]

    scheduler = TaskScheduler(tasks)

    # Record some executions
    scheduler.record_task_execution("task-1", 1.5, True)
    scheduler.record_task_execution("task-1", 2.0, True)
    scheduler.record_task_execution("task-2", 0.5, False)

    # Get statistics
    stats = scheduler.get_task_statistics("task-1")
    assert stats["total_executions"] == 2
    assert stats["successful_executions"] == 2
    assert stats["failed_executions"] == 0
    assert stats["average_duration"] == 1.75

    stats = scheduler.get_task_statistics("task-2")
    assert stats["total_executions"] == 1
    assert stats["successful_executions"] == 0
    assert stats["failed_executions"] == 1

    # Get execution history
    history = scheduler.get_execution_history()
    assert len(history) == 3


@pytest.mark.asyncio
async def test_workflow_with_variables():
    """Test workflow execution with variable substitution."""
    agent = MockAgent()
    agents = {"mock": agent}
    agent_configs = {
        "mock": AgentConfig(
            type="mock",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=1)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
        variables={"project_name": "TestProject"},
    )

    tasks = [
        TaskConfig(
            id="task-1",
            agent="mock",
            prompt="Work on ${project_name}",
        )
    ]

    results = await executor.execute_level(tasks)
    assert len(results) == 1
    assert results["task-1"].success
    assert "Work on TestProject" in agent.executed_prompts[0]


@pytest.mark.asyncio
async def test_workflow_with_task_output_reference():
    """Test workflow with task output references."""
    agent = MockAgent()
    agents = {"mock": agent}
    agent_configs = {
        "mock": AgentConfig(
            type="mock",
            workdir=".",
            allowed_tools=["Read", "Write"],
        )
    }
    strategy = StrategyConfig(max_parallel=1)
    executor = TaskExecutor(
        agents=agents,
        agent_configs=agent_configs,
        strategy=strategy,
    )

    # Pre-populate task outputs
    executor.task_outputs["task-1"] = "output-from-task-1"

    tasks = [
        TaskConfig(
            id="task-2",
            agent="mock",
            prompt="Use output: ${task-1.output}",
        )
    ]

    results = await executor.execute_level(tasks)
    assert len(results) == 1
    assert results["task-2"].success
    # Note: The output reference is resolved by WorkflowParser
    # The mock agent receives the resolved prompt
    assert len(agent.executed_prompts) == 1


def test_workflow_parsing():
    """Test parsing a workflow YAML file."""
    yaml_content = """
name: test-workflow
agents:
  coder:
    type: mock
    workdir: .
    allowed_tools: [Read, Write]

tasks:
  - id: task-1
    agent: coder
    prompt: "First task"
  - id: task-2
    agent: coder
    prompt: "Second task"
    depends_on: [task-1]
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = WorkflowParser.parse(f.name)

    assert config.name == "test-workflow"
    assert len(config.agents) == 1
    assert len(config.tasks) == 2
    assert config.tasks[1].depends_on == ["task-1"]


def test_scheduler_execution_order():
    """Test scheduler produces correct execution order."""
    tasks = [
        TaskConfig(id="task-1", agent="mock", prompt="Task 1"),
        TaskConfig(id="task-2", agent="mock", prompt="Task 2", depends_on=["task-1"]),
        TaskConfig(id="task-3", agent="mock", prompt="Task 3", depends_on=["task-1"]),
        TaskConfig(id="task-4", agent="mock", prompt="Task 4", depends_on=["task-2", "task-3"]),
    ]

    scheduler = TaskScheduler(tasks)
    levels = scheduler.get_execution_order()

    assert len(levels) == 3
    assert levels[0] == ["task-1"]
    assert set(levels[1]) == {"task-2", "task-3"}
    assert levels[2] == ["task-4"]


def test_scheduler_cycle_detection():
    """Test scheduler detects dependency cycles."""
    tasks = [
        TaskConfig(id="task-1", agent="mock", prompt="Task 1", depends_on=["task-2"]),
        TaskConfig(id="task-2", agent="mock", prompt="Task 2", depends_on=["task-1"]),
    ]

    scheduler = TaskScheduler(tasks)
    cycle = scheduler.detect_cycles()

    assert cycle is not None
    assert len(cycle) >= 2


@pytest.mark.asyncio
async def test_log_manager_persistence():
    """Test LogManager persistence."""
    from agent_collab.storage.log_manager import LogManager

    with tempfile.TemporaryDirectory() as tmpdir:
        log_manager = LogManager(log_dir=tmpdir)

        # Add some entries
        log_manager.add_from_dict(
            {
                "task_id": "task-1",
                "agent": "mock",
                "status": "success",
                "duration": 1.5,
                "output_summary": "Task completed",
                "timestamp": 1234567890.0,
            }
        )

        log_manager.add_from_dict(
            {
                "task_id": "task-2",
                "agent": "mock",
                "status": "failed",
                "duration": 0.5,
                "output_summary": "Task failed",
                "timestamp": 1234567891.0,
            }
        )

        # Save session
        log_path = log_manager.save_session("test-session.json")
        assert log_path.exists()

        # Load session
        entries = log_manager.load_session("test-session.json")
        assert len(entries) == 2
        assert entries[0].task_id == "task-1"
        assert entries[1].task_id == "task-2"

        # Get statistics
        stats = log_manager.get_statistics()
        assert stats["total_tasks"] == 2
        assert stats["successful_tasks"] == 1
        assert stats["failed_tasks"] == 1
        assert stats["total_duration"] == 2.0
