# Agent 适配器开发指南

> 本指南面向希望为 AgentCollab 开发自定义 Agent 适配器的开发者。

## 目录

1. [概述](#概述)
2. [架构概览](#架构概览)
3. [快速开始：5 分钟创建适配器](#快速开始5-分钟创建适配器)
4. [BaseAgent 接口详解](#baseagent-接口详解)
5. [AgentResult 数据结构](#agentresult-数据结构)
6. [完整示例：Continue Agent](#完整示例continue-agent)
7. [通过插件系统注册](#通过插件系统注册)
8. [测试指南](#测试指南)
9. [最佳实践](#最佳实践)
10. [FAQ](#faq)

---

## 概述

Agent 适配器是 AgentCollab 与外部 AI 编程工具之间的桥梁。每个适配器封装了与特定 CLI 工具（如 Claude Code、Codex、Aider）的通信逻辑，使工作流引擎能以统一方式调度不同的 AI Agent。

### 为什么需要适配器？

- **统一接口**：工作流 YAML 只需指定 `type: claude-code`，无需关心底层 CLI 参数
- **可扩展性**：通过实现 `BaseAgent` 接口，任何人都能接入新的 AI 工具
- **错误隔离**：每个适配器独立处理超时、CLI 缺失等异常

### 已内置的适配器

| 适配器 | CLI 工具 | 安装方式 |
|--------|----------|----------|
| `claude-code` | `claude` | `npm install -g @anthropic-ai/claude-code` |
| `codex` | `codex` | `npm install -g @openai/codex` |
| `aider` | `aider` | `pip install aider-chat` |
| `opencode` | `opencode` | `go install github.com/opencode-ai/opencode@latest` |

---

## 架构概览

```
┌─────────────────────────────────────────────────┐
│                  Workflow YAML                   │
│              (type: my-custom-agent)             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              AgentCollab Scheduler               │
│         (DAG topological sort + parallel)        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│               TaskExecutor                       │
│      (asyncio subprocess + timeout)              │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│          Your Custom Agent Adapter               │
│  ┌───────────────────────────────────────────┐  │
│  │  BaseAgent (ABC)                           │  │
│  │  ├── execute() → AgentResult              │  │
│  │  ├── name() → str                         │  │
│  │  └── is_available() → bool                │  │
│  └───────────────────────────────────────────┘  │
│                       │                          │
│                       ▼                          │
│              ┌─────────────────┐                 │
│              │  External CLI   │                 │
│              │  (subprocess)   │                 │
│              └─────────────────┘                 │
└─────────────────────────────────────────────────┘
```

核心流程：
1. 工作流 YAML 中定义 `agents` 和 `tasks`
2. 调度器按 DAG 拓扑排序确定执行顺序
3. `TaskExecutor` 为每个任务调用对应适配器的 `execute()` 方法
4. 适配器通过 `asyncio.subprocess` 调用外部 CLI 工具
5. 返回 `AgentResult` 包含执行结果、耗时、文件变更等信息

---

## 快速开始：5 分钟创建适配器

### 第 1 步：创建适配器文件

在 `src/agent_collab/agents/` 下创建新文件，例如 `continue_agent.py`：

```python
"""Continue agent adapter."""

from __future__ import annotations

import asyncio
import shutil
import time

from agent_collab.agents.base import AgentResult, BaseAgent


class ContinueAgent(BaseAgent):
    """Agent adapter that invokes the ``continue`` CLI."""

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        start = time.monotonic()

        cmd = ["continue", "--prompt", prompt]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except TimeoutError:
            proc.kill()
            elapsed = time.monotonic() - start
            return AgentResult(
                success=False,
                output=f"Timed out after {timeout}s",
                duration_seconds=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            return AgentResult(
                success=False,
                output="continue CLI not found. Install from: https://continue.dev",
                duration_seconds=elapsed,
            )

        elapsed = time.monotonic() - start
        raw = stdout.decode().strip()

        return AgentResult(
            success=proc.returncode == 0,
            output=raw if proc.returncode == 0 else stderr.decode().strip() or raw,
            duration_seconds=elapsed,
        )

    def name(self) -> str:
        return "continue"

    def is_available(self) -> bool:
        return shutil.which("continue") is not None
```

### 第 2 步：注册到 Agent 注册表

编辑 `src/agent_collab/cli.py`，在 `_get_agent_registry()` 中添加：

```python
from agent_collab.agents.continue_agent import ContinueAgent

def _get_agent_registry() -> dict[str, BaseAgent]:
    global _AGENT_REGISTRY
    if _AGENT_REGISTRY is None:
        from agent_collab.agents.opencode import OpenCodeAgent
        _AGENT_REGISTRY = {
            "claude-code": ClaudeCodeAgent(),
            "codex": CodexAgent(),
            "aider": AiderAgent(),
            "opencode": OpenCodeAgent(),
            "continue": ContinueAgent(),  # ← 新增
        }
    return _AGENT_REGISTRY
```

### 第 3 步：在工作流中使用

```yaml
name: my-feature
agents:
  coder:
    type: continue       # ← 使用新适配器
    allowed_tools: [Read, Write]

tasks:
  - id: implement
    agent: coder
    prompt: "Add a login endpoint to the API"
```

### 第 4 步：验证

```bash
agent-collab list-agents
# 应该能看到 continue 显示为 available / not found

agent-collab validate workflow.yaml
```

---

## BaseAgent 接口详解

```python
class BaseAgent(ABC):
    """Abstract base class for all agent adapters."""

    def __init__(
        self,
        resume_mode: str = "none",
        session_id: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult: ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...
```

### `__init__(resume_mode, session_id)`

构造函数，支持会话恢复。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `resume_mode` | `str` | `"none"` | 恢复策略：`"none"` / `"continue"` / `"resume"` |
| `session_id` | `str \| None` | `None` | 当 `resume_mode="resume"` 时使用的会话 ID |

**resume_mode 详解**：

- `"none"`：每次都从头开始（默认）
- `"continue"`：继续上一次对话（适用于 Claude Code 的 `--continue`）
- `"resume"`：恢复指定会话（需要提供 `session_id`，适用于 Claude Code 的 `--resume`）

### `execute(prompt, workdir, allowed_tools, timeout)`

执行任务的核心方法。**必须是 async 方法**。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | `str` | — | 发送给 Agent 的指令文本 |
| `workdir` | `str` | — | Agent 的工作目录（通常是项目根目录） |
| `allowed_tools` | `list[str]` | — | Agent 可使用的工具列表（如 `["Read", "Write", "Edit", "Bash"]`） |
| `timeout` | `int` | `600` | 最大执行时间（秒），超时应 kill 进程 |

**返回值**：`AgentResult` 实例。

### `name()`

返回适配器的人类可读名称。这个名称会出现在：
- `agent-collab list-agents` 输出
- 工作流 YAML 的 `type` 字段映射
- 日志和错误消息

**命名规范**：使用 kebab-case（如 `"claude-code"`、`"my-agent"`）。

### `is_available()`

检查该 Agent 的 CLI 工具是否已安装并可访问。

**推荐实现**：使用 `shutil.which()` 检查 CLI 是否在 PATH 中：

```python
def is_available(self) -> bool:
    return shutil.which("your-cli-tool") is not None
```

---

## AgentResult 数据结构

```python
@dataclass
class AgentResult:
    """Result returned by an agent after executing a task."""

    success: bool
    output: str
    files_changed: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    tokens_used: int | None = None
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `success` | `bool` | ✅ | 任务是否成功完成 |
| `output` | `str` | ✅ | Agent 的输出文本（成功时为结果，失败时为错误信息） |
| `files_changed` | `list[str]` | ❌ | Agent 修改的文件路径列表 |
| `duration_seconds` | `float` | ❌ | 执行耗时（秒） |
| `tokens_used` | `int \| None` | ❌ | 消耗的 Token 数量（如果 CLI 支持报告） |

**最佳实践**：
- 成功时 `output` 应包含 Agent 的有意义输出
- 失败时 `output` 应包含清晰的错误描述
- `duration_seconds` 建议始终填充，用于性能分析
- 如果 CLI 输出 JSON，解析 `files_changed` 和 `tokens_used`

---

## 完整示例：Continue Agent

下面是一个完整的、可直接使用的适配器实现，展示了所有最佳实践：

```python
"""Continue Dev agent adapter.

Integrates with the Continue CLI for code generation tasks.
Install: https://docs.continue.dev/getting-started/install
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time

from agent_collab.agents.base import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


class ContinueAgent(BaseAgent):
    """Agent adapter for the Continue Dev CLI.

    Continue is an open-source AI code assistant that runs locally.
    This adapter invokes it in non-interactive mode.

    CLI Usage::

        continue run --prompt "your prompt" --workspace ./src

    Args:
        model: Model to use (e.g. ``"claude-3-sonnet"``, ``"gpt-4"``).
        resume_mode: Session resume strategy.
        session_id: Session ID for resume mode.
    """

    def __init__(
        self,
        model: str = "claude-3-sonnet",
        resume_mode: str = "none",
        session_id: str | None = None,
    ) -> None:
        super().__init__(resume_mode=resume_mode, session_id=session_id)
        self.model = model

    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600,
    ) -> AgentResult:
        """Execute a prompt via the Continue CLI.

        Args:
            prompt: The coding instruction.
            workdir: Working directory for the agent.
            allowed_tools: Tools the agent may use (mapped to Continue config).
            timeout: Max execution time in seconds.

        Returns:
            AgentResult with output, files changed, and timing.
        """
        start = time.monotonic()

        # Build CLI command
        cmd = [
            "continue",
            "run",
            "--prompt", prompt,
            "--workspace", workdir,
            "--model", self.model,
            "--output-format", "json",
        ]

        # Map allowed_tools to Continue's tool format
        tool_mapping = {
            "Read": "file_reader",
            "Write": "file_writer",
            "Edit": "file_editor",
            "Bash": "terminal",
        }
        for tool in allowed_tools:
            mapped = tool_mapping.get(tool)
            if mapped:
                cmd.extend(["--tool", mapped])

        logger.debug("Executing: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except TimeoutError:
            proc.kill()
            elapsed = time.monotonic() - start
            logger.warning("Continue agent timed out after %ds", timeout)
            return AgentResult(
                success=False,
                output=f"Timed out after {timeout}s",
                duration_seconds=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            logger.error("continue CLI not found on PATH")
            return AgentResult(
                success=False,
                output=(
                    "continue CLI not found. "
                    "Install from: https://docs.continue.dev/getting-started/install"
                ),
                duration_seconds=elapsed,
            )

        elapsed = time.monotonic() - start
        raw = stdout.decode().strip()

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() or raw
            logger.error("Continue agent failed: %s", error_msg[:200])
            return AgentResult(
                success=False,
                output=error_msg,
                duration_seconds=elapsed,
            )

        return self._parse_json_output(raw, elapsed)

    def _parse_json_output(self, raw: str, elapsed: float) -> AgentResult:
        """Parse JSON output from Continue CLI.

        Expected format::

            {
                "result": "Generated code...",
                "files_changed": ["src/main.py"],
                "usage": {"total_tokens": 1500}
            }
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: treat raw text as the result
            return AgentResult(
                success=True,
                output=raw,
                duration_seconds=elapsed,
            )

        return AgentResult(
            success=True,
            output=data.get("result", raw),
            files_changed=data.get("files_changed", []),
            duration_seconds=elapsed,
            tokens_used=data.get("usage", {}).get("total_tokens"),
        )

    def name(self) -> str:
        """Return the adapter name used in workflow YAML."""
        return "continue"

    def is_available(self) -> bool:
        """Check if the continue CLI is installed."""
        return shutil.which("continue") is not None
```

---

## 通过插件系统注册

除了直接修改 `cli.py`，你还可以通过 Python 的 `entry_points` 机制注册适配器。这种方式适合发布为独立的 pip 包。

### 第 1 步：创建插件类

```python
# my_continue_plugin/__init__.py

from agent_collab.agents.base import BaseAgent
from agent_collab.plugins.interfaces import AgentPlugin

from .agent import ContinueAgent


class ContinueAgentPlugin(AgentPlugin):
    """Plugin that provides the Continue agent adapter."""

    name = "continue"
    description = "Continue Dev AI code assistant"

    def create_agent(self, **kwargs: object) -> BaseAgent:
        model = kwargs.get("model", "claude-3-sonnet")
        return ContinueAgent(model=str(model))
```

### 第 2 步：配置 entry_points

在你的包的 `pyproject.toml` 中：

```toml
[project]
name = "agent-collab-continue"
version = "0.1.0"
dependencies = ["agent-collab>=2.0.0"]

[project.entry-points."agent_collab.plugins"]
continue = "my_continue_plugin:ContinueAgentPlugin"
```

### 第 3 步：安装并使用

```bash
# 安装你的插件包
pip install -e .

# AgentCollab 会自动发现并加载插件
agent-collab list-agents
```

### 插件加载流程

```
PluginManager.load_plugins()
  → importlib.metadata.entry_points(group="agent_collab.plugins")
    → 每个 entry_point.load() 返回插件类
      → 实例化并调用 register_plugin()
        → AgentPlugin 注册到 _agent_plugins
        → HookPlugin 注册到 _hook_registry
        → FormatterPlugin 注册到 _formatter_plugins
```

---

## 测试指南

### 测试策略

Agent 适配器的测试应覆盖以下场景：

1. **成功执行**：模拟 CLI 返回正常输出
2. **执行失败**：模拟 CLI 返回非零退出码
3. **CLI 未安装**：模拟 `FileNotFoundError`
4. **超时**：模拟执行超时
5. **输出解析**：测试 JSON 输出和纯文本输出的解析
6. **名称和可用性**：验证 `name()` 和 `is_available()`

### 测试模板

```python
"""Tests for Continue agent adapter."""

from __future__ import annotations

import asyncio

import pytest

from agent_collab.agents.continue_agent import ContinueAgent
from agent_collab.agents.base import AgentResult


class _StubProcess:
    """Minimal mock for asyncio.subprocess.Process."""

    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    def kill(self) -> None:
        pass


@pytest.mark.asyncio
async def test_continue_execute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful execution returns parsed JSON output."""
    agent = ContinueAgent()
    fake_output = '{"result": "done", "files_changed": ["a.py"], "usage": {"total_tokens": 42}}'

    async def fake_exec(*args, **kwargs):
        return _StubProcess(0, fake_output.encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", ["Read"])
    assert result.success
    assert result.output == "done"
    assert result.files_changed == ["a.py"]
    assert result.tokens_used == 42


@pytest.mark.asyncio
async def test_continue_execute_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-zero exit code returns failure with error message."""
    agent = ContinueAgent()

    async def fake_exec(*args, **kwargs):
        return _StubProcess(1, b"", b"something broke")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", [])
    assert not result.success
    assert "something broke" in result.output


@pytest.mark.asyncio
async def test_continue_cli_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing CLI returns failure with install instructions."""
    agent = ContinueAgent()

    async def fake_exec(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", [])
    assert not result.success
    assert "not found" in result.output


@pytest.mark.asyncio
async def test_continue_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout returns failure with timeout message."""
    agent = ContinueAgent()
    killed = False

    class SlowProcess(_StubProcess):
        async def communicate(self):
            await asyncio.sleep(100)

        def kill(self):
            nonlocal killed
            killed = True

    async def fake_exec(*args, **kwargs):
        return SlowProcess(0, b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = await agent.execute("do stuff", ".", [], timeout=1)
    assert not result.success
    assert "Timed out" in result.output
    assert killed


def test_continue_name() -> None:
    assert ContinueAgent().name() == "continue"


def test_continue_is_available_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert not ContinueAgent().is_available()


def test_continue_is_available_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/continue")
    assert ContinueAgent().is_available()
```

### 运行测试

```bash
# 运行特定适配器的测试
python3 -m pytest tests/test_agents.py -v -k "continue"

# 运行所有测试
python3 -m pytest tests/ -v
```

---

## 最佳实践

### 1. 错误处理

```python
# ✅ 好：区分不同错误类型
try:
    proc = await asyncio.create_subprocess_exec(*cmd, ...)
except TimeoutError:
    proc.kill()
    return AgentResult(success=False, output=f"Timed out after {timeout}s", ...)
except FileNotFoundError:
    return AgentResult(success=False, output="CLI not found. Install ...", ...)

# ❌ 坏：捕获所有异常
try:
    proc = await asyncio.create_subprocess_exec(*cmd, ...)
except Exception as e:
    return AgentResult(success=False, output=str(e), ...)
```

### 2. 超时处理

```python
# ✅ 好：使用 asyncio.wait_for + kill
try:
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
except TimeoutError:
    proc.kill()  # 确保进程被终止
    ...

# ❌ 坏：不处理超时
stdout, stderr = await proc.communicate()  # 可能永远等待
```

### 3. 输出解析

```python
# ✅ 好：容错解析
def _parse_output(self, raw: str, elapsed: float) -> AgentResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return AgentResult(success=True, output=raw, duration_seconds=elapsed)
    ...

# ❌ 坏：假设输出总是 JSON
data = json.loads(raw)  # 可能抛出异常
```

### 4. 日志记录

```python
import logging

logger = logging.getLogger(__name__)

async def execute(self, prompt, workdir, allowed_tools, timeout=600):
    logger.debug("Executing prompt in %s", workdir)
    # ...
    logger.error("Agent failed: %s", error_msg[:200])
    # ...
    logger.warning("Timed out after %ds", timeout)
```

### 5. 工具映射

不同 CLI 对"工具"的定义不同，建议提供映射：

```python
TOOL_MAPPING = {
    "Read": "file_reader",      # Continue
    "Write": "file_writer",
    "Edit": "file_editor",
    "Bash": "terminal",
}
```

### 6. 进程清理

始终确保子进程被正确清理：

```python
# 超时时必须 kill
except TimeoutError:
    proc.kill()
    await proc.wait()  # 等待进程真正退出
```

---

## FAQ

### Q: 适配器必须是 async 的吗？

**A**: 是的。`execute()` 是 `async` 方法，因为 AgentCollab 使用 `asyncio` 进行并发调度。即使你的 CLI 是同步的，也需要用 `asyncio.create_subprocess_exec` 调用。

### Q: 如何处理不支持 JSON 输出的 CLI？

**A**: 将纯文本输出直接放入 `AgentResult.output`：

```python
return AgentResult(
    success=proc.returncode == 0,
    output=stdout.decode().strip(),
    duration_seconds=elapsed,
)
```

### Q: `allowed_tools` 参数有什么用？

**A**: 它来自工作流 YAML 中的 `allowed_tools` 配置。你可以：
- 直接忽略它（如果 CLI 不支持工具限制）
- 映射到 CLI 的工具参数（如 Claude Code 的 `--allowedTools`）
- 用于日志记录

### Q: 如何支持会话恢复？

**A**: 在 `execute()` 中检查 `self.resume_mode`：

```python
if self.resume_mode == "continue":
    cmd.append("--continue")
elif self.resume_mode == "resume" and self.session_id:
    cmd.extend(["--resume", self.session_id])
```

### Q: 适配器需要处理 `SIGTERM` 吗？

**A**: 不需要。AgentCollab 的 `TaskExecutor` 会通过 `asyncio.wait_for` 处理超时，并调用 `proc.kill()`。你的适配器只需正确处理 `TimeoutError`。

### Q: 如何发布为独立的 pip 包？

**A**: 参考[通过插件系统注册](#通过插件系统注册)一节。关键是：
1. 创建包含 `AgentPlugin` 子类的包
2. 在 `pyproject.toml` 中声明 `entry_points`
3. 用户 `pip install` 后 AgentCollab 自动发现

### Q: 测试时不想真的调用 CLI 怎么办？

**A**: 使用 `monkeypatch` 替换 `asyncio.create_subprocess_exec`：

```python
async def fake_exec(*args, **kwargs):
    return _StubProcess(0, b"fake output")

monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
```

---

## 参考资料

- [BaseAgent 源码](../src/agent_collab/agents/base.py)
- [Claude Code 适配器](../src/agent_collab/agents/claude_code.py) — 完整示例
- [OpenCode 适配器](../src/agent_collab/agents/opencode.py) — 简洁示例
- [插件接口](../src/agent_collab/plugins/interfaces.py) — AgentPlugin / HookPlugin / FormatterPlugin
- [插件管理器](../src/agent_collab/plugins/manager.py) — PluginManager
- [测试示例](../tests/test_agents.py) — 现有适配器的测试
- [用户手册](./user-manual.md) — 完整使用文档
- [API 参考](./api-reference.md) — 所有模块的 API 文档
