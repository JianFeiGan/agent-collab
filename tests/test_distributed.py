"""Tests for distributed execution engine."""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone

from agent_collab.distributed import (
    DistributedTask,
    LoadBalancingStrategy,
    TaskResult,
    TaskStatus,
    WorkerInfo,
    WorkerStatus,
)
from agent_collab.distributed.queue import (
    InMemoryTaskQueue,
    InMemoryWorkerManager,
    LoadBalancer,
)


class TestDistributedTask:
    """Tests for DistributedTask."""

    def test_default_values(self):
        task = DistributedTask()
        assert task.id is not None
        assert task.workflow_id == ""
        assert task.task_id == ""
        assert task.agent_type == ""
        assert task.prompt == ""
        assert task.workdir == "."
        assert task.allowed_tools == []
        assert task.priority == 0
        assert task.timeout == 600
        assert task.max_retries == 3
        assert task.retry_count == 0
        assert task.status == TaskStatus.PENDING
        assert task.assigned_worker is None
        assert task.result is None
        assert task.error is None

    def test_custom_values(self):
        task = DistributedTask(
            workflow_id="wf_1",
            task_id="task_1",
            agent_type="claude-code",
            prompt="Implement feature",
            workdir="/app",
            allowed_tools=["Read", "Write"],
            priority=10,
            timeout=300,
            max_retries=5,
        )
        assert task.workflow_id == "wf_1"
        assert task.task_id == "task_1"
        assert task.agent_type == "claude-code"
        assert task.prompt == "Implement feature"
        assert task.workdir == "/app"
        assert task.allowed_tools == ["Read", "Write"]
        assert task.priority == 10
        assert task.timeout == 300
        assert task.max_retries == 5


class TestTaskResult:
    """Tests for TaskResult."""

    def test_default_values(self):
        result = TaskResult(task_id="task_1", success=True)
        assert result.task_id == "task_1"
        assert result.success is True
        assert result.output == ""
        assert result.error is None
        assert result.duration_seconds == 0.0
        assert result.worker_id == ""

    def test_custom_values(self):
        result = TaskResult(
            task_id="task_1",
            success=True,
            output="Feature implemented",
            duration_seconds=5.0,
            worker_id="worker_1",
        )
        assert result.output == "Feature implemented"
        assert result.duration_seconds == 5.0
        assert result.worker_id == "worker_1"


class TestWorkerInfo:
    """Tests for WorkerInfo."""

    def test_default_values(self):
        worker = WorkerInfo()
        assert worker.id is not None
        assert worker.name == ""
        assert worker.host == ""
        assert worker.port == 0
        assert worker.status == WorkerStatus.IDLE
        assert worker.current_tasks == 0
        assert worker.max_tasks == 10
        assert worker.weight == 1
        assert worker.capabilities == []

    def test_custom_values(self):
        worker = WorkerInfo(
            name="worker-1",
            host="localhost",
            port=8000,
            max_tasks=20,
            weight=2,
            capabilities=["python", "node"],
        )
        assert worker.name == "worker-1"
        assert worker.host == "localhost"
        assert worker.port == 8000
        assert worker.max_tasks == 20
        assert worker.weight == 2
        assert worker.capabilities == ["python", "node"]


