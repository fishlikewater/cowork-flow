# Spec Section Validator — Implementation Plan

## Goal
Add `spec_validator.py` utility with TDD + doubt-review + simplification review.

## Tasks

### Task 1: Implement validate_sections()
- File: `template/.cowork-flow/scripts/common/gates/spec_validator.py`
- Implement `validate_sections(file_path, spec_type)` function
- Lines: < 50 (avoid COMPLEX-FUNC-001)

### Task 2: Unit tests
- File: `tests/test_spec_validator.py`
- 4 tests covering AC-001..AC-004

## Verification
```bash
PYTHONPATH=template/.cowork-flow/scripts python3 -m pytest tests/test_spec_validator.py -v
```
