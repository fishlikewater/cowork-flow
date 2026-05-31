# SkillOpt Entry-Boundary Pilot

## 使用方式

SkillOpt 本身要求 Python 3.10+、benchmark split 目录和模型凭据。当前环境已完成：

- `/tmp/SkillOpt` clone
- `/tmp/skillopt-venv` 安装 SkillOpt
- `/tmp/SkillOpt/scripts/train.py --help` 可运行

当前 Codex 配置可以转成 SkillOpt 的 OpenAI-compatible 配置：

- Codex provider：`asxs_codex_api___mac`
- Endpoint：`https://api.asxs.top/v1`
- Model：`gpt-5.5`
- Reasoning effort：`xhigh`
- API key 来源：`~/.codex/auth.json` 的 `OPENAI_API_KEY`

已新增两个不含明文密钥的配置文件：

- `skillopt/codex-current.env`：source 时从当前 Codex 配置和 auth 文件导出 SkillOpt 环境变量。
- `skillopt/codex-current.yaml`：SkillOpt 模型配置，使用当前 Codex endpoint/model/reasoning。

已在 `/tmp/SkillOpt` 同步写入便捷副本：

- `/tmp/SkillOpt/.env.codex-current`
- `/tmp/SkillOpt/configs/cowork-flow/codex-current.yaml`

烟测结果：source `codex-current.env` 后，SkillOpt `chat_optimizer` 使用 `gpt-5.5` 和 `https://api.asxs.top/v1` 返回预期 `OK`，且确认 API key 未写入上述配置文件。

## Pilot 数据集

训练/验证/测试样例围绕 `entry-boundary` 的真实失败面设计：

| split | case | prompt signal | expected |
| --- | --- | --- | --- |
| train | hard envelope | `COWORK_DISPATCH_V1` + ACK-only output | `DELEGATED_SUBTASK` |
| train | structured Chinese delegate | `任务：` / `约束：不要编辑` / `输出：` | `DELEGATED_SUBTASK` |
| train | advisory no marker | first sentence says bounded delegated task, then asks for analysis only | `DELEGATED_SUBTASK` |
| val | bootstrap after delegate | delegated task followed by AGENTS/workflow text | `DELEGATED_SUBTASK` |
| val | user main request | "继续执行开发计划" / repository change request | `MAIN_SESSION` |
| val | ambiguous short reply | "可以" without recoverable task context | `UNCERTAIN` or parent-context route |
| test | review-only request | concrete file/review target + no edits + findings output | `DELEGATED_SUBTASK` |
| test | full repo work | direct user asks to implement and verify | `MAIN_SESSION` |

## Adopted optimization target

The skill should make the first-screen decision explicit:

1. Find the current task message first.
2. Ignore bootstrap text as task source.
3. Treat project rules as execution constraints after classification.
4. Do not require a hard marker when task/scope/output are present.
5. Keep advisory/default subagent guidance as a natural-language boundary, not a runtime protocol.

## Optimization Run

See `research/skillopt-run-2026-05-31.md`.

Outcome: SkillOpt validated the current `entry-boundary` skill at 100% on train, validation, and held-out pilot examples. It proposed one benchmark-wrapper-specific patch, but the validation gate rejected it because it did not improve the score. No generated patch was migrated into production skill text.
