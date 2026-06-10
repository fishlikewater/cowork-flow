---
description: Run Party Mode V2 as a runtime-controlled advisory board discussion.
---

Party Mode V2 is advisory only. It does not satisfy formal Implement or Check.

Use the runtime controller as the source of truth:

```bash
./.cowork-flow/run party-v2 init
./.cowork-flow/run party-v2 monitor
./.cowork-flow/run party-v2 view
./.cowork-flow/run party-v2 post
./.cowork-flow/run party-v2 respond
./.cowork-flow/run party-v2 advance
./.cowork-flow/run party-v2 finalize
```

Follow runtime `next_actions` with the active OpenCode host adapter. Do not
forward, summarize, or rewrite child opinions. Child agents communicate through
the current-round board API.
