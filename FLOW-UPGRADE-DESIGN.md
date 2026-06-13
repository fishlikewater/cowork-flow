# Cowork-flow 框架升级设计：Flow 看板 + 协作模式引擎

> 面向 Hermes Flow 模式库的架构升级设计。
> 宗旨：工作流逻辑不绑定具体原语，协作模式不绑定具体流程实现。

## 1. 目标与范围

### 1.1 升级目标

将 cowork-flow 从"单任务 + 固定 agent 派发"的工作流引擎，升级为"持久化看板 + 协作模式库 + Web Dashboard"的多 Agent 协作系统。

### 1.2 范围

| 包含 | 不包含 |
|------|--------|
| SQLite 持久化看板（`cowork-flow.db`） | P3 Voting（后续迭代） |
| P1 Fan-out / P2 Pipeline / P5 Human-loop 模式引擎 | P4 Journal / P6 @mention / P8 Fleet |
| Web Dashboard 只读看板视图 | Dashboard 写操作（由 CLI 统一写入口） |
| subagent 协议扩展（spawn-family / check-family） | 宿主适配器运行时实现变更 |
| task.py + subagent.py 重构 | Party Mode V2 改动 |

### 1.3 非目标

- 核心生命周期不再写入旧 `task.json`；hook / resume 只保留只读回退，作为过渡期兼容
- 不引入第三方依赖（`sqlite3`、`http.server` 均为 Python stdlib）
- 不改变现有 template 分发机制（`cowork-flow init/sync/update`）

## 2. 核心架构决策

### 2.1 模块分解

```
.cowork-flow/
├── scripts/
│   ├── run.py                          # 调度器：新增 flow/dashboard 命令注册
│   ├── task.py                         # 重构：薄 CLI + 委托 flow/patterns
│   ├── subagent.py                     # 扩展：spawn-family / check-family
│   │
│   ├── flow/                         # 持久化看板层
│   │   ├── __init__.py
│   │   ├── store.py                    # SQLite CRUD + 迁移
│   │   ├── schema.sql                  # DDL
│   │   └── migrate.py                  # task.json → SQLite 迁移
│   │
│   ├── patterns/                       # 协作模式引擎
│   │   ├── __init__.py
│   │   ├── base.py                     # Pattern 基类 + Action + StepKind
│   │   ├── fan_out.py                  # P1
│   │   ├── pipeline.py                 # P2
│   │   ├── human_loop.py              # P5
│   │   ├── generic.py                  # 默认模式（等价旧行为）
│   │   └── registry.py                # 模式注册与查找
│   │
│   ├── dashboard/                      # Web 看板
│   │   ├── __init__.py
│   │   ├── server.py                   # stdlib http.server
│   │   └── static/
│   │       ├── index.html
│   │       ├── app.js
│   │       └── style.css
│   │
│   └── common/                         # 工具层（微调）
│       ├── git_context.py              # 重构：走 flow/store.py
│       ├── active_task.py              # 重构：走 flow/store.py
│       ├── task_utils.py               # 删除：归档逻辑迁入 Flow
│       └── [其余基本不变]
│
├── adapters/
│   └── <host>/adapter.yaml            # 扩展：加 spawnMultipleSubagents 能力声明
│
├── spec/
│   ├── patterns/                       # 模式规格文档
│   │   ├── index.md
│   │   ├── fan-out.md
│   │   ├── pipeline.md
│   │   └── human-loop.md
│   └── registry.json                   # 契约注册表更新
│
└── cowork-flow.db                      # SQLite 持久化（项目级，gitignore）
```

### 2.2 唯一写入口原则

`flow/store.py` 是操作 `cowork-flow.db` 的唯一数据访问层。`task.py`、`subagent.py`、`dashboard/server.py` 均通过 `flow/store.py` 的公开方法访问数据。迁移脚本位于同一 `flow/` 包内，可在单个批量事务里使用 store 连接写入；其它模块禁止散落裸 `sqlite3.execute()`。

### 2.3 Pattern 独立于宿主与数据层

所有 Pattern 类不引用 `task.py`、`subagent.py`、`adapter.yaml`、`FlowStore`。Pattern 只接收预加载的 `TaskContext`（包含任务视图、子任务视图、活跃阻塞记录），返回 `Action`。数据预加载由调用方（`task.py`）负责，Pattern 保持纯逻辑。更换宿主适配器或数据源不影响 Pattern 逻辑。

### 2.4 SQLite WAL 模式

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

支持 Dashboard 读与 CLI 写并发。cowork-flow 为单用户单会话工具，WAL 并发能力远超实际需求，但作为防御性设计保留。`sqlite3` 是 Python stdlib，不引入新依赖。

### 2.5 事务与读写锁模型

- 写操作统一通过 `FlowStore._transaction()` 使用 `BEGIN IMMEDIATE`，任何异常都必须 rollback；只有 SQLite `locked` 类 `OperationalError` 才重试。
- 读操作不包写事务。`board_view()`、`get_task()`、`list_tasks()` 等 dashboard / hook 查询直接走普通 `SELECT`，避免只读看板占用 writer lock。
- CLI 生命周期命令必须检查 store 返回值。`review/complete/block/unblock/archive` 遇到缺失 DB 行或 DB 更新失败时返回非零，不得打印 `[OK]` 后静默吞错。
- `task archive` 先做 DB 行预检，再移动工件目录；目录移动成功后用单个 store 事务更新 `archived` 状态和父子关系。若 DB 更新失败，必须尝试把目录移回原位并返回失败。

