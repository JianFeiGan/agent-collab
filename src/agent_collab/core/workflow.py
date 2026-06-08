"""Enhanced workflow parsing with conditional branches and loops."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from agent_collab.core.degradation import TaskDegradation


class NodeType(StrEnum):
    """Type of workflow node."""

    TASK = "task"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"


class ConditionConfig(BaseModel):
    """Configuration for conditional branching."""

    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, contains, not_contains, in, not_in, regex
    value: Any
    then: str  # task ID to execute if condition is true
    else_: str | None = Field(None, alias="else")


class LoopConfig(BaseModel):
    """Configuration for loop structure."""

    type: str  # for_each, while
    items: str | list[Any] | None = None  # for for_each loops
    condition: str | None = None  # for while loops
    max_iterations: int = 100
    body: list[str] = Field(default_factory=list)  # task IDs to execute in loop


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
    node_type: NodeType = NodeType.TASK


class ConditionNodeConfig(BaseModel):
    """Configuration for a condition node."""

    id: str
    node_type: NodeType = NodeType.CONDITION
    condition: ConditionConfig
    depends_on: list[str] = Field(default_factory=list)


class LoopNodeConfig(BaseModel):
    """Configuration for a loop node."""

    id: str
    node_type: NodeType = NodeType.LOOP
    loop: LoopConfig
    depends_on: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Configuration for an agent adapter."""

    type: str
    model: str = "sonnet"
    workdir: str = "."
    allowed_tools: list[str] = Field(default_factory=list)


class StrategyConfig(BaseModel):
    """Execution strategy configuration (advisory, per-strategy hints)."""

    # ``max_parallel`` is the historical (v3.1.x and earlier) name for
    # the per-strategy concurrency knob. v3.2.0 promoted it to a
    # top-level ``WorkflowConfig.global_max_parallel`` setting, with
    # ``max_parallel_hint`` here as a per-strategy override. We accept
    # the old name as a regular field and forward it to the hint via
    # a ``model_validator`` so existing YAML configs keep loading.
    max_parallel: int | None = None
    """DEPRECATED: prefer ``max_parallel_hint`` or the workflow-level
    ``global_max_parallel``. Kept for backward compatibility with
    v3.1.x YAMLs that placed the value on the strategy section."""

    max_parallel_hint: int | None = None
    """Optional per-strategy concurrency hint.

    When set, this strategy's tasks may run with concurrency up to
    ``min(hint, workflow.global_max_parallel)``. When ``None`` (default),
    the strategy follows the workflow's ``global_max_parallel`` directly.

    Note: ``max_parallel`` is now a top-level workflow setting. This field
    is kept for backwards compatibility and per-strategy overrides.
    """
    retry_on_failure: bool = False
    max_retries: int = 0
    timeout_per_task: int = 600
    retry_delay: float = 1.0
    checkpoint_enabled: bool = False

    @model_validator(mode="before")
    @classmethod
    def _promote_legacy_max_parallel(cls, values: Any) -> Any:
        """Forward the old ``max_parallel`` key to ``max_parallel_hint``.

        Pre-v3.2.0 YAMLs put the concurrency cap inside ``strategy`` as
        ``max_parallel: N``. We mirror that into ``max_parallel_hint``
        when no explicit hint was provided so the rest of the code only
        has to look at one place.
        """
        if not isinstance(values, dict):
            return values
        if "max_parallel_hint" not in values and "max_parallel" in values:
            legacy = values.get("max_parallel")
            if legacy is not None:
                values["max_parallel_hint"] = legacy
        return values

    def resolved_max_parallel_hint(self) -> int | None:
        """Return the effective per-strategy hint, including legacy
        ``max_parallel`` if it was supplied."""
        if self.max_parallel_hint is not None:
            return self.max_parallel_hint
        return self.max_parallel


