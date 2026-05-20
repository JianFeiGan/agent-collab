# AgentCollab 下一步开发路线图

**创建日期**: 2026-05-20
**当前版本**: v1.0.0
**目标**: 从 CLI 工具演进为企业级多 Agent 编排平台

---

## 🎯 战略定位

**核心定位**: 企业级多模型 Agent 协作平台
**差异化优势**:
1. 多模型智能调度（MoA 架构）
2. 企业级可靠性（断点恢复、降级策略）
3. 可视化编排（Web UI）
4. 灵活人机协作（HITL）

---

## 📅 三个月路线图（MVP 阶段）

### Month 1: 核心框架增强（Week 1-4）

#### Week 1-2: 多模型调度引擎
- [ ] 设计 Agent 抽象层接口（支持 LLM API 直接调用）
- [ ] 实现统一的模型调用接口（OpenAI、Anthropic、Google、本地模型）
- [ ] 集成 LiteLLM 作为多模型路由层
- [ ] 实现模型选择策略（round-robin、cost-optimized、quality-first）
- [ ] 添加成本追踪和统计
- [ ] 编写基础单元测试

#### Week 3-4: MoA（Mixture of Agents）引擎
- [ ] 设计 MoA 架构（参考模型 + 聚合模型）
- [ ] 实现可配置的参考模型列表
- [ ] 实现可配置的聚合模型选择
- [ ] 添加模型响应质量评估
- [ ] 实现自动故障转移机制
- [ ] 编写 MoA 引擎测试用例

### Month 2: 编排能力升级（Week 5-8）

#### Week 5-6: 图编排引擎
- [ ] 设计工作流定义 DSL（YAML/Python）
- [ ] 实现 DAG 解析和验证（已有，需增强）
- [ ] 实现顺序执行模式（已有）
- [ ] 实现并行执行模式（已有）
- [ ] 实现条件分支（if/else）
- [ ] 实现循环结构（for/while）
- [ ] 实现状态管理和上下文传递（增强）
- [ ] 实现检查点和恢复机制（已有，需优化）

#### Week 7-8: 可视化编辑器
- [ ] 搭建 React 前端项目
- [ ] 集成 React Flow 库（拖拽式节点编辑）
- [ ] 实现拖拽式节点创建
- [ ] 实现节点连线和配置
- [ ] 实现工作流保存和加载
- [ ] 实现运行状态实时展示（WebSocket）
- [ ] 实现基础的日志查看
- [ ] 添加示例工作流模板

### Month 3: 企业特性（Week 9-12）

#### Week 9-10: 人机协作（HITL）
- [ ] 设计 Human-in-the-Loop 接口
- [ ] 实现审批节点类型
- [ ] 实现人工输入节点
- [ ] 实现中断和恢复机制
- [ ] 实现通知发送（邮件/Webhook）
- [ ] 实现审批历史记录
- [ ] 编写 HITL 测试用例

#### Week 11-12: 基础设施
- [ ] 编写 Dockerfile
- [ ] 编写 docker-compose.yml
- [ ] 实现健康检查 API
- [ ] 集成基础监控（Prometheus metrics）
- [ ] 实现结构化日志（JSON 格式）
- [ ] 编写 API 文档（OpenAPI）
- [ ] 编写快速开始指南
- [ ] 创建 10 个示例工作流
- [ ] 录制演示视频

---

## 📅 六个月路线图（产品化阶段）

### Month 4: 性能和可靠性（Week 13-16）

#### Week 13-14: 分布式执行引擎
- [ ] 设计任务分发架构
- [ ] 实现任务队列（Celery/Redis）
- [ ] 实现 Worker 节点管理
- [ ] 实现负载均衡策略
- [ ] 实现任务优先级
- [ ] 实现分布式锁

#### Week 15-16: 高可用和容错
- [ ] 实现 Worker 节点健康检查
- [ ] 实现任务重试和超时
- [ ] 实现断点恢复（分布式）
- [ ] 实现故障转移
- [ ] 实现数据持久化（PostgreSQL）
- [ ] 编写 HA 测试用例

### Month 5: 企业级安全（Week 17-20）

#### Week 17-18: 认证和授权
- [ ] 实现用户认证（JWT）
- [ ] 实现角色管理（RBAC）
- [ ] 实现 API Key 管理
- [ ] 实现 OAuth2 集成
- [ ] 实现审计日志
- [ ] 编写安全测试用例

#### Week 19-20: 多租户和隔离
- [ ] 实现多租户架构
- [ ] 实现资源隔离（CPU、内存、API 调用）
- [ ] 实现配额管理
- [ ] 实现计费统计
- [ ] 实现租户管理 API
- [ ] 编写多租户测试用例

### Month 6: 商业化准备（Week 21-24）