## 3. SQLite Schema

### 3.1 表结构

```sql
-- 任务主表
CREATE TABLE task (
    id            TEXT PRIMARY KEY,
    artifact_dir  TEXT NOT NULL UNIQUE,   -- 工件目录名 "MM-DD-slug"，prd.md/jsonl 存放于此
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'planning',
    pattern       TEXT NOT NULL DEFAULT 'generic',
    priority      TEXT NOT NULL DEFAULT 'P2',
    creator       TEXT NOT NULL,
    assignee      TEXT NOT NULL,
    level         TEXT NOT NULL DEFAULT 'L1',
    parent_id     TEXT REFERENCES task(id) ON DELETE SET NULL,
    commit_sha    TEXT,                    -- 归档时关联的 git commit
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    completed_at  TEXT,
    meta          TEXT NOT NULL DEFAULT '{}'
    -- meta 中承载旧 task.json 字段：dev_type, scope, relatedFiles, notes
    -- meta 不宜并发写入；current_stage/current_decision 等运行时字段由 patterns 管理，
    -- 通过 store.update_meta() 串行化写入（cowork-flow 为单写入者架构）。
);

CREATE INDEX idx_task_status ON task(status);
CREATE INDEX idx_task_parent ON task(parent_id);
CREATE INDEX idx_task_pattern ON task(pattern);

-- 子任务关系
CREATE TABLE task_child (
    parent_id   TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    child_id    TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (parent_id, child_id)
);

CREATE INDEX idx_task_child_child ON task_child(child_id);

-- 状态变更审计
CREATE TABLE audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT REFERENCES task(id) ON DELETE SET NULL, -- 归档/删除后保留历史审计
    from_status TEXT,
    to_status   TEXT NOT NULL,
    operator    TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX idx_audit_task ON audit(task_id);

-- 阻塞记录 (P5)
CREATE TABLE block (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    reason      TEXT NOT NULL,
    decision    TEXT,
    decided_by  TEXT,
    blocked_at  TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX idx_block_task ON block(task_id);

-- 子代理运行时映射
CREATE TABLE agent_run (
    id              TEXT PRIMARY KEY,
    task_id         TEXT REFERENCES task(id) ON DELETE SET NULL, -- 运行历史不随 task 行丢失
    agent_type      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    host_context_key TEXT,
    error_message   TEXT,                  -- 失败时的错误信息，方便排查
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    closed_at       TEXT
);

CREATE INDEX idx_agent_run_task ON agent_run(task_id);
```

### 3.2 状态枚举

```python
class TaskStatus(Enum):
    PLANNING    = "planning"
    IN_PROGRESS = "in_progress"
    REVIEW      = "review"
    BLOCKED     = "blocked"     # 通用阻塞状态，所有 pattern 可用
    COMPLETED   = "completed"
    ARCHIVED    = "archived"
```

`blocked` 是通用状态，任何 pattern 的任务均可进入。但仅 P5 (`human_loop`) 定义了从 `blocked` 自动恢复到 `in_progress` 的 unblock 决策流程。其他 pattern 的 `blocked` 状态由人工通过 `task unblock` 手动恢复（无自动决策点）。

### 3.3 迁移策略

`flow/migrate.py` 处理一次性迁移，分四步：

**Step 1: 创建 SQLite 数据库并建表**

```bash
.cowork-flow/run flow migrate
```

**Step 2: 导入数据（事务包裹）**

先遍历 `tasks/*/task.json` 并解析全部记录，建立 `dir_name -> task.id` 映射；缺少 `task.json` 的目录仅警告跳过，不进入事务写入。写入时使用一个 SQLite 事务：

1. 第一遍插入 `task` 行，`artifact_dir` 使用真实目录名，`parent_id` 暂置空，避免 child 目录排在 parent 前面时触发 FK 失败。
2. 第二遍根据 child `parent` 和 parent `children[]` 生成去重后的父子边，写入 `task_child` 并回填 child `parent_id`。
3. 任一 SQL 硬失败 rollback 整个事务，不留下部分 task 行。

字段映射：

| task.json 字段 | SQLite 目标 |
|---------------|------------|
| `id`, `name` → `task.id` | slug |
| `title` | `task.title` |
| `description` | `task.description` |
| `status` | `task.status` |
| `priority` | `task.priority` |
| `creator` | `task.creator` |
| `assignee` | `task.assignee` |
| `completedAt` | `task.completed_at` |
| `commit` | `task.commit_sha` |
| `parent` | 第二遍解析为 `task.parent_id` + `task_child` |
| `children[]` | 第二遍解析为 `task_child` 行（子目录不存在时警告跳过） |
| `dev_type`, `scope`, `relatedFiles`, `notes` | `task.meta` (JSON) |

**Step 3: 校验**

不止检查行数，还需验证：
- 每条记录的 `status` 是合法状态枚举值
- 所有可解析的 `parent_id` 对应的父任务存在；不可解析父目录只输出迁移警告
- 所有 `task_child` 引用的子任务存在
- `audit` 表至少有每个 task 一条 `create` 记录

**Step 4: 回滚或提交**

