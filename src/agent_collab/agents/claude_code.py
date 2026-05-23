"""Claude Code agent adapter."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class ClaudeCodeAgent(BaseAgent):
    """Agent adapter that invokes the ``claude`` CLI in print mode."""

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        start = time.monotonic()

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
            "--max-turns", "50",
        ]
        if self.resume_mode == "continue":
            cmd.append("--continue")
        elif self.resume_mode == "resume":
            if self.session_id is None:
                elapsed = time.monotonic() - start
                return AgentResult(
                    success=False,
                    output="resume_mode='resume' requires a session_id",
                    duration_seconds=elapsed,
                )
            cmd.extend(["--resume", self.session_id])
        for tool in allowed_tools:
            cmd.extend(["--allowedTools", tool])

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
                    "claude CLI not found. "
                    "Install with: npm install -g @anthropic-ai/claude-code"
                ),
                duration_seconds=elapsed,
            )

        elapsed = time.monotonic() - start
        raw = stdout.decode().strip()

        if proc.returncode != 0:
            return AgentResult(
                success=False,
                output=stderr.decode().strip() or raw,
                duration_seconds=elapsed,
            )

        return self._parse_output(raw, elapsed)

    def _parse_output(self, raw: str, elapsed: float) -> AgentResult:
        """Parse JSON output from ``claude -p --output-format json``."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return AgentResult(
                success=True,
                output=raw,
                duration_seconds=elapsed,
            )

        result_text = data.get("result", raw)
        files = data.get("files_changed", [])
        tokens = data.get("usage", {}).get("total_tokens")

        return AgentResult(
            success=True,
            output=result_text,
            files_changed=files,
            duration_seconds=elapsed,
            tokens_used=tokens,
        )

    def name(self) -> str:
        return "claude-code"

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def get_cli_version(self) -> str | None:
        """Get Claude Code CLI version.

        Returns:
            Version string if available, None otherwise.
        """
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from output like "claude 1.0.0"
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[-1]
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return None

    def get_supported_arguments(self) -> list[str]:
        """Get supported CLI arguments for Claude Code.

        Returns:
            List of supported argument strings.
        """
        return [
            "-p", "--print",
            "--output-format",
            "--permission-mode",
            "--max-turns",
            "--continue",
            "--resume",
            "--allowedTools",
            "--model",
            "--system-prompt",
            "--verbose",
        ]

    def check_api_key(self) -> tuple[bool, str]:
        """Check if Anthropic API key is configured.

        Returns:
            Tuple of (is_configured, message).
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            return True, f"ANTHROPIC_API_KEY configured: {masked}"
        return False, "ANTHROPIC_API_KEY not set. Set it via environment variable."

    def _get_resume_modes(self) -> list[str]:
        """Get supported resume modes.

        Returns:
            List of supported resume mode strings.
        """
        return ["none", "continue", "resume"]

    def _supports_json_output(self) -> bool:
        """Claude Code supports JSON output format.

        Returns:
            True as Claude Code supports JSON output.
        """
        return True
