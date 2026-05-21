"""Human-in-the-Loop (HITL) approval and input nodes."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class InputType(str, Enum):
    """Type of human input requested."""

    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    FILE = "file"
    JSON = "json"


@dataclass
class ApprovalRequest:
    """Request for human approval."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    task_id: str = ""
    title: str = ""
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InputRequest:
    """Request for human input."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    task_id: str = ""
    title: str = ""
    description: str = ""
    input_type: InputType = InputType.TEXT
    required: bool = True
    default_value: Any = None
    options: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    submitted_value: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalHistory:
    """History entry for approval actions."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    action: str = ""  # approve, reject, expire, cancel
    actor: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HITLProvider(ABC):
    """Abstract base class for HITL providers.

    HITL providers handle the communication with humans
    for approval and input requests.

    .. note::

        Two implementations are provided:
        :class:`~agent_collab.hitl.InMemoryProvider` for testing, and
        :class:`~agent_collab.hitl.WebhookProvider` for webhook-based
        notification.  For production, consider implementing a provider
        backed by Slack, Discord, or a persistent database.
    """

    @abstractmethod
    async def send_approval_request(self, request: ApprovalRequest) -> bool:
        """Send an approval request to humans.

        Args:
            request: The approval request to send.

        Returns:
            True if the request was sent successfully.
        """

    @abstractmethod
    async def get_approval_status(self, request_id: str) -> ApprovalRequest:
        """Get the status of an approval request.

        Args:
            request_id: The ID of the approval request.

        Returns:
            The current approval request status.
        """

    @abstractmethod
    async def approve(self, request_id: str, actor: str, reason: str | None = None) -> bool:
        """Approve a request.

        Args:
            request_id: The ID of the approval request.
            actor: Who approved the request.
            reason: Optional reason for approval.

        Returns:
            True if the approval was successful.
        """

    @abstractmethod
    async def reject(self, request_id: str, actor: str, reason: str) -> bool:
        """Reject a request.

        Args:
            request_id: The ID of the approval request.
            actor: Who rejected the request.
            reason: Reason for rejection.

        Returns:
            True if the rejection was successful.
        """

    @abstractmethod
    async def send_input_request(self, request: InputRequest) -> bool:
        """Send an input request to humans.

        Args:
            request: The input request to send.

        Returns:
            True if the request was sent successfully.
        """

    @abstractmethod
    async def get_input_status(self, request_id: str) -> InputRequest:
        """Get the status of an input request.

        Args:
            request_id: The ID of the input request.

        Returns:
            The current input request status.
        """

    @abstractmethod
    async def submit_input(self, request_id: str, value: Any, actor: str) -> bool:
        """Submit input for a request.

        Args:
            request_id: The ID of the input request.
            value: The submitted value.
            actor: Who submitted the input.

        Returns:
            True if the submission was successful.
        """


