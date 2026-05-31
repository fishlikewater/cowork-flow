# SkillOpt Run 2026-05-31

## Command

```bash
source .cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/codex-current.env
/tmp/skillopt-venv/bin/python /tmp/SkillOpt/scripts/train.py \
  --config /opt/projects/cowork-flow/.cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt/codex-current.yaml
```

## Model

- Backend: `openai_chat`
- Endpoint: `https://api.asxs.top/v1`
- Model: `gpt-5.5`
- Reasoning effort: `xhigh`
- API key source: `~/.codex/auth.json` at runtime only

## Dataset

- Adapter: `searchqa`
- Train: 3 cases
- Validation: 3 cases
- Held-out test: 2 cases
- Data path: `.cowork-flow/tasks/archive/2026-05/05-31-skillopt-template-skill-optimization/skillopt-searchqa-split`

## Result

- Baseline validation hard/soft: `1.0000 / 1.0000`
- Train rollout hard/soft: `1.0000 / 1.0000`
- Candidate validation hard/soft: `1.0000 / 1.0000`
- Gate action: `reject`
- Best skill step: `0`
- Held-out test hard/soft: `1.0000 / 1.0000`
- Total calls/tokens: `14` calls, `27,321` tokens
- Output directory: `/tmp/SkillOpt/outputs/cowork-flow-entry-boundary`

## Candidate Patch Review

SkillOpt proposed one success-derived edit:

> Add a rule for meta-classification questions containing a `Candidate prompt:` block and allowed labels, so the agent returns only `MAIN_SESSION`, `DELEGATED_SUBTASK`, or `UNCERTAIN`.

Decision: do not migrate.

Reason: the patch is mainly benchmark-wrapper guidance. It does not improve validation score, and adding it would make `entry-boundary` heavier without addressing the real subagent bootstrap drift case. The accepted production skill remains the current hand-optimized text.
