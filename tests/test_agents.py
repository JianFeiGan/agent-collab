"""Tests for agent adapters with enhanced capability detection."""

from __future__ import annotations

import asyncio

import pytest

from agent_collab.agents.aider import AiderAgent
from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.agents.claude_code import ClaudeCodeAgent
from agent_collab.agents.codex import CodexAgent
from agent_collab.agents.opencode import OpenCodeAgent

# ---------------------------------------------------------------------------
# BaseAgent contract tests
# ---------------------------------------------------------------------------


class TestAgentResult:
    def test_defaults(self) -> None:
        r = AgentResult(success=True, output="ok")
        assert r.files_changed == []
        assert r.duration_seconds == 0.0
        assert r.tokens_used is None

    def test_full_construction(self) -> None:
        r = AgentResult(
            success=False,
            output="err",
            files_changed=["a.py"],
            duration_seconds=1.5,
            tokens_used=100,
        )
        assert not r.success
        assert r.files_changed == ["a.py"]
        assert r.tokens_used == 100


class TestBaseAgentInit:
    def test_defaults(self) -> None:
        """BaseAgent defaults to resume_mode='none' and session_id=None."""

        class DummyAgent(BaseAgent):
            async def execute(self, prompt, workdir, allowed_tools, timeout=600):  # type: ignore[override]
                return AgentResult(success=True, output="")

            def name(self) -> str:  # type: ignore[override]
                return "dummy"

            def is_available(self) -> bool:  # type: ignore[override]
                return False

            def get_cli_version(self) -> str | None:  # type: ignore[override]
                return None

            def get_supported_arguments(self) -> list[str]:  # type: ignore[override]
                return []

            def check_api_key(self) -> tuple[bool, str]:  # type: ignore[override]
                return False, "not configured"

        agent = DummyAgent()
        assert agent.resume_mode == "none"
        assert agent.session_id is None

    def test_custom_resume(self) -> None:
        """resume_mode and session_id can be set at construction time."""

        class DummyAgent(BaseAgent):
            async def execute(self, prompt, workdir, allowed_tools, timeout=600):  # type: ignore[override]
                return AgentResult(success=True, output="")

            def name(self) -> str:  # type: ignore[override]
                return "dummy"

            def is_available(self) -> bool:  # type: ignore[override]
                return False

            def get_cli_version(self) -> str | None:  # type: ignore[override]
                return None

            def get_supported_arguments(self) -> list[str]:  # type: ignore[override]
                return []

            def check_api_key(self) -> tuple[bool, str]:  # type: ignore[override]
                return False, "not configured"

        agent = DummyAgent(resume_mode="resume", session_id="abc-123")
        assert agent.resume_mode == "resume"
        assert agent.session_id == "abc-123"


# ---------------------------------------------------------------------------
# Concrete adapter tests (unit — mock subprocess)
# ---------------------------------------------------------------------------


class _StubProcess:
    """Minimal mock for asyncio.subprocess.Process."""

    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    def kill(self) -> None:
        pass


