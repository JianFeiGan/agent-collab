# Changelog

All notable changes to AgentCollab will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-05-08

### Added

- **Claude Code resume session**: Support `--continue` and `--resume <session_id>` modes for continuing interrupted sessions
- **OpenCode agent adapter**: New adapter for [OpenCode](https://github.com/opencode-ai/opencode) CLI
- **Agent auto-detection**: `is_available()` class method checks if agent CLI is installed
- **Workflow variables**: `${VAR}` and `${VAR:-default}` syntax with environment variable fallback
- **Conditional execution**: `when` field on tasks for conditional task scheduling
- **Task output passing**: `${task_id.output}` syntax to pass outputs between tasks
- **Workflow include**: `include` field to reference and merge external YAML workflow files
- **Task priority**: `priority` field for ordering tasks within parallel execution levels
- **Execution log**: JSON-formatted execution history with `export_log()` method
- **Cancel mechanism**: `cancel_all()` method for graceful workflow cancellation

### Changed

- Scheduler now sorts tasks by priority (higher priority executes first)
- Executor records detailed execution logs (task_id, agent, status, duration)
- `timeout_per_task` default increased to 600 seconds

### Test Suite

- 89 tests passing (up from 51 in v0.1.0)
- Added tests for agent adapters, workflow variables, conditional execution, execution logs

## [0.1.0] - 2026-05-08

### Added

- **Workflow engine**: YAML-based workflow definition with Pydantic validation
- **DAG scheduler**: Topological sort with automatic parallel execution level detection
- **Async executor**: Parallel task execution with `asyncio.Semaphore` concurrency control
- **File locking**: `fcntl`-based exclusive locks to prevent concurrent file writes
- **Git merge strategy**: Branch-based task output merging with `--no-ff` preserves
- **Agent adapters**: Claude Code, Codex, and Aider CLI integrations
- **CLI**: `run`, `validate`, and `list-agents` commands via Typer
- **Rich TUI**: Progress display with colored panels and timing information
- **Cycle detection**: DFS-based cycle detection in workflow dependency graphs
- **Retry logic**: Configurable task retry with `retry_on_failure` and `max_retries`
- **Test suite**: 51 tests covering workflow parsing, scheduling, locking, agents, and CLI
