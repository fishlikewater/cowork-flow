# P3-B: Doc Language Unification (core layer)

## Goal

将 spec core 层的中文文档翻译为英文，确立"英文 spec 为权威"的基调。本次聚焦 core 层索引文件和 state-templates，剩余文件后续分期翻译。

## Background

### 现状

- 6 个 spec 文件已英文（quick-start, dispatch, entry, lifecycle, party-mode-v2-board, capabilities）
- 21 个 spec 文件含中文内容
- design.md 方案："spec 工作语言定为全英文，翻译分期进行"

### 本次范围

翻译 core 层最关键的 3 个文件（索引 + 状态模板）：

| 文件 | 中文量 | 优先级 |
|---|---|---|
| `core/backend/index.md` | 459 字 | 高（入口索引） |
| `core/frontend/index.md` | 439 字 | 高（入口索引） |
| `core/state-templates.md` | 382 字 | 高（hook 注入文本） |

`core/backend/*.md` 和 `core/frontend/*.md` 的子文件留到下一期翻译。

## Scope

### 代码改动

1. **翻译 3 个 core spec 文件**（root + template 同步）：
   - `core/backend/index.md` → 全英文
   - `core/frontend/index.md` → 全英文
   - `core/state-templates.md` → 全英文

2. **`quick-start.md` 更新**：
   - 添加"English is the authoritative language for spec"说明。

### Non-Goals

- 不翻译 `core/backend/*.md` 和 `core/frontend/*.md` 子文件（下一期）。
- 不翻译 `reference/guides/*.md`（下一期）。
- 不改动 `AGENTS.md` / `workflow.md`（保留中文摘要）。

## Acceptance Criteria

1. 3 个 core spec 文件内容为全英文。
2. root ↔ template 一致性。
3. `python -m pytest tests/test_no_legacy_template_paths.py -v` 通过（无新失败）。

## Verification

- `python -m pytest tests/test_no_legacy_template_paths.py -v`
- 人工检查翻译质量
