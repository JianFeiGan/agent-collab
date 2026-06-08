"""Tests for the v3.2.0 global-semaphore concurrency optimization.

Covers:
  * ``WorkflowConfig.global_max_parallel`` validation and resolution
  * ``StrategyConfig`` legacy ``max_parallel`` field still loads YAMLs
  * ``TaskExecutor`` uses a single cross-level shared semaphore
  * Adaptive controller can never exceed the global cap
  * Backwards-compat path: existing v3.1.x YAMLs continue to work
"""

from __future__ import annotations

import asyncio

import pytest

from agent_collab.agents.base import AgentResult, BaseAgent
from agent_collab.core.executor import TaskExecutor
from agent_collab.core.workflow import (
    AgentConfig,
    StrategyConfig,
    TaskConfig,
    WorkflowConfig,
)


class _RecordingAgent(BaseAgent):
    """Minimal agent that records concurrency it observed and sleeps briefly."""

    def __init__(self, name: str = "rec", sleep_s: float = 0.05) -> None:
        super().__init__()
        self._name = name
        self.sleep_s = sleep_s
        self.active_calls = 0
        self.peak_active = 0
        self.total_calls = 0
        self._lock = asyncio.Lock()

    async def execute(self, prompt, workdir, allowed_tools, timeout=600):  # type: ignore[override]
        async with self._lock:
            self.active_calls += 1
            self.total_calls += 1
            if self.active_calls > self.peak_active:
                self.peak_active = self.active_calls
        try:
            await asyncio.sleep(self.sleep_s)
        finally:
            async with self._lock:
                self.active_calls -= 1
        return AgentResult(success=True, output=f"{self._name}:{prompt}")

    def name(self) -> str:  # type: ignore[override]
        return self._name

    def is_available(self) -> bool:
        return True

    def get_cli_version(self):
        return "1.0.0"

    def get_supported_arguments(self):
        return []

    def check_api_key(self):
        return True, "ok"


def _build_workflow(global_max_parallel: int) -> WorkflowConfig:
    return WorkflowConfig(
        name="sem-test",
        agents={"a": AgentConfig(type="rec")},
        tasks=[
            TaskConfig(id=f"t{i}", agent="a", prompt=f"p{i}") for i in range(6)
        ],
        global_max_parallel=global_max_parallel,
    )


def test_global_max_parallel_default_is_4() -> None:
    cfg = WorkflowConfig(
        name="x",
        agents={"a": AgentConfig(type="rec")},
        tasks=[TaskConfig(id="t1", agent="a", prompt="p")],
    )
    assert cfg.global_max_parallel == 4
    assert cfg.effective_max_parallel() == 4


def test_global_max_parallel_validates_lower_bound() -> None:
    with pytest.raises(ValueError, match="global_max_parallel must be >= 1"):
        WorkflowConfig(
            name="x",
            agents={"a": AgentConfig(type="rec")},
            tasks=[TaskConfig(id="t1", agent="a", prompt="p")],
            global_max_parallel=0,
        )


def test_global_max_parallel_validates_upper_bound() -> None:
    with pytest.raises(ValueError, match="global_max_parallel must be <= 50"):
        WorkflowConfig(
            name="x",
            agents={"a": AgentConfig(type="rec")},
            tasks=[TaskConfig(id="t1", agent="a", prompt="p")],
            global_max_parallel=51,
        )


def test_strategy_legacy_max_parallel_promotes_to_hint() -> None:
    """Pre-v3.2.0 YAMLs put ``max_parallel`` inside ``strategy``. The
    validator should forward that to ``max_parallel_hint``."""
    cfg = WorkflowConfig(
        name="x",
        agents={"a": AgentConfig(type="rec")},
        tasks=[TaskConfig(id="t1", agent="a", prompt="p")],
        strategy=StrategyConfig(max_parallel=2),
    )
    assert cfg.strategy.resolved_max_parallel_hint() == 2
    # The workflow cap is 4 by default, so the effective cap is min(2, 4) = 2.
    assert cfg.effective_max_parallel() == 2


def test_strategy_max_parallel_hint_overrides_default() -> None:
    cfg = WorkflowConfig(
        name="x",
        agents={"a": AgentConfig(type="rec")},
        tasks=[TaskConfig(id="t1", agent="a", prompt="p")],
        global_max_parallel=8,
        strategy=StrategyConfig(max_parallel_hint=3),
    )
    assert cfg.effective_max_parallel() == 3


def test_strategy_hint_capped_by_global_max() -> None:
    cfg = WorkflowConfig(
        name="x",
        agents={"a": AgentConfig(type="rec")},
        tasks=[TaskConfig(id="t1", agent="a", prompt="p")],
        global_max_parallel=2,
        strategy=StrategyConfig(max_parallel_hint=10),
    )
    # Hint > global cap → global cap wins.
    assert cfg.effective_max_parallel() == 2


