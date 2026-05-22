# AgentCollab CLI 参考文档

## 概述

AgentCollab 命令行界面（CLI）是用于管理多 Agent 工作流的主要工具。它提供了执行工作流、验证配置、管理检查点、安全认证和分布式执行等功能。

## 安装

```bash
# 使用 uv（推荐）
uv install agent-collab

# 或使用 pip
pip install agent-collab
```

## 基本用法

```bash
agent-collab [COMMAND] [OPTIONS]
```

## 命令列表

### 1. 工作流执行

#### `run` - 执行工作流

执行定义在 YAML 文件中的工作流。

```bash
agent-collab run <WORKFLOW_FILE>
```

**参数：**
- `WORKFLOW_FILE`：工作流 YAML 文件路径（必需）

**示例：**
```bash
# 执行简单工作流
agent-collab run workflow.yaml

# 使用 uv 运行
uv run agent-collab run examples/simple-workflow.yaml
```

**退出码：**
- `0`：所有任务成功
- `1`：存在失败任务或验证错误

**输出示例：**
```
🚀 Starting workflow: my-project
📋 Tasks: 5 | Agents: claude-code, codex
⏱️  Level 1/3: [task-1, task-2]
  ✓ task-1 (claude-code) - 12.3s
  ✓ task-2 (codex) - 8.7s
⏱️  Level 2/3: [task-3]
  ✓ task-3 (claude-code) - 15.2s
...
✅ Workflow completed: 5/5 tasks succeeded in 45.2s
```

#### `validate` - 验证工作流

验证工作流 YAML 文件的语法和逻辑，不执行任务。

```bash
agent-collab validate <WORKFLOW_FILE>
```

**参数：**
- `WORKFLOW_FILE`：工作流 YAML 文件路径（必需）

**示例：**
```bash
agent-collab validate workflow.yaml
```

**输出示例：**
```
✓ Workflow 'my-project' is valid.
  Tasks: 5
  Agents: claude-code, codex
  Execution levels: 3
  ⚠ Agent 'custom-agent' (custom-type) CLI is not installed
```

**验证内容：**
- YAML 语法正确性
- 任务依赖关系无环
- Agent 类型是否已注册
- 必填字段完整性

### 2. Agent 管理

#### `list-agents` - 列出可用 Agent

显示所有已注册的 Agent 及其安装状态。

```bash
agent-collab list-agents
```

**输出示例：**
```
┌─────────────┬─────────────┬───────────┐
│ Name        │ Status      │ CLI Tool  │
├─────────────┼─────────────┼───────────┤
│ claude-code │ available   │ claude    │
│ codex       │ available   │ codex     │
│ aider       │ not found   │ aider     │
│ opencode    │ available   │ opencode  │
└─────────────┴─────────────┴───────────┘
```

### 3. 检查点管理

#### `checkpoints` - 管理检查点

管理工作流执行检查点，支持查看和删除。

```bash
agent-collab checkpoints [ACTION] [CHECKPOINT_ID]
```

**参数：**
- `ACTION`：操作类型（默认 `list`）
  - `list`：列出所有检查点
  - `delete`：删除指定检查点
- `CHECKPOINT_ID`：检查点 ID（`delete` 操作必需）

**示例：**
```bash
# 列出所有检查点
agent-collab checkpoints list

# 删除指定检查点
agent-collab checkpoints delete checkpoint-abc123
```

**输出示例（list）：**
```
┌─────────────────┬─────────────┬─────────────────┬─────────────────────┐
│ ID              │ Workflow    │ Completed Tasks │ Timestamp           │
├─────────────────┼─────────────┼─────────────────┼─────────────────────┤
│ cp-20260522-001 │ my-project  │ task-1, task-2  │ 2026-05-22 01:30:00 │
│ cp-20260522-002 │ my-project  │ task-1          │ 2026-05-22 02:15:00 │
└─────────────────┴─────────────┴─────────────────┴─────────────────────┘
```

### 4. 工作流回放

#### `replay` - 从检查点恢复执行

从指定检查点恢复工作流执行。

```bash
agent-collab replay <CHECKPOINT_ID> <WORKFLOW_FILE>
```

**参数：**
- `CHECKPOINT_ID`：检查点 ID（必需）
- `WORKFLOW_FILE`：工作流 YAML 文件路径（必需）

**示例：**
```bash
# 从检查点恢复执行
agent-collab replay cp-20260522-001 workflow.yaml
```

**输出示例：**
```
🔄 Replaying workflow from checkpoint cp-20260522-001...
  ✓ task-1
  ✓ task-2
  ✓ task-3
✅ Replay completed successfully. 3 task(s) executed.
```

### 5. 安全命令

#### `security-create-user` - 创建用户

创建新的用户账户。

```bash
agent-collab security-create-user <USERNAME> <PASSWORD> [OPTIONS]
```

**参数：**
- `USERNAME`：用户名（必需）
- `PASSWORD`：密码（必需）

