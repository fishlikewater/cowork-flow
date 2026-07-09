# Simplification Review

Run when code changes exceed 50 lines or review finds readability issues.

## Pre-Simplification Self-Check (Chesterton's Fence)

For each simplification, answer:
- What is this code's responsibility? Who calls it? What does it call?
- Will existing tests' defined behavior be broken?
- Why did the original author write it this way? (check git blame)

If you cannot answer, stop — you do not understand this code.

## Simplification Signals

| Signal | Action |
|---|---|
| Nesting depth >= 3 levels | Extract guard clause or helper |
| Function > 50 lines | Split by responsibility into multiple named functions |
| Nested ternary `a ? b : c ? d : e` | Replace with if/else / switch / lookup |
| Boolean flag arguments `doThing(true, false, true)` | Replace with options object or split into two functions |
| Same condition checked >= 3 times | Extract as a named predicate function |
| Redundant wrapper `async () => await foo()` | Export foo directly |
| Unused import / variable | Remove (after confirming no side effects) |
| Missing type hint (when project convention requires it) | Add it |

## Naming Readability Signals

| Signal | Action |
|---|---|
| `data`, `result`, `temp`, `val` | Rename to describe content: `userProfile`, `errors` |
| Abbreviations `usr`, `cfg`, `btn`, `evt` | Use full words (`id`, `url`, `api` are exceptions) |
| Name contradicts behavior (`get` but mutates) | Rename to reflect actual behavior |
| "What" comment (`// increment counter` on `count++`) | Remove comment |
| "Why" comment (`// Retry because API is flaky`) | Keep |

## Rule of 500

If a refactoring would modify > 500 lines, use automated tools (sed/codemod/AST transform) rather than manual editing — manual large-scale changes are error-prone and cause review fatigue.

## Red Flags

- Simplification causes test failures (behavior was changed — violates "preserve behavior" principle)
- "Simplification" results in longer and harder-to-read code
- Renaming based on personal preference rather than project convention
- Removing error handling "to make the code cleaner"
- Batching multiple simplifications into one non-rollbackable large commit
