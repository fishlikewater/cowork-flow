# Orchestration Patterns

> 已实现的协作模式声明性目录。
> 本文件是 spec/contracts/ 系列的人可读摘要——权威定义以 spec/contracts/ 为准。

## 核心原则

**主会话是唯一的协调者。固定子代理是叶子执行者。用户是流程的最终决策者。**

---

## 模式 1：叶子执行器（已实现）

```
主会话 -> cowork-implement（实现）-> 返回 -> 主会话验证
主会话 -> cowork-check（验证）     -> 返回 -> 主会话确认
主会话 -> cowork-research（调研）  -> 返回 -> 主会话综合
```

**使用场景**: 当需要与文件系统、Git、任务状态或外部进程交互时。

**约束**:
- R-AG-001: 子代理不能派发其他子代理
- R-AG-002: 子代理不修改 spec 文件
- R-AG-003: 子代理不操作 Git
- R-AG-004: 子代理不提交/归档

**验证**: dispatch 前用 `subagent init --role` 创建 runtime context；child 第一个动作必须是 `subagent bind`；parent 检查 `status: bound`。

---

## 模式 2：并行扇出 + 合并（已实现，主会话管理）

```
主会话 ─┬─> cowork-implement (task-slice-a) ─┐
        ├─> cowork-implement (task-slice-b) ─┤─> 所有返回 ─> 集成验证 ─> 主会话综合
        └─> cowork-research (background)    ─┘
```

**使用场景**: 多个低耦合的实现切片可以并行。

**验证清单**:
1. 子任务之间无写冲突（不同文件或通过 git worktree 隔离）
2. 每个子代理产出不同类型的发现
3. 合并步骤在主 agent 的上下文窗口内可完成
4. 用户等待时长足够使 parallel wall-clock 收益明显

任一答案为否 → 回退为模式 1 顺序执行。

---

## 模式 3：顺序 skill 链（已实现，用户驱动）

```
用户执行: task next --run --title ... -> brainstorming -> task-planning -> task next <dir> --run -> implement -> check -> task next <dir> --run --intent review
```

**使用场景**: 阶段之间有依赖关系，用户在阶段间判断有价值。

**为什么不做生命周期编排 agent**:
- 编排 agent 会在 hand-off 间总结→丢失细微差异
- 用户在阶段间的检查点能早期发现方向错误
- 人工检查的成本 < 走错方向的返工成本

---

## 模式 4：Party Mode V2 Board（已实现，咨询性质）

```
主会话 ─> 启动 Discussion（party-v2 runtime board）
       ─> 子代理通过 board 交流（不直接对话）
       ─> 主持人监控漂移，不参与决策
       ─> 产出建议，不改变任务状态
```

**约束**:
- Board 不能推进任务状态
- 不能替代 Implement/Check formal gates
- 主持人不能转述、总结、合成子代理意见

---

## 反模式 A：路由人格（禁止）

```
/workflow -> 代理人格("需要什么角色?") -> 子人格 -> 代理人格(重述) -> 用户
```

**为什么不行**: 纯路由层没有领域价值; 两次重述→信息丢失+~2x token; AGENTS.md 的 workflow-state 路由已覆盖

**替代方案**: 用 `<workflow-state>` 块直接路由，不通过人格。

---

## 反模式 B：人格调用人格（禁止）

```
cowork-check("看到安全相关代码") -> cowork-security-audit
```

**为什么不行**: 人格设计为产出单一视角; 链式调用破坏此设计; 调用人格传递的摘要丢失上下文; 失败模式相乘

**替代方案**: 当前人格在报告中推荐后续审计；用户或主会话运行第二轮。

---

## 反模式 C：Deep nesting（禁止）

```
/ship -> quality-coordinator -> code-reviewer -> security-auditor
```

**为什么不行**: 每一层增加延迟和 token 但无决策价值; 深层人格的上下文多次总结后失真

**替代方案**: cowork-flow 当前深度 = 1（主会话 → 叶子子代理）。不引入中间层。

---

## 决策流

```
任务是一个视角对一个 artifact？
├── 是 → 直接调用。停止。
└── 否 → task 可并列？
         ├── 否 → 顺序 skill 链（用户驱动）
         └── 是 → 并行扇-out（主会话协调）
                  验证清单：
                  - 子任务无写冲突
                  - 每 persona 产出不同类型
                  - 合并步骤 fit in main context
                  任一不满足 → 回退顺序
```

## 参见

- `spec/contracts/subagent-dispatch.md` — formal dispatch 协议权威定义
- `spec/contracts/party-mode-v2-board.md` — Party Mode V2 权威定义
- `spec/backend/`、`spec/frontend/`、`spec/guides/` — 用户定义规范，由 review skill 按需逐条审查
- `skills/cowork-flow/SKILL.md` — workflow state 路由
