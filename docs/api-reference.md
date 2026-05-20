# AgentCollab API 文档

## 目录

1. [核心模块](#核心模块)
2. [工作流模块](#工作流模块)
3. [LLM 模块](#llm-模块)
4. [HITL 模块](#hitl-模块)
5. [分布式模块](#分布式模块)
6. [安全模块](#安全模块)

---

## 核心模块

### agent_collab.core.workflow

#### TaskConfig

```python
class TaskConfig(BaseModel):
    id: str
    agent: str
    prompt: str
    priority: int = 0
    depends_on: list[str] = []
    outputs: list[str] = []
    merge_strategy: str | None = None
    when: str | None = None
    degradation: TaskDegradation | None = None
    node_type: NodeType = NodeType.TASK
```

**参数说明**：
- `id`：任务唯一标识
- `agent`：执行任务的 Agent 名称
- `prompt`：任务提示词
- `priority`：优先级（越高越先执行）
- `depends_on`：依赖的任务 ID 列表
- `outputs`：输出文件列表
- `merge_strategy`：合并策略
- `when`：条件执行表达式
- `degradation`：降级策略
- `node_type`：节点类型（task, condition, loop, parallel）

#### WorkflowConfig

```python
class WorkflowConfig(BaseModel):
    name: str
    description: str = ""
    agents: dict[str, AgentConfig]
    tasks: list[TaskConfig]
    conditions: list[ConditionNodeConfig] = []
    loops: list[LoopNodeConfig] = []
    strategy: StrategyConfig = StrategyConfig()
    variables: dict[str, str] = {}
    include: list[str] = []
```

#### WorkflowParser

```python
class WorkflowParser:
    @staticmethod
    def parse(file_path: str | Path) -> WorkflowConfig

    @staticmethod
    def resolve_variables(text: str, variables: dict[str, str]) -> str

    @staticmethod
    def resolve_task_outputs(text: str, outputs: dict[str, str]) -> str

    @staticmethod
    def expand_loops(config: WorkflowConfig) -> list[TaskConfig]
```

---

## LLM 模块

### agent_collab.llm

#### LLMConfig

```python
@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    retry_attempts: int = 3
    retry_delay: float = 1.0
```

#### LLMResponse

```python
@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    metadata: dict[str, Any] = {}
```

#### BaseLLMProvider

```python
class BaseLLMProvider(ABC):
    def __init__(self, config: LLMConfig) -> None

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse

    @abstractmethod
    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse

    @property
    @abstractmethod
    def name(self) -> str

    @property
    @abstractmethod
    def models(self) -> list[str]

    def is_available(self) -> bool
```

### agent_collab.llm.scheduler

#### MultiModelScheduler

```python
class MultiModelScheduler:
    def __init__(self, config: SchedulerConfig) -> None

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse

    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse

    def get_stats(self) -> dict[str, ModelStats]
    def get_total_cost(self) -> float
    def get_total_tokens(self) -> tuple[int, int]
    def reset_stats(self) -> None
```

#### SchedulerConfig

```python
@dataclass
class SchedulerConfig:
    models: list[ModelConfig]
    strategy: SelectionStrategy = SelectionStrategy.QUALITY_FIRST
    fallback_enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 60
```

#### SelectionStrategy

```python
class SelectionStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    COST_OPTIMIZED = "cost_optimized"
    QUALITY_FIRST = "quality_first"
    LATENCY_OPTIMIZED = "latency_optimized"
    RANDOM = "random"
```

### agent_collab.llm.moa

#### MoAEngine

```python
class MoAEngine:
    def __init__(
        self,
        scheduler: MultiModelScheduler,
        config: MoAConfig,
    ) -> None

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> MoAResponse
```

#### MoAConfig

```python
@dataclass
class MoAConfig:
    reference_models: list[str]
    aggregator_model: str
    num_reference_rounds: int = 2
    num_references_per_round: int = 3
    temperature: float = 0.7
    max_tokens: int = 4096
```

---

## HITL 模块

### agent_collab.hitl

#### ApprovalRequest

```python
@dataclass
class ApprovalRequest:
    id: str
    workflow_id: str = ""
    task_id: str = ""
    title: str = ""
    description: str = ""
    data: dict[str, Any] = {}
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = ...
    updated_at: datetime = ...
    expires_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = {}
```

#### InputRequest

```python
@dataclass
class InputRequest:
    id: str
    workflow_id: str = ""
    task_id: str = ""
    title: str = ""
    description: str = ""
    input_type: InputType = InputType.TEXT
    required: bool = True
    default_value: Any = None
    options: list[dict[str, Any]] = []
    validation: dict[str, Any] = {}
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = ...
    updated_at: datetime = ...
    expires_at: datetime | None = None
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    submitted_value: Any = None
    metadata: dict[str, Any] = {}
```

#### HITLProvider

```python
class HITLProvider(ABC):
    @abstractmethod
    async def send_approval_request(self, request: ApprovalRequest) -> bool

    @abstractmethod
    async def get_approval_status(self, request_id: str) -> ApprovalRequest

    @abstractmethod
    async def approve(self, request_id: str, actor: str, reason: str | None = None) -> bool

    @abstractmethod
    async def reject(self, request_id: str, actor: str, reason: str) -> bool

    @abstractmethod
    async def send_input_request(self, request: InputRequest) -> bool

    @abstractmethod
    async def get_input_status(self, request_id: str) -> InputRequest

    @abstractmethod
    async def submit_input(self, request_id: str, value: Any, actor: str) -> bool
```

### agent_collab.hitl.nodes

#### HITLManager

```python
class HITLManager:
    def __init__(self, provider: HITLProvider) -> None

    async def create_approval(
        self,
        config: ApprovalNodeConfig,
        workflow_id: str,
        data: dict[str, Any] | None = None,
    ) -> ApprovalRequest

    async def create_input(
        self,
        config: InputNodeConfig,
        workflow_id: str,
    ) -> InputRequest

    async def check_approval(self, request_id: str) -> ApprovalRequest
    async def check_input(self, request_id: str) -> InputRequest
    async def approve(self, request_id: str, actor: str, reason: str | None = None) -> bool
    async def reject(self, request_id: str, actor: str, reason: str) -> bool
    async def submit_input(self, request_id: str, value: Any, actor: str) -> bool
    def get_pending_approvals(self) -> list[ApprovalRequest]
    def get_pending_inputs(self) -> list[InputRequest]
    def get_history(self, request_id: str | None = None) -> list
```

---

## 分布式模块

### agent_collab.distributed

#### DistributedTask

```python
@dataclass
class DistributedTask:
    id: str
    workflow_id: str = ""
    task_id: str = ""
    agent_type: str = ""
    prompt: str = ""
    workdir: str = "."
    allowed_tools: list[str] = []
    priority: int = 0
    timeout: int = 600
    max_retries: int = 3
    retry_count: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = ...
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_worker: str | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = {}
```

#### TaskQueue

```python
class TaskQueue(ABC):
    @abstractmethod
    async def enqueue(self, task: DistributedTask) -> bool

    @abstractmethod
    async def dequeue(self, worker_id: str) -> DistributedTask | None

    @abstractmethod
    async def complete(self, task_id: str, result: TaskResult) -> bool

    @abstractmethod
    async def fail(self, task_id: str, error: str) -> bool

    @abstractmethod
    async def get_task(self, task_id: str) -> DistributedTask | None

    @abstractmethod
    async def get_pending_tasks(self) -> list[DistributedTask]

    @abstractmethod
    async def get_queue_size(self) -> int
```

#### WorkerManager

```python
class WorkerManager(ABC):
    @abstractmethod
    async def register_worker(self, worker: WorkerInfo) -> bool

    @abstractmethod
    async def unregister_worker(self, worker_id: str) -> bool

    @abstractmethod
    async def heartbeat(self, worker_id: str) -> bool

    @abstractmethod
    async def get_worker(self, worker_id: str) -> WorkerInfo | None

    @abstractmethod
    async def get_available_workers(self) -> list[WorkerInfo]

    @abstractmethod
    async def update_worker_status(self, worker_id: str, status: WorkerStatus) -> bool

    @abstractmethod
    async def increment_task_count(self, worker_id: str) -> bool

    @abstractmethod
    async def decrement_task_count(self, worker_id: str) -> bool
```

### agent_collab.distributed.scheduler

#### DistributedScheduler

```python
class DistributedScheduler:
    def __init__(
        self,
        task_queue: TaskQueue,
        worker_manager: WorkerManager,
        executor: DistributedExecutor,
        load_balancer: LoadBalancer | None = None,
        heartbeat_interval: float = 10.0,
        task_timeout: float = 600.0,
    ) -> None

    async def start(self) -> None
    async def stop(self) -> None
    async def submit_task(self, task: DistributedTask) -> bool
    async def cancel_task(self, task_id: str) -> bool
    async def get_task_status(self, task_id: str) -> DistributedTask | None
    async def get_queue_size(self) -> int
    async def get_worker_stats(self) -> dict[str, Any]
```

---

## 安全模块

### agent_collab.security

#### User

```python
@dataclass
class User:
    id: str
    username: str = ""
    email: str = ""
    hashed_password: str = ""
    role: UserRole = UserRole.DEVELOPER
    tenant_id: str = ""
    is_active: bool = True
    created_at: datetime = ...
    updated_at: datetime = ...
    last_login: datetime | None = None
    metadata: dict[str, Any] = {}
```

#### Tenant

```python
@dataclass
class Tenant:
    id: str
    name: str = ""
    slug: str = ""
    plan: str = "free"
    max_users: int = 10
    max_workflows: int = 100
    max_tasks_per_day: int = 1000
    is_active: bool = True
    created_at: datetime = ...
    updated_at: datetime = ...
    metadata: dict[str, Any] = {}
```

#### APIKey

```python
@dataclass
class APIKey:
    id: str
    user_id: str = ""
    tenant_id: str = ""
    name: str = ""
    key_hash: str = ""
    prefix: str = ""
    permissions: set[Permission] = set()
    is_active: bool = True
    expires_at: datetime | None = None
    created_at: datetime = ...
    last_used: datetime | None = None
    metadata: dict[str, Any] = {}
```

#### UserRole

```python
class UserRole(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"
    VIEWER = "viewer"
```

#### Permission

```python
class Permission(Enum):
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_EXECUTE = "workflow:execute"
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_EXECUTE = "task:execute"
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    TENANT_CREATE = "tenant:create"
    TENANT_READ = "tenant:read"
    TENANT_UPDATE = "tenant:update"
    TENANT_DELETE = "tenant:delete"
    API_KEY_CREATE = "api_key:create"
    API_KEY_READ = "api_key:read"
    API_KEY_DELETE = "api_key:delete"
    AUDIT_READ = "audit:read"
    ADMIN_ALL = "admin:all"
```

#### AuthProvider

```python
class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, username: str, password: str) -> User | None

    @abstractmethod
    async def get_user(self, user_id: str) -> User | None

    @abstractmethod
    async def create_user(self, user: User) -> User

    @abstractmethod
    async def update_user(self, user: User) -> User

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool

    @abstractmethod
    async def get_users_by_tenant(self, tenant_id: str) -> list[User]
```

#### 工具函数

```python
def hash_password(password: str) -> str
def verify_password(password: str, hashed_password: str) -> bool
def generate_api_key() -> tuple[str, str, str]
def has_permission(user_role: UserRole, required_permission: Permission) -> bool
```

---

## 错误处理

### 异常类型

```python
class AgentCollabError(Exception):
    """Base exception for AgentCollab"""

class WorkflowError(AgentCollabError):
    """Workflow-related errors"""

class TaskError(AgentCollabError):
    """Task execution errors"""

class AgentError(AgentCollabError):
    """Agent-related errors"""

class SecurityError(AgentCollabError):
    """Security-related errors"""
```

### 错误处理示例

```python
from agent_collab.core.workflow import WorkflowParser
from agent_collab.core.executor import TaskExecutor

try:
    config = WorkflowParser.parse("workflow.yaml")
    executor = TaskExecutor(...)
    result = await executor.execute_task(task)
except WorkflowError as e:
    print(f"Workflow error: {e}")
except TaskError as e:
    print(f"Task error: {e}")
except AgentError as e:
    print(f"Agent error: {e}")
except SecurityError as e:
    print(f"Security error: {e}")
```

---

## 最佳实践

### 1. 异步操作

所有 API 都是异步的，使用 `async/await`：

```python
import asyncio

async def main():
    scheduler = MultiModelScheduler(config)
    response = await scheduler.generate("Hello")

asyncio.run(main())
```

### 2. 错误处理

始终处理可能的异常：

```python
try:
    result = await scheduler.generate("Hello")
except Exception as e:
    logger.error(f"Generation failed: {e}")
```

### 3. 资源清理

使用上下文管理器或确保清理资源：

```python
await scheduler.start()
try:
    # 使用调度器
    pass
finally:
    await scheduler.stop()
```

### 4. 配置管理

使用配置文件管理设置：

```python
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

scheduler_config = SchedulerConfig(**config["scheduler"])
```

---

**版本**：v2.0.0
**最后更新**：2026-05-20
