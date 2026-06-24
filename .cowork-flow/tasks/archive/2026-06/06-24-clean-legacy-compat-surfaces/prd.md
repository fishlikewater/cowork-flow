# 清理旧兼容入口和文案

## 目标

删除仍可删除的旧兼容入口，修正旧 runtime prompt 语义和测试命名噪音，让活跃文档、脚本和测试更贴近 runtime-context 架构。

## 范围

- 移除 `--platform both` 兼容别名和 README 说明。
- 移除 `update --global --yes` 旧参数兼容。
- 移除 `task archive --no-commit` 与 `add-session --no-commit` deprecated no-op。
- 将 `task next` 的 delegated prompt 文案改为 runtime-context 语义。
- 将 “legacy records” 文案改成 “existing records”。
- 更新相关测试命名和断言。
- 同步 root 与 `template/` 镜像文件。

## 非目标

- 不重命名 `delegated_subtask` 状态。
- 不移除当前 runtime-context fail-closed、contract digest fallback 或 adapter capability fallback。
- 不清理历史 archive、plans、workspace journal。

## 验收标准

- AC-001: `--platform both` 不再是有效平台选择，文档不再推荐或描述它。
- AC-002: `cowork-flow update --global --yes` 不再被接受。
- AC-003: `task archive --no-commit` 与 `add-session --no-commit` 不再是可用参数。
- AC-004: `task next` no-task 输出不再使用旧 delegated prompt 语义。
- AC-005: root/template 文件保持一致，相关 focused tests 和全量验证通过。
