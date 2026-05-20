"""Tests for enhanced workflow features (conditions, loops)."""

from __future__ import annotations

import pytest
from pathlib import Path

from agent_collab.core.workflow import (
    AgentConfig,
    ConditionConfig,
    ConditionEvaluator,
    ConditionNodeConfig,
    LoopConfig,
    LoopExpander,
    LoopNodeConfig,
    NodeType,
    TaskConfig,
    WorkflowConfig,
    WorkflowParser,
)


class TestConditionConfig:
    """Tests for ConditionConfig."""

    def test_default_values(self):
        condition = ConditionConfig(
            field="status",
            operator="eq",
            value="success",
            then="task_a",
        )
        assert condition.field == "status"
        assert condition.operator == "eq"
        assert condition.value == "success"
        assert condition.then == "task_a"
        assert condition.else_ is None

    def test_with_else(self):
        condition = ConditionConfig(
            field="status",
            operator="eq",
            value="success",
            then="task_a",
            **{"else": "task_b"},
        )
        assert condition.then == "task_a"
        assert condition.else_ == "task_b"


class TestConditionNodeConfig:
    """Tests for ConditionNodeConfig."""

    def test_default_values(self):
        condition = ConditionConfig(
            field="status",
            operator="eq",
            value="success",
            then="task_a",
        )
        node = ConditionNodeConfig(id="cond_1", condition=condition)
        assert node.id == "cond_1"
        assert node.node_type == NodeType.CONDITION
        assert node.condition.field == "status"
        assert node.depends_on == []


class TestLoopConfig:
    """Tests for LoopConfig."""

    def test_for_each_default(self):
        loop = LoopConfig(
            type="for_each",
            items=["a", "b", "c"],
            body=["task_1"],
        )
        assert loop.type == "for_each"
        assert loop.items == ["a", "b", "c"]
        assert loop.max_iterations == 100
        assert loop.body == ["task_1"]

    def test_while_default(self):
        loop = LoopConfig(
            type="while",
            condition="${count} < 10",
            body=["task_1"],
        )
        assert loop.type == "while"
        assert loop.condition == "${count} < 10"
        assert loop.max_iterations == 100


class TestLoopNodeConfig:
    """Tests for LoopNodeConfig."""

    def test_default_values(self):
        loop = LoopConfig(
            type="for_each",
            items=["a", "b"],
            body=["task_1"],
        )
        node = LoopNodeConfig(id="loop_1", loop=loop)
        assert node.id == "loop_1"
        assert node.node_type == NodeType.LOOP
        assert node.loop.type == "for_each"
        assert node.depends_on == []


