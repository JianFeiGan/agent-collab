"""OpenCode agent adapter."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class OpenCodeAgent(BaseAgent):
    """Agent adapter that invokes the ``opencode`` CLI."""

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        start = time.monotonic()

        cmd: list[str] = ["opencode", "--non-interactive", prompt]

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
        ]

    def check_api_key(self) -> tuple[bool, str]:
        """Check if required API keys are configured.

        OpenCode supports multiple providers.

        Returns:
            Tuple of (is_configured, message).
        """
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
