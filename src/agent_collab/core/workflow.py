"""YAML workflow parsing and validation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import os
import re

import yaml
from pydantic import BaseModel, Field, model_validator

from agent_collab.core.degradation import TaskDegradation


class TaskConfig(BaseModel):
    """Configuration for a single workflow task."""

    id: str
    agent: str
    prompt: str
    priority: int = 0
    depends_on: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    merge_strategy: str | None = None
    when: str | None = None
    degradation: TaskDegradation | None = None


class AgentConfig(BaseModel):
    """Configuration for an agent adapter."""

    type: str
    model: str = "sonnet"
    workdir: str = "."
    allowed_tools: list[str] = Field(default_factory=list)


class StrategyConfig(BaseModel):
    """Execution strategy configuration."""

    max_parallel: int = 4
    retry_on_failure: bool = False
    max_retries: int = 0
    timeout_per_task: int = 600
    retry_delay: float = 1.0
    checkpoint_enabled: bool = False


class WorkflowConfig(BaseModel):
    """Top-level workflow configuration."""

    name: str
    description: str = ""
    agents: dict[str, AgentConfig]
    tasks: list[TaskConfig]
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    variables: dict[str, str] = Field(default_factory=dict)
    include: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> WorkflowConfig:
        """Ensure task agent references and dependencies are valid."""
        agent_names = set(self.agents.keys())
        task_ids = {t.id for t in self.tasks}

        for task in self.tasks:
            if task.agent not in agent_names:
                raise ValueError(
                    f"Task '{task.id}' references unknown agent '{task.agent}'"
                )
            for dep in task.depends_on:
                if dep not in task_ids:
                    raise ValueError(
                        f"Task '{task.id}' depends on unknown task '{dep}'"
                    )

        return self


class WorkflowParser:
    """Parses and validates YAML workflow files."""

    @staticmethod
    def resolve_variables(text: str, variables: dict[str, str]) -> str:
        """Resolve ``${VAR}`` and ``${VAR:-default}`` placeholders in *text*.

        The lookup order is: *variables* dict first, then ``os.environ``.
        If a variable is not found and a default is provided after ``:-``,
        the default is used.  Unresolved placeholders are left as-is.
        """

        def _replace(match: re.Match[str]) -> str:  # type: ignore[type-arg]
            var_name = match.group(1)
            if ":-" in var_name:
                name, default = var_name.split(":-", 1)
            else:
                name, default = var_name, ""
            value = variables.get(name, os.environ.get(name, ""))
            if value:
                return value
            return default

        return re.sub(r"\$\{([^}]+)\}", _replace, text)

    @staticmethod
    def resolve_task_outputs(text: str, outputs: dict[str, str]) -> str:
        """Resolve ``${task_id.output}`` placeholders in *text*.

        Each key in *outputs* is a task ID whose value is that task's
        execution output string.  Unresolved placeholders are left as-is.
        """
        def _replace(match: re.Match[str]) -> str:  # type: ignore[type-arg]
            task_id = match.group(1)
            return outputs.get(task_id, match.group(0))

        return re.sub(r"\$\{(\w+)\.output\}", _replace, text)

    @staticmethod
    def parse(file_path: str | Path) -> WorkflowConfig:
        """Load a YAML file and return a validated WorkflowConfig.

        Supports ``include`` — a list of YAML file paths whose tasks and
        agents are merged into the main workflow.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML structure is invalid or contains cycles.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        with open(path) as f:
            data: dict[str, Any] = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid workflow file: {path}")

        # Process includes: merge tasks and agents from referenced files
        includes: list[str] = data.get("include", [])
        for inc_path_str in includes:
            inc_path = path.parent / inc_path_str
            if not inc_path.exists():
                raise FileNotFoundError(f"Included workflow file not found: {inc_path}")
            with open(inc_path) as f:
                inc_data: dict[str, Any] = yaml.safe_load(f)
            if not isinstance(inc_data, dict):
                raise ValueError(f"Invalid included workflow file: {inc_path}")
            # Merge agents
            if "agents" in inc_data:
                data.setdefault("agents", {}).update(inc_data["agents"])
            # Merge tasks
            if "tasks" in inc_data:
                data.setdefault("tasks", []).extend(inc_data["tasks"])

        config = WorkflowConfig.model_validate(data)

        WorkflowParser._check_cycles(config.tasks)

        return config

    @staticmethod
    def _check_cycles(tasks: list[TaskConfig]) -> None:
        """Detect cycles in the task dependency graph.

        Uses DFS with three-color marking: white (unvisited), gray (in-progress),
        black (done). A back-edge to a gray node means a cycle.
        """
        adj: dict[str, list[str]] = defaultdict(list)
        for task in tasks:
            for dep in task.depends_on:
                adj[dep].append(task.id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {t.id: WHITE for t in tasks}
        path: list[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbor in adj[node]:
                if color[neighbor] == GRAY:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    raise ValueError(
                        f"Dependency cycle detected: {' -> '.join(cycle)}"
                    )
                if color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for task in tasks:
            if color[task.id] == WHITE:
                dfs(task.id)
