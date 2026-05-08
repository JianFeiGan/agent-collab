"""Tests for agent adapters."""

from __future__ import annotations

import asyncio

import pytest
from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.agents.claude_code import ClaudeCodeAgent
from agent_collab.agents.codex import CodexAgent
from agent_collab.agents.aider import AiderAgent
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
