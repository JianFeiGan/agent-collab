"""Distributed execution engine for AgentCollab."""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a distributed task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class WorkerStatus(str, Enum):
    """Status of a worker node."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class LoadBalancingStrategy(str, Enum):
    """Strategy for distributing tasks to workers."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED = "weighted"
    RESOURCE_BASED = "resource_based"


@dataclass
class WorkerInfo:
    """Information about a worker node."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    host: str = ""
    port: int = 0
    status: WorkerStatus = WorkerStatus.IDLE
    current_tasks: int = 0
    max_tasks: int = 10
    weight: int = 1
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DistributedTask:
    """A task for distributed execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    task_id: str = ""
    agent_type: str = ""
    prompt: str = ""
    workdir: str = "."
    allowed_tools: list[str] = field(default_factory=list)
    priority: int = 0
    timeout: int = 600
    max_retries: int = 3
    retry_count: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_worker: str | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of a distributed task execution."""

    task_id: str
    success: bool
    output: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    worker_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskQueue(ABC):
    """Abstract base class for task queues.

    .. note::

        An in-memory implementation (:class:`~agent_collab.distributed.queue.InMemoryTaskQueue`)
        is provided for development and testing.  For production use, implement
        this interface backed by a persistent store (e.g. Redis, PostgreSQL).
    """

    @abstractmethod
    async def enqueue(self, task: DistributedTask) -> bool:
        """Add a task to the queue.

        Args:
            task: The task to enqueue.

        Returns:
            True if the task was enqueued successfully.
        """

    @abstractmethod
    async def dequeue(self, worker_id: str) -> DistributedTask | None:
        """Dequeue a task for a worker.

        Args:
            worker_id: The ID of the worker requesting a task.

        Returns:
            The next task to execute, or None if queue is empty.
        """

    @abstractmethod
    async def complete(self, task_id: str, result: TaskResult) -> bool:
        """Mark a task as completed.

        Args:
            task_id: The ID of the completed task.
            result: The task result.

        Returns:
            True if the task was marked as completed.
        """

    @abstractmethod
    async def fail(self, task_id: str, error: str) -> bool:
        """Mark a task as failed.

        Args:
            task_id: The ID of the failed task.
            error: The error message.

        Returns:
            True if the task was marked as failed.
        """

    @abstractmethod
    async def get_task(self, task_id: str) -> DistributedTask | None:
        """Get a task by ID.

        Args:
            task_id: The ID of the task.

        Returns:
            The task, or None if not found.
        """

    @abstractmethod
    async def get_pending_tasks(self) -> list[DistributedTask]:
        """Get all pending tasks.

        Returns:
            List of pending tasks.
        """

    @abstractmethod
    async def get_queue_size(self) -> int:
        """Get the number of tasks in the queue.

        Returns:
            The queue size.
        """

    @abstractmethod
    async def get_all_tasks(self) -> list[DistributedTask]:
        """Get all tasks regardless of status.

        Returns:
            List of all tasks in the queue.
        """


class WorkerManager(ABC):
    """Abstract base class for worker managers.

    .. note::

        An in-memory implementation (:class:`~agent_collab.distributed.queue.InMemoryWorkerManager`)
        is provided for development and testing.  For production use, implement
        this interface backed by a persistent store.
    """

    @abstractmethod
    async def register_worker(self, worker: WorkerInfo) -> bool:
        """Register a worker node.

        Args:
            worker: The worker information.

        Returns:
            True if the worker was registered successfully.
        """

    @abstractmethod
    async def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker node.

        Args:
            worker_id: The ID of the worker to unregister.

        Returns:
            True if the worker was unregistered successfully.
        """

    @abstractmethod
    async def heartbeat(self, worker_id: str) -> bool:
        """Update worker heartbeat.

        Args:
            worker_id: The ID of the worker.

        Returns:
            True if the heartbeat was updated successfully.
        """

    @abstractmethod
    async def get_worker(self, worker_id: str) -> WorkerInfo | None:
        """Get worker information.

        Args:
            worker_id: The ID of the worker.

        Returns:
            The worker information, or None if not found.
        """

    @abstractmethod
    async def get_available_workers(self) -> list[WorkerInfo]:
        """Get all available workers.

        Returns:
            List of available workers.
        """

    @abstractmethod
    async def update_worker_status(self, worker_id: str, status: WorkerStatus) -> bool:
        """Update worker status.

        Args:
            worker_id: The ID of the worker.
            status: The new status.

        Returns:
            True if the status was updated successfully.
        """

    @abstractmethod
    async def increment_task_count(self, worker_id: str) -> bool:
        """Increment the task count for a worker.

        Args:
            worker_id: The ID of the worker.

        Returns:
            True if the count was incremented successfully.
        """

    @abstractmethod
    async def decrement_task_count(self, worker_id: str) -> bool:
        """Decrement the task count for a worker.

        Args:
            worker_id: The ID of the worker.

        Returns:
            True if the count was decremented successfully.
        """


class DistributedExecutor(ABC):
    """Abstract base class for distributed executors."""

    @abstractmethod
    async def execute_task(self, task: DistributedTask) -> TaskResult:
        """Execute a task.

        Args:
            task: The task to execute.

        Returns:
            The task result.
        """

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: The ID of the task to cancel.

        Returns:
            True if the task was cancelled successfully.
        """
