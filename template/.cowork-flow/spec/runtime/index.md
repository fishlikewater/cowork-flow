# Runtime Specifications

Machine-readable contract files consumed directly by runtime scripts.

| File | Consumer | Purpose |
|------|----------|---------|
| [rules.json](rules.json) | `common/gates.py`, `common/validate_rules.py` | Lifecycle quality gates and agent behavior rules |
| [contract-registry.json](../registry.json) | `common/contract_check.py` | Contract paths and readWhen triggers |
| [schemas/rules.schema.json](../schemas/rules.schema.json) | `common/validate_rules.py` | Rules JSON format validation |

## How to add a rule

1. Add entry to `rules.json` with unique `R-XXX-NNN` ID
2. Set `enforcement` to the handler module
3. Implement the check in the corresponding handler (validate_rules / validate_implementation)
4. Run `python -m pytest tests/test_rules_engine.py`
