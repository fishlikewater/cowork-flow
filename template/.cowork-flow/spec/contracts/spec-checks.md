# Spec Check 契约（规范挂命令）

## 它做什么

用户规范（`.cowork-flow/spec/` 下 `backend/`、`frontend/`、自建目录）可通过 frontmatter 的
`checks:` 声明检查命令。机制只执行声明、不解析规范正文——规则变化 = 用户改同一个文件里的命令，天然同步。

## 什么时候挂

条款能用命令退出码判定时（lint / 测试 / 类型检查 / schema 校验）就值得挂 `checks:`。两条硬约束：

- **声明的命令不存在 = `unchecked` = 阻断 `complete`**：挂之前先确认命令在当前仓库能跑通。
- **edit-only 不是门禁**：`when: edit` 只是编辑期 best-effort 提示——Bash 直写绕过 PostToolUse、无编辑期快跑能力的宿主（见附录 A）都收不到这层反馈，收口期也不补跑；需要硬门禁的检查必须声明 `when: lifecycle` 或默认 `both`。

## 语法

```markdown
---
checks:
  - cmd: npm run lint --silent
    files: "src/"          # 可选：适用范围，目录前缀或扩展名（"*.ts"），逗号分隔
    timeout: 60            # 可选：秒，默认 30，硬顶 120
    when: both             # 可选：edit | lifecycle | both（默认 both）
    cmd.win: npm run lint  # 可选：Windows 覆盖命令
---

# 规范正文（机制不读）
```

- `files` 只支持两种形式：目录前缀（`src/`，以 `/` 结尾或自动补齐）与扩展名（`*.ts`）。完整 glob 形态（`**`、`[]`）解析为错误、声明不执行、doctor 报告——绝不回退为"匹配一切"；多值（`files: "src/", "lib/"`）每个 token 按同一引号规则去引号后生效。
- 引号规则：仅值整体为单对引号时去引号；`"python" -c "..."` 这类含多对引号的命令值原样保留，由执行器按 shell 规则拆分。
- `when: edit` 在编辑期（PostToolUse）对命中 `files` 的改动文件就地执行，超时被钳制到 2.5 秒（为解释器启动与 cmd 包装留 spawn 预算）；慢命令请声明 `when: lifecycle`。
- **文件必须 UTF-8 无 BOM**：BOM 开头的 frontmatter 会被解析器静默忽略（声明数 0、无解析错误）——声明无声失效。挂完声明请跑一次 `spec-check` 确认被解析。

## 三态与门禁

| 状态 | 含义 | complete 门禁 |
| --- | --- | --- |
| `pass` | 退出码 0 | 通过 |
| `violation` | 退出码非 0 | **阻断**（状态不推进） |
| `unchecked` | 命令不存在/解释器缺失/超时 | **阻断**；显式 `--allow-unchecked` 可放行，豁免留痕进 task.json `meta.specCheckExempt` |

unchecked 永不冒充 pass（"没跑成"不是"通过"）；frontmatter 畸形视该 spec 为无检查并进 doctor 报告，不炸流程。解析失败是独立于三态之外的信号：`files` 形态非法等声明解析错误归入 `parseErrors`，不折进 `pass`/`unchecked`，退出码与 `unchecked` 同为 2。文本模式与 `--json` 必须使用同一退出码，且文本模式必须打印解析错误行（`spec-check: N parse error(s): <spec>: <error>`）——只打印 `0 passed, 0 violations, 0 unchecked` 会让畸形声明看起来像干净通过。

退出码契约：`0` 全部 pass；`1` 存在 violation；`2` 存在 unchecked 或 `parseErrors`。`--allow-unchecked` 只豁免 unchecked 的阻断，不豁免解析错误。

**零声明是合法状态，但必须显式可见**：仓库无任何生效声明时退出码为 `0`，文本模式输出独立事实行 `spec-check: no checks declared (<N> spec files scanned)`，与"有声明且全过"的 `spec-check: <n> passed, 0 violations, 0 unchecked` 可区分；`--json` 顶层含 `specFiles`、summary 含 `declarations`。零声明 ≠ 干净通过——它意味着规范链上当前没有可机检约束，是需要被看见的事实，而不是可冒充通过的绿色。

## 时机与输出

- **编辑期**（PostToolUse）：仅 `when: edit`/`both` 且改动命中 `files` 时执行，违规输出单行 `spec-check[<spec>] violation: <首个违规行>`；执行器缺失或超时静默，绝不阻断编辑流。宿主差异与节流细节见附录 A。
- **收口期**（task complete）：全量执行，结果进 `meta.specCheckSummary` 遥测；阻断消息只列未过项摘要。
- **手动查询**：`./.cowork-flow/run spec-check [--file <path>] [--json] [--verbose]`（退出码见上）。

## 声明归使用方维护

