# Dashboard UX Chinese UI Spec

## Contract

- Dashboard is a read-only inspection surface. It may call `GET` APIs only and must not add lifecycle mutation controls.
- Root and template dashboard static files must remain synchronized.
- User-facing dashboard text should be Simplified Chinese.
- Archived tasks should be available but visually secondary to active workflow states.
- Selecting a task should make details visible without requiring the user to discover a page-bottom panel on narrow screens.

## Detail Surface

The task detail view should show:

- task id and artifact directory,
- status, pattern, priority, assignee,
- children count and child rows when present,
- audit trail entries with status transition, operator, reason, and timestamp,
- agent run rows when present,
- active block state when present.

## Responsive Behavior

- Desktop keeps the board and inspector visible together.
- Narrow screens use a compact board/list and a visible detail drawer or panel.
- Empty states should be compact and should not reserve the same vertical weight as populated columns.
