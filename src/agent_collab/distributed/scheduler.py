"""Distributed scheduler for orchestrating task execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from agent_collab.distributed import (
    DistributedExecutor,
    DistributedTask,
    TaskQueue,
    TaskResult,
    TaskStatus,
    WorkerInfo,
    WorkerManager,
    WorkerStatus,
)
from agent_collab.distributed.queue import LoadBalancer

logger = logging.getLogger(__name__)


class DistributedScheduler:
    """Scheduler for distributed task execution.

    Manages task distribution, worker monitoring, and fault tolerance.
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        worker_manager: WorkerManager,
        executor: DistributedExecutor,
        load_balancer: LoadBalancer | None = None,
        heartbeat_interval: float = 10.0,
        task_timeout: float = 600.0,
    ) -> None:
        self.task_queue = task_queue
        self.worker_manager = worker_manager
        self.executor = executor
        self.load_balancer = load_balancer or LoadBalancer(worker_manager)
        self.heartbeat_interval = heartbeat_interval
        self.task_timeout = task_timeout
        self._running = False
        self._scheduler_task: asyncio.Task | None = None
        self._monitor_task: asyncio.Task | None = None
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """Start the distributed scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Distributed scheduler started")

    async def stop(self) -> None:
        """Stop the distributed scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Cancel all active tasks
        for task_id, task in self._active_tasks.items():
            task.cancel()
            logger.info(f"Cancelled active task {task_id}")

        self._active_tasks.clear()
        logger.info("Distributed scheduler stopped")

    async def submit_task(self, task: DistributedTask) -> bool:
        """Submit a task for distributed execution.

        Args:
            task: The task to submit.

        Returns:
            True if the task was submitted successfully.
        """
        task.status = TaskStatus.PENDING
        success = await self.task_queue.enqueue(task)
        if success:
            logger.info(f"Task {task.id} submitted for distributed execution")
        return success

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: The ID of the task to cancel.

        Returns:
            True if the task was cancelled successfully.
        """
        # Cancel active task if running
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            del self._active_tasks[task_id]

        # Cancel in queue
        return await self.task_queue.cancel_task(task_id)

    async def get_task_status(self, task_id: str) -> DistributedTask | None:
        """Get the status of a task.

        Args:
            task_id: The ID of the task.

        Returns:
            The task, or None if not found.
        """
        return await self.task_queue.get_task(task_id)

    async def get_queue_size(self) -> int:
        """Get the number of tasks in the queue."""
        return await self.task_queue.get_queue_size()

    async def get_worker_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        if hasattr(self.worker_manager, 'get_worker_stats'):
            return await self.worker_manager.get_worker_stats()
        workers = await self.worker_manager.get_available_workers()
        return {
            "total_workers": len(workers),
            "available_workers": len(workers),
        }

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Get available workers
                workers = await self.worker_manager.get_available_workers()
                if not workers:
                    await asyncio.sleep(1.0)
                    continue

                # Try to assign tasks to workers
                for worker in workers:
                    if not self._running:
                        break

                    # Check if worker has capacity
                    if worker.current_tasks >= worker.max_tasks:
                        continue

                    # Dequeue a task
                    task = await self.task_queue.dequeue(worker.id)
                    if task is None:
                        break

                    # Increment worker task count
                    await self.worker_manager.increment_task_count(worker.id)

                    # Execute task asynchronously
                    task_async = asyncio.create_task(
                        self._execute_task(task, worker)
                    )
                    self._active_tasks[task.id] = task_async

                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(1.0)

    async def _execute_task(self, task: DistributedTask, worker: WorkerInfo) -> None:
        """Execute a task on a worker."""
        try:
            logger.info(f"Executing task {task.id} on worker {worker.id}")

            # Execute with timeout
            result = await asyncio.wait_for(
                self.executor.execute_task(task),
                timeout=self.task_timeout,
            )

            # Mark task as completed
            await self.task_queue.complete(task.id, result)

            # Decrement worker task count
            await self.worker_manager.decrement_task_count(worker.id)

            logger.info(f"Task {task.id} completed successfully")

        except asyncio.TimeoutError:
            logger.error(f"Task {task.id} timed out")
            await self.task_queue.fail(task.id, "Task timed out")
            await self.worker_manager.decrement_task_count(worker.id)

        except asyncio.CancelledError:
            logger.info(f"Task {task.id} cancelled")
            await self.task_queue.fail(task.id, "Task cancelled")
            await self.worker_manager.decrement_task_count(worker.id)

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            await self.task_queue.fail(task.id, str(e))
            await self.worker_manager.decrement_task_count(worker.id)

        finally:
            # Remove from active tasks
            self._active_tasks.pop(task.id, None)

            # Try to retry failed tasks
            task_info = await self.task_queue.get_task(task.id)
            if task_info and task_info.status == TaskStatus.FAILED:
                if task_info.retry_count < task_info.max_retries:
                    await self.task_queue.retry_task(task.id)
                    logger.info(f"Task {task.id} queued for retry")

    async def _monitor_loop(self) -> None:
        """Monitor workers and handle failures."""
        while self._running:
            try:
                # Check for offline workers
                workers = await self.worker_manager.get_all_workers()
                now = datetime.now(timezone.utc)

                for worker in workers:
                    # Check heartbeat timeout (30 seconds)
                    if (now - worker.last_heartbeat).total_seconds() > 30:
                        if worker.status != WorkerStatus.OFFLINE:
                            await self.worker_manager.update_worker_status(
                                worker.id, WorkerStatus.OFFLINE
                            )
                            logger.warning(f"Worker {worker.id} went offline")

                            # Reassign tasks from offline worker
                            await self._reassign_worker_tasks(worker.id)

                await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(1.0)

    async def _reassign_worker_tasks(self, worker_id: str) -> None:
        """Reassign tasks from an offline worker.

        Args:
            worker_id: The ID of the offline worker.
        """
        # Get all tasks assigned to the worker
        all_tasks = []
        if hasattr(self.task_queue, 'get_all_tasks'):
            all_tasks = await self.task_queue.get_all_tasks()

        for task in all_tasks:
            if task.assigned_worker == worker_id and task.status == TaskStatus.RUNNING:
                # Requeue the task
                task.status = TaskStatus.QUEUED
                task.assigned_worker = None
                task.retry_count += 1

                if task.retry_count <= task.max_retries:
                    await self.task_queue.enqueue(task)
                    logger.info(f"Task {task.id} reassigned from offline worker {worker_id}")
                else:
                    await self.task_queue.fail(task.id, "Max retries exceeded after worker failure")
                    logger.error(f"Task {task.id} failed: max retries exceeded")
