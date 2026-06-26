# Phase 6 Coding Standard Gate

## Goal

Turn UTF-8/no-BOM and explicit text encoding rules into machine-checked lifecycle evidence.

## Files

- `.cowork-flow/scripts/common/coding_standards.py`
- `template/.cowork-flow/scripts/common/coding_standards.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_coding_standards.py`

## Acceptance Criteria

- Scanner detects BOM bytes in changed text files and workflow scripts.
- Scanner detects Python text IO calls missing explicit UTF-8 encoding for text operations.
- Scanner result can be embedded into `quality.json`.
- Completion gate rejects failed coding-standard evidence.
- Tests cover BOM and missing-encoding regressions.

## Verification

Run:

```bash
rtk python -m pytest tests/test_coding_standards.py tests/test_quality_gate.py -q
rtk git diff --check
```