**选项：**
- `--role`：用户角色（默认 `developer`）
  - `admin`：管理员
  - `manager`：经理
  - `developer`：开发者
  - `viewer`：观察者
- `--tenant-id`：租户 ID（默认 `default`）

**示例：**
```bash
# 创建管理员用户
agent-collab security-create-user admin password123 --role admin

# 创建开发者用户
agent-collab security-create-user dev1 secret456 --role developer --tenant-id team-a
```

**输出示例：**
```
✓ User 'admin' created with role 'admin' (id=usr_abc123).
🔑 Access token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### `security-login` - 用户认证

认证用户并获取访问令牌。

```bash
agent-collab security-login <USERNAME> <PASSWORD>
```

**参数：**
- `USERNAME`：用户名（必需）
- `PASSWORD`：密码（必需）

**示例：**
```bash
agent-collab security-login admin password123
```

**输出示例：**
```
✓ Authenticated as 'admin'
🔑 Access token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
⏰ Expires in: 3600s
```

#### `security-verify-token` - 验证令牌

验证访问令牌的有效性并显示其内容。

```bash
agent-collab security-verify-token <TOKEN>
```

**参数：**
- `TOKEN`：JWT 访问令牌（必需）

**示例：**
```bash
agent-collab security-verify-token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**输出示例：**
```
✓ Token is valid.
┌─────────────┬─────────────────┐
│ Field       │ Value           │
├─────────────┼─────────────────┤
│ sub         │ usr_abc123      │
│ username    │ admin           │
│ role        │ admin           │
│ tenant_id   │ default         │
│ exp         │ 1716374400      │
└─────────────┴─────────────────┘
```

### 6. 分布式执行

#### `distributed-status` - 分布式状态

显示分布式执行状态，包括工作节点和任务队列信息。

```bash
agent-collab distributed-status
```

**输出示例：**
```
┌─────────────────┬─────────┐
│ Metric          │ Value   │
├─────────────────┼─────────┤
│ Queue Size      │ 3       │
│ Total Workers   │ 5       │
│ Idle Workers    │ 2       │
│ Busy Workers    │ 3       │
│ Total Capacity  │ 10      │
│ Current Tasks   │ 3       │
└─────────────────┴─────────┘
```

### 7. HITL（人在回路）

#### `hitl-pending` - 待处理请求

列出待批准和待输入的 HITL 请求。

```bash
agent-collab hitl-pending
```

**输出示例：**
```
┌──────────┬─────────┬─────────────────┬─────────┐
│ ID       │ Task ID │ Title           │ Status  │
├──────────┼─────────┼─────────────────┼─────────┤
│ req-001  │ task-3  │ 部署审批        │ pending │
│ req-002  │ task-5  │ 配置确认        │ pending │
└──────────┴─────────┴─────────────────┴─────────┘
```

## 环境变量

AgentCollab 支持以下环境变量配置：

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `AGENT_COLLAB_HOME` | 配置文件目录 | `~/.agent-collab` |
| `AGENT_COLLAB_LOG_LEVEL` | 日志级别 | `INFO` |
| `AGENT_COLLAB_MAX_PARALLEL` | 最大并行任务数 | `4` |
| `AGENT_COLLAB_TIMEOUT` | 任务超时时间（秒） | `300` |

## 配置文件

### 全局配置

配置文件位置：`~/.agent-collab/config.yaml`

```yaml
# 示例配置
max_parallel: 4
timeout: 300
log_level: INFO
checkpoint_dir: ~/.agent-collab/checkpoints
security:
  enabled: true
  token_expiry: 3600
```

### 项目配置

项目根目录下的 `.agent-collab.yaml`：

```yaml
# 项目特定配置
project_name: my-project
agents:
  claude-code:
    model: claude-3-sonnet-20240229
    max_tokens: 4096
  codex:
    model: code-davinci-002
    temperature: 0.2
```

## 错误处理

### 常见错误及解决方案

#### 1. 工作流验证失败

**错误信息：**
```
❌ Workflow validation failed: Circular dependency detected in tasks: task-1 -> task-2 -> task-1
```

**解决方案：**
- 检查任务依赖关系，确保无循环依赖
- 使用 `agent-collab validate` 命令验证工作流

#### 2. Agent 未找到

**错误信息：**
```
❌ Unknown agent type 'custom-agent' for agent 'my-agent'
```

**解决方案：**
- 使用 `agent-collab list-agents` 查看可用 Agent
- 确保 Agent CLI 工具已安装
- 检查工作流 YAML 中的 Agent 类型拼写

#### 3. 检查点不存在

**错误信息：**
```
❌ Checkpoint 'cp-123' not found.
```

**解决方案：**
- 使用 `agent-collab checkpoints list` 查看可用检查点
- 确保检查点 ID 正确

#### 4. 权限不足

**错误信息：**
```
❌ Authentication failed: invalid username or password.
```

**解决方案：**
- 检查用户名和密码
- 使用 `agent-collab security-create-user` 创建用户
- 确保用户角色有足够权限

## 最佳实践

### 1. 工作流设计

