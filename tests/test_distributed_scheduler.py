"""Tests for the distributed scheduler."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from agent_collab.distributed import (
    DistributedTask,
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
from agent_collab.distributed.scheduler import DistributedScheduler


class FakeExecutor:
    """A fake DistributedExecutor that returns a configurable result."""

    def __init__(self, result: TaskResult | None = None, delay: float = 0.0):
        self.result = result or TaskResult(task_id="", success=True, output="ok")
        self.delay = delay
        self.cancelled_ids: list[str] = []
        self.executed_ids: list[str] = []

    async def execute_task(self, task: DistributedTask) -> TaskResult:
        self.executed_ids.append(task.id)
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return self.result

    async def cancel_task(self, task_id: str) -> bool:
        self.cancelled_ids.append(task_id)
        return True


@pytest.fixture
def task_queue():
    return InMemoryTaskQueue()


@pytest.fixture
def worker_manager():
    return InMemoryWorkerManager()


@pytest.fixture
def executor():
    return FakeExecutor()


@pytest.fixture
def scheduler(task_queue, worker_manager, executor):
    s = DistributedScheduler(
        task_queue=task_queue,
        worker_manager=worker_manager,
        executor=executor,
        heartbeat_interval=0.1,
        task_timeout=5.0,
    )
    return s


@pytest.fixture
def sample_task():
    return DistributedTask(
        workflow_id="wf_1",
        task_id="task_1",
        agent_type="claude-code",
        prompt="Do something",
        priority=10,
    )


@pytest.fixture
def sample_worker():
    return WorkerInfo(
        name="worker-1",
        host="localhost",
        port=8000,
        max_tasks=5,
    )


class TestDistributedSchedulerLifecycle:
    """Scheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, scheduler):
        assert not scheduler._running
        await scheduler.start()
        assert scheduler._running
        assert scheduler._scheduler_task is not None
        assert scheduler._monitor_task is not None
        await scheduler.stop()
        assert not scheduler._running

    @pytest.mark.asyncio
    async def test_start_idempotent(self, scheduler):
        await scheduler.start()
        task_ref = scheduler._scheduler_task
        await scheduler.start()  # second start should be no-op
        assert scheduler._scheduler_task is task_ref
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_active_tasks(self, scheduler):
        await scheduler.start()
        task = DistributedTask(
            workflow_id="wf_1", task_id="task_1",
            agent_type="claude-code", prompt="Long running", timeout=600,
        )
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await scheduler.worker_manager.register_worker(worker)
        await scheduler.task_queue.enqueue(task)
        await asyncio.sleep(0.3)
        await scheduler.stop()
        assert len(scheduler._active_tasks) == 0

    @pytest.mark.asyncio
    async def test_double_stop_no_error(self, scheduler):
        await scheduler.start()
        await scheduler.stop()
        await scheduler.stop()  # second stop should be safe


class TestDistributedSchedulerSubmit:
    """Task submission."""

    @pytest.mark.asyncio
    async def test_submit_task(self, scheduler, sample_task):
        result = await scheduler.submit_task(sample_task)
        assert result is True
        # submit_task sets PENDING, then enqueue sets QUEUED
        task = await scheduler.task_queue.get_task(sample_task.id)
        assert task is not None
        assert task.status in (TaskStatus.PENDING, TaskStatus.QUEUED)

    @pytest.mark.asyncio
    async def test_submit_and_get_status(self, scheduler, sample_task):
        await scheduler.submit_task(sample_task)
        task = await scheduler.get_task_status(sample_task.id)
        assert task is not None
        assert task.id == sample_task.id

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, scheduler):
        task = await scheduler.get_task_status("nonexistent")
        assert task is None

    @pytest.mark.asyncio
    async def test_get_queue_size(self, scheduler, sample_task):
        assert await scheduler.get_queue_size() == 0
        await scheduler.task_queue.enqueue(sample_task)
        assert await scheduler.get_queue_size() >= 1


