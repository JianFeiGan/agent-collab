# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Is This?

AgentCollab is a CLI that orchestrates multiple AI coding agents (Claude Code, Codex, Aider, OpenCode) on collaborative software projects. Users define workflows in YAML; the engine resolves a DAG, runs independent tasks in parallel via asyncio + subprocess, applies file locks to prevent write conflicts, and merges results through git branches.

## Commands

```bash
# Setup
uv sync --dev                          # Install all deps including dev extras

# Run tests
uv run pytest tests/ -v --tb=short     # All tests
uv run pytest tests/test_scheduler.py -v  # Single test file
uv run pytest tests/test_scheduler.py::test_name -v  # Single test
uv run pytest tests/ --cov=agent_collab --cov-report=term-missing  # Coverage

# Lint & format
uv run ruff check src/ tests/          # Lint
uv run ruff check src/ tests/ --fix    # Lint + auto-fix
uv run ruff format src/ tests/         # Format
uv run ruff format --check src/ tests/ # Format check (CI uses this)

# CLI usage
uv run agent-collab run workflow.yaml
uv run agent-collab validate workflow.yaml
uv run agent-collab list-agents
```

CI runs on Python 3.11/3.12/3.13. `pytest-asyncio` is configured with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorator needed.

## Architecture

The execution pipeline flows: **YAML → parse → DAG sort → parallel dispatch → agent subprocess → file lock → merge**.

### Core Pipeline (`src/agent_collab/core/`)

- **`workflow.py`** — `WorkflowParser` loads YAML into Pydantic models (`WorkflowConfig`, `TaskConfig`, `AgentConfig`, `StrategyConfig`). Supports `include:` for composing workflows, `${VAR}` / `${VAR:-default}` variable resolution, and `${task_id.output}` cross-task references. Cycle detection uses three-color DFS. Also defines `ConditionEvaluator` and `LoopExpander` for advanced flow control (conditions/loops in YAML).
- **`scheduler.py`** — `TaskScheduler` builds the DAG adjacency list from `depends_on` fields, uses Kahn's algorithm for topological sort, groups tasks into parallel execution levels, and respects `priority` ordering within each level. Tasks with unsatisfied `when` clauses are skipped without blocking dependents.
- **`executor.py`** — `TaskExecutor` dispatches tasks via `asyncio.Semaphore`-limited parallelism. Key behaviors: exponential backoff retries with jitter, adaptive concurrency (adjusts parallelism based on recent task durations), file locking per task outputs, degradation policies (`skip`/`abort`/`continue`), checkpoint auto-save, and lifecycle hook dispatch. Tracks execution log and task outputs for `${task_id.output}` resolution.
- **`merger.py`** — `ResultMerger` creates per-task git branches (`agent-collab/<task_id>`), commits task outputs, and merges back with `--no-ff`.
- **`checkpoint.py`** / **`replay.py`** — Checkpoint persistence and workflow replay from saved state.
- **`degradation.py`** — Task degradation policies for handling failures gracefully.

### Agent Adapters (`src/agent_collab/agents/`)

All agents extend `BaseAgent` (ABC) and implement: `execute()`, `name()`, `is_available()`, `get_cli_version()`, `get_supported_arguments()`, `check_api_key()`. The base class also provides `get_capabilities()` with introspection (resume modes, JSON output support, model selection, etc.).

Four adapters: `claude_code.py`, `codex.py`, `aider.py`, `opencode.py`. Each shells out to its respective CLI tool via `asyncio.create_subprocess_exec`.

### Plugin System (`src/agent_collab/plugins/`)

Three plugin types defined in `interfaces.py`: `AgentPlugin` (provides new agents), `HookPlugin` (lifecycle hooks: before/after/failure), `FormatterPlugin` (output formatting). `HookRegistry` in `hooks.py` manages dispatch. Plugins can be registered via `pyproject.toml` entry points (`[project.entry-points."agent_collab.plugins"]`).

### Other Subsystems

- **`security/`** — RBAC with roles (admin/manager/developer/viewer), JWT-like tokens (stdlib-only HMAC-SHA256, no PyJWT), multi-tenancy, API key management, audit logging. All providers are ABCs; `InMemoryAuthProvider` for development.
- **`hitl/`** — Human-in-the-loop approval/input nodes. `HITLProvider` ABC with `InMemoryProvider` (testing) and `WebhookProvider` (webhook notifications).
- **`distributed/`** — `InMemoryTaskQueue` and `InMemoryWorkerManager` for distributed task scheduling (infrastructure only, no real message broker).
- **`observability/`** — `TokenTracker` (token usage tracking), `TimingStats` (timing statistics), `DAGVisualizer` (DAG visualization).
- **`storage/`** — `LogManager` (JSON log persistence), `ExecutionHistory` (SQLite-based execution history).
- **`llm/`** — Mixture-of-Agents (MOA) orchestration and LLM scheduler.
- **`locks/file_lock.py`** — `fcntl`-based file locking to prevent concurrent writes to the same files.
- **`display/progress.py`** — Rich TUI progress display.

### CLI (`src/agent_collab/cli.py`)

Typer app with commands: `run`, `validate`, `list-agents`, `replay`, `checkpoints`, `security-create-user`, `security-login`, `security-verify-token`, `distributed-status`, `hitl-pending`. Agent registry uses lazy initialization via `_RegistryProxy` to defer imports.

## Code Standards

- Python 3.11+, `from __future__ import annotations` in all modules
- Type hints on all public functions
- Pydantic v2 for data models and validation
- asyncio for all concurrency (no threads)
- Rich for terminal output
- No wildcard imports
- Line length: 100 (ruff config)
- Ruff rules: E, F, I, N, W, UP, B, A, SIM (with specific ignores in `pyproject.toml`)

## Key Patterns

- **Agent registry** is a lazy proxy — don't import `OpenCodeAgent` at module level (it's deferred in `cli.py`)
- **Task outputs flow downstream** via `executor.task_outputs` dict, resolved by `WorkflowParser.resolve_task_outputs()`
- **File locks** are acquired per-task on declared `outputs` paths; lock failure immediately fails the task
- **Retry uses exponential backoff with jitter** — base_delay * 2^attempt, capped at 60s, ±25% jitter
- **Adaptive concurrency** — executor adjusts `_current_parallel` based on rolling average of task durations (< 10s → increase, > 60s → decrease)
- **Plugin entry points** — register via `[project.entry-points."agent_collab.plugins"]` in pyproject.toml
