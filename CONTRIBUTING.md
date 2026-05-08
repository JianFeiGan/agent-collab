# Contributing to AgentCollab

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/agent-collab.git
cd agent-collab

# Install with dev dependencies
uv sync

# Verify everything works
uv run pytest tests/ -v
uv run ruff check src/ tests/
```

## Running Tests

```bash
uv run pytest tests/ -v           # All tests
uv run pytest tests/test_cli.py   # Single file
uv run pytest -k "test_cycle"     # By name pattern
```

## Code Standards

- **Python 3.11+** with type hints on all public functions
- **Google-style docstrings** on public classes and methods
- **`from __future__ import annotations`** in every module
- **Pydantic** for data validation and config models
- **asyncio** for concurrency (no threading)
- **Rich** for terminal output
- Line length: 100 characters max
- Linting: `uv run ruff check src/ tests/`
- Formatting: `uv run ruff format src/ tests/`

## Adding a New Agent Adapter

Agent adapters let AgentCollab talk to different AI coding tools. To add one:

### 1. Create the adapter

Create `src/agent_collab/agents/your_agent.py`:

```python
from __future__ import annotations

import asyncio
import shutil

from agent_collab.agents.base import AgentResult, BaseAgent


class YourAgent(BaseAgent):
    """Adapter for the YourAgent CLI."""

    @property
    def name(self) -> str:
        return "your-agent"

    def is_available(self) -> bool:
        return shutil.which("your-agent") is not None

    async def execute(
        self,
        prompt: str,
        workdir: str = ".",
        allowed_tools: list[str] | None = None,
        timeout: int = 600,
    ) -> AgentResult:
        cmd = ["your-agent", "--prompt", prompt]
        # Build the command for your agent CLI
        # Run it as a subprocess, handle timeouts and errors
        # Return an AgentResult with success, output, files_changed, etc.
```

### 2. Register it

Add your agent to `AGENT_REGISTRY` in `src/agent_collab/cli.py`:

```python
from agent_collab.agents.your_agent import YourAgent

AGENT_REGISTRY: dict[str, BaseAgent] = {
    # ... existing agents ...
    "your-agent": YourAgent(),
}
```

### 3. Add tests

Create tests in `tests/test_agents.py` using `monkeypatch` to mock `asyncio.create_subprocess_exec`. Follow the existing patterns for `_StubProcess`.

### 4. Update docs

- Add your agent to the table in `README.md`
- Add an example workflow in `examples/`

## Pull Request Guidelines

1. **One feature per PR.** Keep changes focused.
2. **Write tests.** New code needs test coverage.
3. **Run the checklist before submitting:**
   ```bash
   uv run pytest tests/ -v        # All tests pass
   uv run ruff check src/ tests/  # No lint errors
   uv run ruff format src/ tests/ # Code is formatted
   ```
4. **Update docs** if you change public APIs or add features.
5. **Write clear commit messages.** Use conventional format:
   - `feat: add GitLab CI agent adapter`
   - `fix: handle timeout in Claude Code adapter`
   - `docs: update workflow YAML reference`
   - `test: add cycle detection edge cases`

## Project Structure

```
src/agent_collab/
├── cli.py              # Typer CLI entry point
├── core/
│   ├── workflow.py     # YAML parsing + Pydantic models
│   ├── scheduler.py    # DAG topological sort
│   ├── executor.py     # Async task execution
│   └── merger.py       # Git merge strategy
├── agents/
│   ├── base.py         # BaseAgent ABC + AgentResult
│   ├── claude_code.py  # Claude Code adapter
│   ├── codex.py        # Codex adapter
│   └── aider.py        # Aider adapter
├── locks/
│   └── file_lock.py    # fcntl-based file locking
└── display/
    └── progress.py     # Rich TUI progress
```

## Questions?

Open an issue or start a discussion. We're happy to help!
