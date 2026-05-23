"""OpenCode agent adapter."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class OpenCodeAgent(BaseAgent):
    """Agent adapter that invokes the ``opencode`` CLI.

    Supports resume session via ``--continue`` and ``--resume`` arguments,
    model selection via ``--model``, and provider configuration via
    ``--provider``.
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
        """Initialise an OpenCodeAgent.

        Args:
            resume_mode: Resume strategy. One of ``'none'``, ``'continue'``, or
                ``'resume'``.
            session_id: Session identifier used when *resume_mode* is
                ``'resume'``.
            model: Model name passed to ``opencode --model``.
            provider: Provider name passed to ``opencode --provider``.
            api_key: API key passed to ``opencode --api-key``.  Falls back to
                environment variables when *None*.
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
        """Execute a prompt via the ``opencode`` CLI.

        Args:
            prompt: The instruction to send to the agent.
            workdir: Working directory for the agent.
            allowed_tools: List of tools the agent may use (unused by opencode).
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
            resume_args = ["--resume", self.session_id]
        else:
            resume_args = []

        # -- model / provider / api-key flags ---------------------------------------
        extra_args: list[str] = []
        if self.model is not None:
            extra_args.extend(["--model", self.model])
        if self.provider is not None:
            extra_args.extend(["--provider", self.provider])

        resolved_key = (
            self.api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        if resolved_key:
            extra_args.extend(["--api-key", resolved_key])

        cmd: list[str] = [
            "opencode",
            "--non-interactive",
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
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
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
                output=(
                    "opencode CLI not found. "
                    "Install with: go install github.com/opencode-ai/opencode@latest"
                ),
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
        return "opencode"

    def is_available(self) -> bool:
        """Check if the ``opencode`` CLI is installed and accessible."""
        return shutil.which("opencode") is not None

    def get_cli_version(self) -> str | None:
        """Get OpenCode CLI version.

        Returns:
            Version string if available, None otherwise.
        """
        try:
            result = subprocess.run(
                ["opencode", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from output like "opencode 0.1.0"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[-1]
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return None

    def get_supported_arguments(self) -> list[str]:
        """Get supported CLI arguments for OpenCode.

        Returns:
            List of supported argument strings.
        """
        return [
            "--non-interactive",
            "--model",
            "--provider",
            "--api-key",
            "--continue",
            "--resume",
        ]

    def check_api_key(self) -> tuple[bool, str]:
        """Check if required API keys are configured.

        OpenCode supports multiple providers.

        Returns:
            Tuple of (is_configured, message).
        """
        # Check instance api_key first
        if self.api_key:
            masked = (
                self.api_key[:8] + "..." + self.api_key[-4:]
                if len(self.api_key) > 12
                else "***"
            )
            return True, f"API key configured: {masked}"

        providers = {
            "ANTHROPIC_API_KEY": "Anthropic",
            "OPENAI_API_KEY": "OpenAI",
        }
        configured = []
        for env_var, provider_name in providers.items():
            key = os.environ.get(env_var)
            if key:
                masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                configured.append(f"{provider_name} ({env_var}={masked})")

        if configured:
            return True, f"API keys configured: {', '.join(configured)}"
        return False, "No API keys found. Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY"

    def _get_resume_modes(self) -> list[str]:
        """Get supported resume modes.

        Returns:
            List of supported resume mode strings.
        """
        return ["none", "continue", "resume"]

    def _supports_model_selection(self) -> bool:
        """OpenCode supports model selection.

        Returns:
            True as OpenCode supports model selection via --model.
        """
        return True
