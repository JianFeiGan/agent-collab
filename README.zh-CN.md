中文版 | [English](README.md)

# 🤖 AgentCollab

**面向 AI 编程助手的多智能体编排引擎。**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-51%20passing-brightgreen.svg)](tests/)

用 YAML 定义工作流，AgentCollab 负责任务调度、并行执行、文件冲突防护和结果合并——让你的 AI 编程团队协同作战，而非相互掣肘。

---

## 为什么选择 AgentCollab？

| 痛点 | 解决方案 |
|------|----------|
| 多个 AI 智能体同时编辑同一文件 | 文件锁机制防止写入冲突 |
| 手动排列各智能体的任务顺序 | DAG 调度器自动解析依赖关系 |
| 串行执行浪费时间 | 无依赖任务并行执行 |
| 多智能体运行过程不可见 | Rich TUI 实时展示执行进度 |
| 智能体输出需要手动合并 | 基于 Git 的合并策略自动处理集成 |

---

## 安装

```bash
# 使用 pip
pip install agent-collab

# 使用 uv（推荐）
uv pip install agent-collab
```

需要 Python 3.11+。你还需要至少安装一个 AI 智能体 CLI：

| 智能体 | 安装方式 |
|--------|----------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` |
| [Codex](https://github.com/openai/codex) | `npm install -g @openai/codex` |
| [Aider](https://aider.chat) | `pip install aider-chat` |

---

## 快速上手

创建工作流文件 `workflow.yaml`：

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

运行：

```bash
agent-collab run workflow.yaml
```

---

## CLI 命令参考

### `agent-collab run <workflow.yaml>`

执行工作流。任务按依赖顺序执行，无依赖的任务并行运行。

```bash
agent-collab run workflow.yaml              # 运行工作流
agent-collab run workflow.yaml --verbose    # 显示详细输出
```

### `agent-collab validate <workflow.yaml>`

验证工作流文件，不执行。检查项包括：
- YAML 语法
- 引用的智能体是否存在
- 依赖的任务是否存在
- 是否存在循环依赖

```bash
agent-collab validate workflow.yaml
```

### `agent-collab list-agents`

列出已注册的智能体及其可用状态。

```bash
agent-collab list-agents
```

---

## 工作流 YAML 格式

```yaml
name: workflow-name          # 必填
description: What it does    # 可选

agents:                      # 智能体定义
  agent-id:                  # 唯一标识符
    type: claude-code        # 智能体类型 (claude-code | codex | aider)
    model: sonnet            # 使用的模型（默认：sonnet）
    workdir: ./path          # 工作目录（默认：.）
    allowed_tools: [Read]    # 允许使用的工具

tasks:                       # 任务定义
  - id: task-id              # 唯一标识符
    agent: agent-id          # 引用上方定义的智能体
    prompt: |                # 给智能体的指令
      Do this specific thing.
    depends_on: [other-id]   # 必须先完成的任务
    outputs: [path/]         # 该任务可能修改的文件/目录
    merge_strategy: comments # 输出合并策略

strategy:                    # 执行配置
  max_parallel: 4            # 最大并行任务数（默认：4）
  retry_on_failure: false    # 失败时是否重试（默认：false）
  max_retries: 0             # 最大重试次数（默认：0）
  timeout_per_task: 600      # 单任务超时秒数（默认：600）
```

---

## 内置智能体

| 智能体 | 类型 | 适用场景 |
|--------|------|----------|
| **Claude Code** | `claude-code` | 复杂推理、多文件编辑、代码审查 |
| **Codex** | `codex` | 快速代码生成、单文件任务 |
| **Aider** | `aider` | Git 感知编辑、结对编程风格 |

所有智能体均实现 `BaseAgent` 接口。适配器实现详见 [`src/agent_collab/agents/`](src/agent_collab/agents/)。

---

## 示例

[`examples/`](examples/) 目录包含开箱即用的工作流示例：

| 工作流 | 说明 |
|--------|------|
| [`fullstack.yaml`](examples/fullstack.yaml) | 并行构建 FastAPI 后端 + React 前端，然后进行代码审查 |
| [`code-review.yaml`](examples/code-review.yaml) | 实现功能 → 代码审查 → 自动修复问题 |
| [`refactor.yaml`](examples/refactor.yaml) | 并行重构两个模块，然后集成变更 |

---

## 架构

```
workflow.yaml
    │
    ▼
┌──────────────┐    Pydantic 校验 + 循环依赖检测
│ WorkflowParser│
└──────┬───────┘
       │
       ▼
┌──────────────┐    Kahn 算法 → 并行执行层级划分
│ TaskScheduler│
└──────┬───────┘
       │
       ▼
┌──────────────┐    asyncio.Semaphore 控制并行度
│ TaskExecutor ├────────────────────┐
└──────┬───────┘                    │
       │                            ▼
┌──────┴───────┐          ┌──────────────┐
│FileLockManager│          │ BaseAgent    │
│ (fcntl 锁)   │          │ (子进程)     │
└──────┬───────┘          └──────────────┘
       │
       ▼
┌──────────────┐    Git 分支/合并工作流
│ ResultMerger │
└──────────────┘
```

---

## 参与贡献

开发环境搭建、编码规范及如何添加新的智能体适配器，请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

MIT 许可证。详见 [LICENSE](LICENSE)。
