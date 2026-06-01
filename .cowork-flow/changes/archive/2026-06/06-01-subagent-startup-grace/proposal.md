# 06-01-subagent-startup-grace

## Problem

Subagents can ACK the dispatch, receive `EXECUTE`, and then spend time reading AGENTS.md, workflow docs, task context, and related specs. During that post-ACK execution window, the main session may see no visible reply or no runtime marker file and incorrectly decide the child is stuck.

## Proposed Behavior

Main-session coordination treats post-ACK execution silence as inconclusive. After `EXECUTE`, a missing reply or missing compass/status file is not enough to close a fixed `cowork-*` subagent.

The main session should keep waiting through a bounded per-dispatch post-ACK execution grace period, then retry or close only when there is clear evidence for that child:

- wrong `dispatch_id` or mismatched ACK;
- child completed;
- user cancelled the work;

The grace duration defaults to `300000` ms and can be overridden with `codex.post_ack_execution_grace_ms` in `.cowork-flow/config.yaml`. Each child gets its own deadline: `deadline[dispatch_id] = execute_sent_at[dispatch_id] + codex.post_ack_execution_grace_ms`. Do not use a shared/global deadline across children.

Grace expiration for one `dispatch_id` is only a review checkpoint for that child. If the child has written progress, compass, or status files, or still appears running, the main session continues waiting instead of closing it; other children keep their own deadlines.

## Non-Goals

- No new runtime state machine.
- No new outbox or ledger.
- No revival of old agent-team behavior.