class TestConditionEvaluator:
    """Tests for ConditionEvaluator."""

    def test_eq_true(self):
        condition = ConditionConfig(
            field="status",
            operator="eq",
            value="success",
            then="task_a",
        )
        context = {"status": "success"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_eq_false(self):
        condition = ConditionConfig(
            field="status",
            operator="eq",
            value="success",
            then="task_a",
        )
        context = {"status": "failed"}
        assert ConditionEvaluator.evaluate(condition, context) is False

    def test_ne_true(self):
        condition = ConditionConfig(
            field="status",
            operator="ne",
            value="failed",
            then="task_a",
        )
        context = {"status": "success"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_gt_true(self):
        condition = ConditionConfig(
            field="count",
            operator="gt",
            value=5,
            then="task_a",
        )
        context = {"count": 10}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_gt_false(self):
        condition = ConditionConfig(
            field="count",
            operator="gt",
            value=5,
            then="task_a",
        )
        context = {"count": 3}
        assert ConditionEvaluator.evaluate(condition, context) is False

    def test_lt_true(self):
        condition = ConditionConfig(
            field="count",
            operator="lt",
            value=5,
            then="task_a",
        )
        context = {"count": 3}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_gte_true(self):
        condition = ConditionConfig(
            field="count",
            operator="gte",
            value=5,
            then="task_a",
        )
        context = {"count": 5}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_lte_true(self):
        condition = ConditionConfig(
            field="count",
            operator="lte",
            value=5,
            then="task_a",
        )
        context = {"count": 5}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_contains_true(self):
        condition = ConditionConfig(
            field="message",
            operator="contains",
            value="error",
            then="task_a",
        )
        context = {"message": "An error occurred"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_contains_false(self):
        condition = ConditionConfig(
            field="message",
            operator="contains",
            value="error",
            then="task_a",
        )
        context = {"message": "Success"}
        assert ConditionEvaluator.evaluate(condition, context) is False

    def test_not_contains_true(self):
        condition = ConditionConfig(
            field="message",
            operator="not_contains",
            value="error",
            then="task_a",
        )
        context = {"message": "Success"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_in_true(self):
        condition = ConditionConfig(
            field="status",
            operator="in",
            value=["success", "completed"],
            then="task_a",
        )
        context = {"status": "success"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_in_false(self):
        condition = ConditionConfig(
            field="status",
            operator="in",
            value=["success", "completed"],
            then="task_a",
        )
        context = {"status": "failed"}
        assert ConditionEvaluator.evaluate(condition, context) is False

    def test_not_in_true(self):
        condition = ConditionConfig(
            field="status",
            operator="not_in",
            value=["failed", "error"],
            then="task_a",
        )
        context = {"status": "success"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_regex_true(self):
        condition = ConditionConfig(
            field="email",
            operator="regex",
            value=r"^[\w\.-]+@[\w\.-]+\.\w+$",
            then="task_a",
        )
        context = {"email": "user@example.com"}
        assert ConditionEvaluator.evaluate(condition, context) is True

    def test_regex_false(self):
        condition = ConditionConfig(
            field="email",
            operator="regex",
            value=r"^[\w\.-]+@[\w\.-]+\.\w+$",
            then="task_a",
        )
        context = {"email": "invalid"}
        assert ConditionEvaluator.evaluate(condition, context) is False

    def test_missing_field(self):
        condition = ConditionConfig(
            field="status",
            operator="eq",
            value="success",
            then="task_a",
        )
        context = {}
        assert ConditionEvaluator.evaluate(condition, context) is False

    def test_unknown_operator(self):
        condition = ConditionConfig(
            field="status",
            operator="unknown",
            value="success",
            then="task_a",
        )
        context = {"status": "success"}
        with pytest.raises(ValueError, match="Unknown operator"):
            ConditionEvaluator.evaluate(condition, context)


class TestLoopExpander:
    """Tests for LoopExpander."""

    def test_expand_for_each(self):
        loop = LoopNodeConfig(
            id="loop_1",
            loop=LoopConfig(
                type="for_each",
                items=["a", "b", "c"],
                body=["task_1"],
            ),
        )
        task_map = {
            "task_1": TaskConfig(
                id="task_1",
                agent="claude-code",
                prompt="Process ${item} at index ${index}",
            ),
        }

        expanded = LoopExpander.expand_for_each(loop, ["a", "b", "c"], task_map)

        assert len(expanded) == 3
        assert expanded[0].id == "task_1_0"
        assert expanded[0].prompt == "Process a at index 0"
        assert expanded[1].id == "task_1_1"
        assert expanded[1].prompt == "Process b at index 1"
        assert expanded[2].id == "task_1_2"
        assert expanded[2].prompt == "Process c at index 2"

    def test_expand_for_each_with_dependencies(self):
        loop = LoopNodeConfig(
            id="loop_1",
            loop=LoopConfig(
                type="for_each",
                items=["a", "b"],
                body=["task_1", "task_2"],
            ),
        )
        task_map = {
            "task_1": TaskConfig(
                id="task_1",
                agent="claude-code",
                prompt="Step 1: ${item}",
            ),
            "task_2": TaskConfig(
                id="task_2",
                agent="claude-code",
                prompt="Step 2: ${item}",
                depends_on=["task_1"],
            ),
        }

        expanded = LoopExpander.expand_for_each(loop, ["a", "b"], task_map)

        assert len(expanded) == 4
        # First iteration
        assert expanded[0].id == "task_1_0"
        assert expanded[1].id == "task_2_0"
        assert expanded[1].depends_on == ["task_1_0"]
        # Second iteration
        assert expanded[2].id == "task_1_1"
        assert expanded[3].id == "task_2_1"
        assert expanded[3].depends_on == ["task_1_1"]

    def test_expand_while(self):
        loop = LoopNodeConfig(
            id="loop_1",
            loop=LoopConfig(
                type="while",
                condition="${count} < 3",
                body=["task_1"],
                max_iterations=3,
            ),
        )
        task_map = {
            "task_1": TaskConfig(
                id="task_1",
                agent="claude-code",
                prompt="Iteration ${index}",
            ),
        }

        expanded = LoopExpander.expand_while(loop, task_map)

        assert len(expanded) == 3
        assert expanded[0].id == "task_1_0"
        assert expanded[0].prompt == "Iteration 0"
        assert expanded[1].id == "task_1_1"
        assert expanded[1].prompt == "Iteration 1"
        assert expanded[2].id == "task_1_2"
        assert expanded[2].prompt == "Iteration 2"


class TestWorkflowConfigWithConditions:
    """Tests for WorkflowConfig with conditions."""

    def test_valid_workflow_with_conditions(self):
        config = WorkflowConfig(
            name="test",
            agents={"claude-code": AgentConfig(type="claude-code")},
            tasks=[
                TaskConfig(id="task_1", agent="claude-code", prompt="test"),
                TaskConfig(id="task_2", agent="claude-code", prompt="test"),
            ],
            conditions=[
                ConditionNodeConfig(
                    id="cond_1",
                    condition=ConditionConfig(
                        field="status",
                        operator="eq",
                        value="success",
                        then="task_2",
                    ),
                    depends_on=["task_1"],
                ),
            ],
        )
        assert len(config.tasks) == 2
        assert len(config.conditions) == 1
        assert config.conditions[0].id == "cond_1"

    def test_invalid_condition_reference(self):
        with pytest.raises(ValueError, match="references unknown 'then' node"):
            WorkflowConfig(
                name="test",
                agents={"claude-code": AgentConfig(type="claude-code")},
                tasks=[
                    TaskConfig(id="task_1", agent="claude-code", prompt="test"),
                ],
                conditions=[
                    ConditionNodeConfig(
                        id="cond_1",
                        condition=ConditionConfig(
                            field="status",
                            operator="eq",
                            value="success",
                            then="nonexistent",
                        ),
                    ),
                ],
            )


class TestWorkflowConfigWithLoops:
    """Tests for WorkflowConfig with loops."""

    def test_valid_workflow_with_loops(self):
        config = WorkflowConfig(
            name="test",
            agents={"claude-code": AgentConfig(type="claude-code")},
            tasks=[
                TaskConfig(id="task_1", agent="claude-code", prompt="test"),
            ],
            loops=[
                LoopNodeConfig(
                    id="loop_1",
                    loop=LoopConfig(
                        type="for_each",
                        items=["a", "b"],
                        body=["task_1"],
                    ),
                ),
            ],
        )
        assert len(config.tasks) == 1
        assert len(config.loops) == 1
        assert config.loops[0].id == "loop_1"

    def test_invalid_loop_body_reference(self):
        with pytest.raises(ValueError, match="references unknown body node"):
            WorkflowConfig(
                name="test",
                agents={"claude-code": AgentConfig(type="claude-code")},
                tasks=[],
                loops=[
                    LoopNodeConfig(
                        id="loop_1",
                        loop=LoopConfig(
                            type="for_each",
                            items=["a"],
                            body=["nonexistent"],
                        ),
                    ),
                ],
            )


class TestWorkflowParserEnhanced:
    """Tests for enhanced WorkflowParser features."""

    def test_expand_loops(self):
        config = WorkflowConfig(
            name="test",
            agents={"claude-code": AgentConfig(type="claude-code")},
            tasks=[
                TaskConfig(id="task_1", agent="claude-code", prompt="Process ${item}"),
            ],
            loops=[
                LoopNodeConfig(
                    id="loop_1",
                    loop=LoopConfig(
                        type="for_each",
                        items=["a", "b", "c"],
                        body=["task_1"],
                    ),
                ),
            ],
            variables={},
        )

        all_tasks = WorkflowParser.expand_loops(config)

        # Original task + 3 expanded tasks
        assert len(all_tasks) == 4
        assert all_tasks[0].id == "task_1"
        assert all_tasks[1].id == "task_1_0"
        assert all_tasks[2].id == "task_1_1"
        assert all_tasks[3].id == "task_1_2"