- **任务分解**：将复杂任务分解为小的、独立的子任务
- **依赖管理**：明确任务依赖，避免不必要的串行执行
- **错误处理**：为关键任务设置降级策略

### 2. 性能优化

- **并行执行**：合理设置 `max_parallel` 参数
- **资源分配**：根据 Agent 能力分配任务
- **检查点使用**：长时间工作流启用检查点

### 3. 安全建议

- **最小权限原则**：为用户分配最小必要权限
- **定期轮换**：定期更换访问令牌
- **审计日志**：启用操作审计日志

### 4. 监控与调试

- **日志记录**：设置适当的日志级别
- **性能监控**：监控任务执行时间和资源使用
- **错误追踪**：记录和分析失败任务

## 示例工作流

### 简单工作流

```yaml
name: simple-project
agents:
  coder:
    type: claude-code
    model: claude-3-sonnet-20240229
  reviewer:
    type: codex
    model: code-davinci-002

tasks:
  - id: implement-feature
    agent: coder
    prompt: |
      实现一个用户认证模块，包含：
      1. 登录功能
      2. 注册功能
      3. JWT 令牌管理
    outputs:
      - src/auth.py
      - tests/test_auth.py

  - id: review-code
    agent: reviewer
    prompt: |
      审查 auth.py 的代码质量，检查：
      1. 安全性
      2. 性能
      3. 代码风格
    depends_on:
      - implement-feature
    outputs:
      - docs/review-report.md

strategy:
  max_parallel: 2
  on_failure: continue
```

### 复杂工作流

```yaml
name: enterprise-project
agents:
  architect:
    type: claude-code
    role: architect
  developer:
    type: claude-code
    role: developer
  tester:
    type: codex
    role: tester
  reviewer:
    type: aider
    role: reviewer

tasks:
  # 设计阶段
  - id: system-design
    agent: architect
    prompt: 设计微服务架构，包含用户服务、订单服务、支付服务
    outputs:
      - docs/architecture.md
      - diagrams/system-design.puml

  # 开发阶段
  - id: user-service
    agent: developer
    prompt: 实现用户服务，包含 CRUD 操作和认证
    depends_on:
      - system-design
    outputs:
      - services/user-service/src/
      - services/user-service/tests/

  - id: order-service
    agent: developer
    prompt: 实现订单服务，包含订单管理和状态跟踪
    depends_on:
      - system-design
    outputs:
      - services/order-service/src/
      - services/order-service/tests/

  - id: payment-service
    agent: developer
    prompt: 实现支付服务，包含支付网关集成
    depends_on:
      - system-design
    outputs:
      - services/payment-service/src/
      - services/payment-service/tests/

  # 测试阶段
  - id: integration-tests
    agent: tester
    prompt: 编写集成测试，测试服务间交互
    depends_on:
      - user-service
      - order-service
      - payment-service
    outputs:
      - tests/integration/

  # 审查阶段
  - id: code-review
    agent: reviewer
    prompt: 审查所有服务的代码质量
    depends_on:
      - integration-tests
    outputs:
      - docs/code-review.md

strategy:
  max_parallel: 3
  on_failure: abort
  timeout: 3600
```

## 故障排查

### 调试模式

启用详细日志：

```bash
AGENT_COLLAB_LOG_LEVEL=DEBUG agent-collab run workflow.yaml
```

### 检查工作流状态

```bash
# 查看当前检查点
agent-collab checkpoints list

# 查看分布式状态
agent-collab distributed-status
```

### 性能分析

```bash
# 使用 cProfile 分析性能
python -m cProfile -o profile.prof -m agent_collab run workflow.yaml

# 分析结果
python -c "import pstats; p = pstats.Stats('profile.prof'); p.sort_stats('cumulative').print_stats(20)"
```

## 扩展开发

### 自定义 Agent

参考 [Agent 适配器开发指南](agent-adapter-guide.md) 开发自定义 Agent。

### 插件系统

参考 [插件系统文档](plugins.md) 开发自定义插件。

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v1.0.0 | 2026-05-31 | 稳定版发布 |
| v0.3.0 | 2026-05-22 | 插件系统、错误恢复 |
| v0.2.0 | 2026-05-15 | 工作流增强、并行优化 |
| v0.1.0 | 2026-05-08 | 初始版本 |

## 相关文档

- [YAML 语法参考](yaml-syntax-reference.md)
- [Agent 适配器开发指南](agent-adapter-guide.md)
- [故障排查指南](troubleshooting.md)
- [API 参考文档](api-reference.md)
- [用户手册](user-manual.md)

## 获取帮助

```bash
# 查看总体帮助
agent-collab --help

# 查看特定命令帮助
agent-collab run --help
agent-collab validate --help

# 查看版本
agent-collab --version
```

## 反馈与贡献

- GitHub Issues: https://github.com/JianFeiGan/agent-collab/issues
- 贡献指南: [CONTRIBUTING.md](../CONTRIBUTING.md)
- 许可证: [MIT License](../LICENSE)