- 校验全部通过：提交事务；CLI 主入口随后重命名 `tasks/` → `tasks.backup/`，将 `tasks.backup/` 追加到 `.gitignore`
- 任一硬失败：回滚事务，打印错误详情，退出码非零；不得留下部分已迁移 task 行

### 3.4 任务工件存储策略

任务工件（`prd.md`、`implement.jsonl`、`check.jsonl`、`debug.jsonl`）仍存储在文件系统：

```
tasks/<artifact_dir>/
├── prd.md
├── implement.jsonl
├── check.jsonl
└── debug.jsonl
```

- `artifact_dir` 格式保持 `MM-DD-slug`；`task create` 先确定真实目录名并传给 `FlowStore.create_task(artifact_dir=...)`，迁移则使用原目录名
- `artifact_dir` 是相对于 `tasks/` 的目录名，完整路径为 `{repo_root}/.cowork-flow/tasks/{artifact_dir}/`
- 工件目录与 SQLite 中的 `task` 行通过 `artifact_dir` 字段关联
- `task.json` 不再写入文件系统，任务状态以 SQLite 为准
- `task create` 时同时创建 SQLite 行和工件目录，`task archive` 时将 `tasks/<artifact_dir>/` 移动到 `tasks/archive/YYYY-MM/<artifact_dir>/`，同步更新 SQLite `status` 为 `archived`

## 4. Pattern Engine

### 4.1 基类

```python
class StepKind(Enum):
    CREATE_TASK    = "create_task"
    DISPATCH_AGENT = "dispatch_agent"
    WAIT_CHILDREN  = "wait_children"
    BLOCK          = "block"
    UNBLOCK        = "unblock"
    COMPLETE       = "complete"

@dataclass
class Action:
    kind: StepKind
    description: str
    task_id: str
    agent_type: str | None = None
    children: list[str] = field(default_factory=list)

@dataclass
class TaskView:
    id: str
    artifact_dir: str
    title: str
    status: str
    pattern: str
    parent_id: str | None
    children: list[str]
    meta: dict
    block_reason: str | None

@dataclass
class BlockView:
    id: int
    task_id: str
    reason: str
    decision: str | None
    decided_by: str | None
    blocked_at: str
    resolved_at: str | None

@dataclass
class TaskContext:
    """Pattern 所需的预加载上下文。

    由 task.py 在调用 Pattern 方法前构建，Pattern 不直接访问数据层。
    """
    task: TaskView
    children: list[TaskView]
    active_block: BlockView | None

class Pattern(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    @property
    @abstractmethod
    def valid_transitions(self) -> dict[str, set[str]]:
        """状态转换白名单。值为无条件允许的目标状态集合。
        如果某对 (from,to) 有条件约束，在此返回 from→{to}，
        条件逻辑由 can_transition() 控制。
        """
        ...
    @abstractmethod
    def validate(self, ctx: TaskContext) -> list[str]: ...
    @abstractmethod
    def next_action(self, ctx: TaskContext) -> Action | None: ...
    def transition_allowed(self, from_status: str, to_status: str) -> bool:
        """快速门禁：目标状态是否在白名单中。"""
        return to_status in self.valid_transitions.get(from_status, set())
    def can_transition(self, ctx: TaskContext, to_status: str) -> bool:
        """条件门禁：子类重写以表达状态转换的附加条件。
        默认回退到 transition_allowed()。
        """
        return self.transition_allowed(ctx.task.status, to_status)
```

### 4.2 P1 — Fan-out

状态转换：`planning → in_progress → review → completed → archived`

```python
class FanOut(Pattern):
    """1 父拆 N 子，并行执行，等所有子 done 才完成。

    ctx.children: 预加载的子任务 TaskView 列表。
    """
    name = "fan_out"
    valid_transitions = {
        "planning":    {"in_progress"},
        "in_progress": {"review"},
        "review":      {"completed"},
        "completed":   {"archived"},
    }

    def validate(self, ctx: TaskContext) -> list[str]:
        if not ctx.children:
            return ["Fan-out task must have child tasks"]
        issues = []
        for child in ctx.children:
            if child.pattern != "generic":
                issues.append(f"Child '{child.id}' pattern must be 'generic'")
        return issues

    def next_action(self, ctx: TaskContext) -> Action | None:
        if ctx.task.status == "in_progress":
            pending = [c for c in ctx.children if c.status not in ("completed", "archived")]
            if not pending:
                return Action(kind=StepKind.COMPLETE, description="All children done", task_id=ctx.task.id)
            return Action(kind=StepKind.WAIT_CHILDREN, description=f"Waiting for {len(pending)} children", task_id=ctx.task.id, children=[c.id for c in pending])
        return None
```

关键约束：
- 子任务只能是 `pattern='generic'` 的叶子任务
- 父任务进入 `review` 后锁定子任务列表，不再允许增删
- `in_progress` 状态下允许通过 `task link-child` 追加子任务
- 所有子任务完成前，父任务不能进入 review（`validate()` 校验）

### 4.2.1 Generic — 默认模式

状态转换（等价旧行为）。注意：Generic 新增了 `blocked` 状态（`in_progress → blocked → in_progress`），这是有意的行为变更 —— 升级后所有旧任务均可进入 blocked，与 §3.2 的"blocked 是通用状态"一致：