class WorkflowConfig(BaseModel):
    """Top-level workflow configuration."""

    name: str
    description: str = ""
    agents: dict[str, AgentConfig]
    tasks: list[TaskConfig]
    conditions: list[ConditionNodeConfig] = Field(default_factory=list)
    loops: list[LoopNodeConfig] = Field(default_factory=list)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    variables: dict[str, str] = Field(default_factory=dict)
    include: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Global concurrency control (signal-semaphore optimization)
    # ------------------------------------------------------------------
    # The semaphore used to cap in-flight agent calls is shared across all
    # execution levels so that the workflow's true parallelism never exceeds
    # what the user asked for, regardless of how many levels are produced by
    # the dependency graph.
    global_max_parallel: int = 4
    """Maximum number of agent tasks allowed to run in parallel across
    the entire workflow. Acts as the upper bound for the cross-level
    asyncio.Semaphore that the executor uses. Default: 4."""

    enable_adaptive_concurrency: bool = True
    """When True, the executor will gently increase concurrency when tasks
    complete quickly and decrease it when they run long, within
    ``[1, global_max_parallel]`` (or ``[1, strategy.max_parallel_hint]``
    when a per-strategy hint is set)."""

    @field_validator("global_max_parallel")
    @classmethod
    def _validate_global_max_parallel(cls, value: int) -> int:
        """Clamp the global semaphore bound to a safe range.

        ``1`` keeps workflows fully serial (useful for debugging). The
        upper bound protects against runaway values that would exhaust
        file descriptors / sockets on the host.
        """
        if value < 1:
            raise ValueError(
                f"global_max_parallel must be >= 1, got {value}"
            )
        if value > 50:
            raise ValueError(
                f"global_max_parallel must be <= 50 to protect host "
                f"resources, got {value}"
            )
        return value

    def effective_max_parallel(self) -> int:
        """Resolve the effective concurrency ceiling for this workflow.

        Order of precedence:
          1. ``strategy.max_parallel_hint`` (per-strategy override) if set
          2. ``strategy.max_parallel`` (legacy v3.1.x field) if set
          3. ``global_max_parallel`` (workflow-wide cap)
        """
        hint = self.strategy.resolved_max_parallel_hint()
        if hint is None:
            return self.global_max_parallel
        return max(1, min(hint, self.global_max_parallel))

    @model_validator(mode="after")
    def validate_references(self) -> WorkflowConfig:
        """Ensure task agent references and dependencies are valid."""
        agent_names = set(self.agents.keys())
        task_ids = {t.id for t in self.tasks}
        condition_ids = {c.id for c in self.conditions}
        loop_ids = {l.id for l in self.loops}
        all_ids = task_ids | condition_ids | loop_ids

        for task in self.tasks:
            if task.agent not in agent_names:
                raise ValueError(f"Task '{task.id}' references unknown agent '{task.agent}'")
            for dep in task.depends_on:
                if dep not in all_ids:
                    raise ValueError(f"Task '{task.id}' depends on unknown node '{dep}'")

        for condition in self.conditions:
            for dep in condition.depends_on:
                if dep not in all_ids:
                    raise ValueError(f"Condition '{condition.id}' depends on unknown node '{dep}'")
            # Validate condition references
            if condition.condition.then not in all_ids:
                raise ValueError(
                    f"Condition '{condition.id}' references unknown 'then' node '{condition.condition.then}'"
                )
            if condition.condition.else_ and condition.condition.else_ not in all_ids:
                raise ValueError(
                    f"Condition '{condition.id}' references unknown 'else' node '{condition.condition.else_}'"
                )

        for loop in self.loops:
            for dep in loop.depends_on:
                if dep not in all_ids:
                    raise ValueError(f"Loop '{loop.id}' depends on unknown node '{dep}'")
            for body_id in loop.loop.body:
                if body_id not in all_ids:
                    raise ValueError(f"Loop '{loop.id}' references unknown body node '{body_id}'")

        return self


class ConditionEvaluator:
    """Evaluates conditions for conditional branching."""

    @staticmethod
    def evaluate(condition: ConditionConfig, context: dict[str, Any]) -> bool:
        """Evaluate a condition against the context.

        Args:
            condition: The condition configuration.
            context: The execution context with variable values.

        Returns:
            True if condition is met, False otherwise.
        """
        value = context.get(condition.field)
        if value is None:
            return False

        operator = condition.operator
        target = condition.value

        if operator == "eq":
            return value == target
        elif operator == "ne":
            return value != target
        elif operator == "gt":
            return float(value) > float(target)
        elif operator == "lt":
            return float(value) < float(target)
        elif operator == "gte":
            return float(value) >= float(target)
        elif operator == "lte":
            return float(value) <= float(target)
        elif operator == "contains":
            return str(target) in str(value)
        elif operator == "not_contains":
            return str(target) not in str(value)
        elif operator == "in":
            if isinstance(target, list):
                return value in target
            return False
        elif operator == "not_in":
            if isinstance(target, list):
                return value not in target
            return True
        elif operator == "regex":
            return bool(re.match(str(target), str(value)))
        else:
            raise ValueError(f"Unknown operator: {operator}")


