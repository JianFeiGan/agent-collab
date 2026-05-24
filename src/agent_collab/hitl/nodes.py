"""HITL nodes for workflow integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from agent_collab.hitl import (
    ApprovalRequest,
    ApprovalStatus,
    HITLProvider,
    InputRequest,
    InputType,
)

logger = logging.getLogger(__name__)


class HITLNodeType(StrEnum):
    """Type of HITL node."""

    APPROVAL = "approval"
    INPUT = "input"
    REVIEW = "review"


@dataclass
class ApprovalNodeConfig:
    """Configuration for an approval node."""

    id: str
    title: str = ""
    description: str = ""
    required_approvals: int = 1
    timeout_seconds: int = 3600
    auto_approve: bool = False
    depends_on: list[str] = field(default_factory=list)
    next_on_approve: str = ""
    next_on_reject: str = ""


@dataclass
class InputNodeConfig:
    """Configuration for an input node."""

    id: str
    title: str = ""
    description: str = ""
    input_type: InputType = InputType.TEXT
    required: bool = True
    default_value: Any = None
    options: list[dict[str, Any]] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 3600
    depends_on: list[str] = field(default_factory=list)
    next_node: str = ""


@dataclass
class ReviewNodeConfig:
    """Configuration for a review node."""

    id: str
    title: str = ""
    description: str = ""
    review_items: list[str] = field(default_factory=list)
    required_approvals: int = 1
    timeout_seconds: int = 3600
    depends_on: list[str] = field(default_factory=list)
    next_on_approve: str = ""
    next_on_reject: str = ""


class HITLManager:
    """Manages HITL nodes and their lifecycle."""

    def __init__(self, provider: HITLProvider) -> None:
        self.provider = provider
        self._pending_approvals: dict[str, ApprovalRequest] = {}
        self._pending_inputs: dict[str, InputRequest] = {}

    async def create_approval(
        self,
        config: ApprovalNodeConfig,
        workflow_id: str,
        data: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create and send an approval request.

        Args:
            config: Approval node configuration.
            workflow_id: ID of the workflow.
            data: Optional data to include in the request.

        Returns:
            The created approval request.
        """
        request = ApprovalRequest(
            workflow_id=workflow_id,
            task_id=config.id,
            title=config.title or f"Approval required for {config.id}",
            description=config.description,
            data=data or {},
        )

        # Auto-approve if configured
        if config.auto_approve:
            request.status = ApprovalStatus.APPROVED
            request.approved_by = "system"
            request.approved_at = request.created_at
            logger.info(f"Auto-approved request {request.id}")
            return request

        # Send approval request
        success = await self.provider.send_approval_request(request)
        if success:
            self._pending_approvals[request.id] = request
            logger.info(f"Approval request {request.id} created for node {config.id}")
        else:
            request.status = ApprovalStatus.CANCELLED
            logger.error(f"Failed to send approval request for node {config.id}")

        return request

    async def create_input(
        self,
        config: InputNodeConfig,
        workflow_id: str,
    ) -> InputRequest:
        """Create and send an input request.

        Args:
            config: Input node configuration.
            workflow_id: ID of the workflow.

        Returns:
            The created input request.
        """
        request = InputRequest(
            workflow_id=workflow_id,
            task_id=config.id,
            title=config.title or f"Input required for {config.id}",
            description=config.description,
            input_type=config.input_type,
            required=config.required,
            default_value=config.default_value,
            options=config.options,
            validation=config.validation,
        )

        # Send input request
        success = await self.provider.send_input_request(request)
        if success:
            self._pending_inputs[request.id] = request
            logger.info(f"Input request {request.id} created for node {config.id}")
        else:
            request.status = ApprovalStatus.CANCELLED
            logger.error(f"Failed to send input request for node {config.id}")

        return request

    async def check_approval(self, request_id: str) -> ApprovalRequest:
        """Check the status of an approval request.

        Args:
            request_id: ID of the approval request.

        Returns:
            The current approval request status.
        """
        request = await self.provider.get_approval_status(request_id)

        # Update pending approvals
        if request.status != ApprovalStatus.PENDING:
            self._pending_approvals.pop(request_id, None)

        return request

    async def check_input(self, request_id: str) -> InputRequest:
        """Check the status of an input request.

        Args:
            request_id: ID of the input request.

        Returns:
            The current input request status.
        """
        request = await self.provider.get_input_status(request_id)

        # Update pending inputs
        if request.status != ApprovalStatus.PENDING:
            self._pending_inputs.pop(request_id, None)

        return request

    async def approve(self, request_id: str, actor: str, reason: str | None = None) -> bool:
        """Approve a request.

        Args:
            request_id: ID of the approval request.
            actor: Who approved the request.
            reason: Optional reason for approval.

        Returns:
            True if the approval was successful.
        """
        success = await self.provider.approve(request_id, actor, reason)
        if success:
            self._pending_approvals.pop(request_id, None)
        return success

    async def reject(self, request_id: str, actor: str, reason: str) -> bool:
        """Reject a request.

        Args:
            request_id: ID of the approval request.
            actor: Who rejected the request.
            reason: Reason for rejection.

        Returns:
            True if the rejection was successful.
        """
        success = await self.provider.reject(request_id, actor, reason)
        if success:
            self._pending_approvals.pop(request_id, None)
        return success

    async def submit_input(self, request_id: str, value: Any, actor: str) -> bool:
        """Submit input for a request.

        Args:
            request_id: ID of the input request.
            value: The submitted value.
            actor: Who submitted the input.

        Returns:
            True if the submission was successful.
        """
        success = await self.provider.submit_input(request_id, value, actor)
        if success:
            self._pending_inputs.pop(request_id, None)
        return success

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self._pending_approvals.values())

    def get_pending_inputs(self) -> list[InputRequest]:
        """Get all pending input requests."""
        return list(self._pending_inputs.values())

    def get_history(self, request_id: str | None = None) -> list:
        """Get approval/input history."""
        return self.provider.get_history(request_id)
