# Awesome List PR Templates

## Target Lists

| List | URL | Category | Fit |
|------|-----|----------|-----|
| awesome-ai-agents | github.com/e2b-dev/awesome-ai-agents | AI Agents / Orchestration | High |
| awesome-python | github.com/vinta/awesome-python | Development Tools | Medium |
| awesome-cli-apps | github.com/agarrharr/awesome-cli-apps | Developer Utilities | Medium |

---

## PR Template: awesome-ai-agents

### Title
```
Add AgentCollab — multi-agent orchestration engine
```

### Suggested Placement
Under **Orchestration & Frameworks** or **Developer Tools** section, near entries like AutoGen, CrewAI, or LangGraph.

### Entry
```markdown
- [AgentCollab](https://github.com/user/agent-collab) - Multi-agent orchestration engine for AI coding assistants (Claude Code, Codex, Aider). Define workflows in YAML, run agents in parallel with DAG scheduling and file locking.
```

### PR Description
```markdown
## What is AgentCollab?

AgentCollab is a CLI tool that orchestrates multiple AI coding assistants to work together on software projects. It supports Claude Code, Codex, and Aider as built-in agents.

## Why it belongs here

- **AI Agent orchestration**: schedules, executes, and merges outputs from multiple AI agents
- **Production-ready**: 51 tests, Pydantic validation, async execution, file locking
- **Open source**: MIT license, active development

## Key features
- YAML workflow definition with dependency graphs
- DAG-based scheduler with automatic parallel execution
- fcntl file locking to prevent write conflicts
- Git-based merge strategy for task outputs
- Rich TUI for real-time progress monitoring
```

---

## PR Template: awesome-python

### Title
```
Add AgentCollab — multi-agent workflow orchestration
```

### Suggested Placement
Under **DevOps Tools** or **Task Queues** section, near tools for workflow automation.

### Entry
```markdown
- [AgentCollab](https://github.com/user/agent-collab) - Multi-agent orchestration engine for AI coding assistants. Define workflows in YAML with DAG scheduling, file locking, and async execution. ![stars](https://img.shields.io/github/stars/user/agent-collab)
```

### PR Description
```markdown
## What is AgentCollab?

A Python 3.11+ CLI tool for orchestrating multiple AI coding agents (Claude Code, Codex, Aider) to collaborate on software projects.

## Why it belongs here

- Pure Python with modern tooling (asyncio, Pydantic, Typer, Rich)
- Well-structured package with type hints on all public functions
- 51 tests with pytest
- MIT license

## Tech stack
- Python 3.11+ / asyncio / Pydantic / Typer / Rich / PyYAML
```

---

## PR Template: awesome-cli-apps

### Title
```
Add AgentCollab — multi-agent orchestration CLI
```

### Suggested Placement
Under **Development** or **Utilities** section, near developer productivity tools.

### Entry
```markdown
- [AgentCollab](https://github.com/user/agent-collab) - Orchestrate multiple AI coding assistants (Claude Code, Codex, Aider) with YAML workflows. Handles scheduling, parallel execution, and file locking.
```

### PR Description
```markdown
## What is AgentCollab?

A CLI tool (`agent-collab`) for running multi-agent AI coding workflows.

## CLI commands
- `agent-collab run <workflow.yaml>` — Execute a workflow
- `agent-collab validate <workflow.yaml>` — Validate workflow YAML
- `agent-collab list-agents` — List available agents

## Why it belongs here

- Clean CLI interface built with Typer
- Solves a real developer productivity problem
- Installable via pip/uv, no runtime dependencies beyond Python
```

---

## Submission Checklist

Before submitting PRs:

- [ ] Verify the list's contribution guidelines (CONTRIBUTING.md)
- [ ] Check alphabetical ordering requirements
- [ ] Ensure the entry format matches existing entries exactly
- [ ] Confirm the repo has a clear README and LICENSE
- [ ] Add badge if the list supports it (stars, tests)
- [ ] Keep PR descriptions concise — maintainers review many PRs
- [ ] One PR per list (don't bundle)
- [ ] Wait at least 2 weeks before pinging maintainers
