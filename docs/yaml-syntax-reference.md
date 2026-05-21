# AgentCollab YAML 工作流语法参考

本文档是 AgentCollab YAML 工作流文件的完整语法参考手册。

---

## 目录

1. [文件结构概览](#文件结构概览)
2. [顶层字段](#顶层字段)
3. [Agent 定义](#agent-定义)
4. [任务定义](#任务定义)
5. [执行策略](#执行策略)
6. [变量替换](#变量替换)
7. [条件分支](#条件分支)
8. [循环结构](#循环结构)
9. [文件引用（include）](#文件引用include)
10. [降级策略](#降级策略)
11. [完整示例](#完整示例)
12. [字段速查表](#字段速查表)

---

## 文件结构概览

一个完整的 AgentCollab 工作流文件包含以下顶层结构：

```yaml
name: my-workflow              # 必填：工作流名称
description: 描述信息           # 可选：工作流描述
agents: { ... }                # 必填：Agent 定义
tasks: [ ... ]                 # 必填：任务列表
conditions: [ ... ]            # 可选：条件节点
loops: [ ... ]                 # 可选：循环节点
strategy: { ... }              # 可选：执行策略
variables: { ... }             # 可选：变量定义
include: [ ... ]               # 可选：引用其他文件
```

---

## 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | ✅ | — | 工作流名称，用于标识和日志 |
| `description` | string | ❌ | `""` | 工作流描述 |
| `agents` | map | ✅ | — | Agent 定义，键为 Agent 名称 |
| `tasks` | list | ✅ | — | 任务列表 |
| `conditions` | list | ❌ | `[]` | 条件节点列表 |
| `loops` | list | ❌ | `[]` | 循环节点列表 |
| `strategy` | object | ❌ | 见[执行策略](#执行策略) | 执行策略配置 |
| `variables` | map | ❌ | `{}` | 变量定义 |
| `include` | list | ❌ | `[]` | 引用的其他 YAML 文件路径 |

---

## Agent 定义

`agents` 字段定义工作流中使用的所有 Agent。每个 Agent 是一个命名配置，指定其类型、模型和行为。

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `type` | string | ✅ | — | Agent 类型，支持：`claude-code`、`codex`、`aider`、`opencode` |
| `model` | string | ❌ | `"sonnet"` | 使用的模型 |
| `workdir` | string | ❌ | `"."` | Agent 的工作目录 |
| `allowed_tools` | list | ❌ | `[]` | Agent 可使用的工具列表 |

### 示例

```yaml
agents:
  # 代码编写 Agent — 可读写文件、执行命令
  coder:
    type: claude-code
    model: sonnet
    workdir: ./src
    allowed_tools: [Read, Write, Edit, Bash]

  # 代码审查 Agent — 只读，使用更强的模型
  reviewer:
    type: claude-code
    model: opus
    allowed_tools: [Read]

  # Codex Agent — 用于快速代码生成
  quick-coder:
    type: codex
    model: codex-mini
    workdir: ./lib

  # Aider Agent — 多文件编辑
  refactor-agent:
    type: aider
    model: gpt-4o
    workdir: ./legacy

  # OpenCode Agent
  doc-writer:
    type: opencode
    workdir: ./docs
```

### Agent 类型列表

| 类型 | 说明 | 安装方式 |
|------|------|----------|
| `claude-code` | Anthropic Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| `codex` | OpenAI Codex CLI | `npm install -g @openai/codex` |
| `aider` | Aider AI pair programmer | `pip install aider-chat` |
| `opencode` | OpenCode CLI | 见 [OpenCode 文档](https://github.com/opencode-ai/opencode) |

---

## 任务定义

`tasks` 字段是一个列表，每个元素定义一个独立任务。

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string | ✅ | — | 任务唯一标识符 |
| `agent` | string | ✅ | — | 使用的 Agent 名称（引用 `agents` 中的键） |
| `prompt` | string | ✅ | — | 任务提示词 |
| `priority` | int | ❌ | `0` | 任务优先级，数值越大越先执行 |
| `depends_on` | list | ❌ | `[]` | 依赖的任务 ID 列表 |
| `outputs` | list | ❌ | `[]` | 任务产出的文件/目录路径 |
| `merge_strategy` | string | ❌ | `null` | 合并策略 |
| `when` | string | ❌ | `null` | 条件执行表达式 |
| `degradation` | object | ❌ | `null` | 降级策略配置 |
| `node_type` | string | ❌ | `"task"` | 节点类型，通常为 `task` |

### 基本示例

```yaml
tasks:
  - id: write-tests
    agent: coder
    prompt: |
      为 auth.py 中的所有公开函数编写 pytest 测试。
      使用 mock 隔离外部依赖，确保测试覆盖率 > 90%。
    outputs: [tests/test_auth.py]
```

### 带依赖的任务

```yaml
tasks:
  - id: implement-api
    agent: coder
    prompt: 实现 REST API 接口
    outputs: [src/api.py]

  - id: write-tests
    agent: coder
    depends_on: [implement-api]
    prompt: |
      为 src/api.py 编写完整的测试套件。
      参考上一步的输出来了解 API 接口。
    outputs: [tests/test_api.py]

  - id: review
    agent: reviewer
    depends_on: [implement-api, write-tests]
    prompt: 审查代码质量和测试覆盖
    merge_strategy: comments
```

### 任务输出传递

任务产出可通过 `${task_id.output}` 传递给下游任务：

```yaml
tasks:
  - id: analyze
    agent: coder
    prompt: 分析代码库结构并输出依赖关系
    outputs: [analysis.md]

  - id: refactor
    agent: coder
    depends_on: [analyze]
    prompt: |
      根据分析结果进行重构：
      ${analyze.output}
```

---

## 执行策略

`strategy` 字段控制工作流的全局执行行为。

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `max_parallel` | int | ❌ | `4` | 最大并行任务数 |
| `retry_on_failure` | bool | ❌ | `false` | 失败时是否自动重试 |
| `max_retries` | int | ❌ | `0` | 最大重试次数 |
| `timeout_per_task` | int | ❌ | `600` | 单任务超时时间（秒） |
| `retry_delay` | float | ❌ | `1.0` | 重试间隔（秒），支持指数退避 |
| `checkpoint_enabled` | bool | ❌ | `false` | 是否启用检查点 |

### 示例

```yaml
strategy:
  max_parallel: 3            # 最多 3 个任务并行
  retry_on_failure: true     # 失败自动重试
  max_retries: 2             # 最多重试 2 次
  timeout_per_task: 900      # 每个任务最多 15 分钟
  retry_delay: 2.0           # 重试间隔 2 秒
  checkpoint_enabled: true   # 启用检查点，支持断点恢复
```

---

## 变量替换

工作流支持在 `prompt` 和其他文本字段中使用变量替换。

### 语法

| 语法 | 说明 | 示例 |
|------|------|------|
| `${VAR}` | 引用变量，无默认值 | `${PROJECT_NAME}` |
| `${VAR:-default}` | 引用变量，带默认值 | `${ENV:-production}` |
| `${task_id.output}` | 引用任务输出 | `${analyze.output}` |

### 变量查找顺序

1. `variables` 字典中定义的变量
2. 系统环境变量（`os.environ`）
3. 如果使用 `:-` 语法，则回退到默认值

### 示例

```yaml
variables:
  PROJECT_NAME: my-app
  PYTHON_VERSION: "3.11"

agents:
  coder:
    type: claude-code
    model: sonnet

tasks:
  - id: setup
    agent: coder
    prompt: |
      创建项目 ${PROJECT_NAME}，使用 Python ${PYTHON_VERSION}。
      部署环境：${DEPLOY_ENV:-staging}
      输出目录：${OUTPUT_DIR:-./build}
```

在上例中：
- `${PROJECT_NAME}` → `my-app`（来自 variables）
- `${PYTHON_VERSION}` → `3.11`（来自 variables）
- `${DEPLOY_ENV:-staging}` → 环境变量 `DEPLOY_ENV` 的值，或 `staging`
- `${OUTPUT_DIR:-./build}` → 环境变量 `OUTPUT_DIR` 的值，或 `./build`

---

## 条件分支

条件节点允许根据上下文变量决定执行路径。

### 条件节点字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 条件节点 ID |
| `depends_on` | list | ❌ | 依赖的节点 ID |
| `condition.field` | string | ✅ | 要检查的上下文字段名 |
| `condition.operator` | string | ✅ | 比较运算符 |
| `condition.value` | any | ✅ | 比较目标值 |
| `condition.then` | string | ✅ | 条件为真时执行的节点 ID |
| `condition.else` | string | ❌ | 条件为假时执行的节点 ID |

### 支持的运算符

| 运算符 | 说明 | 适用类型 |
|--------|------|----------|
| `eq` | 等于 | 任意 |
| `ne` | 不等于 | 任意 |
| `gt` | 大于 | 数值 |
| `lt` | 小于 | 数值 |
| `gte` | 大于等于 | 数值 |
| `lte` | 小于等于 | 数值 |
| `contains` | 包含子串 | 字符串 |
| `not_contains` | 不包含子串 | 字符串 |
| `in` | 在列表中 | 任意 |
| `not_in` | 不在列表中 | 任意 |
| `regex` | 正则匹配 | 字符串 |

### 示例

```yaml
variables:
  test_coverage: "85"

conditions:
  - id: check-coverage
    condition:
      field: test_coverage
      operator: gte
      value: 80
      then: deploy
      else: fix-coverage

tasks:
  - id: run-tests
    agent: coder
    prompt: 运行测试套件并输出覆盖率

  - id: fix-coverage
    depends_on: [run-tests]
    agent: coder
    prompt: 测试覆盖率不足 80%，请补充测试用例

  - id: deploy
    depends_on: [run-tests]
    agent: coder
    prompt: 测试通过，执行部署流程
```

### 条件节点的执行流程

1. 当依赖的所有前置节点完成后，条件节点被触发
2. 评估 `condition` 中定义的条件
3. 条件为真 → 调度 `then` 指向的节点
4. 条件为假 → 调度 `else` 指向的节点（如果存在）

---

## 循环结构

循环节点支持 `for_each` 和 `while` 两种循环模式。

### 循环节点字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 循环节点 ID |
| `depends_on` | list | ❌ | 依赖的节点 ID |
| `loop.type` | string | ✅ | 循环类型：`for_each` 或 `while` |
| `loop.items` | string \| list | ❌ | `for_each` 的迭代项（可引用变量名） |
| `loop.condition` | string | ❌ | `while` 的条件表达式 |
| `loop.max_iterations` | int | ❌ | 最大迭代次数（默认 100） |
| `loop.body` | list | ✅ | 循环体中的任务 ID 列表 |

### for_each 循环

```yaml
variables:
  modules: "auth,api,db,utils"

loops:
  - id: lint-each-module
    loop:
      type: for_each
      items:
        - auth
        - api
        - db
        - utils
      body: [lint-task]

tasks:
  - id: lint-task
    agent: coder
    prompt: |
      对 ${item} 模块运行 lint 检查并修复所有问题。
      这是第 ${index} 个模块。
```

循环会展开为 `lint-task_0`、`lint-task_1`、`lint-task_2`、`lint-task_3` 四个独立任务。

### while 循环

```yaml
loops:
  - id: fix-loop
    loop:
      type: while
      condition: tests_failing
      max_iterations: 5
      body: [fix-and-retest]

tasks:
  - id: fix-and-retest
    agent: coder
    prompt: |
      修复失败的测试（迭代 ${index}），然后重新运行测试。
```

### 循环变量

在循环体的任务 prompt 中可使用以下变量：

| 变量 | 说明 |
|------|------|
| `${item}` | 当前迭代项（仅 `for_each`） |
| `${index}` | 当前迭代索引（从 0 开始） |

---

## 文件引用（include）

`include` 字段允许将工作流拆分到多个文件中。

### 合并规则

被引用文件中的以下字段会被合并到主文件：
- `agents` — 合并到主文件的 agents（同名覆盖）
- `tasks` — 追加到主文件的 tasks 列表
- `conditions` — 追加到主文件的 conditions 列表
- `loops` — 追加到主文件的 loops 列表

路径相对于主文件所在目录解析。

### 示例

**主文件 `workflow.yaml`：**

```yaml
name: modular-workflow
description: 使用 include 组织大型工作流

include:
  - agents/ai-agents.yaml
  - tasks/setup-tasks.yaml

agents:
  main-agent:
    type: claude-code
    model: sonnet

tasks:
  - id: final-integration
    agent: main-agent
    depends_on: [setup-db, setup-auth]
    prompt: 集成所有模块并运行集成测试
```

**`agents/ai-agents.yaml`：**

```yaml
agents:
  db-agent:
    type: claude-code
    model: sonnet
    workdir: ./database
    allowed_tools: [Read, Write, Edit, Bash]

  auth-agent:
    type: claude-code
    model: sonnet
    workdir: ./auth
    allowed_tools: [Read, Write, Edit]
```

**`tasks/setup-tasks.yaml`：**

```yaml
tasks:
  - id: setup-db
    agent: db-agent
    prompt: 创建数据库 schema 和迁移文件

  - id: setup-auth
    agent: auth-agent
    prompt: 实现 JWT 认证中间件
```

---

## 降级策略

`degradation` 字段定义任务失败时的处理方式。

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `policy` | string | ❌ | `"abort"` | 降级策略 |
| `fallback_task_id` | string | ❌ | `null` | 失败时执行的备用任务 ID |
| `max_failures` | int | ❌ | `1` | 触发降级前的最大失败次数 |

### 策略类型

| 策略 | 说明 |
|------|------|
| `abort` | 中止整个工作流（默认） |
| `skip` | 跳过失败任务，继续执行 |
| `continue` | 标记为失败但继续执行下游任务 |

### 示例

```yaml
tasks:
  - id: optional-report
    agent: coder
    prompt: 生成代码质量报告
    degradation:
      policy: skip              # 失败时跳过，不影响整体流程
      max_failures: 2           # 失败 2 次后才跳过

  - id: critical-deploy
    agent: coder
    prompt: 执行生产部署
    degradation:
      policy: abort             # 失败时中止整个工作流

  - id: primary-cache
    agent: coder
    prompt: 构建 Redis 缓存层
    degradation:
      policy: continue          # 失败后继续执行下游
      fallback_task_id: fallback-memcache  # 备用方案
      max_failures: 3

  - id: fallback-memcache
    agent: coder
    prompt: 使用 Memcached 作为缓存替代方案
```

---

## 完整示例

### 示例 1：全栈并行开发

```yaml
name: fullstack-webapp
description: 并行构建前后端，最后审查

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
    prompt: 创建 FastAPI 项目，包含用户 CRUD 接口
    outputs: [backend/]

  - id: setup-frontend
    agent: frontend
    prompt: 创建 React + TypeScript 前端项目
    outputs: [frontend/]

  - id: review
    depends_on: [setup-backend, setup-frontend]
    agent: reviewer
    prompt: 审查全栈项目的生产就绪性
    merge_strategy: comments

strategy:
  max_parallel: 2
  retry_on_failure: true
  max_retries: 1
  timeout_per_task: 600
```

### 示例 2：带条件和降级的流水线

```yaml
name: ci-pipeline
description: CI 流水线 — 测试、构建、条件部署

variables:
  DEPLOY_ENV: staging

agents:
  worker:
    type: claude-code
    model: sonnet
    allowed_tools: [Read, Write, Edit, Bash]

tasks:
  - id: run-tests
    agent: worker
    prompt: 运行完整测试套件并输出结果

  - id: build
    depends_on: [run-tests]
    agent: worker
    prompt: 构建项目并生成制品
    degradation:
      policy: abort

  - id: deploy-staging
    depends_on: [build]
    agent: worker
    prompt: 部署到 ${DEPLOY_ENV:-staging} 环境
    degradation:
      policy: skip
      max_failures: 2

  - id: notify
    depends_on: [deploy-staging]
    agent: worker
    prompt: 发送部署通知
    degradation:
      policy: continue

conditions:
  - id: check-env
    depends_on: [run-tests]
    condition:
      field: DEPLOY_ENV
      operator: eq
      value: production
      then: deploy-staging

strategy:
  max_parallel: 1
  retry_on_failure: true
  max_retries: 2
  timeout_per_task: 900
  checkpoint_enabled: true
```

---

## 字段速查表

### 顶层字段

```
name: string (required)
description: string
agents: map<string, AgentConfig> (required)
tasks: list<TaskConfig> (required)
conditions: list<ConditionNodeConfig>
loops: list<LoopNodeConfig>
strategy: StrategyConfig
variables: map<string, string>
include: list<string>
```

### AgentConfig

```
type: string (required) — claude-code | codex | aider | opencode
model: string — default: "sonnet"
workdir: string — default: "."
allowed_tools: list<string>
```

### TaskConfig

```
id: string (required)
agent: string (required)
prompt: string (required)
priority: int — default: 0
depends_on: list<string>
outputs: list<string>
merge_strategy: string
when: string
degradation: TaskDegradation
node_type: string — default: "task"
```

### StrategyConfig

```
max_parallel: int — default: 4
retry_on_failure: bool — default: false
max_retries: int — default: 0
timeout_per_task: int — default: 600
retry_delay: float — default: 1.0
checkpoint_enabled: bool — default: false
```

### TaskDegradation

```
policy: string — abort | skip | continue (default: "abort")
fallback_task_id: string
max_failures: int — default: 1
```

### ConditionConfig

```
field: string (required)
operator: string (required) — eq|ne|gt|lt|gte|lte|contains|not_contains|in|not_in|regex
value: any (required)
then: string (required)
else: string
```

### LoopConfig

```
type: string (required) — for_each | while
items: string | list — for for_each loops
condition: string — for while loops
max_iterations: int — default: 100
body: list<string> (required)
```

---

## 验证规则

AgentCollab 在解析工作流时会自动验证：

1. **Agent 引用**：每个任务的 `agent` 必须在 `agents` 中定义
2. **依赖引用**：`depends_on` 中的每个 ID 必须指向已定义的节点
3. **循环依赖检测**：使用 DFS 检测 DAG 中的环，发现循环时抛出错误
4. **条件引用**：`then` 和 `else` 指向的节点必须存在
5. **循环体引用**：`body` 中的任务 ID 必须存在

### 验证命令

```bash
# 验证工作流文件
agent-collab validate workflow.yaml

# 验证并执行
agent-collab run workflow.yaml
```

---

*最后更新：2026-05-22*