class TestInMemoryTaskQueue:
    """Tests for InMemoryTaskQueue."""

    @pytest.fixture
    def queue(self):
        return InMemoryTaskQueue()

    async def test_enqueue(self, queue):
        task = DistributedTask(id="task_1", priority=5)
        result = await queue.enqueue(task)
        assert result is True
        assert task.status == TaskStatus.QUEUED

    async def test_dequeue(self, queue):
        task = DistributedTask(id="task_1", priority=5)
        await queue.enqueue(task)

        dequeued = await queue.dequeue("worker_1")
        assert dequeued is not None
        assert dequeued.id == "task_1"
        assert dequeued.status == TaskStatus.RUNNING
        assert dequeued.assigned_worker == "worker_1"

    async def test_dequeue_priority(self, queue):
        task1 = DistributedTask(id="task_1", priority=1)
        task2 = DistributedTask(id="task_2", priority=10)
        task3 = DistributedTask(id="task_3", priority=5)

        await queue.enqueue(task1)
        await queue.enqueue(task2)
        await queue.enqueue(task3)

        # Should dequeue highest priority first
        dequeued = await queue.dequeue("worker_1")
        assert dequeued.id == "task_2"

        dequeued = await queue.dequeue("worker_1")
        assert dequeued.id == "task_3"

        dequeued = await queue.dequeue("worker_1")
        assert dequeued.id == "task_1"

    async def test_complete(self, queue):
        task = DistributedTask(id="task_1")
        await queue.enqueue(task)
        await queue.dequeue("worker_1")

        result = TaskResult(task_id="task_1", success=True, output="Done")
        success = await queue.complete("task_1", result)
        assert success is True

        task = await queue.get_task("task_1")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == result

    async def test_fail(self, queue):
        task = DistributedTask(id="task_1")
        await queue.enqueue(task)
        await queue.dequeue("worker_1")

        success = await queue.fail("task_1", "Error occurred")
        assert success is True

        task = await queue.get_task("task_1")
        assert task.status == TaskStatus.FAILED
        assert task.error == "Error occurred"

    async def test_get_pending_tasks(self, queue):
        task1 = DistributedTask(id="task_1")
        task2 = DistributedTask(id="task_2")
        await queue.enqueue(task1)
        await queue.enqueue(task2)

        pending = await queue.get_pending_tasks()
        assert len(pending) == 2

    async def test_get_queue_size(self, queue):
        task1 = DistributedTask(id="task_1")
        task2 = DistributedTask(id="task_2")
        await queue.enqueue(task1)
        await queue.enqueue(task2)

        size = await queue.get_queue_size()
        assert size == 2

    async def test_retry_task(self, queue):
        task = DistributedTask(id="task_1", max_retries=3)
        await queue.enqueue(task)
        await queue.dequeue("worker_1")
        await queue.fail("task_1", "Error")

        success = await queue.retry_task("task_1")
        assert success is True

        task = await queue.get_task("task_1")
        assert task.status == TaskStatus.QUEUED
        assert task.retry_count == 1

    async def test_retry_task_max_retries(self, queue):
        task = DistributedTask(id="task_1", max_retries=1, retry_count=1)
        await queue.enqueue(task)
        await queue.dequeue("worker_1")
        await queue.fail("task_1", "Error")

        success = await queue.retry_task("task_1")
        assert success is False

    async def test_cancel_task(self, queue):
        task = DistributedTask(id="task_1")
        await queue.enqueue(task)

        success = await queue.cancel_task("task_1")
        assert success is True

        task = await queue.get_task("task_1")
        assert task.status == TaskStatus.CANCELLED


class TestInMemoryWorkerManager:
    """Tests for InMemoryWorkerManager."""

    @pytest.fixture
    def manager(self):
        return InMemoryWorkerManager()

    async def test_register_worker(self, manager):
        worker = WorkerInfo(id="worker_1", name="Worker 1")
        result = await manager.register_worker(worker)
        assert result is True

        retrieved = await manager.get_worker("worker_1")
        assert retrieved is not None
        assert retrieved.name == "Worker 1"

    async def test_unregister_worker(self, manager):
        worker = WorkerInfo(id="worker_1", name="Worker 1")
        await manager.register_worker(worker)

        result = await manager.unregister_worker("worker_1")
        assert result is True

        retrieved = await manager.get_worker("worker_1")
        assert retrieved is None

    async def test_heartbeat(self, manager):
        worker = WorkerInfo(id="worker_1", name="Worker 1")
        await manager.register_worker(worker)

        result = await manager.heartbeat("worker_1")
        assert result is True

        retrieved = await manager.get_worker("worker_1")
        assert retrieved is not None
        assert retrieved.last_heartbeat is not None

    async def test_get_available_workers(self, manager):
        worker1 = WorkerInfo(id="worker_1", name="Worker 1", status=WorkerStatus.IDLE)
        worker2 = WorkerInfo(id="worker_2", name="Worker 2", status=WorkerStatus.BUSY)
        worker3 = WorkerInfo(id="worker_3", name="Worker 3", status=WorkerStatus.OFFLINE)

        await manager.register_worker(worker1)
        await manager.register_worker(worker2)
        await manager.register_worker(worker3)

        available = await manager.get_available_workers()
        assert len(available) == 2  # worker1 and worker2 (busy but has capacity)

    async def test_update_worker_status(self, manager):
        worker = WorkerInfo(id="worker_1", name="Worker 1")
        await manager.register_worker(worker)

        result = await manager.update_worker_status("worker_1", WorkerStatus.BUSY)
        assert result is True

        retrieved = await manager.get_worker("worker_1")
        assert retrieved.status == WorkerStatus.BUSY

    async def test_increment_task_count(self, manager):
        worker = WorkerInfo(id="worker_1", name="Worker 1", max_tasks=2)
        await manager.register_worker(worker)

        await manager.increment_task_count("worker_1")
        worker = await manager.get_worker("worker_1")
        assert worker.current_tasks == 1

        await manager.increment_task_count("worker_1")
        worker = await manager.get_worker("worker_1")
        assert worker.current_tasks == 2
        assert worker.status == WorkerStatus.BUSY

    async def test_decrement_task_count(self, manager):
        worker = WorkerInfo(id="worker_1", name="Worker 1", max_tasks=2, current_tasks=2)
        await manager.register_worker(worker)

        await manager.decrement_task_count("worker_1")
        worker = await manager.get_worker("worker_1")
        assert worker.current_tasks == 1
        assert worker.status == WorkerStatus.IDLE


