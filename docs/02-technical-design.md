# 技术方案设计 — AgentCollab

## 1. 系统架构

```
agent-collab/
├── src/agent_collab/
│   ├── __init__.py
│   ├── cli.py              # Typer CLI 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── workflow.py      # YAML 工作流解析与验证
│   │   ├── scheduler.py     # DAG 调度引擎
│   │   ├── executor.py      # 任务执行器
│   │   └── merger.py        # 结果合并 (git merge)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py          # Agent 适配器基类
│   │   ├── claude_code.py   # Claude Code 适配器
│   │   ├── codex.py         # Codex 适配器
│   │   └── aider.py         # Aider 适配器
│   ├── locks/
│   │   ├── __init__.py
│   │   └── file_lock.py     # 文件锁机制
│   └── display/
│       ├── __init__.py
│       └── progress.py      # 进度展示 (Rich TUI)
├── tests/
├── examples/
│   ├── fullstack.yaml       # 全栈开发示例
│   ├── code-review.yaml     # 写代码 + Review 示例
│   └── refactor.yaml        # 大规模重构示例
├── docs/
├── pyproject.toml
├── README.md
└── LICENSE
```

## 2. 核心数据流

```
workflow.yaml
    |
[Workflow Parser] -> TaskGraph (DAG)
    |
[Scheduler] -> 拓扑排序 -> 并行任务组
    |
[Executor] -> 分配 Agent -> 执行任务
    |                              |
[File Lock] <-> 文件锁检查    [Progress Display]
    |
[Merger] -> git merge 各分支
    |
最终结果
```

## 3. YAML 工作流定义

```yaml
name: fullstack-app
description: 全栈 Web 应用开发

agents:
  frontend:
    type: claude-code
    model: sonnet
    workdir: ./frontend
    allowed_tools: [Read, Write, Edit, Bash]
  backend:
    type: claude-code
    model: sonnet
    workdir: ./backend
    allowed_tools: [Read, Write, Edit, Bash]
  reviewer:
    type: claude-code
    model: opus
    allowed_tools: [Read]

tasks:
  - id: setup-backend
    agent: backend
    prompt: |
      Initialize a FastAPI project with SQLAlchemy...
    outputs: [backend/]

  - id: setup-frontend
    agent: frontend
    prompt: |
      Initialize a React project with TypeScript...
    outputs: [frontend/]

  - id: api-design
    depends_on: [setup-backend]
    agent: backend
    prompt: |
      Design REST API endpoints...
    outputs: [backend/api/]

  - id: frontend-integration
    depends_on: [setup-frontend, api-design]
    agent: frontend
    prompt: |
      Implement API client based on backend design...
    outputs: [frontend/src/api/]

  - id: review
    depends_on: [frontend-integration]
    agent: reviewer
    prompt: |
      Review the entire codebase for bugs...
    merge_strategy: comments

strategy:
  max_parallel: 2
  retry_on_failure: true
  max_retries: 2
  timeout_per_task: 600
```

## 4. 核心模块设计

### 4.1 Agent 适配器 (BaseAgent)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentResult:
    success: bool
    output: str
    files_changed: list[str]
    duration_seconds: float
    tokens_used: Optional[int] = None

class BaseAgent(ABC):
    @abstractmethod
    async def execute(
        self,
        prompt: str,
        workdir: str,
        allowed_tools: list[str],
        timeout: int = 600
    ) -> AgentResult:
        ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...
```

### 4.2 DAG 调度器 (Scheduler)

```python
from collections import defaultdict, deque

class TaskScheduler:
    def __init__(self, tasks):
        self.tasks = {t.id: t for t in tasks}
        self.graph = self._build_dag(tasks)

    def _build_dag(self, tasks):
        graph = defaultdict(set)
        for task in tasks:
            for dep in task.depends_on:
                graph[dep].add(task.id)
        return graph

    def get_execution_order(self):
        # Returns list of parallel task groups (topological sort)
        in_degree = {t: 0 for t in self.tasks}
        for t, deps in self.graph.items():
            in_degree[t] += len(deps)

        levels = []
        queue = deque([t for t, d in in_degree.items() if d == 0])

        while queue:
            level = list(queue)
            levels.append(level)
            next_queue = deque()
            for t in level:
                for neighbor in self.graph[t]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        return levels
```

### 4.3 文件锁 (FileLock)

```python
import fcntl
from pathlib import Path

class FileLockManager:
    def __init__(self, lock_dir):
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(exist_ok=True)

    def acquire(self, file_path, task_id):
        lock_file = self.lock_dir / f"{Path(file_path).name}.lock"
        try:
            fd = open(lock_file, 'w')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd.write(task_id)
            return True
        except OSError:
            return False

    def release(self, file_path):
        lock_file = self.lock_dir / f"{Path(file_path).name}.lock"
        if lock_file.exists():
            lock_file.unlink()
```

## 5. 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 生态丰富, Agent 工具链多为 Python |
| CLI | Typer + Rich | 现代 CLI 框架, TUI 进度展示 |
| 工作流定义 | PyYAML | 轻量, 开发者友好 |
| 异步执行 | asyncio | 并行任务调度 |
| 进程管理 | subprocess | 调用外部 CLI Agent |
| 文件锁 | fcntl | Unix 原生, 轻量 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |
| 打包 | pyproject.toml + setuptools | 标准 Python 打包 |
| Lint | ruff | 快速, 功能全面 |

## 6. 测试策略

- **单元测试**: DAG 调度器、YAML 解析、文件锁
- **集成测试**: 完整工作流执行 (Mock Agent)
- **端到端测试**: 真实 Agent 执行简单任务
- **覆盖率目标**: > 80%

## 7. 风险评估

| 风险 | 概率 | 影响 | 缓解方案 |
|------|------|------|----------|
| Agent CLI 变更 | 中 | 高 | 适配器模式, 隔离变化 |
| 并发文件冲突 | 高 | 中 | 文件锁 + 合并策略 |
| Agent 执行超时 | 中 | 中 | 超时控制 + 重试机制 |
| YAML 解析错误 | 低 | 低 | Pydantic 验证 + 友好错误提示 |
