# Spec Check 契约（规范挂命令）

用户规范（`.cowork-flow/spec/` 下 `backend/`、`frontend/`、自建目录）可通过
frontmatter 的 `checks:` 声明检查命令。机制只执行声明、不解析规范正文——
规则变化 = 用户改同一个文件里的命令，天然同步。

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

- `files` 只支持两种形式：目录前缀（`src/`，以 `/` 结尾或自动补齐）与
  扩展名（`*.ts`）。完整 glob 形态（`**`、`[]`）解析为错误，声明不执行，
  doctor 报告——绝不回退为"匹配一切"。多值形态（如 `files: "src/", "lib/"`）
  每个 token 按同样的引号规则去引号后生效。
- `when: edit` 的声明在编辑期（PostToolUse）对命中 `files` 的改动文件
  就地执行，超时被钳制到 2.5 秒（为解释器启动与 cmd 包装留 spawn 预算）；
  慢命令请声明 `when: lifecycle`。
- 引号规则：仅值整体为单对引号时去引号；`"python" -c "..."`
  这类含多对引号的命令值原样保留，由执行器按 shell 规则拆分。

## 三态结果（完成门禁语义）

| 状态 | 含义 | complete 门禁 |
| --- | --- | --- |
| `pass` | 退出码 0 | 通过 |
| `violation` | 退出码非 0 | **阻断**（状态不推进） |
| `unchecked` | 命令不存在/解释器缺失/超时 | **阻断**；显式 `--allow-unchecked` 可放行，豁免留痕进 task.json `meta.specCheckExempt` |

unchecked 永不冒充 pass（"没跑成"不是"通过"）。frontmatter 畸形视该
spec 为无检查并进 doctor 报告，不炸流程。

## 时机与单行输出

- **编辑期**（zcode/claude）：违规输出单行
  `spec-check[<spec>] violation: <首个违规行>`；同一文件 10 秒内只报一次
  （节流状态在 `.cowork-flow/.runtime/spec-edit-throttle.json`，检查完整
  跑过才写节流——执行器崩溃不消费时间窗，重试仍会执行）；执行器
  缺失或超时静默，绝不阻断编辑流。delegated 子代理会话同样收到 spec
  违规反馈（子代理是主力写码者）；scope 警告保持 main-only。zcode 主
  会话的 hook 身份（对话自身 session id）不会被绑定——激活发生在 Bash
  侧显式身份下——显示与编辑期警告按最新主会话兜底；claude/codex 保持
  严格会话身份（其 Bash env 携带同一 session id）。zcode 经
  shim 转发到单源入口（`inject.py`），scope 警告与 spec 警告合并进同一个
  additionalContext 载荷；claude 走 exit 2 stderr 反馈。
- **收口期**（task complete）：全量执行，结果进 `meta.specCheckSummary`
  遥测；阻断消息只列未过项摘要。
- 手动查询：`./.cowork-flow/run spec-check [--file <path>] [--json]
  [--verbose]`。
- **edit-only 是 best-effort 提示，不是门禁**：Bash 直写绕过 PostToolUse
  不会触发编辑期反馈；无编辑期快跑能力的宿主（见能力矩阵）同样没有
  这层提示，且收口期不会对 `when: edit` 声明补跑。需要硬门禁的检查
  必须声明 `when: lifecycle` 或默认 `both`。
- **开放决策**：收口期全量执行没有聚合预算——声明多且慢的仓库 complete
  会线性变慢；是否给收口加并行/预算上限留给后续产品决策，当前保持
  简单串行。

## 归属与 sync 策略

- **模板自带 spec**（`spec/backend/` 等随包分发）的 check 声明由
  cowork-flow 上游维护，属 sync safe 资产——本地修改会被 sync 覆盖。
- **用户自定义规范**请放自建 spec 文件（如 `spec/team-xxx.md` 或自建
  子目录），sync 不触碰；check 声明随规范正文一起由用户维护。

## 宿主能力矩阵

| 宿主 | digest 注入 | 编辑期快跑 | 收口强制 |
| --- | --- | --- | --- |
| zcode | 有（Specs 行 h2 digest） | 有（PostToolUse 短路径） | 有 |
| claude-code | 有（Python 单源） | 有（PostToolUse，exit 2 反馈） | 有 |
| opencode | 有 | **降级：无**（插件无 PostToolUse 短路径） | 有 |

## digest 注入

进入 in_progress 后，stage-contract 的 Specs 行升级为
`Specs: <spec>(<h2 标题树>); …`：最多 6 个 h2 条目、每条截断 24 字符、剔除
`();` 字符；文件缺失不加注解。digest 是条目名索引不是正文，受
scope-rules.json `stageContract.budget` 硬顶，超预算整行让位
（Scope/Gates 行永不丢）。python/zcode 输出同源于单一 Python 入口，
opencode 镜像与它逐字相等由 matrix 用例锁定
（`test/stage-contract.test.js` matrix）。