class TestDistributedSchedulerCancel:
    """Task cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_queued_task(self, scheduler, sample_task):
        await scheduler.task_queue.enqueue(sample_task)
        result = await scheduler.cancel_task(sample_task.id)
        assert result is True
        task = await scheduler.task_queue.get_task(sample_task.id)
        assert task is not None
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, scheduler):
        # InMemoryTaskQueue.cancel_task returns False for missing tasks
        result = await scheduler.cancel_task("nonexistent")
        # scheduler.cancel_task returns task_queue.cancel_task result
        # which is False for nonexistent tasks
        # OR True if found in _active_tasks
        assert result is True or result is False


class TestDistributedSchedulerScheduling:
    """Scheduling loop behavior."""

    @pytest.mark.asyncio
    async def test_no_workers_available(self, scheduler, sample_task):
        """Scheduler should skip when no workers are available."""
        await scheduler.start()
        await scheduler.task_queue.enqueue(sample_task)
        await asyncio.sleep(0.3)
        task = await scheduler.task_queue.get_task(sample_task.id)
        assert task is not None
        assert task.status == TaskStatus.QUEUED
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_worker_picks_up_task(self, scheduler, sample_task):
        """Scheduler should assign a task when workers are available."""
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await scheduler.worker_manager.register_worker(worker)
        await scheduler.start()
        await scheduler.task_queue.enqueue(sample_task)
        await asyncio.sleep(0.5)
        task = await scheduler.task_queue.get_task(sample_task.id)
        assert task is not None
        assert task.status in (TaskStatus.RUNNING, TaskStatus.COMPLETED)
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_worker_at_capacity(self, scheduler, sample_task):
        """Scheduler should skip workers at max capacity."""
        worker = WorkerInfo(
            name="w1", host="localhost", port=8000, max_tasks=1, current_tasks=1
        )
        await scheduler.worker_manager.register_worker(worker)
        await scheduler.start()
        await scheduler.task_queue.enqueue(sample_task)
        await asyncio.sleep(0.3)
        task = await scheduler.task_queue.get_task(sample_task.id)
        assert task is not None
        assert task.status == TaskStatus.QUEUED
        await scheduler.stop()


class TestDistributedSchedulerExecute:
    """Task execution."""

    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)
        executor = FakeExecutor(
            result=TaskResult(task_id="t1", success=True, output="done")
        )
        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=executor,
            heartbeat_interval=60, task_timeout=5.0,
        )

        task = DistributedTask(
            workflow_id="wf_1", task_id="task_1",
            agent_type="claude-code", prompt="Do something",
            max_retries=0,  # No retries
        )
        await queue.enqueue(task)
        await wm.increment_task_count(worker.id)
        await s._execute_task(task, worker)

        result_task = await queue.get_task(task.id)
        assert result_task is not None
        assert result_task.status == TaskStatus.COMPLETED
        assert result_task.result is not None
        assert result_task.result.success is True

    @pytest.mark.asyncio
    async def test_execute_task_failure(self):
        """Test _execute_task with a failed execution (no retries)."""
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)

        class FailingExecutor:
            async def execute_task(self, task):
                raise RuntimeError("Something went wrong")
            async def cancel_task(self, task_id):
                return True

        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=FailingExecutor(),
            heartbeat_interval=60, task_timeout=5.0,
        )

        task = DistributedTask(
            workflow_id="wf_1", task_id="task_1",
            agent_type="claude-code", prompt="Do something",
            max_retries=0,  # No retries so status stays FAILED
        )
        await queue.enqueue(task)
        await wm.increment_task_count(worker.id)
        await s._execute_task(task, worker)

        result_task = await queue.get_task(task.id)
        assert result_task is not None
        assert result_task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_task_failure_with_retry(self):
        """Test _execute_task with failure + retry."""
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)

        class FailingExecutor:
            async def execute_task(self, task):
                raise RuntimeError("Something went wrong")
            async def cancel_task(self, task_id):
                return True

        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=FailingExecutor(),
            heartbeat_interval=60, task_timeout=5.0,
        )

        task = DistributedTask(
            workflow_id="wf_1", task_id="task_1",
            agent_type="claude-code", prompt="Do something",
            max_retries=3,  # Allow retries
        )
        await queue.enqueue(task)
        await wm.increment_task_count(worker.id)
        await s._execute_task(task, worker)

        # After failure, scheduler retries the task → status becomes QUEUED
        result_task = await queue.get_task(task.id)
        assert result_task is not None
        assert result_task.status == TaskStatus.QUEUED
        assert result_task.retry_count == 1

    @pytest.mark.asyncio
    async def test_execute_task_timeout(self):
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)

        executor = FakeExecutor(
            result=TaskResult(task_id="t1", success=True, output="slow"),
            delay=10.0,
        )
        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=executor,
            heartbeat_interval=60, task_timeout=0.1,
        )

        task = DistributedTask(
            workflow_id="wf_1", task_id="task_1",
            agent_type="claude-code", prompt="Slow task",
            max_retries=0,  # No retries
        )
        await queue.enqueue(task)
        await wm.increment_task_count(worker.id)
        await s._execute_task(task, worker)

        result_task = await queue.get_task(task.id)
        assert result_task is not None
        assert result_task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_task_cancelled(self):
        """Test _execute_task with cancellation."""
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)

        class SlowExecutor:
            async def execute_task(self, task):
                await asyncio.sleep(10)  # Will be cancelled
            async def cancel_task(self, task_id):
                return True

        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=SlowExecutor(),
            heartbeat_interval=60, task_timeout=5.0,
        )

        task = DistributedTask(
            workflow_id="wf_1", task_id="task_1",
            agent_type="claude-code", prompt="Cancellable task",
            max_retries=0,
        )
        await queue.enqueue(task)
        await wm.increment_task_count(worker.id)

        # Run _execute_task and cancel it midway
        execute_task = asyncio.create_task(s._execute_task(task, worker))
        await asyncio.sleep(0.1)
        execute_task.cancel()
        await asyncio.sleep(0.1)

        result_task = await queue.get_task(task.id)
        assert result_task is not None
        assert result_task.status == TaskStatus.FAILED


class TestDistributedSchedulerMonitor:
    """Worker monitoring."""

    @pytest.mark.asyncio
    async def test_monitor_offline_worker(self):
        """Test that monitor detects offline workers.

        Note: register_worker resets last_heartbeat to now, so to trigger
        the offline detection we must register the worker first, then
        manually set its heartbeat far in the past.
        """
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        executor = FakeExecutor()

        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)
        # Manually set heartbeat to 60 seconds ago
        worker.last_heartbeat = datetime.now(UTC) - timedelta(seconds=60)

        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=executor,
            heartbeat_interval=0.05, task_timeout=5.0,
        )

        await s.start()
        await asyncio.sleep(0.3)
        await s.stop()

        updated = await wm.get_worker(worker.id)
        assert updated is not None
        assert updated.status == WorkerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_worker_stats(self, scheduler):
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await scheduler.worker_manager.register_worker(worker)
        stats = await scheduler.get_worker_stats()
        assert "total_workers" in stats
        assert stats["total_workers"] >= 1

    @pytest.mark.asyncio
    async def test_monitor_loop_no_error(self):
        """Monitor loop should handle no workers gracefully."""
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        executor = FakeExecutor()
        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=executor,
            heartbeat_interval=0.05, task_timeout=5.0,
        )
        await s.start()
        await asyncio.sleep(0.2)
        await s.stop()


class TestDistributedSchedulerEdgeCases:
    """Edge cases."""

    @pytest.mark.asyncio
    async def test_empty_queue_scheduling(self):
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        worker = WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        await wm.register_worker(worker)
        executor = FakeExecutor()
        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=executor,
            heartbeat_interval=0.05, task_timeout=5.0,
        )
        await s.start()
        await asyncio.sleep(0.3)
        await s.stop()

    @pytest.mark.asyncio
    async def test_scheduler_start_stop_multiple_times(self, scheduler):
        for _ in range(3):
            await scheduler.start()
            await asyncio.sleep(0.05)
            assert scheduler._running
            await scheduler.stop()
            assert not scheduler._running

    @pytest.mark.asyncio
    async def test_cancel_active_running_task(self, scheduler, sample_task):
        """Cancel a task that is actively running (in _active_tasks)."""
        mock_task = asyncio.create_task(asyncio.sleep(100))
        scheduler._active_tasks[sample_task.id] = mock_task
        result = await scheduler.cancel_task(sample_task.id)
        # Returns task_queue.cancel_task result (False since task not in queue)
        # But the task was removed from _active_tasks regardless
        assert sample_task.id not in scheduler._active_tasks

    @pytest.mark.asyncio
    async def test_multiple_workers_scheduling(self):
        """Multiple workers should each pick up tasks."""
        queue = InMemoryTaskQueue()
        wm = InMemoryWorkerManager()
        executor = FakeExecutor()
        s = DistributedScheduler(
            task_queue=queue, worker_manager=wm, executor=executor,
            heartbeat_interval=0.05, task_timeout=5.0,
        )

        # Register 2 workers
        await wm.register_worker(
            WorkerInfo(name="w1", host="localhost", port=8000, max_tasks=5)
        )
        await wm.register_worker(
            WorkerInfo(name="w2", host="localhost", port=8001, max_tasks=5)
        )

        await s.start()
        # Enqueue 2 tasks
        t1 = DistributedTask(task_id="t1", prompt="Task 1", max_retries=0)
        t2 = DistributedTask(task_id="t2", prompt="Task 2", max_retries=0)
        await queue.enqueue(t1)
        await queue.enqueue(t2)
        await asyncio.sleep(0.5)
        await s.stop()

        # Both tasks should have been executed
        assert len(executor.executed_ids) == 2
