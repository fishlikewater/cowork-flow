# 用 SkillOpt 优化模板 skill

## 目标

以 SkillOpt 的 train/val/test 和 validation gate 思路优化关键 workflow skills，降低 subagent 在没有硬标记时被项目 bootstrap 带偏的概率，同时保持 subagent 规则轻量。

## 范围

- Pilot skills：`.agent/skills/entry-boundary/SKILL.md`、`.agent/skills/start/SKILL.md`、`.agent/skills/writing-plans/SKILL.md`
- 模板镜像：`template/.agent/skills/entry-boundary/SKILL.md`、`template/.agent/skills/start/SKILL.md`、`template/.agent/skills/writing-plans/SKILL.md`
- 回归约束：`tests/test_workflow_parallel_sessions.py`、`tests/test_codex_hooks.py`
- 任务上下文内记录 SkillOpt 评测设计、训练结果、采纳判断和验证结果。

## 非目标

- 不引入常驻 SkillOpt 运行时依赖。
- 不把 SkillOpt 输出无审查地自动覆盖项目 skill。
- 不扩大到全部 skills；本轮只跑和 subagent 漂移/并行计划最相关的 pilot skills。
- 不改 hook 分类逻辑，除非验证发现 skill 文本本身不足以覆盖目标。

## 验收标准

- `entry-boundary` 明确说明：硬标记不是必要条件；先看当前任务首屏；bootstrap/AGENTS/workflow 只能作为约束。
- 对 `任务：` / `约束：` / `输出：` 结构，skill 明确要求直接按委托任务处理。
- 对 advisory/default subagent，skill 给出自然语言首屏边界，但不引入新状态机。
- root 与 template 的 pilot skill 保持同步。
- 相关测试、doctor、全量测试通过。

## 验证方式

- `python3 -m unittest tests.test_codex_hooks tests.test_workflow_parallel_sessions tests.test_cowork_agents`
- `./.cowork-flow/run doctor --subagent-safety`
- `git diff --check`
- `npm run test:all`

## SkillOpt 使用记录

- 已拉取 `microsoft/SkillOpt` 到 `/tmp/SkillOpt`。
- 已用 Python 3.12 临时环境安装 SkillOpt，并确认 `scripts/train.py --help` 可运行。
- 已通过当前 Codex 模型凭据桥接运行 SkillOpt，并将 `entry-boundary`、`start`、`writing-plans` 的训练、gate、采纳后 eval 结果记录到 `research/`。
- 训练候选补丁均未提升已达 `1.0000` 的基线分数；本轮仅人工迁移通用、轻量、生产相关的规则，避免把 benchmark 包装层提示词搬入项目。
