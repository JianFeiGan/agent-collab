# AgentCollab — Multi-Agent Orchestration Engine

## Project Overview
A CLI tool for orchestrating multiple AI coding agents (Claude Code, Codex, Aider) to collaborate on software projects. Define workflows in YAML, and AgentCollab handles task scheduling, parallel execution, file locking, and result merging.

## Architecture
- `src/agent_collab/cli.py` — Typer CLI entry point
- `src/agent_collab/core/workflow.py` — YAML workflow parser (Pydantic models)
- `src/agent_collab/core/scheduler.py` — DAG topological sort + parallel execution
- `src/agent_collab/core/executor.py` — Task executor (asyncio + subprocess)
- `src/agent_collab/core/merger.py` — Git merge strategy for task outputs
- `src/agent_collab/agents/base.py` — BaseAgent ABC
- `src/agent_collab/agents/claude_code.py` — Claude Code adapter
- `src/agent_collab/agents/codex.py` — Codex adapter
- `src/agent_collab/agents/aider.py` — Aider adapter
- `src/agent_collab/locks/file_lock.py` — fcntl-based file locking
- `src/agent_collab/display/progress.py` — Rich TUI progress display

## Key Commands
- `uv run agent-collab run workflow.yaml` — Execute a workflow
- `uv run agent-collab validate workflow.yaml` — Validate workflow YAML
- `uv run agent-collab list-agents` — List available agents
- `uv run pytest tests/` — Run tests
- `uv run ruff check src/ tests/` — Lint
- `uv run ruff format src/ tests/` — Format

## Code Standards
- Python 3.11+, type hints on ALL public functions
- Docstrings in Google style
- Use asyncio for concurrency
- Pydantic for data validation
- Rich for terminal output
- No wildcard imports
- Use `from __future__ import annotations` in all modules

## Tech Stack
- Python 3.11+ / PyYAML / Typer / Rich / Pydantic / asyncio / pytest
