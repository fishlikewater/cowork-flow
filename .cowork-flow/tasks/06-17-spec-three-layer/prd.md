# P1-B: Spec Three-Layer Documentation Refactor

## Goal

将 `.cowork-flow/spec/` 从平面结构重构为三层文档体系（quick-start / core / reference），解决概念密度高、新读者无处入手的问题。每层服务不同读者，同一条规则只有一个权威位置。

## Background

当前 spec 目录有 29 个文件分布在 5 个子目录，核心规范（workflow.md、subagent-dispatch.md、entry-contract.md、patterns/*、workflow-state-templates.md）超过 1000 行概念密度，新接触者没有清晰的阅读路径。

P0-A、P0-B、P1-A 已全部完成，spec 文档数量和内容持续累积，需要结构性整理。

## Scope

### 改动范围

1. **新建目录结构**：

   ```
   .cowork-flow/spec/
   ├── quick-start.md                    # 新读者 1 页入门：最小流程 + 索引
   ├── core/                             # Core Protocol：规则正文
   │   ├── entry.md                      # 从 entry-contract.md 迁入
   │   ├── dispatch.md                   # 从 subagent-dispatch.md 迁入
   │   ├── lifecycle.md                  # 从 workflow.md 迁移任务生命周期部分
   │   └── state-templates.md            # 从 workflow-state-templates.md 迁入
   └── reference/                        # Reference：细节
       ├── patterns/                     # 从 spec/patterns/ 迁入
       │   ├── index.md
       │   ├── fan-out.md
       │   ├── pipeline.md
       │   └── human-loop.md
       ├── adapters/                     # 从 spec 根目录迁入
       │   ├── capabilities.md
       │   └── adapter.schema.json
       ├── party-mode-v2-board.md        # 从 spec 根目录迁入
       └── guides/                       # 从 spec/guides/ 迁入
           ├── index.md
           ├── code-reuse-thinking-guide.md
           ├── cross-layer-thinking-guide.md
           └── pre-implementation-checklist.md
   ```

2. **quick-start.md**：
   - 只放索引 + 最小流程图 + "何时读哪份"导航
   - 不放规则正文
   - 面向首次接触项目的开发者，1 页内读完

3. **core/ 目录**：
   - 放必须遵守的规则，是 AI 和人类都要读的权威
   - `entry.md` = 原 `entry-contract.md` 全文迁移
   - `dispatch.md` = 原 `subagent-dispatch.md` 全文迁移
   - `lifecycle.md` = 从 `workflow.md` 提取任务生命周期相关章节（状态机、阶段命令、固定代理）
   - `state-templates.md` = 原 `workflow-state-templates.md` 全文迁移

4. **reference/ 目录**：
   - 放细节契约，按需读
   - `patterns/` = 原 `spec/patterns/` 目录平移
   - `adapters/` = 原 `spec/capabilities.md` + `spec/adapter.schema.json`
   - `party-mode-v2-board.md` = 原文件平移
   - `guides/` = 原 `spec/guides/` 目录平移

5. **registry.json 更新**：
   - 所有契约 path 指向新位置
   - readWhen 保持不变

6. **workflow.md 更新**：
   - 移除已迁入 core/ 的内容引用
   - 改为索引指向 core/ 文档

### 不改动

- 不改变任何规则正文内容（仅位置迁移）
- 不新增或修改 spec 规则
- 不改动代码、adapter.yaml、config.yaml
- 不改动 tests/
- 不改动 `.cowork-flow/workflow.md`（流程不变，只是文档位置变了）

## Acceptance Criteria

1. 所有原 spec 文件内容已迁移到新位置，无内容丢失。
2. `quick-start.md` 包含索引和"何时读哪份"导航，不超过 1 页。
3. `core/` 目录包含全部必须遵守的规则。
4. `reference/` 目录包含所有细节契约。
5. `registry.json` 的契约 path 全部更新为新位置。
6. `workflow.md` 中的 spec 引用更新为新路径。
7. 文档唯一性检查：无同一条规则出现在两个权威位置（允许 quick-start 引用 core 标题）。
8. root ↔ template 一致性：template 目录同步完成，FC 确认无差异。
9. 所有现有代码中的 spec 文件路径引用更新为新路径。

## Verification

- `fc /N` 对比 root 和 template spec 文件
- 检查代码中 `.cowork-flow/spec/` 路径引用是否更新
- `npm run test:template` 验证 template 一致性

## 关联

- Plan: `2026-06-15-workflow-maturity-roadmap.md` → P1-B
- Change: `06-15-workflow-maturity-roadmap`
- 上游：P0-A 已完成 entry-contract.md V2 改造