class WebhookProvider(HITLProvider):
    """HITL provider that sends notifications via webhooks."""

    def __init__(self, webhook_url: str, headers: dict[str, str] | None = None) -> None:
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self._requests: dict[str, ApprovalRequest] = {}
        self._input_requests: dict[str, InputRequest] = {}
        self._history: list[ApprovalHistory] = []

    async def send_approval_request(self, request: ApprovalRequest) -> bool:
        """Send approval request via webhook."""
        import httpx

        self._requests[request.id] = request

        payload = {
            "type": "approval_request",
            "id": request.id,
            "workflow_id": request.workflow_id,
            "task_id": request.task_id,
            "title": request.title,
            "description": request.description,
            "data": request.data,
            "created_at": request.created_at.isoformat(),
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=30,
                )
                response.raise_for_status()
                logger.info(f"Approval request {request.id} sent via webhook")
                return True
        except Exception as e:
            logger.error(f"Failed to send approval request via webhook: {e}")
            return False

    async def get_approval_status(self, request_id: str) -> ApprovalRequest:
        """Get approval request status."""
        if request_id not in self._requests:
            raise ValueError(f"Approval request {request_id} not found")
        return self._requests[request_id]

    async def approve(self, request_id: str, actor: str, reason: str | None = None) -> bool:
        """Approve a request."""
        if request_id not in self._requests:
            raise ValueError(f"Approval request {request_id} not found")

        request = self._requests[request_id]
        request.status = ApprovalStatus.APPROVED
        request.approved_by = actor
        request.approved_at = datetime.now(timezone.utc)
        request.updated_at = datetime.now(timezone.utc)

        self._history.append(ApprovalHistory(
            request_id=request_id,
            action="approve",
            actor=actor,
            reason=reason,
        ))

        logger.info(f"Approval request {request_id} approved by {actor}")
        return True

    async def reject(self, request_id: str, actor: str, reason: str) -> bool:
        """Reject a request."""
        if request_id not in self._requests:
            raise ValueError(f"Approval request {request_id} not found")

        request = self._requests[request_id]
        request.status = ApprovalStatus.REJECTED
        request.rejection_reason = reason
        request.updated_at = datetime.now(timezone.utc)

        self._history.append(ApprovalHistory(
            request_id=request_id,
            action="reject",
            actor=actor,
            reason=reason,
        ))

        logger.info(f"Approval request {request_id} rejected by {actor}")
        return True

    async def send_input_request(self, request: InputRequest) -> bool:
        """Send input request via webhook."""
        import httpx

        self._input_requests[request.id] = request

        payload = {
            "type": "input_request",
            "id": request.id,
            "workflow_id": request.workflow_id,
            "task_id": request.task_id,
            "title": request.title,
            "description": request.description,
            "input_type": request.input_type.value,
            "required": request.required,
            "default_value": request.default_value,
            "options": request.options,
            "created_at": request.created_at.isoformat(),
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=30,
                )
                response.raise_for_status()
                logger.info(f"Input request {request.id} sent via webhook")
                return True
        except Exception as e:
            logger.error(f"Failed to send input request via webhook: {e}")
            return False

    async def get_input_status(self, request_id: str) -> InputRequest:
        """Get input request status."""
        if request_id not in self._input_requests:
            raise ValueError(f"Input request {request_id} not found")
        return self._input_requests[request_id]

    async def submit_input(self, request_id: str, value: Any, actor: str) -> bool:
        """Submit input for a request."""
        if request_id not in self._input_requests:
            raise ValueError(f"Input request {request_id} not found")

        request = self._input_requests[request_id]
        request.status = ApprovalStatus.APPROVED
        request.submitted_by = actor
        request.submitted_at = datetime.now(timezone.utc)
        request.submitted_value = value
        request.updated_at = datetime.now(timezone.utc)

        self._history.append(ApprovalHistory(
            request_id=request_id,
            action="submit_input",
            actor=actor,
            metadata={"value": value},
        ))

        logger.info(f"Input request {request_id} submitted by {actor}")
        return True

    def get_history(self, request_id: str | None = None) -> list[ApprovalHistory]:
        """Get approval history.

        Args:
            request_id: Optional filter by request ID.

        Returns:
            List of approval history entries.
        """
        if request_id:
            return [h for h in self._history if h.request_id == request_id]
        return list(self._history)


class InMemoryProvider(HITLProvider):
    """In-memory HITL provider for testing."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._input_requests: dict[str, InputRequest] = {}
        self._history: list[ApprovalHistory] = []

    async def send_approval_request(self, request: ApprovalRequest) -> bool:
        """Store approval request in memory."""
        self._requests[request.id] = request
        return True

    async def get_approval_status(self, request_id: str) -> ApprovalRequest:
        """Get approval request status."""
        if request_id not in self._requests:
            raise ValueError(f"Approval request {request_id} not found")
        return self._requests[request_id]

    async def approve(self, request_id: str, actor: str, reason: str | None = None) -> bool:
        """Approve a request."""
        if request_id not in self._requests:
            raise ValueError(f"Approval request {request_id} not found")

        request = self._requests[request_id]
        request.status = ApprovalStatus.APPROVED
        request.approved_by = actor
        request.approved_at = datetime.now(timezone.utc)
        request.updated_at = datetime.now(timezone.utc)

        self._history.append(ApprovalHistory(
            request_id=request_id,
            action="approve",
            actor=actor,
            reason=reason,
        ))

        return True

    async def reject(self, request_id: str, actor: str, reason: str) -> bool:
        """Reject a request."""
        if request_id not in self._requests:
            raise ValueError(f"Approval request {request_id} not found")

        request = self._requests[request_id]
        request.status = ApprovalStatus.REJECTED
        request.rejection_reason = reason
        request.updated_at = datetime.now(timezone.utc)

        self._history.append(ApprovalHistory(
            request_id=request_id,
            action="reject",
            actor=actor,
            reason=reason,
        ))

        return True

    async def send_input_request(self, request: InputRequest) -> bool:
        """Store input request in memory."""
        self._input_requests[request.id] = request
        return True

    async def get_input_status(self, request_id: str) -> InputRequest:
        """Get input request status."""
        if request_id not in self._input_requests:
            raise ValueError(f"Input request {request_id} not found")
        return self._input_requests[request_id]

    async def submit_input(self, request_id: str, value: Any, actor: str) -> bool:
        """Submit input for a request."""
        if request_id not in self._input_requests:
            raise ValueError(f"Input request {request_id} not found")

        request = self._input_requests[request_id]
        request.status = ApprovalStatus.APPROVED
        request.submitted_by = actor
        request.submitted_at = datetime.now(timezone.utc)
        request.submitted_value = value
        request.updated_at = datetime.now(timezone.utc)

        self._history.append(ApprovalHistory(
            request_id=request_id,
            action="submit_input",
            actor=actor,
            metadata={"value": value},
        ))

        return True

    def get_history(self, request_id: str | None = None) -> list[ApprovalHistory]:
        """Get approval history."""
        if request_id:
            return [h for h in self._history if h.request_id == request_id]
        return list(self._history)
