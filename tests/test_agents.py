"""Tests for agent adapters."""

from __future__ import annotations

import asyncio

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.agents.claude_code import ClaudeCodeAgent
from agent_collab.agents.codex import CodexAgent
from agent_collab.agents.aider import AiderAgent


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


def test_is_available_depends_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_available returns False when CLI is not on PATH."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert not ClaudeCodeAgent().is_available()
    assert not CodexAgent().is_available()
    assert not AiderAgent().is_available()
