"""Aider agent adapter."""

from __future__ import annotations

import asyncio
import shutil
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class AiderAgent(BaseAgent):
    """Agent adapter that invokes the ``aider`` CLI."""

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        start = time.monotonic()

        cmd = [
            "aider",
            "--yes",
            "--no-auto-commits",
            "--no-git",
            "--message", prompt,
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
        return "aider"

    def is_available(self) -> bool:
        return shutil.which("aider") is not None