class TestLoadBalancer:
    """Tests for LoadBalancer."""

    @pytest.fixture
    def manager(self):
        return InMemoryWorkerManager()

    @pytest.fixture
    def balancer(self, manager):
        return LoadBalancer(manager, LoadBalancingStrategy.ROUND_ROBIN)

    async def test_select_worker_round_robin(self, manager, balancer):
        worker1 = WorkerInfo(id="worker_1", name="Worker 1")
        worker2 = WorkerInfo(id="worker_2", name="Worker 2")
        await manager.register_worker(worker1)
        await manager.register_worker(worker2)

        task = DistributedTask(id="task_1")

        selected1 = await balancer.select_worker(task)
        selected2 = await balancer.select_worker(task)
        selected3 = await balancer.select_worker(task)

        assert selected1.id == "worker_1"
        assert selected2.id == "worker_2"
        assert selected3.id == "worker_1"  # Round robin

    async def test_select_worker_least_connections(self, manager):
        balancer = LoadBalancer(manager, LoadBalancingStrategy.LEAST_CONNECTIONS)

        worker1 = WorkerInfo(id="worker_1", name="Worker 1", current_tasks=3)
        worker2 = WorkerInfo(id="worker_2", name="Worker 2", current_tasks=1)
        await manager.register_worker(worker1)
        await manager.register_worker(worker2)

        task = DistributedTask(id="task_1")
        selected = await balancer.select_worker(task)
        assert selected.id == "worker_2"

    async def test_select_worker_weighted(self, manager):
        balancer = LoadBalancer(manager, LoadBalancingStrategy.WEIGHTED)

        worker1 = WorkerInfo(id="worker_1", name="Worker 1", weight=1)
        worker2 = WorkerInfo(id="worker_2", name="Worker 2", weight=3)
        await manager.register_worker(worker1)
        await manager.register_worker(worker2)

        task = DistributedTask(id="task_1")

        # Run multiple times to test weighted distribution
        selections = []
        for _ in range(100):
            selected = await balancer.select_worker(task)
            selections.append(selected.id)

        # Worker 2 should be selected more often due to higher weight
        assert selections.count("worker_2") > selections.count("worker_1")

    async def test_select_worker_with_capabilities(self, manager, balancer):
        worker1 = WorkerInfo(id="worker_1", name="Worker 1", capabilities=["python"])
        worker2 = WorkerInfo(id="worker_2", name="Worker 2", capabilities=["node", "python"])
        await manager.register_worker(worker1)
        await manager.register_worker(worker2)

        task = DistributedTask(
            id="task_1",
            metadata={"required_capabilities": ["node"]},
        )

        selected = await balancer.select_worker(task)
        assert selected.id == "worker_2"

    async def test_select_worker_no_workers(self, balancer):
        task = DistributedTask(id="task_1")
        selected = await balancer.select_worker(task)
        assert selected is None
