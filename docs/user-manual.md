# AgentCollab 用户手册

## 目录

1. [简介](#简介)
2. [安装](#安装)
3. [快速开始](#快速开始)
4. [核心概念](#核心概念)
5. [工作流定义](#工作流定义)
6. [Agent 适配器](#agent-适配器)
7. [多模型调度](#多模型调度)
8. [条件分支和循环](#条件分支和循环)
9. [HITL 审批](#hitl-审批)
10. [分布式执行](#分布式执行)
11. [企业级安全](#企业级安全)
12. [Web UI](#web-ui)
13. [CLI 命令](#cli-命令)
14. [配置](#配置)
15. [故障排除](#故障排除)
16. [最佳实践](#最佳实践)

---

## 简介

AgentCollab 是一个多 Agent 编排引擎，用于协调多个 AI 编程助手（如 Claude Code、Codex、Aider）协同工作。

### 核心特性

- **工作流引擎**：YAML 定义工作流，DAG 调度，并行执行
- **多模型调度**：智能路由到不同 LLM 提供商
- **条件分支和循环**：动态工作流控制
- **HITL 审批**：人工审批和输入节点
- **分布式执行**：跨多个 Worker 分布式执行
- **企业级安全**：RBAC、多租户、API Key、审计日志
- **Web UI**：可视化工作流编辑器
- **插件系统**：可扩展的插件架构

### 适用场景

- **代码生成**：多个 Agent 并行生成不同模块
- **代码审查**：一个 Agent 写代码，另一个 Agent 审查
- **大规模重构**：将重构任务分解为多个子任务
- **全栈开发**：前后端并行开发
- **测试驱动开发**：先写测试，再写实现

---

## 安装

### 使用 pip

```bash
pip install agent-collab
```

### 使用 uv（推荐）

```bash
uv pip install agent-collab
```

### 从源码安装

```bash
git clone https://github.com/JianFeiGan/agent-collab.git
cd agent-collab
uv sync
```

### 依赖要求

- Python 3.11+
- 至少一个 AI Agent CLI：
  - [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
  - [Codex](https://github.com/openai/codex)
  - [Aider](https://aider.chat)
  - [OpenCode](https://github.com/opencode-ai/opencode)

---

## 快速开始

### 1. 创建工作流文件

创建 `workflow.yaml`：

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
```

### 2. 执行工作流

```bash
agent-collab run workflow.yaml
```

### 3. 验证工作流

```bash
agent-collab validate workflow.yaml
```

### 4. 查看可用 Agent

```bash
agent-collab list-agents
```

---

## 核心概念

### 工作流（Workflow）

工作流是一个 YAML 文件，定义了一系列任务及其依赖关系。

### 任务（Task）

任务是工作流中的最小执行单元，由一个 Agent 执行。

### Agent

Agent 是执行任务的 AI 编程助手，如 Claude Code、Codex 等。

### 依赖（Dependencies）

任务之间的依赖关系，决定了执行顺序。

### 执行级别（Execution Level）

可以并行执行的任务组。

---

## 工作流定义

### 基本结构

```yaml
name: workflow-name
description: Workflow description

agents:
  agent-name:
    type: agent-type
    model: model-name
    workdir: working-directory
    allowed_tools: [tool1, tool2]

tasks:
  - id: task-id
    agent: agent-name
    prompt: Task prompt
    depends_on: [other-task-id]
    outputs: [file1.py, file2.py]
    priority: 0

strategy:
  max_parallel: 4
  retry_on_failure: false
  max_retries: 0
  timeout_per_task: 600

variables:
  key: value
```

### Agent 配置

```yaml
agents:
  coder:
    type: claude-code
    model: sonnet
    workdir: ./src
    allowed_tools: [Read, Write, Edit, Bash]
```

### 任务配置

```yaml
tasks:
  - id: implement
    agent: coder
    prompt: Implement the feature
    depends_on: [setup]
    outputs: [main.py, utils.py]
    priority: 10
    when: "${environment} == 'development'"
```

### 策略配置

```yaml
strategy:
  max_parallel: 4
  retry_on_failure: true
  max_retries: 3
  timeout_per_task: 600
  retry_delay: 1.0
  checkpoint_enabled: true
```

---

## Agent 适配器

### Claude Code

```yaml
agents:
  coder:
    type: claude-code
    model: sonnet
    allowed_tools: [Read, Write, Edit, Bash]
```

### Codex

```yaml
agents:
  coder:
    type: codex
    model: code-davinci-002
    allowed_tools: [Read, Write]
```

### Aider

```yaml
agents:
  coder:
    type: aider
    model: gpt-4
    allowed_tools: [Read, Write, Edit]
```

### OpenCode

```yaml
agents:
  coder:
    type: opencode
    model: gpt-4
    allowed_tools: [Read, Write, Edit, Bash]
```

---

## 多模型调度

### 使用多模型调度器

```python
from agent_collab.llm.scheduler import MultiModelScheduler, SchedulerConfig, ModelConfig, SelectionStrategy

config = SchedulerConfig(
    models=[
        ModelConfig(provider="openai", model="gpt-4o", api_key="sk-..."),
        ModelConfig(provider="anthropic", model="claude-3-opus", api_key="sk-ant-..."),
        ModelConfig(provider="google", model="gemini-1.5-pro", api_key="AIza..."),
    ],
    strategy=SelectionStrategy.QUALITY_FIRST,
)

scheduler = MultiModelScheduler(config)
response = await scheduler.generate("Explain quantum computing")
```

### 选择策略

- `ROUND_ROBIN`：轮询
- `COST_OPTIMIZED`：成本优先
- `QUALITY_FIRST`：质量优先
- `LATENCY_OPTIMIZED`：延迟优先
- `RANDOM`：随机

---

## 条件分支和循环

### 条件分支

```yaml
conditions:
  - id: check_tests
    condition:
      field: test_result
      operator: eq
      value: pass
      then: deploy
      else: fix_tests
```

### 循环

```yaml
loops:
  - id: process_items
    loop:
      type: for_each
      items: [item1, item2, item3]
      body: [process_item]
```

---

## HITL 审批

### 审批节点

```python
from agent_collab.hitl.nodes import HITLManager, ApprovalNodeConfig

config = ApprovalNodeConfig(
    id="deploy_approval",
    title="Deploy to Production",
    description="Please approve deployment",
    required_approvals=1,
    timeout_seconds=3600,
)

manager = HITLManager(provider)
request = await manager.create_approval(config, "workflow_1")
```

### 输入节点

```python
from agent_collab.hitl import InputType
from agent_collab.hitl.nodes import InputNodeConfig

config = InputNodeConfig(
    id="select_env",
    title="Select Environment",
    input_type=InputType.SELECT,
    options=[
        {"label": "Production", "value": "prod"},
        {"label": "Staging", "value": "staging"},
    ],
)
```

---

## 分布式执行

### 创建分布式调度器

```python
from agent_collab.distributed.queue import InMemoryTaskQueue, InMemoryWorkerManager, LoadBalancer
from agent_collab.distributed.scheduler import DistributedScheduler

task_queue = InMemoryTaskQueue()
worker_manager = InMemoryWorkerManager()
load_balancer = LoadBalancer(worker_manager)

scheduler = DistributedScheduler(
    task_queue=task_queue,
    worker_manager=worker_manager,
    executor=your_executor,
    load_balancer=load_balancer,
)

await scheduler.start()
```

### 提交任务

```python
from agent_collab.distributed import DistributedTask

task = DistributedTask(
    workflow_id="wf_1",
    task_id="task_1",
    agent_type="claude-code",
    prompt="Implement feature",
    priority=10,
)

await scheduler.submit_task(task)
```

---

## 企业级安全

### 用户认证

```python
from agent_collab.security import User, UserRole, hash_password
from agent_collab.security.providers import InMemoryAuthProvider

auth = InMemoryAuthProvider()

user = User(
    username="admin",
    email="admin@example.com",
    hashed_password=hash_password("secure_password"),
    role=UserRole.ADMIN,
    tenant_id="tenant_1",
)

await auth.create_user(user)
authenticated = await auth.authenticate("admin", "secure_password")
```

### RBAC 权限检查

```python
from agent_collab.security import has_permission, UserRole, Permission

if has_permission(user.role, Permission.WORKFLOW_CREATE):
    print("User can create workflows")
```

### API Key 管理

```python
from agent_collab.security import APIKey, Permission
from agent_collab.security.providers import InMemoryAPIKeyProvider

api_key_provider = InMemoryAPIKeyProvider()

api_key = APIKey(
    user_id="user_1",
    tenant_id="tenant_1",
    name="My API Key",
    permissions={Permission.WORKFLOW_READ, Permission.TASK_READ},
)

raw_key = await api_key_provider.create_api_key(api_key)
validated = await api_key_provider.validate_api_key(raw_key)
```

---

## Web UI

### 启动 Web UI

```bash
cd web
npm install
npm run dev
```

打开 http://localhost:5173

### 功能

- 拖拽式节点编辑
- 实时执行面板
- 导出为 YAML/JSON
- 自定义节点类型

---

## CLI 命令

### run

执行工作流：

```bash
agent-collab run workflow.yaml
```

### validate

验证工作流：

```bash
agent-collab validate workflow.yaml
```

### list-agents

查看可用 Agent：

```bash
agent-collab list-agents
```

### replay

从检查点恢复：

```bash
agent-collab replay checkpoint-id workflow.yaml
```

### checkpoints

管理检查点：

```bash
agent-collab checkpoints list
agent-collab checkpoints delete checkpoint-id
```

---

## 配置

### 配置文件

配置文件位于 `~/.agent-collab/config.yaml`：

```yaml
# 默认 Agent 配置
default_agent:
  type: claude-code
  model: sonnet

# 执行策略
strategy:
  max_parallel: 4
  retry_on_failure: true
  max_retries: 3
  timeout_per_task: 600

# 日志配置
logging:
  level: INFO
  file: ~/.agent-collab/logs/agent.log
```

### 环境变量

- `AGENT_COLLAB_CONFIG`：配置文件路径
- `AGENT_COLLAB_LOG_LEVEL`：日志级别
- `AGENT_COLLAB_TIMEOUT`：默认超时时间

---

## 故障排除

### 常见问题

#### 1. Agent CLI 未找到

```
Error: Agent 'claude-code' CLI is not installed
```

**解决方案**：安装对应的 Agent CLI：

```bash
npm install -g @anthropic-ai/claude-code
```

#### 2. 循环依赖

```
Error: Dependency cycle detected: a -> b -> c -> a
```

**解决方案**：检查任务依赖关系，消除循环。

#### 3. 任务超时

```
Error: Task 'task_1' timed out after 600 seconds
```

**解决方案**：增加超时时间或优化任务：

```yaml
strategy:
  timeout_per_task: 1200
```

#### 4. 文件锁冲突

```
Error: Could not acquire lock for file.py
```

**解决方案**：确保没有其他进程在修改文件。

---

## 最佳实践

### 1. 工作流设计

- **单一职责**：每个任务只做一件事
- **合理并行**：将独立任务并行执行
- **明确依赖**：清晰定义任务依赖关系
- **设置超时**：为长时间任务设置合理超时

### 2. Agent 选择

- **代码生成**：使用 Claude Code 或 Codex
- **代码审查**：使用 Claude Code (opus)
- **简单任务**：使用轻量级 Agent

### 3. 错误处理

- **启用重试**：对于可能失败的任务
- **设置降级策略**：定义失败后的处理方式
- **使用检查点**：长时间工作流启用检查点

### 4. 安全性

- **最小权限**：只授予必要的权限
- **API Key 管理**：定期轮换 API Key
- **审计日志**：启用审计日志记录

### 5. 性能优化

- **合理并行度**：根据系统资源设置并行度
- **任务拆分**：将大任务拆分为小任务
- **缓存结果**：对于重复任务缓存结果

---

## 示例

### 示例 1：全栈开发

```yaml
name: fullstack-app
description: Build a full-stack application

agents:
  backend:
    type: claude-code
    model: sonnet
    workdir: ./backend
    allowed_tools: [Read, Write, Edit, Bash]
  frontend:
    type: claude-code
    model: sonnet
    workdir: ./frontend
    allowed_tools: [Read, Write, Edit, Bash]
  reviewer:
    type: claude-code
    model: opus
    allowed_tools: [Read]

tasks:
  - id: setup-backend
    agent: backend
    prompt: Create FastAPI backend with health endpoint

  - id: setup-frontend
    agent: frontend
    prompt: Create React frontend with routing

  - id: integrate
    agent: backend
    depends_on: [setup-backend, setup-frontend]
    prompt: Connect frontend to backend API

  - id: review
    agent: reviewer
    depends_on: [integrate]
    prompt: Review the full-stack integration
```

### 示例 2：条件工作流

```yaml
name: conditional-deploy
description: Deploy with approval

agents:
  coder:
    type: claude-code
    model: sonnet
  deployer:
    type: claude-code
    model: sonnet

tasks:
  - id: run_tests
    agent: coder
    prompt: Run all tests

conditions:
  - id: check_tests
    condition:
      field: test_result
      operator: eq
      value: pass
      then: deploy
      else: fix_tests

tasks:
  - id: deploy
    agent: deployer
    prompt: Deploy to production

  - id: fix_tests
    agent: coder
    prompt: Fix failing tests
```

---

## 更多资源

- [GitHub 仓库](https://github.com/JianFeiGan/agent-collab)
- [API 文档](https://github.com/JianFeiGan/agent-collab/tree/main/docs/api)
- [示例工作流](https://github.com/JianFeiGan/agent-collab/tree/main/examples)
- [贡献指南](https://github.com/JianFeiGan/agent-collab/blob/main/CONTRIBUTING.md)

---

**版本**：v2.0.0
**最后更新**：2026-05-20
