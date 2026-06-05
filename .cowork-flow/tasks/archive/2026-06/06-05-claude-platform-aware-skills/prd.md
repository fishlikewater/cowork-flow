# Claude-only 平台感知技能路径

## 目标

- Claude Code-only 初始化和同步不再复制 `.agent/skills/`。
- Codex、OpenCode、all / multi-platform 仍支持 `.agent/skills/`。
- `task init-context` 根据已安装平台选择技能上下文路径：Claude-only 使用 `.claude/skills/`，其他场景使用 `.agent/skills/`。

## 范围

- 修改 CLI 平台过滤与同步行为。
- 修改 `task init-context` 的默认技能上下文路径生成。
- 更新相关测试和 README 文案。

## 非目标

- 不改历史 archive task 内已有 JSONL。
- 不删除模板中的 `.agent/skills/`。
- 不改变 Claude `.claude/skills/` 内容。

## 验收标准

- `init --platform claude-code` 不创建 `.agent/skills/`。
- `sync` 在 Claude-only 项目缺失 `.agent/skills/` 时不创建它。
- Codex-only、OpenCode-only 和 multi-platform 仍包含 `.agent/skills/`。
- Claude-only 项目运行 `task init-context` 生成 `.claude/skills/...`。
- 现有测试通过。
