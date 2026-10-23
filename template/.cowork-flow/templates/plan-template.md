# <功能> 实施计划

> 执行规则：本计划用于防止实现漂移，实现者必须按任务顺序推进。
> 如果计划与当前代码事实冲突、需要计划外文件，或测试因未计划的原因失败，停止并报告，不要扩大范围。
>
> 正式固定代理工作：使用 `.cowork-flow/run subagent init` 创建 runtime context，通过当前 Host Adapter 传入 `cowork_runtime_context_id: <runtime_context_id>`，再派发 `cowork-implement` 或 `cowork-check`；验证完成后关闭 runtime context。

| 字段 | 内容 |
|----|------|
| **任务类型** | Tiny / Normal / High-risk：<理由> |
| **执行策略** | Serial / Parallel：<理由> |
| **成功标准** | AC-001 / AC-002 / AC-003 |
| **最终验证** | `<command>` → exit 0；逐条核对适用的 `.cowork-flow/spec/<dev_type>/` 规范与项目门禁 → 每条 `pass` / `not_applicable` |
| **主要风险** | Low / Medium / High：<一句话> |

**目标:** <一句话描述可观察的行为变化>

## 目标

<1-3 句话描述预期可观察行为。>

## 验收标准

- AC-001: <可验证行为>
- AC-002: <可验证行为>

## 全局约束

- <必须保留的架构边界、兼容要求、命令或输出字段>
- <明确禁止的范围扩张>

## 文件边界

- `path/a.py`：<职责；只改这个函数或区域>
- `tests/test_a.py`：<职责；只新增或修改这些测试>

## 任务

Tiny 任务可保留简化 brief，但仍须写明精确文件边界、完成条件和一条验证命令。

### 任务 N：<小目标>

**目的**
- <本任务完成后的可观察行为>

**代码事实来源**
- Read: `path/a.py::function_name`
- Read: `tests/test_a.py::test_existing_behavior`

**文件边界**
- Create / Modify / Test: `path/a.py`（只改 <函数/区域>）
- Test: `tests/test_a.py`（只改 <测试/区域>）

**关键符号**
- Change: `function_name()`、`ClassName.method()`、`<config-key>`
- Preserve: `existing_helper()`、输出字段 `<field>`

**实现说明**
```python
# 核心控制流草图；按现有代码调整名称。
# 不要把完整实现复制进计划。
...
```

**测试证明**
- `tests/test_a.py::test_x`：证明 <具体行为>
- 核心断言：<一句话描述断言，不只有测试名>

**验证命令**
```bash
<command>
```

当改动文件受 `.cowork-flow/spec/<dev_type>/` 规则覆盖时，在这里加入决定命令或规范门禁核对行（`pass` / `not_applicable` 并附理由）。strict 非 Tiny 任务启动前必须把 `<pass / not_applicable + 理由>` 替换为实际核对结果；保留模板占位符会被 start 门禁阻断。

**完成条件**
- <2-4 条可检查条件>

**禁止漂移**
- <2-5 条明确禁止的改动>

**偏差条件**
- 如果 <计划外文件/层> 变得必要，必须停止并报告，因为文件边界有误。

## 最终验证

```bash
<command>
```

规范核对：逐条核对 `.cowork-flow/spec/<dev_type>/` 适用规范 → <pass / not_applicable + 理由>。
