"""Tests for HITL (Human-in-the-Loop) module."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from agent_collab.hitl import (
    ApprovalHistory,
    ApprovalRequest,
    ApprovalStatus,
    InMemoryProvider,
    InputRequest,
    InputType,
)
from agent_collab.hitl.nodes import (
    ApprovalNodeConfig,
    HITLManager,
    InputNodeConfig,
    ReviewNodeConfig,
)


class TestApprovalRequest:
    """Tests for ApprovalRequest."""

    def test_default_values(self):
        request = ApprovalRequest()
        assert request.id is not None
        assert request.workflow_id == ""
        assert request.task_id == ""
        assert request.title == ""
        assert request.description == ""
        assert request.data == {}
        assert request.status == ApprovalStatus.PENDING
        assert request.approved_by is None
        assert request.approved_at is None
        assert request.rejection_reason is None

    def test_custom_values(self):
        request = ApprovalRequest(
            workflow_id="wf_1",
            task_id="task_1",
            title="Test Approval",
            description="Please approve this",
            data={"key": "value"},
        )
        assert request.workflow_id == "wf_1"
        assert request.task_id == "task_1"
        assert request.title == "Test Approval"
        assert request.description == "Please approve this"
        assert request.data == {"key": "value"}


class TestInputRequest:
    """Tests for InputRequest."""

    def test_default_values(self):
        request = InputRequest()
        assert request.id is not None
        assert request.workflow_id == ""
        assert request.task_id == ""
        assert request.title == ""
        assert request.description == ""
        assert request.input_type == InputType.TEXT
        assert request.required is True
        assert request.default_value is None
        assert request.options == []
        assert request.validation == {}
        assert request.status == ApprovalStatus.PENDING
        assert request.submitted_by is None
        assert request.submitted_at is None
        assert request.submitted_value is None

    def test_custom_values(self):
        request = InputRequest(
            workflow_id="wf_1",
            task_id="task_1",
            title="Select Option",
            description="Choose an option",
            input_type=InputType.SELECT,
            required=True,
            options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
        )
        assert request.workflow_id == "wf_1"
        assert request.task_id == "task_1"
        assert request.title == "Select Option"
        assert request.input_type == InputType.SELECT
        assert len(request.options) == 2


class TestApprovalHistory:
    """Tests for ApprovalHistory."""

    def test_default_values(self):
        history = ApprovalHistory()
        assert history.id is not None
        assert history.request_id == ""
        assert history.action == ""
        assert history.actor == ""
        assert history.reason is None
        assert history.metadata == {}

    def test_custom_values(self):
        history = ApprovalHistory(
            request_id="req_1",
            action="approve",
            actor="user_1",
            reason="Looks good",
        )
        assert history.request_id == "req_1"
        assert history.action == "approve"
        assert history.actor == "user_1"
        assert history.reason == "Looks good"


class TestInMemoryProvider:
    """Tests for InMemoryProvider."""

    @pytest.fixture
    def provider(self):
        return InMemoryProvider()

    @pytest.fixture
    def approval_request(self):
        return ApprovalRequest(
            workflow_id="wf_1",
            task_id="task_1",
            title="Test Approval",
        )

    @pytest.fixture
    def input_request(self):
        return InputRequest(
            workflow_id="wf_1",
            task_id="task_1",
            title="Test Input",
            input_type=InputType.TEXT,
        )

    async def test_send_approval_request(self, provider, approval_request):
        result = await provider.send_approval_request(approval_request)
        assert result is True
        assert approval_request.id in provider._requests

    async def test_get_approval_status(self, provider, approval_request):
        await provider.send_approval_request(approval_request)
        result = await provider.get_approval_status(approval_request.id)
        assert result.id == approval_request.id
        assert result.status == ApprovalStatus.PENDING

    async def test_approve(self, provider, approval_request):
        await provider.send_approval_request(approval_request)
        result = await provider.approve(approval_request.id, "user_1", "Looks good")
        assert result is True

        request = await provider.get_approval_status(approval_request.id)
        assert request.status == ApprovalStatus.APPROVED
        assert request.approved_by == "user_1"
        assert request.approved_at is not None

    async def test_reject(self, provider, approval_request):
        await provider.send_approval_request(approval_request)
        result = await provider.reject(approval_request.id, "user_1", "Needs changes")
        assert result is True

        request = await provider.get_approval_status(approval_request.id)
        assert request.status == ApprovalStatus.REJECTED
        assert request.rejection_reason == "Needs changes"

    async def test_send_input_request(self, provider, input_request):
        result = await provider.send_input_request(input_request)
        assert result is True
        assert input_request.id in provider._input_requests

    async def test_get_input_status(self, provider, input_request):
        await provider.send_input_request(input_request)
        result = await provider.get_input_status(input_request.id)
        assert result.id == input_request.id
        assert result.status == ApprovalStatus.PENDING

    async def test_submit_input(self, provider, input_request):
        await provider.send_input_request(input_request)
        result = await provider.submit_input(input_request.id, "test value", "user_1")
        assert result is True

        request = await provider.get_input_status(input_request.id)
        assert request.status == ApprovalStatus.APPROVED
        assert request.submitted_by == "user_1"
        assert request.submitted_value == "test value"
        assert request.submitted_at is not None

    async def test_get_history(self, provider, approval_request):
        await provider.send_approval_request(approval_request)
        await provider.approve(approval_request.id, "user_1", "Looks good")

        history = provider.get_history(approval_request.id)
        assert len(history) == 1
        assert history[0].action == "approve"
        assert history[0].actor == "user_1"

    async def test_get_all_history(self, provider, approval_request, input_request):
        await provider.send_approval_request(approval_request)
        await provider.approve(approval_request.id, "user_1", "Looks good")

        await provider.send_input_request(input_request)
        await provider.submit_input(input_request.id, "value", "user_2")

        history = provider.get_history()
        assert len(history) == 2


class TestApprovalNodeConfig:
    """Tests for ApprovalNodeConfig."""

    def test_default_values(self):
        config = ApprovalNodeConfig(id="approval_1")
        assert config.id == "approval_1"
        assert config.title == ""
        assert config.description == ""
        assert config.required_approvals == 1
        assert config.timeout_seconds == 3600
        assert config.auto_approve is False
        assert config.depends_on == []
        assert config.next_on_approve == ""
        assert config.next_on_reject == ""

    def test_custom_values(self):
        config = ApprovalNodeConfig(
            id="approval_1",
            title="Deploy Approval",
            description="Please approve deployment",
            required_approvals=2,
            timeout_seconds=7200,
            auto_approve=False,
            depends_on=["task_1"],
            next_on_approve="deploy",
            next_on_reject="fix",
        )
        assert config.title == "Deploy Approval"
        assert config.required_approvals == 2
        assert config.timeout_seconds == 7200
        assert config.next_on_approve == "deploy"
        assert config.next_on_reject == "fix"


class TestInputNodeConfig:
    """Tests for InputNodeConfig."""

    def test_default_values(self):
        config = InputNodeConfig(id="input_1")
        assert config.id == "input_1"
        assert config.title == ""
        assert config.description == ""
        assert config.input_type == InputType.TEXT
        assert config.required is True
        assert config.default_value is None
        assert config.options == []
        assert config.validation == {}
        assert config.timeout_seconds == 3600
        assert config.depends_on == []
        assert config.next_node == ""

    def test_custom_values(self):
        config = InputNodeConfig(
            id="input_1",
            title="Select Environment",
            description="Choose deployment environment",
            input_type=InputType.SELECT,
            required=True,
            options=[
                {"label": "Production", "value": "prod"},
                {"label": "Staging", "value": "staging"},
            ],
            timeout_seconds=1800,
            depends_on=["task_1"],
            next_node="deploy",
        )
        assert config.title == "Select Environment"
        assert config.input_type == InputType.SELECT
        assert len(config.options) == 2
        assert config.next_node == "deploy"


class TestReviewNodeConfig:
    """Tests for ReviewNodeConfig."""

    def test_default_values(self):
        config = ReviewNodeConfig(id="review_1")
        assert config.id == "review_1"
        assert config.title == ""
        assert config.description == ""
        assert config.review_items == []
        assert config.required_approvals == 1
        assert config.timeout_seconds == 3600
        assert config.depends_on == []
        assert config.next_on_approve == ""
        assert config.next_on_reject == ""

    def test_custom_values(self):
        config = ReviewNodeConfig(
            id="review_1",
            title="Code Review",
            description="Review code changes",
            review_items=["file1.py", "file2.py"],
            required_approvals=2,
            timeout_seconds=7200,
            depends_on=["task_1"],
            next_on_approve="merge",
            next_on_reject="fix",
        )
        assert config.title == "Code Review"
        assert len(config.review_items) == 2
        assert config.required_approvals == 2


class TestHITLManager:
    """Tests for HITLManager."""

    @pytest.fixture
    def provider(self):
        return InMemoryProvider()

    @pytest.fixture
    def manager(self, provider):
        return HITLManager(provider)

    async def test_create_approval(self, manager):
        config = ApprovalNodeConfig(
            id="approval_1",
            title="Deploy Approval",
            description="Please approve deployment",
        )

        request = await manager.create_approval(config, "wf_1", {"env": "prod"})

        assert request.workflow_id == "wf_1"
        assert request.task_id == "approval_1"
        assert request.title == "Deploy Approval"
        assert request.data == {"env": "prod"}
        assert request.status == ApprovalStatus.PENDING

    async def test_create_approval_auto_approve(self, manager):
        config = ApprovalNodeConfig(
            id="approval_1",
            title="Auto Approve",
            auto_approve=True,
        )

        request = await manager.create_approval(config, "wf_1")

        assert request.status == ApprovalStatus.APPROVED
        assert request.approved_by == "system"

    async def test_create_input(self, manager):
        config = InputNodeConfig(
            id="input_1",
            title="Select Environment",
            description="Choose deployment environment",
            input_type=InputType.SELECT,
            options=[
                {"label": "Production", "value": "prod"},
                {"label": "Staging", "value": "staging"},
            ],
        )

        request = await manager.create_input(config, "wf_1")

        assert request.workflow_id == "wf_1"
        assert request.task_id == "input_1"
        assert request.title == "Select Environment"
        assert request.input_type == InputType.SELECT
        assert len(request.options) == 2
        assert request.status == ApprovalStatus.PENDING

    async def test_check_approval(self, manager):
        config = ApprovalNodeConfig(id="approval_1", title="Test")
        request = await manager.create_approval(config, "wf_1")

        # Check pending status
        result = await manager.check_approval(request.id)
        assert result.status == ApprovalStatus.PENDING

        # Approve
        await manager.approve(request.id, "user_1")

        # Check approved status
        result = await manager.check_approval(request.id)
        assert result.status == ApprovalStatus.APPROVED
        assert result.approved_by == "user_1"

    async def test_check_input(self, manager):
        config = InputNodeConfig(id="input_1", title="Test")
        request = await manager.create_input(config, "wf_1")

        # Check pending status
        result = await manager.check_input(request.id)
        assert result.status == ApprovalStatus.PENDING

        # Submit input
        await manager.submit_input(request.id, "value", "user_1")

        # Check approved status
        result = await manager.check_input(request.id)
        assert result.status == ApprovalStatus.APPROVED
        assert result.submitted_value == "value"

    async def test_approve(self, manager):
        config = ApprovalNodeConfig(id="approval_1", title="Test")
        request = await manager.create_approval(config, "wf_1")

        result = await manager.approve(request.id, "user_1", "Looks good")
        assert result is True

        # Check it's no longer pending
        pending = manager.get_pending_approvals()
        assert len(pending) == 0

    async def test_reject(self, manager):
        config = ApprovalNodeConfig(id="approval_1", title="Test")
        request = await manager.create_approval(config, "wf_1")

        result = await manager.reject(request.id, "user_1", "Needs changes")
        assert result is True

        # Check it's no longer pending
        pending = manager.get_pending_approvals()
        assert len(pending) == 0

    async def test_submit_input(self, manager):
        config = InputNodeConfig(id="input_1", title="Test")
        request = await manager.create_input(config, "wf_1")

        result = await manager.submit_input(request.id, "value", "user_1")
        assert result is True

        # Check it's no longer pending
        pending = manager.get_pending_inputs()
        assert len(pending) == 0

    async def test_get_pending_approvals(self, manager):
        config1 = ApprovalNodeConfig(id="approval_1", title="Test 1")
        config2 = ApprovalNodeConfig(id="approval_2", title="Test 2")

        await manager.create_approval(config1, "wf_1")
        await manager.create_approval(config2, "wf_1")

        pending = manager.get_pending_approvals()
        assert len(pending) == 2

    async def test_get_pending_inputs(self, manager):
        config1 = InputNodeConfig(id="input_1", title="Test 1")
        config2 = InputNodeConfig(id="input_2", title="Test 2")

        await manager.create_input(config1, "wf_1")
        await manager.create_input(config2, "wf_1")

        pending = manager.get_pending_inputs()
        assert len(pending) == 2

    async def test_get_history(self, manager):
        config = ApprovalNodeConfig(id="approval_1", title="Test")
        request = await manager.create_approval(config, "wf_1")

        await manager.approve(request.id, "user_1", "Looks good")

        history = manager.get_history(request.id)
        assert len(history) == 1
        assert history[0].action == "approve"
        assert history[0].actor == "user_1"
