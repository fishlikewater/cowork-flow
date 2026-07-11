# P3 文档与新用户闭环体验重构

## Goal

把 README、workflow/spec 和技能文档调整为围绕真实最小闭环与维护者状态模型展开，让新用户能快速跑通，维护者能准确理解状态权威和宿主适配边界。

## Scope

- README 入口页重构。
- 增加或整理 quickstart、maintainer guide、runtime contract、adapter guide。
- 增加最小闭环 demo 和状态流转图。
- 同步 `.agents/skills`、`.claude/skills`、template 文档。
- 校验文档命令真实存在。

## Non-Goals

- 不修改 runtime 行为。
- 不承诺尚未实现的命令或自动化。
- 不把 Party Mode 重新写入主 workflow。

## Acceptance Criteria

1. README 能在前几段说明项目定位、适用/不适用场景和 5 分钟最小闭环入口。
2. 文档包含真实命令的最小闭环 demo。
3. 维护者文档包含 change/plan/task/runtime_session/runtime_context/journal/archive 的关系图。
4. 文档不再引用旧文件态作为当前运行时权威。
5. root/template 文档与 skills 同步。
6. 文档 smoke check 和 sync/package 测试通过。

## Relevant Files

- `README.md`
- `.cowork-flow/workflow.md`
- `.cowork-flow/spec/core/entry.md`
- `.cowork-flow/spec/core/dispatch.md`
- `.cowork-flow/spec/core/lifecycle.md`
- `.cowork-flow/spec/reference/adapters/`
- `.agents/skills/start/SKILL.md`
- `.agents/skills/writing-plans/SKILL.md`
- `.agents/skills/finish-work/SKILL.md`
- `template/`

## Verification

- `npm test -- test/sync.test.js test/package.test.js`
- `.cowork-flow/run.cmd task --help`
- `.cowork-flow/run.cmd change --help`
- `.cowork-flow/run.cmd subagent --help`
- `.cowork-flow/run.cmd flow migrate --help`
- `.cowork-flow/run.cmd doctor --release-health`
- `git diff --check`