class LoopExpander:
    """Expands loop constructs into concrete task sequences."""

    @staticmethod
    def expand_for_each(
        loop: LoopNodeConfig,
        items: list[Any],
        task_map: dict[str, TaskConfig],
    ) -> list[TaskConfig]:
        """Expand a for_each loop into concrete tasks.

        Args:
            loop: The loop configuration.
            items: The items to iterate over.
            task_map: Map of task ID to task config.

        Returns:
            List of expanded task configs.
        """
        expanded_tasks = []
        for i, item in enumerate(items):
            for body_task_id in loop.loop.body:
                original_task = task_map.get(body_task_id)
                if original_task is None:
                    continue

                # Create a new task with indexed ID
                new_task = original_task.model_copy()
                new_task.id = f"{original_task.id}_{i}"
                new_task.depends_on = [
                    f"{dep}_{i}" if dep in loop.loop.body else dep
                    for dep in original_task.depends_on
                ]

                # Replace loop variable in prompt
                new_task.prompt = new_task.prompt.replace("${item}", str(item))
                new_task.prompt = new_task.prompt.replace("${index}", str(i))

                expanded_tasks.append(new_task)

        return expanded_tasks

    @staticmethod
    def expand_while(
        loop: LoopNodeConfig,
        task_map: dict[str, TaskConfig],
    ) -> list[TaskConfig]:
        """Expand a while loop into concrete tasks.

        Note: While loops are expanded up to max_iterations.
        Actual runtime will need to evaluate the condition.

        Args:
            loop: The loop configuration.
            task_map: Map of task ID to task config.

        Returns:
            List of expanded task configs.
        """
        expanded_tasks = []
        for i in range(loop.loop.max_iterations):
            for body_task_id in loop.loop.body:
                original_task = task_map.get(body_task_id)
                if original_task is None:
                    continue

                # Create a new task with indexed ID
                new_task = original_task.model_copy()
                new_task.id = f"{original_task.id}_{i}"
                new_task.depends_on = [
                    f"{dep}_{i}" if dep in loop.loop.body else dep
                    for dep in original_task.depends_on
                ]

                # Add iteration index to prompt
                new_task.prompt = new_task.prompt.replace("${index}", str(i))

                expanded_tasks.append(new_task)

        return expanded_tasks


class WorkflowParser:
    """Parses and validates YAML workflow files with enhanced features."""

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
            # Merge conditions
            if "conditions" in inc_data:
                data.setdefault("conditions", []).extend(inc_data["conditions"])
            # Merge loops
            if "loops" in inc_data:
                data.setdefault("loops", []).extend(inc_data["loops"])

        config = WorkflowConfig.model_validate(data)

        WorkflowParser._check_cycles(config)

        return config

    @staticmethod
    def _check_cycles(config: WorkflowConfig) -> None:
        """Detect cycles in the task dependency graph.

        Uses DFS with three-color marking: white (unvisited), gray (in-progress),
        black (done). A back-edge to a gray node means a cycle.
        """
        # Build adjacency list from all nodes
        adj: dict[str, list[str]] = defaultdict(list)

        # Task dependencies
        for task in config.tasks:
            for dep in task.depends_on:
                adj[dep].append(task.id)

        # Condition dependencies
        for condition in config.conditions:
            for dep in condition.depends_on:
                adj[dep].append(condition.id)
            # Add edges for then/else branches
            adj[condition.id].append(condition.condition.then)
            if condition.condition.else_:
                adj[condition.id].append(condition.condition.else_)

        # Loop dependencies
        for loop in config.loops:
            for dep in loop.depends_on:
                adj[dep].append(loop.id)
            for body_id in loop.loop.body:
                adj[loop.id].append(body_id)

        # Get all node IDs
        all_ids = (
            {t.id for t in config.tasks}
            | {c.id for c in config.conditions}
            | {l.id for l in config.loops}
        )

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in all_ids}
        path: list[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    raise ValueError(f"Dependency cycle detected: {' -> '.join(cycle)}")
                if color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for node_id in all_ids:
            if color.get(node_id) == WHITE:
                dfs(node_id)

    @staticmethod
    def expand_loops(config: WorkflowConfig) -> list[TaskConfig]:
        """Expand loop constructs into concrete tasks.

        Args:
            config: The workflow configuration.

        Returns:
            List of all tasks including expanded loop bodies.
        """
        all_tasks = list(config.tasks)
        task_map = {t.id: t for t in config.tasks}

        for loop in config.loops:
            if loop.loop.type == "for_each":
                # Get items from variables or context
                items = loop.loop.items
                if isinstance(items, str):
                    # Resolve variable reference
                    items = config.variables.get(items, [])
                if isinstance(items, list):
                    expanded = LoopExpander.expand_for_each(loop, items, task_map)
                    all_tasks.extend(expanded)
            elif loop.loop.type == "while":
                expanded = LoopExpander.expand_while(loop, task_map)
                all_tasks.extend(expanded)

        return all_tasks
