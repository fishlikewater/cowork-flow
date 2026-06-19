# 2026-06-18 formal subagent result timing probe

1. Prepare task context and start the planning task.
   Verification: `task current` points at `06-18-formal-subagent-result-timing-probe`.

2. Dispatch a minimal fast `cowork-implement` child that binds, writes a marker,
   and returns a short final string.
   Verification: runtime status, marker file, and parent wait result all align.

3. If the fast probe does not return cleanly, dispatch a deliberate slow child to
   separate timeout sensitivity from return-channel failure.
   Verification: start/end markers and final wait result provide a clear verdict.

4. Close probe runtimes and summarize the evidence.
   Verification: runtime statuses are no longer left hanging without explanation.
