# P1 建立 root/template 同步强门禁

## Goal

把 root/template 漂移转化为可测试、可阻断、可解释的同步门禁，降低模板分发时遗漏 root 改动的风险。

## Scope

- 建立应同步清单和允许差异清单。
- 增强 `test/sync.test.js`、`scripts/pack-check.js` 或等价检查入口。
- 覆盖 `.cowork-flow/scripts`、`.cowork-flow/spec`、skills、agents、host assets 和 package files 边界。
- 明确排除 archive、runtime 本地状态、pycache、生成文件。

## Non-Goals

- 不改变模板复制语义，除非 sync gate 证明现有复制边界错误。
- 不批量重写所有文档。
- 不处理与 root/template 无关的 lint 或格式问题。

## Acceptance Criteria

1. sync gate 能报告应同步文件的具体漂移路径。
2. 允许差异清单可被测试读取，并说明每类差异原因。
3. root/template 核心 runtime、spec、skills、host assets 的同步关系被覆盖。
4. runtime 本地状态、archive、pycache、包排除项不会误报。
5. `npm run test:template` 和 `npm run pack:check` 通过。

## Relevant Files

- `test/sync.test.js`
- `scripts/pack-check.js`
- `src/lib/copy-template.js`
- `.cowork-flow/spec/registry.json`
- `.cowork-flow/scripts/`
- `template/.cowork-flow/scripts/`
- `.agents/skills/`
- `template/.agents/skills/`

## Verification

- `npm test -- test/sync.test.js`
- `npm run test:template`
- `npm run pack:check`
- `git diff --check`