```python
class Generic(Pattern):
    name = "generic"
    valid_transitions = {
        "planning":    {"in_progress"},
        "in_progress": {"blocked", "review"},
        "blocked":     {"in_progress"},
        "review":      {"completed"},
        "completed":   {"archived"},
    }
    # validate() 和 next_action() 无特殊逻辑，返回空/None
```

> **行为变更说明**：旧版状态机为 `planning → in_progress → review → completed → archived`，无 `blocked`。升级后 Generic 模式增加了 `in_progress ↔ blocked` 转换。这是一个**有意的行为变更**，源于 §3.2 审核结论"blocked 应当作为通用状态"。升级后如需阻塞任务，使用 `task block <id> --reason`；恢复使用 `task unblock <id>`。

### 4.3 P2 — Pipeline

状态转换：`planning → in_progress → review → (in_progress | completed) → archived`

```python
class Pipeline(Pattern):
    """链式角色管道：A → B → C。

    meta 格式:
    {
      "stages": [
        {"name": "implement", "agent_type": "cowork-implement"},
        {"name": "check",     "agent_type": "cowork-check"}
      ],
      "current_stage": 0
    }
    """
    name = "pipeline"
    valid_transitions = {
        "planning":    {"in_progress"},
        "in_progress": {"review"},
        "review":      {"in_progress", "completed"},
        "completed":   {"archived"},
    }
```

关键约束：
- `stages` 必填，至少 1 个阶段
- `review → in_progress` 表示当前阶段审查不通过，打回重做；`current_stage` 保持不变（重做当前阶段，不回退）
- `review → completed` 仅当 `current_stage >= len(stages)` 时合法

条件转换示例（Pipeline 重写 `can_transition`）：

```python
class Pipeline(Pattern):
    def can_transition(self, ctx, to_status):
        if to_status == "completed":
            stages = ctx.task.meta.get("stages", [])
            current = ctx.task.meta.get("current_stage", 0)
            return current >= len(stages)
        return super().can_transition(ctx, to_status)
```

### 4.4 P5 — Human-in-the-loop

状态转换：`planning → in_progress → blocked → in_progress → review → completed → archived`

```python
class HumanLoop(Pattern):
    """关键决策点卡人：AI 提议 → Human 决策 → 恢复执行。

    meta 格式:
    {
      "decision_points": [
        {"question": "用户协议涉及 GDPR，选择 A(显式同意)还是 B(不收集IP)？"}
      ],
      "current_decision": 0
    }
    """
    name = "human_loop"
    valid_transitions = {
        "planning":    {"in_progress"},
        "in_progress": {"blocked", "review"},
        "blocked":     {"in_progress"},
        "review":      {"completed"},
        "completed":   {"archived"},
    }
```

关键约束：
- `decision_points` 必填
- P5 是唯一在 `blocked` 状态下有自动 unblock 决策路径的模式（通过 `task unblock` 人工决策后自动恢复）
- 非 P5 模式的 `blocked` 需通过 `task unblock --force` 手动恢复，无决策记录要求
- unblock 时写入 `block` 表的 `decision` 和 `decided_by` 字段
- respawn agent 时注入完整 block 历史到 runtime context 的 `allowed_context`

### 4.5 模式注册表

```python
class PatternRegistry:
    def __init__(self):
        self._patterns: dict[str, Pattern] = {}

    def register(self, pattern: Pattern) -> None:
        self._patterns[pattern.name] = pattern

    def get(self, name: str) -> Pattern | None:
        return self._patterns.get(name)

    def resolve(self, task: TaskView) -> Pattern:
        return self._patterns.get(task.pattern, self._patterns["generic"])

    def select(self, task: TaskView) -> Pattern:
        """根据任务特征启发式推荐模式（仅建议，非权威）。

        不应用于自动决策。用户可显式指定 pattern 覆盖推荐。
        使用 `is not None` 而非 truthiness，避免空列表被误判。
        """
        if task.children:
            return self._patterns["fan_out"]
        if task.meta.get("stages") is not None:
            return self._patterns["pipeline"]
        if task.meta.get("decision_points") is not None:
            return self._patterns["human_loop"]
        return self._patterns["generic"]


def create_registry() -> PatternRegistry:
    from .fan_out import FanOut
    from .pipeline import Pipeline
    from .human_loop import HumanLoop
    from .generic import Generic
    r = PatternRegistry()
    r.register(FanOut())
    r.register(Pipeline())
    r.register(HumanLoop())
    r.register(Generic())
    return r
```

### 4.6 Pattern 与 task.py 的调用关系

`task.py` 中每个生命周期命令（start/review/complete/archive/block/unblock/next）的模式如下：

```python
from common.paths import get_db_path
from patterns.base import TaskContext

def _build_context(store: FlowStore, task_id: str) -> TaskContext:
    """预加载 Pattern 所需的全部数据。

    当前采用 eager load：遍历所有子任务，无论模式是否需要。
    cowork-flow 为单用户工具，任务规模不会超过数十个，此开销可接受。
    规模扩展时将 provider 注入 Pattern，改为 lazy load。
    """
    task = store.get_task(task_id)
    children = store.list_children(task_id)
    active_block = store.get_active_block(task_id)
    return TaskContext(task=task, children=children, active_block=active_block)

def _execute_with_pattern(task_id: str, target_status: str, operator: str):
    registry = create_registry()
    store = FlowStore(get_db_path())
    ctx = _build_context(store, task_id)
    pattern = registry.resolve(ctx.task)

    # 1. 校验状态转换（快速门禁，先于业务校验）
    if not pattern.can_transition(ctx, target_status):
        return _fail(f"pattern '{pattern.name}' forbids {ctx.task.status} → {target_status}")

    # 2. 校验模式约束
    issues = pattern.validate(ctx)
    if issues:
        return _fail(issues)

    # 3. 执行
    store.update_status(task_id, target_status, operator)

    # 4. 返回 next action
    ctx = _build_context(store, task_id)
    action = pattern.next_action(ctx)
    return action
```

