[中文版](README.zh-CN.md) | English

# 🤖 AgentCollab

**Multi-agent orchestration engine for AI coding assistants.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-89%20passing-brightgreen.svg)](tests/)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/JianFeiGan/agent-collab/releases)

Define workflows in YAML. AgentCollab schedules tasks, runs agents in parallel, prevents file conflicts, and merges results — so your AI coding team works together, not against each other.

---

## Why AgentCollab?

| Problem | Solution |
|---------|----------|
| Multiple AI agents editing the same files | File locking prevents write conflicts |
| Manual task ordering across agents | DAG scheduler auto-resolves dependencies |
| Sequential execution wastes time | Parallel execution of independent tasks |
| No visibility into multi-agent runs | Rich TUI shows progress in real time |
| Agent outputs need manual merging | Git-based merge strategy handles integration |

---

## Installation

```bash
# With pip
pip install agent-collab

# With uv (recommended)
uv pip install agent-collab
```

Requires Python 3.11+. You also need at least one AI agent CLI installed:

| Agent | Install |
|-------|---------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` |
| [Codex](https://github.com/openai/codex) | `npm install -g @openai/codex` |
| [Aider](https://aider.chat) | `pip install aider-chat` |

---

## Quick Start

Create a workflow file `workflow.yaml`:

```yaml
name: my-feature
description: Implement a feature with code review

agents:
  coder:
    type: claude-code
    model: sonnet
    allowed_tools: [Read, Write, Edit, Bash]
  reviewer:
    type: claude-code
    model: opus
    allowed_tools: [Read]

tasks:
  - id: implement
    agent: coder
    prompt: |
      Add a /health endpoint to the FastAPI app that returns
      {"status": "ok"} with a 200 status code.
    outputs: [app/main.py]

  - id: review
    depends_on: [implement]
    agent: reviewer
    prompt: |
      Review the /health endpoint implementation for
      correctness, error handling, and API best practices.

strategy:
  max_parallel: 2
  timeout_per_task: 300
```

Run it:

```bash
agent-collab run workflow.yaml
```

---

## CLI Reference

### `agent-collab run <workflow.yaml>`

Execute a workflow. Tasks run in dependency order; independent tasks run in parallel.

```bash
agent-collab run workflow.yaml              # Run workflow
agent-collab run workflow.yaml --verbose    # Show detailed output
```

### `agent-collab validate <workflow.yaml>`

Validate a workflow file without executing it. Checks:
- YAML syntax
- Agent references exist
- Dependency references exist
- No circular dependencies

```bash
agent-collab validate workflow.yaml
```

### `agent-collab list-agents`

Show registered agents and their availability status.

```bash
agent-collab list-agents
```

---

## Workflow YAML Format

```yaml
name: workflow-name          # Required
description: What it does    # Optional

agents:                      # Agent definitions
  agent-id:                  # Unique identifier
    type: claude-code        # Agent type (claude-code | codex | aider)
    model: sonnet            # Model to use (default: sonnet)
    workdir: ./path          # Working directory (default: .)
    allowed_tools: [Read]    # Tools the agent may use

tasks:                       # Task definitions
  - id: task-id              # Unique identifier
    agent: agent-id          # Reference to an agent above
    prompt: |                # Instructions for the agent
      Do this specific thing.
      Supports ${VAR} and ${VAR:-default} variables.
      Can reference upstream output: ${task_id.output}
    depends_on: [other-id]   # Tasks that must complete first
    outputs: [path/]         # Files/dirs this task may modify
    merge_strategy: comments # How to handle outputs
    priority: 10             # Higher = runs first in parallel level
    when: "other_task.output contains 'success'"  # Conditional execution

variables:                   # Workflow-level variables (v0.2+)
  env_name: production
  max_retries: "3"

include: []                  # Include external workflow files (v0.2+)
  # - shared-tasks.yaml

strategy:                    # Execution settings
  max_parallel: 4            # Max concurrent tasks (default: 4)
  retry_on_failure: false    # Retry failed tasks (default: false)
  max_retries: 0             # Max retry attempts (default: 0)
  timeout_per_task: 600      # Seconds per task (default: 600)
```

---

## Built-in Agents

| Agent | Type | Best For |
|-------|------|----------|
| **Claude Code** | `claude-code` | Complex reasoning, multi-file edits, code review |
| **Codex** | `codex` | Quick code generation, single-file tasks |
| **Aider** | `aider` | Git-aware edits, pair programming style |

All agents implement the `BaseAgent` interface. See [`src/agent_collab/agents/`](src/agent_collab/agents/) for the adapter implementations.

---

## Examples

The [`examples/`](examples/) directory contains ready-to-use workflows:

| Workflow | Description |
|----------|-------------|
| [`fullstack.yaml`](examples/fullstack.yaml) | Build a FastAPI backend + React frontend in parallel, then review |
| [`code-review.yaml`](examples/code-review.yaml) | Implement a feature, review it, then auto-fix issues |
| [`refactor.yaml`](examples/refactor.yaml) | Refactor two modules in parallel, then integrate changes |

---

## Architecture

```
workflow.yaml
    │
    ▼
┌──────────────┐    Pydantic validation + cycle detection
│ WorkflowParser│
└──────┬───────┘
       │
       ▼
┌──────────────┐    Kahn's algorithm → parallel execution levels
│ TaskScheduler│
└──────┬───────┘
       │
       ▼
┌──────────────┐    asyncio.Semaphore-limited parallel dispatch
│ TaskExecutor ├────────────────────┐
└──────┬───────┘                    │
       │                            ▼
┌──────┴───────┐          ┌──────────────┐
│FileLockManager│          │ BaseAgent    │
│ (fcntl locks) │          │ (subprocess) │
└──────┬───────┘          └──────────────┘
       │
       ▼
┌──────────────┐    Git branch/merge workflow
│ ResultMerger │
└──────────────┘
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and how to add new agent adapters.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
