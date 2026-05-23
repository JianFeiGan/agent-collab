# Contributing to AgentCollab

Thank you for your interest in contributing to AgentCollab! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment
4. Create a new branch for your changes
5. Make your changes
6. Test your changes
7. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/agent-collab.git
cd agent-collab

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=agent_collab --cov-report=html

# Run specific test file
uv run pytest tests/test_agents.py -v
```

## Making Changes

### Branch Naming

- Feature: `feature/description`
- Bug fix: `fix/description`
- Documentation: `docs/description`
- Refactor: `refactor/description`

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semi-colons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(agents): add resume session support for Aider agent
fix(workflow): resolve include path handling on Windows
docs(readme): update installation instructions
test(agents): add tests for capability detection
```

## Testing

### Writing Tests

- Place tests in the `tests/` directory
- Name test files as `test_*.py`
- Use descriptive test names that explain what is being tested
- Follow the Arrange-Act-Assert pattern
- Use fixtures for common setup

Example:

```python
import pytest
from agent_collab.agents.base import AgentResult

@pytest.fixture
def sample_result():
    """Create a sample AgentResult for testing."""
    return AgentResult(
        success=True,
        output="test output",
        files_changed=["file1.py"],
        duration_seconds=1.5,
        tokens_used=100,
    )

def test_agent_result_success(sample_result):
    """Test that AgentResult correctly stores success status."""
    # Arrange & Act (done by fixture)
    # Assert
    assert sample_result.success is True
    assert sample_result.output == "test output"
    assert len(sample_result.files_changed) == 1
```

### Test Coverage

We aim for high test coverage. When adding new features:

1. Write tests for all new code
2. Ensure existing tests still pass
3. Check coverage with `uv run pytest --cov`

## Code Style

### Python Standards

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Use type hints for all function signatures
- Write docstrings in Google style
- Maximum line length: 88 characters (Black default)

### Formatting

We use several tools to maintain code quality:

```bash
# Format code
uv run ruff format src/ tests/

# Check for linting issues
uv run ruff check src/ tests/

# Fix auto-fixable issues
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/
```

### Import Organization

```python
# Standard library imports
import asyncio
import json
from pathlib import Path

# Third-party imports
import typer
from rich.console import Console
from pydantic import BaseModel

# Local imports
from agent_collab.agents.base import BaseAgent, AgentResult
from agent_collab.core.workflow import WorkflowParser
```

## Submitting Changes

### Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md if applicable
5. Fill out the pull request template completely
6. Request review from maintainers

### Pull Request Template

```markdown
## Description

Brief description of changes.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing

- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes

## Checklist

- [ ] My code follows the code style of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Step-by-step instructions
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**: Python version, OS, etc.
6. **Screenshots**: If applicable

### Issue Template

```markdown
## Description

[Clear description of the issue]

## Steps to Reproduce

1. [First step]
2. [Second step]
3. [and so on...]

## Expected Behavior

[What you expected to happen]

## Actual Behavior

[What actually happened]

## Environment

- Python version: [e.g., 3.11.0]
- OS: [e.g., macOS 14.0, Ubuntu 22.04]
- AgentCollab version: [e.g., 2.2.0]

## Additional Context

[Any other context about the problem]
```

## Feature Requests

We welcome feature requests! Please:

1. Check existing issues to avoid duplicates
2. Clearly describe the feature and its benefits
3. Provide use cases
4. Consider implementation complexity

## Adding New Agent Adapters

To add a new agent adapter:

1. Create a new file in `src/agent_collab/agents/`
2. Implement the `BaseAgent` abstract class
3. Add tests in `tests/test_agents.py`
4. Update documentation
5. Add to `__init__.py` exports

Example:

```python
"""New agent adapter."""

from __future__ import annotations

import asyncio
import shutil
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class NewAgent(BaseAgent):
    """Agent adapter for new CLI tool."""

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        """Execute a prompt using the new agent."""
        # Implementation here
        pass

    def name(self) -> str:
        """Return the agent name."""
        return "new-agent"

    def is_available(self) -> bool:
        """Check if the CLI tool is available."""
        return shutil.which("new-agent") is not None

    def get_cli_version(self) -> str | None:
        """Get the CLI version."""
        # Implementation here
        pass

    def get_supported_arguments(self) -> list[str]:
        """Get supported CLI arguments."""
        return ["--help", "--version"]

    def check_api_key(self) -> tuple[bool, str]:
        """Check if API key is configured."""
        # Implementation here
        pass
```

## Questions?

Feel free to open an issue or reach out to the maintainers if you have questions.

Thank you for contributing to AgentCollab! 🚀
