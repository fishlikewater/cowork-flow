# Schemas

JSON Schemas for validating machine-readable spec files.

| File | Validates | Used by |
|------|-----------|---------|
| [rules.schema.json](rules.schema.json) | `spec/runtime/rules.json` | `common/validate_rules.py` self-check |
| [adapter.schema.json](../reference/adapters/adapter.schema.json) | `adapters/*/adapter.yaml` | `doctor.py` |