#### Week 21-22: 产品化打磨
- [ ] 完善文档（用户手册、API 文档、最佳实践）
- [ ] 创建视频教程
- [ ] 优化性能（基准测试、瓶颈分析）
- [ ] 修复已知 Bug
- [ ] 准备发布材料

#### Week 23-24: 社区和推广
- [ ] 开源社区建设（GitHub、Discord、论坛）
- [ ] 技术博客和文章
- [ ] 参加技术会议
- [ ] 寻找早期用户
- [ ] 准备商业化方案

---

## 🏗️ 技术架构演进

### 当前架构（v1.0.0）
```
CLI (Typer)
    ↓
TaskScheduler (DAG)
    ↓
TaskExecutor (asyncio)
    ↓
Agent Adapters (Claude Code, Codex, Aider, OpenCode)
```

### 目标架构（v2.0.0）
```
Web UI (React + React Flow)
    ↓
API Server (FastAPI)
    ↓
Orchestrator (核心引擎)
    ↓
┌─────────────────────────────────────┐
│  Task Queue (Redis/Celery)          │
│  ↓                                  │
│  Worker Nodes (分布式执行)           │
│  ↓                                  │
│  Agent Pool (多模型调度)             │
│  - Claude Code                      │
│  - Codex                            │
│  - Aider                            │
│  - OpenCode                         │
│  - OpenAI API                       │
│  - Anthropic API                    │
│  - Google Gemini API                │
│  - 本地模型 (Ollama)                │
└─────────────────────────────────────┘
    ↓
Storage Layer
    - PostgreSQL (元数据、用户、租户)
    - Redis (缓存、会话、任务队列)
    - S3 (文件存储、工作流定义)
    - SQLite (本地开发)
```

---

## 💰 商业化路径

### 开源版（Community Edition）
- 核心功能：工作流定义、DAG 调度、Agent 适配器
- 单机部署
- 社区支持
- 免费

### 商业版（Enterprise Edition）
- 企业级特性：多租户、RBAC、审计日志
- 分布式执行
- 高可用和容错
- 优先支持
- 按用户/节点计费

### SaaS 版（Cloud Edition）
- 托管服务
- 按用量计费（API 调用、计算资源）
- 自动扩展
- 全球部署
- SLA 保障

---

## 📊 关键指标

### 技术指标
- 测试覆盖率：> 80%
- 性能：单机 100+ 并发任务
- 可用性：99.9%（商业版）
- 响应时间：< 100ms（API 调用）

### 业务指标
- GitHub Stars：1000+（6 个月内）
- 活跃用户：100+（6 个月内）
- 付费客户：10+（6 个月内）
- 社区贡献者：20+（6 个月内）

---

## 🚀 立即行动清单

### 本周（Week 1）
1. 创建 v1.1.0 分支
2. 设计多模型调度接口
3. 集成 LiteLLM
4. 编写多模型调度测试

### 下周（Week 2）
1. 实现 MoA 引擎原型
2. 添加条件分支支持
3. 创建 Web UI 项目骨架
4. 编写 MoA 测试用例

### 本月（Month 1）
1. 完成多模型调度引擎
2. 完成 MoA 引擎
3. 发布 v1.1.0
4. 开始 Web UI 开发

---

## 📚 参考资源

### 竞品分析
- AutoGen: https://github.com/microsoft/autogen
- CrewAI: https://github.com/crewAIInc/crewAI
- LangGraph: https://github.com/langchain-ai/langgraph
- MetaGPT: https://github.com/geekan/MetaGPT

### 技术栈
- 多模型路由：LiteLLM
- 任务队列：Celery + Redis
- 前端：React + React Flow + TypeScript
- 后端：FastAPI + SQLAlchemy + PostgreSQL
- 监控：Prometheus + Grafana
- 日志：ELK Stack

### 学习资源
- Multi-Agent Systems: https://arxiv.org/abs/2308.08155
- Mixture of Agents: https://arxiv.org/abs/2406.04692
- DAG Scheduling: https://en.wikipedia.org/wiki/Directed_acyclic_graph

---

## 📝 决策记录

### 2026-05-20: 代码评审修复
- 修复 cli.py 多次 asyncio.run() 问题
- 修复 file_lock.py 类型标注和同名文件冲突
- 实现 AGENT_REGISTRY 延迟初始化
- 集成 HookPlugin 到 TaskExecutor
- 添加 opencode agent 到注册表
- 所有 189 个测试通过

### 2026-05-20: 业务方向确定
- 定位：企业级多模型 Agent 协作平台
- 差异化：多模型调度 + 企业级可靠性 + 可视化编排 + HITL
- 商业化：开源 + 商业版 + SaaS 混合模式
- 目标：6 个月内实现首批付费客户

---

**文档维护者**: Hermes
**最后更新**: 2026-05-20
**版本**: 1.0.0