`task next` 命令在 Phase 2 重构为调用 pattern.next_action()，输出人类可读的下一步指令：

```
$ ./cowork-flow run task next my-feature

  Pattern: fan_out
  Status:  in_progress
  Next:    WAIT_CHILDREN — 2/3 children done, waiting: child-3
  Action:  subagent spawn-family my-feature   # if some children not dispatched
           subagent check-family my-feature   # to verify completion
```

### 4.7 CLI 接口变更

`task create` 新增 `--pattern` 和 `--meta` 参数：

```
task create "<title>" [--slug <name>] [--pattern generic|fan_out|pipeline|human_loop]
           [--meta '{}'] [--assignee <dev>] [--priority P0|P1|P2|P3] [--parent <dir>]
```

| 新参数 | 默认值 | 说明 |
|--------|--------|------|
| `--pattern` | `generic` | 指定协作模式。`task.py` 传入 `FlowStore.create_task(pattern=...)` |
| `--meta` | `{}` | JSON 字符串，存储模式特异性配置（stages/decision_points 等） |

`task next` 各状态行为：

| 状态 | 期望输出 |
|------|---------|
| `planning` | 提示缺失的 prd.md/context，建议 `task start` |
| `in_progress` | 根据 pattern.next_action() 输出下一步指令 |
| `blocked` | 显示 block 历史（原因、决策人、时间），建议 `task unblock` |
| `review` | 建议派发 `cowork-check`，提示检查清单 |
| `completed` | 建议 `task archive`，显示完成时间 |

`task archive` 归档路径：将 `tasks/<artifact_dir>/` 移动到 `tasks/archive/YYYY-MM/<artifact_dir>/`，同步更新 SQLite `status` 为 `archived`。

`task list-context`、`task add-context`、`task validate`：仍操作文件系统中的 JSONL 文件，路径从 `store.get_task(id).artifact_dir` 拼接完整路径。

## 5. flow/store.py 公开接口

### 5.1 DB 路径解析

```python
# common/paths.py 新增
def get_db_path(repo_root: Path | None = None) -> Path:
    """返回 SQLite 数据库文件路径。"""
    root = repo_root or get_repo_root()
    return root / DIR_WORKFLOW / "cowork-flow.db"
```

### 5.2 公开接口

```python
class FlowStore:
    """SQLite 持久化看板的唯一数据访问层。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    # --- Schema ---
    def _ensure_schema(self) -> None: ...

    # --- Task CRUD ---
    def create_task(self, *,
        id: str, title: str,
        description: str = "", status: str = "planning",
        pattern: str = "generic", priority: str = "P2",
        creator: str, assignee: str, level: str = "L1",
        parent_id: str | None = None,
        artifact_dir: str | None = None,
        commit_sha: str | None = None,
        meta: dict | None = None,
    ) -> str:
        """创建任务。artifact_dir 由 CLI/迁移传入；省略时回退为 MM-DD-{id}。返回 task id。
        meta 可承载 dev_type, scope, relatedFiles, notes 等辅助字段。
        """
        ...

    def get_task(self, task_id: str) -> TaskView | None: ...
    def get_task_by_artifact_dir(self, artifact_dir: str) -> TaskView | None: ...
    def update_status(self, task_id: str, new_status: str,
                      operator: str, reason: str = "") -> bool: ...
    def update_meta(self, task_id: str, meta: dict) -> bool:
        """原子更新 meta JSON。内部使用 BEGIN IMMEDIATE 事务防止读-改-写竞态。
        适用于 current_stage/current_decision 等运行时字段更新。
        遇到 SQLITE_BUSY 时内置 3 次重试（间隔 100ms），3 次均失败则抛异常。
        """
        ...
    def list_tasks(self, status: str | None = None) -> list[TaskView]: ...
    def list_children(self, parent_id: str) -> list[TaskView]: ...

    # --- 父子关系 ---
    def link_child(self, parent_id: str, child_id: str, sort_order: int = 0) -> bool: ...
    def unlink_child(self, parent_id: str, child_id: str) -> bool: ...
    def all_children_done(self, parent_id: str) -> bool: ...

    # --- Block ---
    def block_task(self, task_id: str, reason: str) -> bool: ...
    def unblock_task(self, task_id: str, decision: str = "", decided_by: str = "") -> bool: ...
    def get_active_block(self, task_id: str) -> BlockView | None: ...

    # --- Agent Run ---
    def create_agent_run(self, *,
        id: str, task_id: str, agent_type: str,
        status: str = "pending",
        host_context_key: str | None = None,
        created_at: str,
    ) -> str: ...
    def update_agent_run_status(self, run_id: str, status: str) -> bool: ...
    def get_active_agent_run(self, task_id: str) -> AgentRunView | None: ...
    def list_agent_runs_for_parent(self, parent_id: str) -> list[AgentRunView]: ...

    # --- Audit ---
    def get_audit_trail(self, task_id: str) -> list[AuditEntry]: ...
    def archive_task(self, task_id: str, operator: str, reason: str = "") -> bool: ...

    # --- Dashboard ---
    def board_view(self) -> BoardView: ...
```

