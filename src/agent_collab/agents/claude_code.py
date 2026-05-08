"""Claude Code agent adapter."""

from __future__ import annotations

import asyncio
import json
import shutil
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
        except asyncio.TimeoutError:
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
                output="claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
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
