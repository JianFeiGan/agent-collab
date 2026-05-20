# Changelog

All notable changes to AgentCollab will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-05-20

### 🎉 First Stable Release

AgentCollab reaches v1.0.0 — a production-ready multi-agent orchestration engine for AI coding assistants.

### Highlights

- **189 tests passing** with comprehensive coverage across all modules
- **Plugin system** with entry_points-based discovery and hook lifecycle
- **Checkpoint & resume** for long-running workflows
- **Token tracking** with per-task and per-agent aggregation
- **Execution history** persisted to SQLite for analysis

### Added

- **v0.3.0 features** (observability, error recovery, plugins):
  - Token consumption tracking (`TokenTracker`)
  - SQLite execution history (`ExecutionHistory`)
  - Exponential backoff retry with jitter
  - Degradation policies (SKIP / ABORT / CONTINUE)
  - Checkpoint mechanism with resume support
  - Plugin system with AgentPlugin, HookPlugin, FormatterPlugin interfaces
  - Hook system (before_task, after_task, on_failure)

- **v0.2.0 features** (workflow enhancements):
  - Claude Code resume session (`--continue` and `--resume`)
  - OpenCode agent adapter
  - Agent auto-detection (`is_available()`)
  - Workflow variables (`${VAR}` and `${VAR:-default}`)
  - Conditional execution (`when` field)
  - Task output passing (`${task_id.output}`)
  - Workflow include (`include` field)
  - Task priority ordering
  - Execution log with JSON export
  - Cancel mechanism (`cancel_all()`)

- **v0.1.0 features** (core engine):
  - YAML-based workflow definition with Pydantic validation
  - DAG scheduler with topological sort and parallel execution
  - Async executor with `asyncio.Semaphore` concurrency control
  - File locking (`fcntl`-based exclusive locks)
  - Git merge strategy for task outputs
  - Agent adapters (Claude Code, Codex, Aider)
  - CLI with `run`, `validate`, and `list-agents` commands
  - Rich TUI progress display
  - Cycle detection and retry logic

### Documentation

- Comprehensive README with installation, quick start, and usage guide
- Chinese README (README.zh-CN.md) with bilingual language switcher
- Contributing guide (CONTRIBUTING.md) with agent adapter development instructions
- Business requirements, technical design, and self-review documents
- Example workflows (fullstack, code-review, refactor)
- Sample plugins (EchoAgentPlugin, LoggingHookPlugin)

### Test Suite

- 189 tests covering workflow parsing, scheduling, execution, locking, agents, CLI, plugins, hooks, checkpoints, and more

## [0.3.0] - 2026-05-13

### Added

- **Token consumption tracking**: `TokenTracker` class tracks per-task input/output/total tokens with agent-level aggregation, Rich table rendering, and JSON export
- **SQLite execution history**: `ExecutionHistory` class persists workflow runs to `~/.agent-collab/history.db` with full task-level detail and query support
- **Exponential backoff retry**: Task retries now use `base_delay * 2^attempt` with ±25% jitter (capped at 60s), configurable via `retry_delay` in strategy
- **Degradation policies**: `DegradationPolicy` enum (SKIP / ABORT / CONTINUE) with per-task degradation config and failure tracking
- **Checkpoint mechanism**: `CheckpointManager` auto-saves progress after each task; supports resume from last checkpoint via `~/.agent-collab/checkpoints/`
- **Workflow replay**: `WorkflowReplayer` restores execution state from checkpoints; CLI commands `replay` and `checkpoints list|delete`
- **Plugin system**: `PluginManager` with `entry_points`-based discovery; ABC interfaces for `AgentPlugin`, `HookPlugin`, `FormatterPlugin`
- **Hook system**: `HookRegistry` with `before_task`, `after_task`, `on_failure` hooks; exception-resilient execution (one failing hook doesn't block others)
- **Sample plugins**: `EchoAgentPlugin` and `LoggingHookPlugin` in `examples/sample_plugin/`

### Changed

- `TaskExecutor` now accepts optional `token_tracker`, `history`, `checkpoint_manager`, and `plugin_manager` parameters
- Hooks fire automatically around task execution lifecycle
- `TaskConfig` gained `degradation` field; `StrategyConfig` gained `retry_delay` and `checkpoint_enabled` fields

### Test Suite

- 189 tests passing (up from 89 in v0.2.0)
- New test files: test_token_tracker, test_history, test_degradation, test_checkpoint, test_replay, test_plugins, test_hooks

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
