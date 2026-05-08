# 让多个AI编程助手协同工作：AgentCollab多Agent编排引擎实战

## 痛点：单Agent的天花板

你是否遇到过这样的场景：用Claude Code写完后端，手动切到Codex生成前端，再用Aider做代码审查？每次切换都要复制上下文、手动排序任务、处理文件冲突。当项目规模增长，这种"人工编排"的方式效率越来越低。

单个AI Agent再强大，也无法同时处理前端、后端、测试、审查。我们需要的不是一个更强的Agent，而是让多个Agent像团队一样协作。

## AgentCollab是什么

AgentCollab是一个多Agent编排引擎，用YAML定义工作流，自动调度Claude Code、Codex、Aider等AI编程助手并行执行任务。

核心能力：

- **DAG调度器**：基于拓扑排序自动解析任务依赖，无依赖的任务并行执行
- **文件锁**：fcntl级别的文件锁，防止多个Agent同时写入同一文件
- **异步执行器**：asyncio + Semaphore控制并发度
- **Git合并策略**：分支式任务输出合并，保留完整历史

## 架构一览

```
workflow.yaml
    │
    ▼
┌──────────────┐   Pydantic校验 + 环检测
│ WorkflowParser│
└──────┬───────┘
       │
       ▼
┌──────────────┐   Kahn算法 → 并行执行层级
│ TaskScheduler│
└──────┬───────┘
       │
       ▼
┌──────────────┐   asyncio.Semaphore 并发控制
│ TaskExecutor ├────────────────────┐
└──────┬───────┘                    │
       │                            ▼
┌──────┴───────┐          ┌──────────────┐
│FileLockManager│          │ BaseAgent    │
│ (fcntl锁)    │          │ (子进程调用) │
└──────┬───────┘          └──────────────┘
       │
       ▼
┌──────────────┐   Git分支/合并工作流
│ ResultMerger │
└──────────────┘
```

## 实战：5分钟构建全栈应用

### 第一步：定义工作流

```yaml
name: fullstack-webapp
description: 并行构建FastAPI后端和React前端，最后安全审查

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
    prompt: 创建FastAPI项目，包含User模型和CRUD端点
    outputs: [backend/]

  - id: setup-frontend
    agent: frontend
    prompt: 创建React+TypeScript项目，包含用户列表和表单组件
    outputs: [frontend/]

  - id: review
    depends_on: [setup-backend, setup-frontend]
    agent: reviewer
    prompt: 审查全栈项目的生产就绪性：安全、错误处理、类型安全

strategy:
  max_parallel: 2
  timeout_per_task: 600
```

### 第二步：执行

```bash
# 验证工作流
agent-collab validate workflow.yaml

# 运行
agent-collab run workflow.yaml

# 查看可用Agent
agent-collab list-agents
```

### 第三步：观察执行

执行时，backend和frontend任务并行运行（它们没有依赖关系），review任务等待两者完成后自动启动。Rich TUI实时显示每个任务的进度和耗时。

## 关键技术决策

**为什么用DAG而不是简单队列？** 真实工作流中任务之间有复杂依赖关系。DAG调度器用Kahn算法做拓扑排序，自动识别哪些任务可以并行，哪些必须等待。还内置了环检测，防止死锁。

**为什么用fcntl文件锁？** 多个Agent可能同时修改同一个文件。fcntl是操作系统级别的锁，比应用层锁更可靠。每个任务执行前声明outputs，锁管理器自动处理加锁和释放。

**为什么用asyncio？** Agent执行是I/O密集型（等待子进程），asyncio让我们用Semaphore轻松控制"最多同时运行N个Agent"，避免资源争抢。

## 快速开始

```bash
pip install agent-collab
# 或
uv pip install agent-collab
```

需要Python 3.11+，以及至少一个AI Agent CLI（Claude Code、Codex或Aider）。

## 路线图

- v0.2：Web UI仪表板，实时可视化工作流执行
- v0.3：自定义Agent适配器，支持接入任意CLI工具
- v0.4：工作流模板市场，社区共享常用工作流
- v0.5：分布式执行，跨机器调度Agent

## 写在最后

AgentCollab不是要取代单个AI Agent，而是让它们像真正的开发团队一样协作。当你需要多个Agent处理不同关注点时，用YAML定义工作流，让调度器处理依赖、并发和冲突——你只需要审查最终结果。

项目地址：https://github.com/user/agent-collab（MIT协议）
