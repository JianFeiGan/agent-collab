"""Tests for CLI commands - additional coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from agent_collab.cli import app

runner = CliRunner()


class TestCheckpointsCommand:
    """Tests for checkpoints command."""

    def test_checkpoints_list_empty(self, tmp_path: Path) -> None:
        """Test listing checkpoints when none exist."""
        with patch("agent_collab.cli.CheckpointManager") as mock_manager:
            mock_manager.return_value.list_checkpoints.return_value = []
            result = runner.invoke(app, ["checkpoints", "list"])
            assert result.exit_code == 0
            assert "No checkpoints found" in result.output

    def test_checkpoints_list_with_data(self, tmp_path: Path) -> None:
        """Test listing checkpoints with data."""
        mock_checkpoint = MagicMock()
        mock_checkpoint.checkpoint_id = "cp-123"
        mock_checkpoint.workflow_name = "test-workflow"
        mock_checkpoint.completed_tasks = ["task1", "task2"]
        mock_checkpoint.timestamp = "2024-01-01T00:00:00"
        
        with patch("agent_collab.cli.CheckpointManager") as mock_manager:
            mock_manager.return_value.list_checkpoints.return_value = [mock_checkpoint]
            result = runner.invoke(app, ["checkpoints", "list"])
            assert result.exit_code == 0
            assert "cp-123" in result.output
            assert "test-workflow" in result.output

    def test_checkpoints_delete_success(self, tmp_path: Path) -> None:
        """Test deleting a checkpoint successfully."""
        with patch("agent_collab.cli.CheckpointManager") as mock_manager:
            mock_manager.return_value.delete.return_value = True
            result = runner.invoke(app, ["checkpoints", "delete", "cp-123"])
            assert result.exit_code == 0
            assert "Deleted checkpoint 'cp-123'" in result.output

    def test_checkpoints_delete_not_found(self, tmp_path: Path) -> None:
        """Test deleting a nonexistent checkpoint."""
        with patch("agent_collab.cli.CheckpointManager") as mock_manager:
            mock_manager.return_value.delete.return_value = False
            result = runner.invoke(app, ["checkpoints", "delete", "cp-123"])
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_checkpoints_delete_missing_id(self, tmp_path: Path) -> None:
        """Test deleting without providing checkpoint ID."""
        result = runner.invoke(app, ["checkpoints", "delete"])
        assert result.exit_code != 0

    def test_checkpoints_unknown_action(self, tmp_path: Path) -> None:
        """Test unknown action."""
        result = runner.invoke(app, ["checkpoints", "unknown"])
        assert result.exit_code == 1
        assert "Unknown action" in result.output


class TestReplayCommand:
    """Tests for replay command."""

    def test_replay_workflow_file_not_found(self, tmp_path: Path) -> None:
        """Test replay with nonexistent workflow file."""
        result = runner.invoke(app, ["replay", "cp-123", str(tmp_path / "nonexistent.yaml")])
        assert result.exit_code != 0

    def test_replay_workflow_invalid_yaml(self, tmp_path: Path) -> None:
        """Test replay with invalid YAML."""
        workflow_file = tmp_path / "bad.yaml"
        workflow_file.write_text("invalid: yaml: {{")
        result = runner.invoke(app, ["replay", "cp-123", str(workflow_file)])
        assert result.exit_code != 0

    def test_replay_workflow_unknown_agent(self, tmp_path: Path) -> None:
        """Test replay with unknown agent type."""
        import yaml
        workflow_file = tmp_path / "workflow.yaml"
        workflow_data = {
            "name": "test",
            "agents": {"worker": {"type": "unknown-agent"}},
            "tasks": [{"id": "t1", "agent": "worker", "prompt": "test"}],
        }
        workflow_file.write_text(yaml.dump(workflow_data))
        result = runner.invoke(app, ["replay", "cp-123", str(workflow_file)])
        assert result.exit_code == 1
        assert "Unknown agent type" in result.output


class TestSecurityCommands:
    """Tests for security commands."""

    def test_security_create_user_success(self) -> None:
        """Test creating a user successfully."""
        with patch("agent_collab.security.providers.InMemoryAuthProvider") as mock_provider:
            mock_provider.return_value.create_user = AsyncMock()
            result = runner.invoke(app, ["security-create-user", "testuser", "password123"])
            assert result.exit_code == 0
            assert "User 'testuser' created" in result.output

    def test_security_create_user_invalid_role(self) -> None:
        """Test creating a user with invalid role."""
        result = runner.invoke(app, [
            "security-create-user", "testuser", "password123", "--role", "invalid"
        ])
        assert result.exit_code == 1
        assert "Invalid role" in result.output

    def test_security_login_success(self) -> None:
        """Test successful login."""
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.username = "testuser"
        mock_user.role = MagicMock(value="developer")
        mock_user.tenant_id = "default"
        mock_user.hashed_password = "hashed"
        
        with patch("agent_collab.security.providers.InMemoryAuthProvider") as mock_provider:
            mock_provider.return_value.authenticate = AsyncMock(return_value=mock_user)
            with patch("agent_collab.security.generate_token") as mock_gen_token:
                mock_token = MagicMock()
                mock_token.access_token = "test-token-123"
                mock_token.expires_in = 3600
                mock_gen_token.return_value = mock_token
                result = runner.invoke(app, ["security-login", "testuser", "password123"])
                assert result.exit_code == 0
                assert "Authenticated as 'testuser'" in result.output

    def test_security_login_failure(self) -> None:
        """Test failed login."""
        with patch("agent_collab.security.providers.InMemoryAuthProvider") as mock_provider:
            mock_provider.return_value.authenticate = AsyncMock(return_value=None)
            result = runner.invoke(app, ["security-login", "testuser", "wrongpassword"])
            assert result.exit_code == 1
            assert "Authentication failed" in result.output

    def test_security_verify_token_valid(self) -> None:
        """Test verifying a valid token."""
        mock_payload = {"sub": "user-123", "exp": 1234567890}
        with patch("agent_collab.security.verify_token", return_value=mock_payload):
            result = runner.invoke(app, ["security-verify-token", "valid-token"])
            assert result.exit_code == 0
            assert "Token is valid" in result.output

    def test_security_verify_token_invalid(self) -> None:
        """Test verifying an invalid token."""
        with patch("agent_collab.security.verify_token", return_value=None):
            result = runner.invoke(app, ["security-verify-token", "invalid-token"])
            assert result.exit_code == 1
            assert "Token is invalid" in result.output


class TestDistributedCommand:
    """Tests for distributed status command."""

    def test_distributed_status(self) -> None:
        """Test showing distributed status."""
        with patch("agent_collab.distributed.queue.InMemoryTaskQueue") as mock_queue:
            with patch("agent_collab.distributed.queue.InMemoryWorkerManager") as mock_wm:
                mock_queue.return_value.get_queue_size = AsyncMock(return_value=5)
                mock_wm.return_value.get_worker_stats = AsyncMock(return_value={
                    "total_workers": 3,
                    "idle_workers": 2,
                    "busy_workers": 1,
                    "total_capacity": 10,
                    "current_tasks": 1,
                })
                result = runner.invoke(app, ["distributed-status"])
                assert result.exit_code == 0
                assert "Distributed Status" in result.output
                assert "5" in result.output
                assert "3" in result.output


class TestHITLCommand:
    """Tests for HITL pending command."""

    def test_hitl_pending_empty(self) -> None:
        """Test showing pending HITL requests when none exist."""
        with patch("agent_collab.hitl.InMemoryProvider") as mock_provider:
            with patch("agent_collab.hitl.nodes.HITLManager") as mock_manager:
                mock_manager.return_value.get_pending_approvals.return_value = []
                mock_manager.return_value.get_pending_inputs.return_value = []
                result = runner.invoke(app, ["hitl-pending"])
                assert result.exit_code == 0
                assert "No pending HITL requests" in result.output

    def test_hitl_pending_with_approvals(self) -> None:
        """Test showing pending HITL requests with approvals."""
        mock_approval = MagicMock()
        mock_approval.id = "approval-12345678"
        mock_approval.task_id = "task1"
        mock_approval.title = "Test Approval"
        mock_approval.status.value = "pending"
        
        with patch("agent_collab.hitl.InMemoryProvider") as mock_provider:
            with patch("agent_collab.hitl.nodes.HITLManager") as mock_manager:
                mock_manager.return_value.get_pending_approvals.return_value = [mock_approval]
                mock_manager.return_value.get_pending_inputs.return_value = []
                result = runner.invoke(app, ["hitl-pending"])
                assert result.exit_code == 0
                assert "Pending Approvals" in result.output
                assert "task1" in result.output

    def test_hitl_pending_with_inputs(self) -> None:
        """Test showing pending HITL requests with inputs."""
        mock_input = MagicMock()
        mock_input.id = "input-12345678"
        mock_input.task_id = "task1"
        mock_input.title = "Test Input"
        mock_input.input_type.value = "text"
        mock_input.status.value = "pending"
        
        with patch("agent_collab.hitl.InMemoryProvider") as mock_provider:
            with patch("agent_collab.hitl.nodes.HITLManager") as mock_manager:
                mock_manager.return_value.get_pending_approvals.return_value = []
                mock_manager.return_value.get_pending_inputs.return_value = [mock_input]
                result = runner.invoke(app, ["hitl-pending"])
                assert result.exit_code == 0
                assert "Pending Inputs" in result.output
                assert "task1" in result.output