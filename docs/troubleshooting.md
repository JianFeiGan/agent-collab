# AgentCollab 故障排查指南

本文档帮助你诊断和解决使用 AgentCollab 过程中遇到的常见问题。

---

## 目录

1. [安装与环境问题](#安装与环境问题)
2. [Agent 相关问题](#agent-相关问题)
3. [工作流解析错误](#工作流解析错误)
4. [执行与调度问题](#执行与调度问题)
5. [并行与锁冲突](#并行与锁冲突)
6. [超时与重试](#超时与重试)
7. [检查点与恢复](#检查点与恢复)
8. [插件与扩展问题](#插件与扩展问题)
9. [性能问题](#性能问题)
10. [调试技巧](#调试技巧)

---

## 安装与环境问题

### 问题：`command not found: agent-collab`

**症状**：
```
zsh: command not found: agent-collab
```

**原因**：AgentCollab 未安装或未在 PATH 中。

**解决方案**：

```bash
# 方式 1：使用 pip 安装
pip install agent-collab

# 方式 2：使用 uv 安装（推荐）
uv pip install agent-collab

# 方式 3：从源码安装
git clone https://github.com/JianFeiGan/agent-collab.git
cd agent-collab
uv sync
uv run agent-collab --help
```

如果用 `uv sync` 安装，需要用 `uv run agent-collab` 代替直接调用。

### 问题：`ModuleNotFoundError: No module named 'agent_collab'`

**原因**：Python 环境不正确。

**解决方案**：
```bash
# 确认使用正确的 Python
which python3
python3 --version  # 需要 3.11+

# 使用 uv 管理的虚拟环境
cd agent-collab
uv sync
uv run python -c "import agent_collab; print('OK')"
```

### 问题：Python 版本过低

**症状**：
```
ERROR: Package 'agent-collab' requires a different Python: 3.10.x not in '>=3.11'
```

**解决方案**：升级到 Python 3.11+。推荐使用 `pyenv`：
```bash
pyenv install 3.12
pyenv local 3.12
```

---

## Agent 相关问题

### 问题：Agent CLI 未找到

**症状**：
```
Error: Agent 'claude-code' CLI is not installed
```

**解决方案**：安装对应的 Agent CLI：

```bash
# Claude Code
npm install -g @anthropic-ai/claude-code

# Codex
npm install -g @openai/codex

# Aider
pip install aider-chat

# OpenCode
# 参见 https://github.com/opencode-ai/opencode
```

验证安装：
```bash
agent-collab list-agents
```

### 问题：Agent 执行失败但无错误信息

**症状**：任务显示失败，但日志中没有明确的错误信息。

**排查步骤**：

1. 检查 Agent 是否能独立运行：
   ```bash
   claude --version    # Claude Code
   codex --version     # Codex
   aider --version     # Aider
   ```

2. 检查 API Key 是否配置：
   ```bash
   echo $ANTHROPIC_API_KEY   # Claude Code
   echo $OPENAI_API_KEY      # Codex / Aider
   ```

3. 检查 Agent 的 `workdir` 是否存在：
   ```yaml
   agents:
     my-agent:
       type: claude-code
       workdir: ./src  # 确保此目录存在
   ```

### 问题：Agent 类型未知

**症状**：
```
ValueError: Unknown agent type 'xxx' for agent 'my-agent'
```

**解决方案**：检查 `agents` 中的 `type` 字段。支持的类型：
- `claude-code`
- `codex`
- `aider`
- `opencode`

---

## 工作流解析错误

### 问题：文件未找到

**症状**：
```
FileNotFoundError: Workflow file not found: workflow.yaml
```

**解决方案**：
- 检查文件路径是否正确
- 使用绝对路径或相对于当前目录的路径
- 检查文件权限

### 问题：YAML 格式错误

**症状**：
```
yaml.scanner.ScannerError: while scanning a simple key
```

**排查步骤**：
1. 使用 `agent-collab validate` 检查语法
2. 在线 YAML 校验器检查格式
3. 常见问题：
   - 缩进不一致（YAML 只允许空格，不允许 Tab）
   - 冒号后缺少空格
   - 引号不匹配

### 问题：循环依赖

**症状**：
```
Error: Dependency cycle detected: a -> b -> c -> a
```

**原因**：任务之间的依赖关系形成了环。

**解决方案**：
1. 画出任务依赖图，找出环路
2. 重新设计任务拆分，打破循环
3. 典型修复：将双向依赖改为单向，或合并相关任务

```yaml
# ❌ 错误：循环依赖
tasks:
  - id: a
    depends_on: [b]
    ...
  - id: b
    depends_on: [a]
    ...

# ✅ 正确：线性依赖
tasks:
  - id: a
    ...
  - id: b
    depends_on: [a]
    ...
```

### 问题：引用未知 Agent

**症状**：
```
ValueError: Task 'xxx' references unknown agent 'yyy'
```

**解决方案**：确保任务中 `agent` 字段的值在 `agents` 中有定义：

```yaml
agents:
  coder:        # ← 定义的名称
    type: claude-code
    model: sonnet

tasks:
  - id: my-task
    agent: coder  # ← 必须匹配上面的名称
    prompt: ...
```

### 问题：引用未知依赖

**症状**：
```
ValueError: Task 'xxx' depends on unknown node 'yyy'
```

**解决方案**：确保 `depends_on` 中的每个 ID 都指向已定义的任务、条件或循环节点。

---

## 执行与调度问题

### 问题：所有任务串行执行，未并行

**排查步骤**：

1. 检查 `max_parallel` 设置：
   ```yaml
   strategy:
     max_parallel: 4  # 确保大于 1
   ```

2. 检查任务依赖关系 — 如果每个任务都依赖前一个，自然无法并行：
   ```yaml
   # ❌ 全部串行
   tasks:
     - id: a
     - id: b
       depends_on: [a]
     - id: c
       depends_on: [b]

   # ✅ 部分并行
   tasks:
     - id: a
     - id: b       # a 和 b 可以并行
     - id: c
       depends_on: [a, b]  # c 等待 a、b 完成
   ```

### 问题：任务执行顺序不符合预期

**原因**：AgentCollab 使用 DAG 拓扑排序决定执行顺序。同层级的任务可以并行执行。

**理解执行层级**：

```
层级 0: [a, b]          ← a、b 并行执行
层级 1: [c]             ← c 等 a、b 都完成
层级 2: [d]             ← d 等 c 完成
```

使用 `validate` 命令查看执行层级：
```bash
agent-collab validate workflow.yaml
```

### 问题：工作流在某任务后卡住

**排查步骤**：
1. 检查该任务是否超时
2. 检查是否有下游任务在等待
3. 检查 Agent 进程是否仍在运行：
   ```bash
   ps aux | grep claude
   ps aux | grep codex
   ```

---

## 并行与锁冲突

### 问题：文件锁冲突

**症状**：
```
Error: Could not acquire lock for file.py
```

**原因**：多个并行任务尝试修改同一文件。

**解决方案**：
1. 为不同 Agent 分配不同的 `workdir`
2. 确保并行任务操作不同的文件
3. 使用 `outputs` 字段声明产出，帮助检测冲突

```yaml
agents:
  auth-agent:
    type: claude-code
    workdir: ./src/auth    # 独立工作目录
  api-agent:
    type: claude-code
    workdir: ./src/api     # 不同的工作目录
```

### 问题：并行任务的输出互相覆盖

**解决方案**：
- 为每个 Agent 设置独立的 `workdir`
- 使用 `outputs` 字段明确声明每个任务的产出
- 避免多个并行任务写入同一文件

---

## 超时与重试

### 问题：任务超时

**症状**：
```
Error: Task 'xxx' timed out after 600 seconds
```

**解决方案**：

1. **增加超时时间**：
   ```yaml
   strategy:
     timeout_per_task: 1200  # 20 分钟
   ```

2. **拆分大任务**：将一个复杂任务拆成多个小任务

3. **优化 prompt**：让 Agent 的任务更聚焦，减少不必要的探索

### 问题：重试未生效

**排查步骤**：
1. 确认启用了重试：
   ```yaml
   strategy:
     retry_on_failure: true
     max_retries: 3
     retry_delay: 2.0
   ```

2. 重试策略说明：
   - 失败后等待 `retry_delay` 秒再重试
   - 每次重试间隔翻倍（指数退避）
   - 达到 `max_retries` 后应用降级策略

---

## 检查点与恢复

### 问题：检查点未保存

**排查步骤**：
1. 确认启用了检查点：
   ```yaml
   strategy:
     checkpoint_enabled: true
   ```

2. 检查检查点目录：
   ```bash
   ls ~/.agent-collab/checkpoints/
   ```

### 问题：从检查点恢复失败

**解决方案**：
```bash
# 列出所有检查点
agent-collab checkpoints list

# 从检查点恢复
agent-collab replay <checkpoint-id> workflow.yaml

# 删除损坏的检查点
agent-collab checkpoints delete <checkpoint-id>
```

### 检查点文件格式

检查点保存在 `~/.agent-collab/checkpoints/` 目录下，格式为 JSON：

```json
{
  "checkpoint_id": "uuid",
  "workflow_name": "my-workflow",
  "completed_tasks": ["task-1", "task-2"],
  "task_outputs": {
    "task-1": "output content..."
  },
  "timestamp": "2026-05-22T01:00:00Z"
}
```

---

## 插件与扩展问题

### 问题：插件未加载

**排查步骤**：
1. 检查插件目录：
   ```bash
   ls ~/.agent-collab/plugins/
   ```

2. 检查插件是否实现了正确的接口（继承 `BasePlugin`）

3. 检查插件文件是否有语法错误：
   ```bash
   python3 -c "import your_plugin"
   ```

### 问题：Hook 未触发

**排查步骤**：
1. 确认 Hook 名称正确：`before_task`、`after_task`、`on_failure`
2. 确认 Hook 注册在正确的事件上
3. 检查 Hook 函数是否有异常被静默吞掉

---

## 性能问题

### 问题：启动缓慢

**可能原因**：
- 导入了大量可选依赖
- 插件加载时间过长

**解决方案**：
- 使用 lazy import 减少启动开销
- 减少不必要的插件

### 问题：大型工作流执行慢

**优化建议**：
1. 增大 `max_parallel`
2. 确保独立任务不互相依赖
3. 为不同 Agent 分配独立工作目录避免锁竞争
4. 使用 `priority` 字段优先执行关键路径任务

---

## 调试技巧

### 启用详细日志

```bash
# 设置环境变量
export AGENT_COLLAB_LOG_LEVEL=DEBUG

# 或在命令行中
agent-collab run workflow.yaml --verbose
```

### 验证工作流而不执行

```bash
agent-collab validate workflow.yaml
```

输出示例：
```
✓ Workflow 'my-workflow' is valid.
  Tasks: 5
  Agents: coder, reviewer
  Execution levels: 3
```

### 查看可用 Agent

```bash
agent-collab list-agents
```

输出示例：
```
Agent          Type          Status
────────────────────────────────────
coder          claude-code   ✓ installed
reviewer       claude-code   ✓ installed
quick-coder    codex         ✗ not installed
```

### 常见错误模式速查

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `Workflow file not found` | 文件路径错误 | 检查路径和文件名 |
| `Dependency cycle detected` | 任务循环依赖 | 重新设计依赖关系 |
| `Unknown agent type` | Agent type 拼写错误 | 检查 agents 定义 |
| `Unknown node 'xxx'` | depends_on 引用了不存在的 ID | 检查任务 ID 拼写 |
| `CLI is not installed` | Agent CLI 未安装 | 安装对应的 CLI |
| `timed out after N seconds` | 任务执行超时 | 增加超时或拆分任务 |
| `Could not acquire lock` | 文件锁冲突 | 分配独立 workdir |
| `ScannerError` | YAML 格式错误 | 检查缩进和语法 |

### 获取帮助

- **GitHub Issues**: https://github.com/JianFeiGan/agent-collab/issues
- **文档**: https://github.com/JianFeiGan/agent-collab/tree/main/docs
- **API 参考**: [docs/api-reference.md](api-reference.md)
- **YAML 语法参考**: [docs/yaml-syntax-reference.md](yaml-syntax-reference.md)

---

*最后更新：2026-05-22*
