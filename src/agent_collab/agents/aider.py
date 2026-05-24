"""Aider agent adapter."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class AiderAgent(BaseAgent):
    """Agent adapter that invokes the ``aider`` CLI.

    Supports multi-file editing via ``--file``, model selection via ``--model``,
    and session resumption via ``--resume-session`` / ``--session``.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        files: list[str] | None = None,
        resume_mode: str = "none",
        session_id: str | None = None,
    ) -> None:
        """Initialise an AiderAgent.

        Args:
            model: Model name to pass to ``aider --model`` (e.g.
                ``'gpt-4o'``, ``'anthropic/claude-3-5-sonnet'``).  When
                *None*, aider uses its default model.
            files: List of file paths to add to the aider editing session.
                Each is passed as a ``--file`` argument.
            resume_mode: Resume strategy.  ``'none'`` starts a fresh session,
                ``'continue'`` resumes the last session, and ``'resume'``
                resumes a specific session identified by *session_id*.
            session_id: Aider session id used when *resume_mode* is
                ``'resume'``.
        """
        super().__init__(resume_mode=resume_mode, session_id=session_id)
        self.model: str | None = model
        self.files: list[str] = list(files) if files else []

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        """Execute a prompt via ``aider``.

        Args:
            prompt: The instruction to send to aider.
            workdir: Working directory for the aider process.
            allowed_tools: Accepted for interface compatibility (unused).
            timeout: Maximum execution time in seconds.

        Returns:
            AgentResult with execution details.
        """
        start = time.monotonic()

        cmd: list[str] = [
            "aider",
            "--yes",
            "--no-auto-commits",
            "--no-git",
        ]

        # -- model selection --
        if self.model is not None:
            cmd.extend(["--model", self.model])

        # -- multi-file editing --
        for fpath in self.files:
            cmd.extend(["--file", fpath])

        # -- session resume --
        if self.resume_mode == "continue":
            cmd.append("--resume-session")
        elif self.resume_mode == "resume":
            if self.session_id is None:
                elapsed = time.monotonic() - start
                return AgentResult(
                    success=False,
                    output="resume_mode='resume' requires a session_id",
                    duration_seconds=elapsed,
                )
            cmd.extend(["--session", self.session_id])

        # -- prompt (must come last) --
        cmd.extend(["--message", prompt])

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
                output="aider CLI not found. Install with: pip install aider-chat",
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
        """Return the agent name."""
        return "aider"

    def is_available(self) -> bool:
        """Check if the ``aider`` CLI is on PATH."""
        return shutil.which("aider") is not None

    def get_cli_version(self) -> str | None:
        """Get Aider CLI version.

        Returns:
            Version string if available, None otherwise.
        """
        try:
            result = subprocess.run(
                ["aider", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from output like "aider 0.1.0"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[-1]
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return None

    def get_supported_arguments(self) -> list[str]:
        """Get supported CLI arguments for Aider.

        Returns:
            List of supported argument strings.
        """
        return [
            "--yes",
            "--no-auto-commits",
            "--no-git",
            "--message",
            "--model",
            "--file",
            "--resume-session",
            "--session",
            "--edit-format",
            "--map-tokens",
            "--no-pretty",
            "--no-stream",
        ]

    def check_api_key(self) -> tuple[bool, str]:
        """Check if required API keys are configured.

        Aider supports multiple providers, so checks several key names.

        Returns:
            Tuple of (is_configured, message).
        """
        providers = {
            "ANTHROPIC_API_KEY": "Anthropic",
            "OPENAI_API_KEY": "OpenAI",
            "GEMINI_API_KEY": "Google Gemini",
        }
        configured = []
        for env_var, provider_name in providers.items():
            key = os.environ.get(env_var)
            if key:
                masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                configured.append(f"{provider_name} ({env_var}={masked})")

        if configured:
            return True, f"API keys configured: {', '.join(configured)}"
        return False, (
            "No API keys found. Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY"
        )

    def _get_resume_modes(self) -> list[str]:
        """Get supported resume modes.

        Returns:
            List of supported resume mode strings.
        """
        return ["none", "continue", "resume"]

    def _supports_model_selection(self) -> bool:
        """Aider supports model selection.

        Returns:
            True as Aider supports model selection via --model.
        """
        return True

    def _supports_multi_file_editing(self) -> bool:
        """Aider supports multi-file editing.

        Returns:
            True as Aider supports multi-file editing via --file.
        """
        return True