- **模板不预置声明**：模板自带的 spec 文件不含生效的 `checks:` 声明——模板无法预知项目命令，而命令缺失会归 `unchecked` 并阻断 `complete`。请把声明写进自建 spec 文件（如 `spec/team-xxx.md` 或自建子目录），sync 不触碰，声明随规范正文一起由使用方维护。
- **sync 保护前缀与具名例外**：`spec/` 整体是 sync 保护前缀，已存在的 spec 文件不会被 `sync` 覆盖（模板里 spec 的更新只对 `init` 新装生效）；唯一具名例外是 `spec/contracts/` 下列入 `spec/runtime/host-assets.json` `syncPolicy.safeFiles` 的条目（本文件与 `workflow-state-templates.md`），它们随 sync 更新，使契约修正能到达已安装项目。
- **识别并挂声明是主会话 AI 的职责**：声明归项目所有。review / 规范维护时，主会话 AI 负责识别可机检条款并补 `checks:` 声明（条款正文不擅自改——发现条款与实现冲突时按 review 流程提出，由用户决策）；仅主会话写入 spec，delegated 子代理只上报候选、不越 scope。完整职责见 `task-review` 与 `spec-sync` Skill。
- **质量纪律四条**：① 在干净树上跑出 `pass`；② 用一个反例证明该检查确实能报错（不是恒过的装饰）；③ 用 `files` 限定适用范围；④ 挂后跑一次 `spec-check` 确认声明被解析（防 BOM / `files` 形态错误静默失效）；并在 review 报告列出「条款 → 命令」清单。

## 附录 A 宿主能力矩阵

| 宿主 | digest 注入 | 编辑期快跑 | 收口强制 |
| --- | --- | --- | --- |
| zcode | 有（Specs 行 h2 digest） | 有（PostToolUse 短路径；**仅主会话**） | 有 |
| claude-code | 有（Python 单源） | 有（PostToolUse，exit 2 反馈） | 有 |
| codex | 有 | 有（PostToolUse，`apply_patch\|Write\|Edit` → exit 2 stderr） | 有 |
| opencode | 有 | 有（插件 `tool.execute.after` 单行追加到工具结果） | 有 |
| dsh | 有（预设注入） | 有（预设插件 `tools/post-execute` → `additionalContexts`） | 有 |
| kimi-code | 有（UserPromptSubmit hook → `inject.py --host kimi-code`） | 无（未注册 PostToolUse；观察型事件 stdout 被丢弃） | 有 |
| qoder | 有（插件 hook → `inject.py --host qoder`） | 有（`PostToolUse` 非阻断事件，告警走 `additionalContext`、exit 0） | 有 |

zcode / codex / claude-code 经 Python 单源共享 `run_edit_checks`；opencode 在插件内以 CLI 拉取同一执行器（`run spec-check --phase edit --throttled`），dsh 经预设插件的 `tools/post-execute` 调同一 Python 协议，qoder 经插件 hook 的 `PostToolUse` 调同一执行器（该事件在 Qoder 不可阻断，告警以 `additionalContext` 随 exit 0 返回，而非 claude-code/codex 的 stderr + exit 2）——具备编辑期快跑的六家共享同一节流状态与三态语义，不各自实现检查逻辑；kimi-code 只走收口强制与子代理自查。

编辑期节流：同一文件 10 秒内只报一次；节流状态在 `.cowork-flow/.runtime/spec-edit-throttle.json`，检查完整跑过才写节流——执行器崩溃不消费时间窗，重试仍会执行。delegated 子代理会话同样收到 spec 违规反馈（子代理是主力写码者）；scope 警告保持 main-only。zcode 主会话的 hook 身份（对话自身 session id）不会被绑定——激活发生在 Bash 侧显式身份下——显示与编辑期警告按最新主会话兜底；claude/codex 保持严格会话身份（其 Bash env 携带同一 session id）。zcode 经 shim 转发到单源入口（`inject.py`），scope 警告与 spec 警告合并进同一个 additionalContext 载荷；claude 走 exit 2 stderr 反馈。

## 附录 B delegated 编辑期缺口与补偿

**delegated 子代理编辑期缺口（zcode 实测，2026-09-09 两轮）**：ZCode 的插件 hook 只在主会话工具流上派发（事件模型七事件均挂主会话；子代理是独立内部会话流 `sess_subagent_agent_*`），Agent 子代理的 Edit/Write 收不到 `spec-check[...] violation` 行——runtime 绑定与检查逻辑均正常，缺的是宿主派发。补偿机制（subagent-dispatch.md 契约固化）：

1. 子代理完成前自查：`./.cowork-flow/run spec-check` 全量并修复（拉取路径，实测有效）；
2. 父会话验收前再查：violation 视为验收阻塞（反馈时点从收口提前到返回）；
3. 实现类任务 Verify 命令默认含 spec-check 自查；
4. 收口硬门禁兜底不变（violation 阻断 complete）。

治理方向：向宿主提需求扩展子代理工具流的 hook 派发；落地后第 1 条自动退化为冗余保险。

## 附录 C digest 注入

进入 in_progress 后，stage-contract 的 Specs 行升级为 `Specs: <spec>(<h2 标题树>); …`：最多 6 个 h2 条目、每条截断 24 字符、剔除 `();` 字符；文件缺失不加注解。digest 是条目名索引不是正文，受 scope-rules.json `stageContract.budget` 硬顶，超预算整行让位（Scope/Gates 行永不丢）。python/zcode 输出同源于单一 Python 入口，opencode 镜像与它逐字相等由 matrix 用例锁定（`test/stage-contract.test.js` matrix）。

## 附录 D 开放决策

**收口期聚合预算**：收口期全量执行没有聚合预算——声明多且慢的仓库 complete 会线性变慢；是否给收口加并行/预算上限留给后续产品决策，当前保持简单串行。
