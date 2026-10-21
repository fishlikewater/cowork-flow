# Testing Checklist

> Quick reference for test quality. Load on demand when reviewing test files, writing test cases, or checking behavior coverage.

## Test structure

- Test names describe behavior: `test_<unit>_<scenario>_<expected>`
- AAA layout (visual separation between Arrange/Act/Assert)
- One test verifies one behavior
- Assert behavior contracts, not implementation details
- Mocks verify behavior calls, not call counts

## Depth

- Not a test that passes via `assert True`
- Not a test that only checks whether a function exists
- Not a test that uses `unittest.mock` call counts instead of behavior verification
- Not a test that snapshots an empty structure (`assert result == {}`)
- Does not depend on test execution order
- Does not skip necessary setup/teardown
- Asserts exact values or behavior contracts, not truthy/falsy
- Has at least one test for the error path

## Anti-patterns

| Anti-pattern | Problem | Alternative |
|---|---|---|
| Hard-coding expected values to implementation output | Test couples to implementation; it fails when implementation changes but behavior does not | Verify the behavior contract: input -> expected output |
| Mocking internal calls of the function under test | Tests implementation instead of behavior | Keep mocks at boundaries (API/filesystem/time) |
| Packing unrelated behaviors into one test | A failure does not reveal what broke | One test per behavior, with a descriptive name |
| Asserting `assert True` | Always passes | Use semantic assertions (assertEqual/assertGreater, etc.) |
| Only checking that a function exists (`assert module.func`) | Does not verify behavior | Call the function and verify output or exceptions |
| Not cleaning up global state / fixtures | Cross-test pollution causes order dependence | Clean up in setup/teardown |

## Scope

- The changed function/module has a direct unit test
- Downstream dependencies have integration tests
- Boundary conditions (empty/extreme values/concurrency) have at least one test

## See also

- `spec/backend/quality-guidelines.md` — backend testing rules
- `skills/test-first/SKILL.md` — full TDD workflow
- `references/security-checklist.md` — security boundary checks in tests
