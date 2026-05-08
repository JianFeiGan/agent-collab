# 业务需求文档 — AgentCollab

## 1. 行业背景

### 1.1 AI Coding Agent 爆发式增长

2025-2026年, AI Coding Agent 生态迎来爆发:
- **Claude Code** (Anthropic) — 终端原生 AI 编码代理
- **Codex** (OpenAI) — 沙箱化编码代理
- **Cursor** — IDE 集成 AI 编码
- **Aider** — 开源 AI 结对编程
- **OpenCode** — 开源编码代理

GitHub Trending 显示:
- `hermes-agent` 137K stars (自进化 Agent)
- `multica` 25K stars (Agent 即队友)
- `free-claude-code` 22K stars (免费 Claude Code)

### 1.2 多 Agent 协作成为刚需

单个 Agent 能力有限, 复杂项目需要多个 Agent 分工协作:
- **前后端分离**: 一个 Agent 负责前端, 另一个负责后端
- **代码 + 测试**: 一个 Agent 写代码, 另一个写测试
- **开发 + 审查**: 一个 Agent 实现功能, 另一个做 Code Review
- **多语言项目**: 不同 Agent 擅长不同语言/框架

### 1.3 现有方案的不足

| 方案 | 问题 |
|------|------|
| multica (25K stars) | 偏重 Web UI, CLI 场景支持弱 |
| 手动切换 Agent | 无协调, 容易产生文件冲突 |
| tmux 手动管理 | 原始, 无依赖管理和冲突检测 |
| 无标准编排协议 | 各 Agent 各自为政, 无法协作 |

## 2. 痛点场景

### 场景 1: 全栈项目开发
**用户**: 独立开发者
**痛点**: 一个人要同时处理前端、后端、数据库、测试, 频繁切换上下文
**期望**: 定义一个 YAML 工作流, 自动让不同 Agent 并行处理不同模块

### 场景 2: 大规模重构
**用户**: 技术团队 Lead
**痛点**: 重构涉及 20+ 文件, 单个 Agent 上下文窗口不够用
**期望**: 拆分为多个子任务, 分配给多个 Agent 并行执行, 自动合并结果

### 场景 3: Code Review + 修复
**用户**: 开发者
**痛点**: 写完代码后要手动让 Agent review, 再手动修复发现的问题
**期望**: 定义 pipeline: Agent A 写代码 -> Agent B review -> Agent A 自动修复

### 场景 4: 多语言/多框架项目
**用户**: 全栈团队
**痛点**: Python 后端 + TypeScript 前端 + Go 微服务, 每个 Agent 只擅长一种
**期望**: 按语言/框架自动路由到最合适的 Agent

## 3. 目标用户画像

| 用户类型 | 场景 | 付费意愿 |
|----------|------|----------|
| 独立开发者 | 个人项目加速 | 中 |
| 技术团队 Lead | 团队效能提升 | 高 |
| 开源贡献者 | 大型开源项目协作 | 低 (但传播力强) |
| AI 工具爱好者 | 尝鲜多 Agent 编排 | 中 |

## 4. 竞品分析

| 维度 | multica | agent-collab (我们) |
|------|---------|---------------------|
| 定位 | Web 平台 | CLI 工具 |
| Agent 支持 | 自有 Agent | 任意 CLI Agent |
| 编排方式 | GUI 拖拽 | YAML 声明式 |
| 冲突检测 | 无 | 文件锁 + 合并策略 |
| 依赖管理 | 无 | 任务 DAG |
| 安装方式 | Docker | pip / uv |
| 扩展性 | 中 | 高 (插件式 Agent 适配器) |

## 5. 功能需求 (MoSCoW)

### Must Have (MVP)
- [ ] YAML 工作流定义 (任务、依赖、Agent 分配)
- [ ] 任务调度引擎 (DAG 拓扑排序 + 并行执行)
- [ ] 内置 Agent 适配器: Claude Code、Codex、Aider
- [ ] 文件锁机制 (防止多 Agent 同时编辑同一文件)
- [ ] 进度追踪与日志输出
- [ ] CLI 入口: `agent-collab run workflow.yaml`

### Should Have
- [ ] 任务结果合并 (git merge 策略)
- [ ] Agent 能力匹配 (按语言/框架自动选择)
- [ ] 失败重试与回滚
- [ ] 实时进度 TUI 显示

### Could Have
- [ ] Web Dashboard (查看任务状态)
- [ ] Agent 性能统计 (成功率、耗时、Token 消耗)
- [ ] 自定义 Agent 适配器插件

### Won't Have (本版本不做)
- 自有 Agent 实现 (只编排现有 Agent)
- 云端部署 (纯本地 CLI)

## 6. 成功标准

| 指标 | 目标 |
|------|------|
| GitHub Stars | 500+ (首月) |
| PyPI 下载量 | 1000+ (首月) |
| 示例工作流 | 5+ 个可用示例 |
| 测试覆盖率 | > 80% |
| 文档完整度 | README + CLI docs + 5 个 examples |
