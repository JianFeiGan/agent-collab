# Changelog

All notable changes to AgentCollab will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
