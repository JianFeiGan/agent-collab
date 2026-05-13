"""Degradation policies for handling task failures."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DegradationPolicy(str, Enum):
    """Policy for handling task failures during workflow execution.

    Attributes:
        SKIP: Skip the failed task and continue with remaining tasks.
        ABORT: Abort the entire workflow on failure.
        CONTINUE: Continue execution of downstream tasks despite failure.
    """

    SKIP = "skip"
    ABORT = "abort"
    CONTINUE = "continue"


class TaskDegradation(BaseModel):
    """Degradation configuration for a single task.

    Attributes:
        policy: The degradation policy to apply on failure.
        fallback_task_id: Optional task ID to execute as fallback on failure.
        max_failures: Maximum number of failures before applying degradation.
            If the failure count is below this threshold, the task is retried
            normally. Once exceeded, the degradation policy kicks in.
    """

    policy: DegradationPolicy = DegradationPolicy.ABORT
    fallback_task_id: str | None = None
    max_failures: int = Field(default=1, ge=0)


class DegradationHandler:
    """Handles task failures according to configured degradation policies.

    Attributes:
        failure_counts: Tracks the number of failures per task ID.
    """

    def __init__(self) -> None:
        """Initialise the DegradationHandler with empty failure counts."""
        self.failure_counts: dict[str, int] = {}

    def record_failure(self, task_id: str) -> int:
        """Record a failure for the given task and return updated count.

        Args:
            task_id: The task identifier.

        Returns:
            The total failure count for this task.
        """
        self.failure_counts[task_id] = self.failure_counts.get(task_id, 0) + 1
        return self.failure_counts[task_id]

    def should_degrade(self, task_id: str, degradation: TaskDegradation) -> bool:
        """Check whether the degradation policy should activate.

        Args:
            task_id: The task identifier.
            degradation: The degradation configuration.

        Returns:
            True if the failure count has reached or exceeded max_failures.
        """
        return self.failure_counts.get(task_id, 0) >= degradation.max_failures

    def get_policy(
        self, task_id: str, degradation: TaskDegradation
    ) -> DegradationPolicy:
        """Return the effective degradation policy for a task.

        If the failure count has not yet reached max_failures, returns
        ``DegradationPolicy.CONTINUE`` (i.e. retry normally).

        Args:
            task_id: The task identifier.
            degradation: The degradation configuration.

        Returns:
            The effective degradation policy.
        """
        if self.should_degrade(task_id, degradation):
            return degradation.policy
        return DegradationPolicy.CONTINUE
