"""Codex agent adapter."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class CodexAgent(BaseAgent):
    """Agent adapter that invokes the ``codex`` CLI.

    Supports additional Codex-specific options such as ``--model``,
    ``--provider``, and ``--api-key``.
    """

    def __init__(
        self,
        *,
        resume_mode: str = "none",
        session_id: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialise a CodexAgent.

        Args:
            resume_mode: Resume strategy. One of ``'none'``, ``'continue'``, or
                ``'resume'``.
            session_id: Session identifier used when *resume_mode* is
                ``'resume'``.
            model: Model name passed to ``codex --model``.
            provider: Provider name passed to ``codex --provider``.
            api_key: API key passed to ``codex --api-key``.  Falls back to the
                ``OPENAI_API_KEY`` environment variable when *None*.
        """
        super().__init__(resume_mode=resume_mode, session_id=session_id)
        self.model: str | None = model
        self.provider: str | None = provider
        self.api_key: str | None = api_key

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        """Execute a prompt via the ``codex`` CLI.

        Args:
            prompt: The instruction to send to the agent.
            workdir: Working directory for the agent.
            allowed_tools: List of tools the agent may use (unused by codex).
            timeout: Maximum execution time in seconds.

        Returns:
            AgentResult with execution details.
        """
        start = time.monotonic()

        # -- resume mode validation ------------------------------------------------
        if self.resume_mode == "continue":
            resume_args: list[str] = ["--continue"]
        elif self.resume_mode == "resume":
            if self.session_id is None:
                elapsed = time.monotonic() - start
                return AgentResult(
                    success=False,
                    output="resume_mode='resume' requires a session_id",
                    duration_seconds=elapsed,
                )
            resume_args = ["--last-session", self.session_id]
        else:
            resume_args = []

        # -- model / provider / api-key flags ---------------------------------------
        extra_args: list[str] = []
        if self.model is not None:
            extra_args.extend(["--model", self.model])
        if self.provider is not None:
            extra_args.extend(["--provider", self.provider])

        resolved_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if resolved_key:
            extra_args.extend(["--api-key", resolved_key])

        cmd = [
            "codex",
            "--quiet",
            "--full-auto",
            *extra_args,
            *resume_args,
            prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            elapsed = time.monotonic() - start
            return AgentResult(
                success=False,
                output=f"Timed out after {timeout}s",
                duration_seconds=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            return AgentResult(
                success=False,
                output="codex CLI not found. Install with: npm install -g @openai/codex",
                duration_seconds=elapsed,
            )

        elapsed = time.monotonic() - start
        raw = stdout.decode().strip()

        return AgentResult(
            success=proc.returncode == 0,
            output=raw if proc.returncode == 0 else stderr.decode().strip() or raw,
            duration_seconds=elapsed,
        )

    def name(self) -> str:
        """Return the human-readable name of this agent."""
        return "codex"

    def is_available(self) -> bool:
        """Check if the ``codex`` CLI is installed and accessible."""
        return shutil.which("codex") is not None

    def get_cli_version(self) -> str | None:
        """Get Codex CLI version.

        Returns:
            Version string if available, None otherwise.
        """
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[-1]
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return None

    def get_supported_arguments(self) -> list[str]:
        """Get supported CLI arguments for Codex.

        Returns:
            List of supported argument strings.
        """
        return [
            "--quiet",
            "--full-auto",
            "--model",
            "--provider",
            "--api-key",
            "--approval-mode",
            "--continue",
            "--last-session",
        ]

    def check_api_key(self) -> tuple[bool, str]:
        """Check if OpenAI API key is configured.

        Returns:
            Tuple of (is_configured, message).
        """
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if api_key:
            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            return True, f"OPENAI_API_KEY configured: {masked}"
        return False, "OPENAI_API_KEY not set. Set it via environment variable."

    def _get_resume_modes(self) -> list[str]:
        """Get supported resume modes.

        Returns:
            List of supported resume mode strings.
        """
        return ["none", "continue", "resume"]

    def _supports_model_selection(self) -> bool:
        """Codex supports model selection.

        Returns:
            True as Codex supports model selection via --model.
        """
        return True