@pytest.mark.asyncio
async def test_claude_code_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = ClaudeCodeAgent()
    fake_output = '{"result": "done", "files_changed": ["a.py"], "usage": {"total_tokens": 42}}'

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _StubProcess(0, fake_output.encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", ["Read"])
    assert result.success
    assert result.output == "done"
    assert result.files_changed == ["a.py"]
    assert result.tokens_used == 42


@pytest.mark.asyncio
async def test_claude_code_execute_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = ClaudeCodeAgent()

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _StubProcess(1, b"", b"something broke")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", [])
    assert not result.success
    assert "something broke" in result.output


@pytest.mark.asyncio
async def test_claude_code_cli_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = ClaudeCodeAgent()

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", [])
    assert not result.success
    assert "not found" in result.output


@pytest.mark.asyncio
async def test_claude_code_resume_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    """resume_mode='continue' appends --continue to the CLI command."""
    agent = ClaudeCodeAgent(resume_mode="continue")
    fake_output = '{"result": "resumed"}'
    captured_cmd: list[str] = []

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_cmd.extend(args)
        return _StubProcess(0, fake_output.encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("continue task", ".", [])
    assert result.success
    assert "--continue" in captured_cmd


@pytest.mark.asyncio
async def test_claude_code_resume_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """resume_mode='resume' appends --resume {session_id}."""
    agent = ClaudeCodeAgent(resume_mode="resume", session_id="sess-42")
    fake_output = '{"result": "resumed"}'
    captured_cmd: list[str] = []

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_cmd.extend(args)
        return _StubProcess(0, fake_output.encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("resume task", ".", [])
    assert result.success
    assert "--resume" in captured_cmd
    assert "sess-42" in captured_cmd


@pytest.mark.asyncio
async def test_claude_code_resume_without_session_id() -> None:
    """resume_mode='resume' without session_id returns error."""
    agent = ClaudeCodeAgent(resume_mode="resume", session_id=None)
    result = await agent.execute("resume task", ".", [])
    assert not result.success
    assert "session_id" in result.output


@pytest.mark.asyncio
async def test_opencode_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = OpenCodeAgent()

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _StubProcess(0, b"opencode output")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("build it", ".", [])
    assert result.success
    assert "opencode output" in result.output


@pytest.mark.asyncio
async def test_opencode_cli_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = OpenCodeAgent()

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("build it", ".", [])
    assert not result.success
    assert "not found" in result.output


@pytest.mark.asyncio
async def test_opencode_resume_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    """resume_mode='continue' appends --continue to the CLI command."""
    agent = OpenCodeAgent(resume_mode="continue")
    captured_cmd: list[str] = []

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_cmd.extend(args)
        return _StubProcess(0, b"resumed")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("continue task", ".", [])
    assert result.success
    assert "--continue" in captured_cmd


@pytest.mark.asyncio
async def test_opencode_resume_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """resume_mode='resume' appends --resume {session_id}."""
    agent = OpenCodeAgent(resume_mode="resume", session_id="sess-42")
    captured_cmd: list[str] = []

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_cmd.extend(args)
        return _StubProcess(0, b"resumed")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("resume task", ".", [])
    assert result.success
    assert "--resume" in captured_cmd
    assert "sess-42" in captured_cmd


@pytest.mark.asyncio
async def test_opencode_resume_without_session_id() -> None:
    """resume_mode='resume' without session_id returns error."""
    agent = OpenCodeAgent(resume_mode="resume", session_id=None)
    result = await agent.execute("resume task", ".", [])
    assert not result.success
    assert "session_id" in result.output


@pytest.mark.asyncio
async def test_codex_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = CodexAgent()

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _StubProcess(0, b"codex output")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("build it", ".", [])
    assert result.success
    assert "codex output" in result.output


@pytest.mark.asyncio
async def test_aider_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = AiderAgent()

    async def fake_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _StubProcess(0, b"aider output")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("refactor", ".", [])
    assert result.success
    assert "aider output" in result.output


def test_agent_names() -> None:
    assert ClaudeCodeAgent().name() == "claude-code"
    assert CodexAgent().name() == "codex"
    assert AiderAgent().name() == "aider"
    assert OpenCodeAgent().name() == "opencode"


def test_is_available_depends_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_available returns False when CLI is not on PATH."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert not ClaudeCodeAgent().is_available()
    assert not CodexAgent().is_available()
    assert not AiderAgent().is_available()
    assert not OpenCodeAgent().is_available()


# ---------------------------------------------------------------------------
# Enhanced capability detection tests
# ---------------------------------------------------------------------------


class TestCapabilityDetection:
    """Tests for enhanced agent capability detection."""

    def test_get_cli_version_returns_string_or_none(self) -> None:
        """get_cli_version returns string or None."""
        agents = [ClaudeCodeAgent(), CodexAgent(), AiderAgent(), OpenCodeAgent()]
        for agent in agents:
            version = agent.get_cli_version()
            assert version is None or isinstance(version, str)

    def test_get_supported_arguments_returns_list(self) -> None:
        """get_supported_arguments returns list of strings."""
        agents = [ClaudeCodeAgent(), CodexAgent(), AiderAgent(), OpenCodeAgent()]
        for agent in agents:
            args = agent.get_supported_arguments()
            assert isinstance(args, list)
            assert all(isinstance(arg, str) for arg in args)
            assert len(args) > 0

    def test_check_api_key_returns_tuple(self) -> None:
        """check_api_key returns (bool, str) tuple."""
        agents = [ClaudeCodeAgent(), CodexAgent(), AiderAgent(), OpenCodeAgent()]
        for agent in agents:
            result = agent.check_api_key()
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], str)

    def test_claude_code_supported_arguments(self) -> None:
        """Claude Code agent reports correct supported arguments."""
        agent = ClaudeCodeAgent()
        args = agent.get_supported_arguments()
        assert "-p" in args
        assert "--output-format" in args
        assert "--permission-mode" in args
        assert "--max-turns" in args
        assert "--continue" in args
        assert "--resume" in args
        assert "--allowedTools" in args

    def test_codex_supported_arguments(self) -> None:
        """Codex agent reports correct supported arguments."""
        agent = CodexAgent()
        args = agent.get_supported_arguments()
        assert "--quiet" in args
        assert "--full-auto" in args
        assert "--model" in args
        assert "--provider" in args
        assert "--api-key" in args

    def test_aider_supported_arguments(self) -> None:
        """Aider agent reports correct supported arguments."""
        agent = AiderAgent()
        args = agent.get_supported_arguments()
        assert "--yes" in args
        assert "--no-auto-commits" in args
        assert "--no-git" in args
        assert "--message" in args
        assert "--model" in args

    def test_opencode_supported_arguments(self) -> None:
        """OpenCode agent reports correct supported arguments."""
        agent = OpenCodeAgent()
        args = agent.get_supported_arguments()
        assert "--non-interactive" in args
        assert "--model" in args
        assert "--provider" in args
        assert "--api-key" in args
        assert "--continue" in args
        assert "--resume" in args

    def test_check_api_key_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """check_api_key detects environment variables."""
        # Test Claude Code with ANTHROPIC_API_KEY (needs >12 chars for masking)
        test_key = "abcdefghijklmnopqrst"
        monkeypatch.setenv("ANTHROPIC_API_KEY", test_key)
        agent = ClaudeCodeAgent()
        configured, message = agent.check_api_key()
        assert configured is True
        assert "ANTHROPIC_API_KEY" in message
        assert "abcdefgh" in message  # First 8 chars of key

    def test_check_api_key_without_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """check_api_key reports missing environment variables."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        agent = ClaudeCodeAgent()
        configured, message = agent.check_api_key()
        assert configured is False
        assert "not set" in message.lower() or "not found" in message.lower()

    def test_codex_check_api_key_uses_instance_key(self) -> None:
        """Codex check_api_key uses instance api_key if set."""
        agent = CodexAgent(api_key="abcdefghijklmnopqrst")
        configured, message = agent.check_api_key()
        assert configured is True
        assert "OPENAI_API_KEY" in message

    def test_opencode_check_api_key_uses_instance_key(self) -> None:
        """OpenCode check_api_key uses instance api_key if set."""
        agent = OpenCodeAgent(api_key="abcdefghijklmnopqrst")
        configured, message = agent.check_api_key()
        assert configured is True
        assert "API key configured" in message

    def test_get_capabilities_returns_dict(self) -> None:
        """get_capabilities returns complete capability dictionary."""
        agent = ClaudeCodeAgent()
        caps = agent.get_capabilities()

        assert isinstance(caps, dict)
        assert "name" in caps
        assert "available" in caps
        assert "version" in caps
        assert "api_key_configured" in caps
        assert "api_key_message" in caps
        assert "supported_arguments" in caps
        assert "resume_modes" in caps
        assert "supports_json_output" in caps

        assert caps["name"] == "claude-code"
        assert isinstance(caps["available"], bool)
        assert isinstance(caps["api_key_configured"], bool)
        assert isinstance(caps["api_key_message"], str)
        assert isinstance(caps["supported_arguments"], list)
        assert isinstance(caps["resume_modes"], list)
        assert isinstance(caps["supports_json_output"], bool)

    def test_claude_code_capabilities_details(self) -> None:
        """Claude Code capabilities include specific features."""
        agent = ClaudeCodeAgent()
        caps = agent.get_capabilities()

        assert caps["supports_json_output"] is True
        assert "none" in caps["resume_modes"]
        assert "continue" in caps["resume_modes"]
        assert "resume" in caps["resume_modes"]

    def test_codex_capabilities_details(self) -> None:
        """Codex capabilities include specific features."""
        agent = CodexAgent()
        caps = agent.get_capabilities()

        assert caps["name"] == "codex"
        assert "none" in caps["resume_modes"]
        assert "continue" in caps["resume_modes"]
        assert "resume" in caps["resume_modes"]

    def test_aider_capabilities_details(self) -> None:
        """Aider capabilities include specific features."""
        agent = AiderAgent()
        caps = agent.get_capabilities()

        assert caps["name"] == "aider"
        assert "none" in caps["resume_modes"]
        assert "continue" in caps["resume_modes"]
        assert "resume" in caps["resume_modes"]

    def test_opencode_capabilities_details(self) -> None:
        """OpenCode capabilities include specific features."""
        agent = OpenCodeAgent()
        caps = agent.get_capabilities()

        assert caps["name"] == "opencode"
        assert "none" in caps["resume_modes"]
        assert "continue" in caps["resume_modes"]
        assert "resume" in caps["resume_modes"]

    def test_capabilities_include_new_fields(self) -> None:
        """Capabilities include new fields for model selection and multi-file editing."""
        agents = [ClaudeCodeAgent(), CodexAgent(), AiderAgent(), OpenCodeAgent()]
        for agent in agents:
            caps = agent.get_capabilities()
            assert "supports_model_selection" in caps
            assert "supports_multi_file_editing" in caps
            assert "max_concurrent_tasks" in caps
            assert isinstance(caps["supports_model_selection"], bool)
            assert isinstance(caps["supports_multi_file_editing"], bool)
            assert caps["max_concurrent_tasks"] is None or isinstance(
                caps["max_concurrent_tasks"], int
            )

    def test_model_selection_support(self) -> None:
        """All agents support model selection."""
        agents = [ClaudeCodeAgent(), CodexAgent(), AiderAgent(), OpenCodeAgent()]
        for agent in agents:
            assert agent._supports_model_selection() is True

    def test_multi_file_editing_support(self) -> None:
        """Only Aider supports multi-file editing."""
        assert AiderAgent()._supports_multi_file_editing() is True
        assert ClaudeCodeAgent()._supports_multi_file_editing() is False
        assert CodexAgent()._supports_multi_file_editing() is False
        assert OpenCodeAgent()._supports_multi_file_editing() is False

    def test_capabilities_cache(self) -> None:
        """Capabilities are cached after first call."""
        agent = ClaudeCodeAgent()
        caps1 = agent.get_capabilities()
        caps2 = agent.get_capabilities()
        assert caps1 is caps2  # Same object reference due to caching

    def test_get_cli_version_with_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_cli_version parses version output correctly."""
        import subprocess

        class MockCompletedProcess:
            def __init__(self, returncode: int, stdout: str) -> None:
                self.returncode = returncode
                self.stdout = stdout

        def mock_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            return MockCompletedProcess(0, "claude 1.2.3")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/claude")

        agent = ClaudeCodeAgent()
        version = agent.get_cli_version()
        assert version == "1.2.3"

    def test_get_cli_version_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_cli_version returns None on failure."""
        import subprocess

        def mock_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", mock_run)

        agent = ClaudeCodeAgent()
        version = agent.get_cli_version()
        assert version is None
