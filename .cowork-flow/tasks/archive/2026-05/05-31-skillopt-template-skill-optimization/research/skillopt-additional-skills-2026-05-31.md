# SkillOpt Additional Skills 2026-05-31

## Scope

After the `entry-boundary` pilot, run SkillOpt against two adjacent template skills:

- `.agent/skills/start/SKILL.md`
- `.agent/skills/writing-plans/SKILL.md`

The goal is to improve the same failure area without making subagent behavior heavy:

- keep delegated-task first-screen routing ahead of project bootstrap;
- clarify when main-session startup should load project state;
- make plan-time parallelism a coordinator decision instead of a user burden.

## Model and Credentials

- Backend: `openai_chat`
- Endpoint: `https://api.asxs.top/v1`
- Model: `gpt-5.5`
- Reasoning effort: `xhigh`
- API key source: `~/.codex/auth.json` at runtime only
- Env bridge: `skillopt/codex-current.env`

No API key is stored in the task files or SkillOpt config files.

## Datasets

Both runs use SearchQA-compatible task-local splits:

- `skillopt-searchqa-split-start`
- `skillopt-searchqa-split-writing-plans`

Each split contains 9 cases across train, validation, and test.

`start` cases cover:

- bounded delegated prompts before bootstrap;
- main-session repository changes that must load workflow state;
- staged routing before and after Load State;
- multi-step implementation routing through plan writing before fixed-agent dispatch;
- advisory/default subagent prompts that rely on natural-language first-screen boundaries.

`writing-plans` cases cover:

- executable scope and acceptance criteria gating;
- serial versus parallel execution decisions;
- low-conflict parallel slices with file ownership and verification;
- worktree parallelism for independent broad changes;
- final integrated verification after parallel work.

## Commands

```bash
source .cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/codex-current.env

/tmp/skillopt-venv/bin/python /tmp/SkillOpt/scripts/train.py \
  --config /opt/projects/cowork-flow/.cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/start.yaml

/tmp/skillopt-venv/bin/python /tmp/SkillOpt/scripts/train.py \
  --config /opt/projects/cowork-flow/.cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/writing-plans.yaml
```

After manually migrating only production-relevant guidance, both adopted skill files were evaluated again:

```bash
/tmp/skillopt-venv/bin/python /tmp/SkillOpt/scripts/eval_only.py \
  --config /opt/projects/cowork-flow/.cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/start.yaml \
  --skill /opt/projects/cowork-flow/.agent/skills/start/SKILL.md \
  --split all \
  --out_root /tmp/SkillOpt/outputs/cowork-flow-start-eval-adopted

/tmp/skillopt-venv/bin/python /tmp/SkillOpt/scripts/eval_only.py \
  --config /opt/projects/cowork-flow/.cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/writing-plans.yaml \
  --skill /opt/projects/cowork-flow/.agent/skills/writing-plans/SKILL.md \
  --split all \
  --out_root /tmp/SkillOpt/outputs/cowork-flow-writing-plans-eval-adopted
```

## Results

### start

- Output directory: `/tmp/SkillOpt/outputs/cowork-flow-start`
- Baseline validation hard/soft: `1.0000 / 1.0000`
- Candidate validation hard/soft: `1.0000 / 1.0000`
- Held-out test hard/soft: `1.0000 / 1.0000`
- Gate action: `reject`
- Reason: baseline already scored `1.0000`; candidate did not improve measured score.
- Token usage: `15` calls, `27,634` tokens
- Adopted eval output: `/tmp/SkillOpt/outputs/cowork-flow-start-eval-adopted`
- Adopted eval hard/soft: `1.0000 / 1.0000` on all 9 cases

### writing-plans

- Output directory: `/tmp/SkillOpt/outputs/cowork-flow-writing-plans`
- Baseline validation hard/soft: `1.0000 / 1.0000`
- Candidate validation hard/soft: `1.0000 / 1.0000`
- Held-out test hard/soft: `1.0000 / 1.0000`
- Gate action: `reject`
- Reason: baseline already scored `1.0000`; candidate did not improve measured score.
- Token usage: `15` calls, `22,653` tokens
- Adopted eval output: `/tmp/SkillOpt/outputs/cowork-flow-writing-plans-eval-adopted`
- Adopted eval hard/soft: `1.0000 / 1.0000` on all 9 cases

## Candidate Review and Migration

SkillOpt rejected both candidates at the gate because the current skills already passed the benchmark. The generated candidates still contained production-relevant wording, so only concise, generalizable guidance was migrated:

- `start`: route in stages; before loading project state, bounded delegated prompts and question-only work can bypass Load State; repository-changing main-session work still loads state first.
- `start`: default/advisory subagent prompts should use a natural-language first-screen boundary rather than relying on bootstrap inference.
- `writing-plans`: confirm executable scope, acceptance criteria, and intended behavior before writing a plan.
- `writing-plans`: make execution strategy explicit; use serial work for shared files or behavior chains, parallel slices only when ownership and verification are clean, and worktrees for broad independent changes.

The migration was applied to both root and template copies and covered by regression assertions in `tests/test_workflow_parallel_sessions.py`.
