# 更新 README 当前流程说明

## 目标

让 `README.md` 的常用入口、任务状态推进和当前实际 cowork-flow 流程保持一致，并补充状态流转图。

## 范围

- 更新 `README.md` 中 `task next`、任务阶段命令、固定代理与 hook 的说明。
- 添加 Mermaid 状态流转图。

## 非目标

- 不修改 runtime、脚本、模板行为或规格合同。
- 不重写完整 README 结构。

## 验收标准

- README 明确说明 `task next` 只读，不推进状态。
- README 覆盖 `task create/start/review/complete/archive/finish` 的实际状态关系。
- README 包含可读的状态流转图。
- 文档改动通过 diff whitespace 检查。

## 相关文件

- `README.md`

## 验证方式

- `git diff --check`
