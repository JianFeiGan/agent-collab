# AgentCollab 六月计划第一周执行计划

## 目标
提前执行六月计划第一周任务：Agent 适配器增强 + 社区启动

## 当前状态分析

### 已完成的功能 ✅
1. **Claude Code agent** - 支持 resume session（--continue / --resume）
2. **Codex agent** - 适配最新 CLI 参数（--model, --provider, --api-key）
3. **Aider agent** - 支持多文件编辑模式（--file 参数）
4. **Agent 能力自动检测** - 所有 agent 都实现了 is_available() 方法

### 需要改进的地方 🔧
1. **OpenCode agent** - 不支持 resume session
2. **能力检测增强** - 可以添加更多能力检测
3. **测试覆盖** - 确保所有新功能都有测试覆盖

## 执行计划

### 第一阶段：OpenCode agent 增强（05-23 ~ 05-24）

#### 任务 1.1：为 OpenCode 添加 resume session 支持
- **文件**: `src/agent_collab/agents/opencode.py`
- **修改内容**:
  1. 添加 `resume_mode` 和 `session_id` 参数到 `__init__`
  2. 在 `execute` 方法中处理 resume 逻辑
  3. 添加 `--continue` 和 `--resume` 参数支持
  4. 更新 `get_supported_arguments` 方法
  5. 实现 `_get_resume_modes` 方法

#### 任务 1.2：更新 OpenCode 测试
- **文件**: `tests/test_agents.py`
- **修改内容**:
  1. 添加 OpenCode resume session 测试
  2. 添加 OpenCode capabilities 测试
  3. 确保测试覆盖所有新功能

### 第二阶段：能力检测增强（05-24 ~ 05-25）

#### 任务 2.1：增强 BaseAgent 能力检测
- **文件**: `src/agent_collab/agents/base.py`
- **修改内容**:
  1. 添加 `supports_model_selection` 能力检测
  2. 添加 `supports_multi_file_editing` 能力检测
  3. 添加 `supports_json_output` 能力检测（已有）
  4. 添加 `max_concurrent_tasks` 能力检测

#### 任务 2.2：更新所有 agent 的能力检测
- **文件**: 所有 agent 文件
- **修改内容**:
  1. 为每个 agent 实现新的能力检测方法
  2. 更新 `get_capabilities` 方法返回新能力信息

### 第三阶段：测试和文档（05-25 ~ 05-26）

#### 任务 3.1：完善测试覆盖
- **文件**: `tests/test_agents.py`
- **修改内容**:
  1. 添加所有新功能的单元测试
  2. 添加集成测试
  3. 确保测试覆盖率达到 90%+

#### 任务 3.2：更新文档
- **文件**: `docs/` 目录
- **修改内容**:
  1. 更新 Agent 适配器开发指南
  2. 添加 resume session 使用示例
  3. 更新 CLI 参考文档

## 验证步骤

### 1. 代码质量检查
```bash
cd /Volumes/macmini_disk/HermesWork/GitHub/agent-collab
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### 2. 测试执行
```bash
uv run pytest tests/ -v --tb=short
```

### 3. 功能验证
```bash
# 测试 agent 能力检测
uv run agent-collab list-agents --verbose

# 测试 workflow 执行
uv run agent-collab run examples/sample-workflow.yaml
```

## 风险和缓解措施

### 风险 1：OpenCode CLI 变化
- **缓解**: 检查最新 OpenCode CLI 文档，确保参数兼容性

### 风险 2：测试覆盖率不足
- **缓解**: 使用 coverage 工具监控覆盖率，确保达到 90%+

### 风险 3：性能影响
- **缓解**: 进行性能测试，确保新功能不影响执行速度

## 成功标准

1. ✅ OpenCode agent 支持 resume session
2. ✅ 所有 agent 能力检测完善
3. ✅ 测试覆盖率达到 90%+
4. ✅ 文档更新完整
5. ✅ 代码质量检查通过

## 时间安排

- **05-23**: OpenCode agent 增强
- **05-24**: 能力检测增强
- **05-25**: 测试和文档
- **05-26**: 代码审查和发布准备

## 后续任务

完成第一周任务后，可以开始第二周任务：
- 并行执行优化
- 测试覆盖率提升
- 文档国际化

---

*计划制定日期: 2026-05-23*
*执行周期: 2026-05-23 ~ 2026-05-26*