### 5.3 Hook 环境变量变更

旧：`TASK_JSON_PATH` 指向 `task.json`。
新：生命周期 hook 子进程接收以下环境变量：

| 变量 | 值 | 示例 |
|------|----|------|
| `COWORK_TASK_ID` | 任务 slug | `my-feature` |
| `COWORK_TASK_DIR` | 工件目录相对路径 | `.cowork-flow/tasks/06-11-my-feature` |
| `COWORK_DB_PATH` | SQLite 数据库路径 | `.cowork-flow/cowork-flow.db` |

**过渡期策略**：核心 task 操作（create/start/review/complete/archive/block/unblock）以 SQLite 为真源，不再写 `task.json`，也不再向生命周期 hook 传 `TASK_JSON_PATH`。workflow-state 注入先通过 `COWORK_DB_PATH` / `FlowStore` 按 `artifact_dir` 读取真实状态；只有 DB 不存在或任务行不可解析时，才只读回退旧 `task.json`，避免旧项目恢复时直接失明。

`config.yaml` 中 hook 示例相应更新：

```yaml
hooks:
  after_create:
    - "python scripts/on_task_event.py after_create"
  after_start:
    - "python scripts/on_task_event.py after_start"
```

## 6. Subagent 协议扩展

### 6.1 新增命令

| 命令 | 用途 | 关联模式 |
|------|------|---------|
| `subagent spawn-family` | 为父任务的所有子任务批量创建 runtime context | P1 |
| `subagent check-family` | 检查父任务下所有子 agent 是否全部 done | P1 |

`agent_run` 表是 SQLite 索引层，用于 dashboard 查询和 `check-family` 批量状态检查。`.runtime/subagents/*.json` 文件仍由 `subagent.py` 维护，用于 host adapter 的 binding 协议。两者通过 `id`（即 `runtime_context_id`）关联。`agent_run` 不替代文件系统 runtime context。

### 6.2 spawn-family

```
subagent spawn-family <parent_id> [--agent-type cowork-implement] [--host opencode]
```

遍历 `task_child` 表中父任务的所有子任务，为 `status != completed` 且尚无 active agent_run 的子任务创建 runtime context。

幂等性保护：同一 `(task_id, agent_type)` 已存在 `status != 'closed'` 的 `agent_run` 时，跳过创建并标记 `already_running`。

返回 JSON：
```json
[
  {"id": "rtx_20260611_01", "task_id": "child-1", "status": "pending"},
  {"id": "rtx_20260611_02", "task_id": "child-2", "status": "pending"}
]
```

### 6.3 check-family

```
subagent check-family <parent_id>
```

返回 JSON：
```json
{
  "all_done": false,
  "pending": [{"id": "rtx_01", "task_id": "child-1", "status": "bound"}],
  "done": [{"id": "rtx_02", "task_id": "child-2", "status": "success"}],
  "failed": []
}
```

Exit code 0 = all done，1 = 还有未完成的或有失败的。

### 6.4 adapter.yaml 扩展

```yaml
capabilities:
  spawnMultipleSubagents: native     # 新增
  waitMultipleChildren: native       # 新增
```

### 6.5 workflow.md 更新要点

- 实现阶段新增 fan-out 分支：P1 任务先运行 `subagent spawn-family`，再逐条 dispatch
- P5 任务在到达决策点时，通过 `task block` 进入 blocked 状态
- human 通过 `task unblock` 恢复

### 6.6 Fan-out 完整工作流示例

```
# 1. 创建 fan-out 父任务
task create "Implement auth module" --pattern fan_out

# 2. 创建子任务并自动关联
task create "Implement login" --parent auth-module
task create "Implement signup" --parent auth-module
task create "Implement OAuth" --parent auth-module
# --parent 自动执行 link-child，子任务默认 pattern=generic

# 3. 启动父任务
task start auth-module

# 4. 批量创建子 agent runtime context
subagent spawn-family auth-module --agent-type cowork-implement

# 5. Host adapter 逐条 dispatch 子 agent（并行）

# 6. 检查子 agent 完成状态
subagent check-family auth-module

# 7. 所有子完成后，父任务进入 review
task review auth-module
```

## 7. Dashboard

### 7.1 API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/` | 看板页面 |
| `GET` | `/api/board` | 看板数据（按 status 分组） |
| `GET` | `/api/task/{id}` | 任务详情 + audit trail + block 历史 |
| `GET` | `/api/task/{id}/children` | 子任务列表 |
| `GET` | `/api/patterns` | 已注册模式列表 |
| `GET` | `/static/*` | 静态资源 |

### 7.2 看板视图

6 列布局：

```
│ 计划中 │ 进行中 │ 审查中 │ 已阻塞 │ 已完成 │ 已归档 │
```