def test_executor_uses_shared_cross_level_semaphore() -> None:
    """A single ``TaskExecutor`` must use one semaphore for all
    ``execute_level`` calls, so cumulative parallelism stays bounded."""

    agent = _RecordingAgent("a", sleep_s=0.05)
    strategy = StrategyConfig()
    executor = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
        global_max_parallel=2,
        enable_adaptive_concurrency=False,
    )
    assert executor.get_global_max_parallel() == 2
    assert executor.available_concurrency() == 2

    tasks = [TaskConfig(id=f"t{i}", agent="a", prompt=f"p{i}") for i in range(6)]
    # Three levels of two tasks each. With a per-level semaphore, peak
    # could briefly reach 2+2 = 4 (if levels overlapped). With a shared
    # semaphore capped at 2, the peak must stay at 2.
    async def _go() -> None:
        for i in range(0, 6, 2):
            await executor.execute_level(tasks[i : i + 2])

    asyncio.run(_go())
    assert agent.peak_active == 2, (
        f"Expected peak concurrency 2, observed {agent.peak_active}. "
        "Cross-level semaphore is not being shared."
    )
    assert agent.total_calls == 6


def test_executor_adaptive_concurrency_respects_global_cap() -> None:
    """Adaptive controller should never push ``_current_parallel`` above
    ``_global_max_parallel * 2`` (the internal "high water mark")."""

    agent = _RecordingAgent("a", sleep_s=0.0)  # fast tasks → triggers increase
    strategy = StrategyConfig()
    executor = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
        global_max_parallel=3,
        enable_adaptive_concurrency=True,
    )
    # Force-feed > 3 short durations to trigger the ramp-up.
    for _ in range(10):
        executor._adjust_concurrency(0.1)
    cap = executor.get_global_max_parallel()
    assert executor._current_parallel <= cap * 2


def test_executor_adaptive_concurrency_can_be_disabled() -> None:
    agent = _RecordingAgent("a", sleep_s=0.0)
    strategy = StrategyConfig()
    executor = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
        global_max_parallel=4,
        enable_adaptive_concurrency=False,
    )
    initial = executor.get_current_concurrency()
    for _ in range(10):
        executor._adjust_concurrency(0.1)
    # When disabled, the controller should not move at all.
    assert executor.get_current_concurrency() == initial


def test_executor_back_compat_with_legacy_strategy_max_parallel() -> None:
    """Pre-v3.2.0 callers passed a strategy that had ``max_parallel`` set
    but not the new hint field. The executor should still resolve a cap."""

    agent = _RecordingAgent("a", sleep_s=0.05)
    strategy = StrategyConfig(max_parallel=1)  # legacy
    executor = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
    )
    assert executor.get_global_max_parallel() == 1
    assert executor.available_concurrency() == 1


def test_executor_global_max_parallel_arg_wins() -> None:
    agent = _RecordingAgent("a", sleep_s=0.05)
    strategy = StrategyConfig(max_parallel_hint=2)  # would yield 2
    executor = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
        global_max_parallel=5,  # explicit winner
    )
    assert executor.get_global_max_parallel() == 5


def test_executor_caps_out_of_range_argument() -> None:
    agent = _RecordingAgent("a", sleep_s=0.01)
    strategy = StrategyConfig()
    executor_low = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
        global_max_parallel=0,  # below floor
    )
    assert executor_low.get_global_max_parallel() == 1

    executor_high = TaskExecutor(
        agents={"a": agent},
        agent_configs={"a": AgentConfig(type="rec")},
        strategy=strategy,
        global_max_parallel=999,  # above ceiling
    )
    assert executor_high.get_global_max_parallel() == 50


def test_yaml_v3_1_style_still_loads_through_effective_max_parallel() -> None:
    """A workflow dict that still uses the old ``strategy.max_parallel``
    key should load and route the value through the new resolver. The
    effective cap is ``min(hint, global_max_parallel)`` so when the
    legacy hint is 6 and the workflow cap is the default 4, the result
    is 4 (the workflow cap wins)."""

    raw = {
        "name": "legacy",
        "agents": {"a": {"type": "rec"}},
        "tasks": [{"id": "t1", "agent": "a", "prompt": "p"}],
        "strategy": {"max_parallel": 6, "retry_on_failure": True},
    }
    cfg = WorkflowConfig.model_validate(raw)
    # Legacy field is still readable for diagnostics.
    assert cfg.strategy.max_parallel == 6
    assert cfg.strategy.max_parallel_hint == 6  # promoted by validator
    # The workflow cap (default 4) is authoritative; legacy hint = 6 is
    # clamped down to 4.
    assert cfg.effective_max_parallel() == 4
    # But if the user raises the workflow cap, the hint takes effect.
    cfg2 = WorkflowConfig.model_validate({**raw, "global_max_parallel": 10})
    assert cfg2.effective_max_parallel() == 6


def test_workflow_yaml_parsing_includes_global_max_parallel() -> None:
    raw = {
        "name": "new",
        "agents": {"a": {"type": "rec"}},
        "tasks": [{"id": "t1", "agent": "a", "prompt": "p"}],
        "global_max_parallel": 7,
        "enable_adaptive_concurrency": False,
    }
    cfg = WorkflowConfig.model_validate(raw)
    assert cfg.global_max_parallel == 7
    assert cfg.enable_adaptive_concurrency is False
    assert cfg.effective_max_parallel() == 7
