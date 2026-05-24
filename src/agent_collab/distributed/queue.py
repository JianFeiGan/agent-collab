"""In-memory implementations for distributed execution."""

from __future__ import annotations

import asyncio
import heapq
import logging
from datetime import UTC, datetime
from typing import Any

from agent_collab.distributed import (
    DistributedTask,
    LoadBalancingStrategy,
    TaskQueue,
    TaskResult,
    TaskStatus,
    WorkerInfo,
    WorkerManager,
    WorkerStatus,
)

logger = logging.getLogger(__name__)


class InMemoryTaskQueue(TaskQueue):
    """In-memory task queue with priority support."""

    def __init__(self) -> None:
        self._tasks: dict[str, DistributedTask] = {}
        self._queue: list[tuple[int, str]] = []  # (priority, task_id)
        self._lock = asyncio.Lock()

    async def enqueue(self, task: DistributedTask) -> bool:
        """Add a task to the queue with priority."""
        async with self._lock:
            task.status = TaskStatus.QUEUED
            self._tasks[task.id] = task
            # Use negative priority for max-heap behavior (higher priority first)
            heapq.heappush(self._queue, (-task.priority, task.id))
            logger.info(f"Task {task.id} enqueued with priority {task.priority}")
            return True

    async def dequeue(self, worker_id: str) -> DistributedTask | None:
        """Dequeue the highest priority task."""
        async with self._lock:
            while self._queue:
                priority, task_id = heapq.heappop(self._queue)
                task = self._tasks.get(task_id)
                if task and task.status == TaskStatus.QUEUED:
                    task.status = TaskStatus.RUNNING
                    task.assigned_worker = worker_id
                    task.started_at = datetime.now(UTC)
                    logger.info(f"Task {task.id} dequeued by worker {worker_id}")
                    return task
            return None

    async def complete(self, task_id: str, result: TaskResult) -> bool:
        """Mark a task as completed."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(UTC)
                task.result = result
                logger.info(f"Task {task_id} completed")
                return True
            return False

    async def fail(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(UTC)
                task.error = error
                logger.info(f"Task {task_id} failed: {error}")
                return True
            return False

    async def get_task(self, task_id: str) -> DistributedTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def get_pending_tasks(self) -> list[DistributedTask]:
        """Get all pending tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.QUEUED]

    async def get_queue_size(self) -> int:
        """Get the number of tasks in the queue."""
        return len([t for t in self._tasks.values() if t.status == TaskStatus.QUEUED])

    async def get_all_tasks(self) -> list[DistributedTask]:
        """Get all tasks."""
        return list(self._tasks.values())

    async def retry_task(self, task_id: str) -> bool:
        """Retry a failed task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.FAILED:
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.QUEUED
                    task.assigned_worker = None
                    task.error = None
                    heapq.heappush(self._queue, (-task.priority, task.id))
                    logger.info(f"Task {task_id} retried (attempt {task.retry_count})")
                    return True
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(UTC)
                logger.info(f"Task {task_id} cancelled")
                return True
            return False


class InMemoryWorkerManager(WorkerManager):
    """In-memory worker manager."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerInfo] = {}
        self._lock = asyncio.Lock()

    async def register_worker(self, worker: WorkerInfo) -> bool:
        """Register a worker node."""
        async with self._lock:
            worker.registered_at = datetime.now(UTC)
            worker.last_heartbeat = datetime.now(UTC)
            self._workers[worker.id] = worker
            logger.info(f"Worker {worker.id} registered: {worker.name}")
            return True

    async def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker node."""
        async with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                logger.info(f"Worker {worker_id} unregistered")
                return True
            return False

    async def heartbeat(self, worker_id: str) -> bool:
        """Update worker heartbeat."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.last_heartbeat = datetime.now(UTC)
                return True
            return False

    async def get_worker(self, worker_id: str) -> WorkerInfo | None:
        """Get worker information."""
        return self._workers.get(worker_id)

    async def get_available_workers(self) -> list[WorkerInfo]:
        """Get all available workers."""
        now = datetime.now(UTC)
        available = []
        for worker in self._workers.values():
            # Check if worker is online (heartbeat within last 30 seconds)
            if (now - worker.last_heartbeat).total_seconds() < 30:
                if worker.status == WorkerStatus.IDLE or (
                    worker.status == WorkerStatus.BUSY and worker.current_tasks < worker.max_tasks
                ):
                    available.append(worker)
        return available

    async def update_worker_status(self, worker_id: str, status: WorkerStatus) -> bool:
        """Update worker status."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.status = status
                return True
            return False

    async def increment_task_count(self, worker_id: str) -> bool:
        """Increment the task count for a worker."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.current_tasks += 1
                if worker.current_tasks >= worker.max_tasks:
                    worker.status = WorkerStatus.BUSY
                return True
            return False

    async def decrement_task_count(self, worker_id: str) -> bool:
        """Decrement the task count for a worker."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.current_tasks = max(0, worker.current_tasks - 1)
                if worker.current_tasks < worker.max_tasks:
                    worker.status = WorkerStatus.IDLE
                return True
            return False

    async def get_all_workers(self) -> list[WorkerInfo]:
        """Get all registered workers."""
        return list(self._workers.values())

    async def get_worker_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        workers = list(self._workers.values())
        return {
            "total_workers": len(workers),
            "idle_workers": len([w for w in workers if w.status == WorkerStatus.IDLE]),
            "busy_workers": len([w for w in workers if w.status == WorkerStatus.BUSY]),
            "offline_workers": len([w for w in workers if w.status == WorkerStatus.OFFLINE]),
            "total_capacity": sum(w.max_tasks for w in workers),
            "current_tasks": sum(w.current_tasks for w in workers),
        }


class LoadBalancer:
    """Load balancer for distributing tasks to workers."""

    def __init__(
        self,
        worker_manager: WorkerManager,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ) -> None:
        self.worker_manager = worker_manager
        self.strategy = strategy
        self._round_robin_index = 0

    async def select_worker(self, task: DistributedTask) -> WorkerInfo | None:
        """Select a worker for a task based on the load balancing strategy.

        Args:
            task: The task to assign.

        Returns:
            The selected worker, or None if no workers are available.
        """
        workers = await self.worker_manager.get_available_workers()
        if not workers:
            return None

        # Filter workers by capabilities if task requires specific capabilities
        if task.metadata.get("required_capabilities"):
            required = set(task.metadata["required_capabilities"])
            workers = [w for w in workers if required.issubset(set(w.capabilities))]
            if not workers:
                return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(workers)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._select_least_connections(workers)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return self._select_random(workers)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED:
            return self._select_weighted(workers)
        elif self.strategy == LoadBalancingStrategy.RESOURCE_BASED:
            return self._select_resource_based(workers)
        else:
            return workers[0] if workers else None

    def _select_round_robin(self, workers: list[WorkerInfo]) -> WorkerInfo:
        """Select worker using round-robin strategy."""
        idx = self._round_robin_index % len(workers)
        self._round_robin_index += 1
        return workers[idx]

    def _select_least_connections(self, workers: list[WorkerInfo]) -> WorkerInfo:
        """Select worker with least connections."""
        return min(workers, key=lambda w: w.current_tasks)

    def _select_random(self, workers: list[WorkerInfo]) -> WorkerInfo:
        """Select random worker."""
        import random

        return random.choice(workers)

    def _select_weighted(self, workers: list[WorkerInfo]) -> WorkerInfo:
        """Select worker based on weight."""
        import random

        total_weight = sum(w.weight for w in workers)
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        for worker in workers:
            cumulative += worker.weight
            if r <= cumulative:
                return worker
        return workers[-1]

    def _select_resource_based(self, workers: list[WorkerInfo]) -> WorkerInfo:
        """Select worker based on available resources."""

        # Calculate resource score (lower is better)
        def resource_score(worker: WorkerInfo) -> float:
            task_ratio = worker.current_tasks / worker.max_tasks if worker.max_tasks > 0 else 1.0
            return task_ratio / worker.weight if worker.weight > 0 else task_ratio

        return min(workers, key=resource_score)