每张任务卡片显示：
- 标题
- Pattern 图标（`◈` fan-out / `⇶` pipeline / `⛔` human-loop）
- 优先级颜色（P1 红 / P2 黄 / P3 灰）
- Assignee
- 子任务完成进度 `2/5 done`（仅 fan-out 显示）
- 当前阶段 `stage 2/3`（仅 pipeline 显示）

### 7.3 启动方式

```
.\.cowork-flow\run.cmd dashboard [--port 8080]
```

Python `http.server` + 内嵌 HTML/CSS/JS。无构建步骤，无 npm 依赖。端口被占用时自动尝试 `port+1`（最多尝试 10 次），输出最终绑定的 URL。

`dashboard/server.py` 需在顶部注入导入路径：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

同时更新 `run.py` 的 `COMMAND_SCRIPTS` 注册 `dashboard` 命令。

### 7.4 Dashboard 是只读的

所有写操作（创建任务、转移状态、block/unblock）必须通过 `task.py` CLI 走 `flow/store.py`。Dashboard 不提供 POST/PUT/DELETE 端点。

### 7.5 自动刷新

前端通过 `setInterval(fetch /api/board, 3000)` 每 3 秒轮询。卡片变更时做 diff 而非全量重绘，减少 DOM 闪动。

## 8. 实施阶段

### Phase 1: 看板基础（预估 3-4 天）

| 步骤 | 内容 | 验证 |
|------|------|------|
| 1.1 | 新建 `flow/store.py`，实现 SQLite schema + CRUD。更新 `run.py` 的 `COMMAND_SCRIPTS` 注册 `flow` 命令 | 单元测试：创建/读取/更新/删除；`IntegrityError` 后连接仍可继续写 |
| 1.2 | 新建 `flow/schema.sql`，定义全部 5 张表 | DDL 语法校验通过；audit/agent_run 历史行 FK 策略明确 |
| 1.3 | 新建 `flow/migrate.py`，从 `task.json` 迁移（整批事务 + 回滚） | 迁移测试：正常数据 + 子在父前 + 孤儿引用 + 硬失败整批 rollback + 空目录 |
| 1.4 | 重构 `task.py`：create/start/review/complete/archive/block/unblock/list/current/next 全部走 `flow/store.py`；list-context/add-context/validate 路径改为从 `artifact_dir` 拼接 | 全量 task 命令测试通过；缺失 DB 行不得静默成功 |
| 1.5 | 重构 `common/git_context.py`，`_load_task_json_by_dir()`→`store.list_tasks()` | resume/get_context 输出一致 |
| 1.6 | 重构 `common/active_task.py` 和 workflow-state hook，状态优先从 SQLite 查询 | 会话恢复测试通过；Flow-only 任务不返回 `stale` |
| 1.7 | 删除 `common/task_utils.py` 中的归档逻辑 + `FILE_TASK_JSON` 引用 | 无死代码引用 |
| 1.8 | 更新 `template/`：移除 task.json 相关文件、新增 `cowork-flow.db` 和 `tasks.backup/` 到 `.gitignore` | 模板安装后新项目走 SQLite，`task create` 自动初始化 db |
| 1.9 | Phase 1 reliability gate | `tests/test_flow_store.py tests/test_flow_migrate.py tests/test_flow_script_paths.py tests/test_codex_hooks.py tests/test_claude_hooks.py` 通过；`board_view()` 不发 `BEGIN IMMEDIATE` |

### Phase 2: 模式引擎（预估 3-4 天）

| 步骤 | 内容 | 验证 |
|------|------|------|
| 2.1 | 新建 `patterns/base.py`（基类 + Action + TaskView + StepKind） | 接口完整性检查 |
| 2.2 | 新建 `patterns/generic.py`（等价旧行为） | 与 Phase 1 行为一致 |
| 2.3 | 新建 `patterns/fan_out.py` + `patterns/pipeline.py` + `patterns/human_loop.py` | 各自单元测试 |
| 2.4 | 新建 `patterns/registry.py` | 注册/查找/推荐测试 |
| 2.5 | 重构 `task.py` 接入 pattern engine | 模式选择 + 校验 + 状态转换 gate |
| 2.6 | 扩展 `task.py` 支持 `task block <id> --reason` / `task unblock <id> --decision` | P5 阻塞/解除流程测试 |
| 2.7 | 新建 `.cowork-flow/spec/patterns/*.md` | 模式文档完整性 |

### Phase 3: Subagent + Dashboard + 模板同步（预估 3-4 天）

| 步骤 | 内容 | 验证 |
|------|------|------|
| 3.1 | 扩展 `subagent.py` — spawn-family / check-family | P1 fan-out 端到端测试 |
| 3.2 | 扩展 `adapter.yaml`（所有 host）加能力声明 | schema 校验通过 |
| 3.3 | 新建 `dashboard/server.py` + `dashboard/static/` | 看板 API 返回正确 + 页面可渲染 |
| 3.4 | 更新 `workflow.md` 描述新模式使用方式 | 文档自洽 |
| 3.5 | 更新 `template/` 所有模板文件 + 平台脚本 | 完整模板安装 + 新项目启动测试 |
| 3.6 | 更新 `registry.json` 加 pattern-related 契约 | 契约索引完整 |

### Phase 4: 回归验证 + 发布（预估 1-2 天）

| 步骤 | 内容 |
|------|------|
| 4.1 | `npm run test:all` 全量测试 |
| 4.2 | 从零 install → init → 创建 P1/P2/P5 任务 → 完整流程走通 |
| 4.3 | 旧项目迁移测试（v0.0.26 → new），通过 `.cowork-flow/run flow migrate` 验证 CLI、DB、backup、`.gitignore` |
| 4.4 | 发布 npm + changelog；本地阶段只做 package dry-run，真实 `npm publish` 需人工确认 |

## 9. 测试策略

### 9.1 单元测试

`flow/store.py`：每个公开方法一个测试用例，覆盖：
- 正常路径（CRUD 成功）
- 约束违反（重复主键、外键不存在）
- 并发写入（多线程 insert + 读一致性）

SQLite 使用 `:memory:` 模式，每个测试独立创建 `FlowStore(":memory:")`，`_ensure_schema()` 自动建表。

`tests/conftest.py` 新增 fixture：

```python
@pytest.fixture
def store():
    """提供独立内存数据库的 FlowStore 实例。"""
    s = FlowStore(":memory:")
    yield s
```

`patterns/*.py`：每个 Pattern：
- `validate()` 合法任务返回空
- `validate()` 不合法任务返回具体问题
- `transition_allowed()` 每对 (from, to) 覆盖
- `can_transition()` 条件转换覆盖
- `next_action()` 各状态下的正确 Action
- 所有测试通过构造 `TaskContext` 实例驱动，不依赖 `FlowStore`

### 9.2 集成测试

- task.py + Flow + patterns：完整生命周期 flow
- subagent.py + Flow：spawn-family → bind → check-family → close
- dashboard + Flow：/api/board 返回数据正确

### 9.3 回归验证

- 所有现有 Node.js 测试（`test/`）保持通过
- 所有现有 Python 测试（`tests/`）更新后通过
- `npm run test:template` 更新模板后通过

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| task.py 重构导致隐藏 bug | 中 | 高 | Phase 1 全量 task 命令测试覆盖，generic pattern 等价旧行为 |
| SQLite WAL 在 Windows 上的并发锁 | 低 | 中 | 测试验证 WAL 模式在 Win/NTFS 的表现 |
| 模板同步遗漏文件 | 中 | 中 | Phase 3 有专门模板更新步骤 + 全量安装测试 |
| 旧项目迁移数据丢失 | 低 | 高 | migrate.py 事务包裹 + 回滚 + tasks.backup/ 保留 |
| Dashboard 前端代码量膨胀 | 低 | 低 | 单文件 HTML，不超过 500 行 JS，可接受 |
| git_context.py 重构遗漏引用 | 中 | 中 | 回归验证 resume.py 输出 + add_session 输出一致性 |
| 孤儿 children 引用导致迁移卡死 | 低 | 中 | 迁移脚本跳过不存在的子目录，输出警告 |
| 内存数据库模式与文件数据库行为差异 | 低 | 低 | CI 中同时运行 :memory: 和临时文件两种模式测试 |
| Hook 环境变量变更导致静默失败 | 中 | 中 | lifecycle hook 只传 `COWORK_*` 变量；workflow-state 注入先查 SQLite，再只读回退 `task.json` |
| DB 状态与任务目录移动分裂 | 中 | 高 | `task archive` 先 DB 预检，目录移动后用单事务更新 DB；DB 失败则尝试回滚目录 |
| 只读 Dashboard 占用写锁 | 低 | 中 | `board_view()` 不走 `BEGIN IMMEDIATE`，仅执行普通 `SELECT` |
| tasks.backup/ 被意外提交 | 低 | 中 | 迁移后自动追加到 .gitignore |
| meta 字段扩容后 JSON 膨胀 | 低 | 低 | meta 仅承载低频辅助字段，运行时状态通过专用列管理 |

## 11. 验收标准

### 11.1 Phase 1 必须先满足

1. `FlowStore` 任意写事务失败都会 rollback，同一连接在 `IntegrityError` 后仍可继续写。
2. `task create --parent` 只生成一条父子关系，不因重复 `link_child` 失败。
3. `flow.migrate.run_migration()` 不受目录排序影响；任一硬失败不留下部分迁移数据。
4. `block/unblock/review/complete/archive` 遇到缺失 DB 行或 DB 更新失败时返回非零。
5. workflow-state hook 对只有 SQLite、没有 `task.json` 的 active task 返回真实状态。
6. `board_view()` 为只读查询，不执行 `BEGIN IMMEDIATE`。
7. root/template runtime 文件保持同步。

### 11.2 完整升级验收

1. 通过 `task create --pattern fan_out` 创建 P1 任务，拆 3 个子任务，3 个子 agent 并行执行，父任务等所有子 done 后自动进入 review
2. 通过 `task create --pattern pipeline --meta '{"stages":[...]}'` 创建 P2 任务，依序 dispense implement → check agent，中间可打回重做
3. 通过 `task create --pattern human_loop --meta '{"decision_points":[...]}'` 创建 P5 任务，agent 运行中触发 block，human 通过 `task unblock` 恢复
4. `cowork-flow dashboard` 启动后浏览器可见 6 列看板，每列显示对应状态的任务
5. 从旧版 v0.0.26 项目运行 `cowork-flow update` 后，执行 `migrate` 成功迁移所有现有任务
6. 零第三方依赖（`pip list --not-required` 不新增条目，npm 不新增 dependents）
