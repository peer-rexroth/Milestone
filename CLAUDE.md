# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Overview

dbPlanner is a single-file, zero-dependency HTML application — the entire app (HTML, CSS, JavaScript) lives in `dbplanner.html`. There is no build step and no package manager. It's a local-first project planner: a single Gantt chart with a work-breakdown hierarchy (parent/summary tasks roll up dates and progress from their children), predecessor/successor dependencies (Finish-to-Start/Start-to-Start/Finish-to-Finish/Start-to-Finish with lag), auto-scheduling (moving a task forward cascades to its dependents), and a critical-path view. It's also an installable PWA (manifest, service worker, icons), and shares the same data-durability feature set as this author's other single-file apps (Pulse, mytasks): JSON export/import, rolling local backups, deletion tombstones with undo, and optional File System Access API file sync.

**Sibling projects**: [Pulse](../Pulse/CLAUDE.md) (a programme dashboard) and mytasks (a task manager) are this same author's other single-file apps — dbPlanner's color scheme system, PWA setup, and data-durability mechanisms are ported from Pulse (see its own CLAUDE.md for the fuller narrative history behind those patterns; dbPlanner's own version below is the same design, freshly built rather than copy-pasted).

## Running it

A plain `file://` open of `dbplanner.html` works for quick checks, but PWA install/offline support requires serving it over http — browsers refuse to register a service worker for `file://` pages. `./start-dbplanner.command` serves the directory on `http://127.0.0.1:8937` and opens it in Chrome/Edge (Safari can't install this kind of PWA on macOS, and the File System Access API sync feature is Chrome/Edge-only regardless of how the page is served). `./stop-dbplanner.command` kills the server.

There is no automated test suite yet (unlike Pulse/mytasks' JXA-based one) — verified so far by driving the app end-to-end in a real headless Chromium via Playwright (add/edit/delete tasks, dependency cascade, drag-to-reschedule cascade, critical path, theme/scheme switching) with a clean console. Add a real test harness if this app's surface grows enough to need one.

## Architecture

The file has three logical sections in order: CSS styles, HTML structure, and a `<script>` block containing all application logic — same convention as Pulse/mytasks.

### Data model

All state lives in `localStorage` under `"dbplanner-v1"`:

```js
{
  version: 1,
  project: { name: '...', updatedAt: 0 },
  tasks: [Task],
  deletedTaskIds: [{id, deletedAt}],
  theme: 'light' | 'dark',
  colorScheme: 'standard' | 'modern' | 'dracula' | 'github' | 'githubdimmed',
  zoom: 'day' | 'week' | 'month'
}
```

`theme`/`colorScheme`/`zoom` are deliberately per-device display preferences — `syncPayload()` (what gets exported, backed up, and written to a linked sync file) omits them, matching Pulse's own "personal preference stays local" convention.

A **task**:
```js
{
  id, name, parentId: null|id, order: Number,
  startDate: 'YYYY-MM-DD', endDate: 'YYYY-MM-DD',   // equal when milestone is true
  progress: 0-100,
  milestone: Boolean,
  color: null | 'blue'|'teal'|'purple'|'amber'|'pink'|'green'|'red'|'grey',  // null = auto (by status)
  notes: String,
  predecessors: [{ id: taskId, type: 'FS'|'SS'|'FF'|'SF', lag: Number }],  // days, can be negative
  collapsed: Boolean,   // hierarchy expand/collapse state
  updatedAt: Number      // Date.now() — last-write-wins timestamp for merge
}
```

**A task with children is a summary/rollup task**: its effective start/end/progress are computed at render time from its descendants (`effectiveDates()`, memoized per render pass) rather than stored — dragging or editing a summary task's own bar isn't supported, only its leaf descendants. `normalizeData()` enforces this both ways: a task that has children has its own `predecessors` forcibly cleared (a summary task can't itself be independently scheduled), and no task can pick a summary task as its predecessor (the predecessor picker in the task modal only lists leaf tasks).

### Scheduling engine

`constraintStart(task)` computes a task's earliest allowed start from its own `predecessors`, per dependency type (FS/SS/FF/SF, each with its own lag). `cascadeSchedule(changedId)` walks forward through the successor graph from `changedId`, pushing a dependent task's dates later whenever its constraint is violated, and continuing on to *its* successors — implemented as a plain worklist/relaxation loop (not a single topological pass), since a diamond-shaped dependency graph can need a downstream task revisited after a second predecessor's own cascade lands. It only ever pushes a task **later**, never pulls one earlier — a task placed manually ahead of its own constraint is left alone (surfaced as a visual warning via the cycle-detection icon's sibling styling, not silently corrected), so a deliberate early placement is never overwritten by an unrelated edit elsewhere in the chain.

`taskCycleSet()` (plain DFS over the predecessor graph, recursion-stack based) finds every task participating in a circular dependency; those tasks are excluded from `cascadeSchedule()`'s traversal entirely and flagged with a warning icon in the grid rather than crashing or looping.

**`applyConstraints(taskId)` vs `cascadeSchedule(taskId)`** — two different call sites need two different things, and using the wrong one silently drops the dependency: `cascadeSchedule()` alone only pushes `taskId`'s *successors*, assuming `taskId`'s own dates just changed by an intentional, already-valid action (a drag). Saving the task modal or drag-linking a new dependency changes `taskId`'s own *predecessor list*, not its dates — `taskId` itself may now violate a constraint nothing has re-checked yet. `applyConstraints()` checks `taskId`'s own constraint first (shifting it if needed) and *then* cascades to successors; `saveTaskFromModal()` and the drag-to-link handler both call `applyConstraints()` for this reason, while the bar-drag handlers call `cascadeSchedule()` directly.

**Critical path** (`computeCriticalPath()`) is a standard forward/backward CPM pass (earliest start/finish, then latest start/finish from the project end, slack = latest − earliest, critical when slack ≤ 0) over leaf tasks only. **Known v1 simplification**: every dependency is treated as Finish-to-Start for this specific slack calculation, regardless of its real type — SS/FF/SF links still drive the actual forward-scheduling cascade above correctly, just not this slack math. Good enough for highlighting the dominant chain; a mixed-type project's critical path may be approximate.

### Task constraints

`CONSTRAINT_TYPES` ports Microsoft Project's 8 primary constraint types (ASAP/ALAP/MSO/MFO/SNET/SNLT/FNET/FNLT), each entry carrying `hasDate`, `basis` (`'start'` or `'finish'` — which of the task's own dates the constraint date binds), and `bound` (`'lower'`, `'upper'`, or `'exact'`). A task stores `constraintType` (default `'ASAP'`) and `constraintDate` (`null` unless `hasDate`).

How each `bound` interacts with the forward-only cascade above is the crux of this port, since dbPlanner has no bidirectional scheduler to fully enforce an upper bound or a true backward ALAP pass:

- **`lower`** (SNET/FNET) and **`exact`** (MSO/MFO) fold directly into `constraintStart(task)` as one more candidate alongside every predecessor's own earliest-start push — whichever candidate is latest wins, the same mechanism that already resolves multiple predecessors against each other. This is why an MSO/SNET date can still end up pushed later than the pin: a predecessor genuinely demanding a later start always wins, exactly like real MS Project's own "meet as many constraints as possible" behavior when a schedule is over-constrained.
- **`exact`** additionally gets pinned immediately in `saveTaskFromModal()` the moment the constraint is set (the task's stored dates are set to the constraint date right then, preserving duration) — this is what makes "Must Start/Finish On" actually *move* a task instead of merely capping it, the one behavior `constraintStart()`'s lower-bound treatment alone wouldn't produce.
- **`upper`** (SNLT/FNLT) is deliberately **not** enforced by the cascade at all — this app's scheduling engine only ever pushes a date later (see `cascadeSchedule()`'s own comment above), so there is no code path that could honor an upper bound without contradicting that rule. Instead, `constraintViolated(task)` checks whether the task's *current* dates still satisfy its constraint (exact: date must match exactly; upper: current date must not exceed it) and the grid surfaces a mismatch via a small thumbtack icon next to the task name, turning `--danger`-colored when violated — the same "surface it, don't silently override a deliberate placement" stance already established for a manual placement ahead of a predecessor. Real MS Project does the same thing here: an over-constrained schedule gets a conflict indicator, not a silent reversal of whichever constraint lost.
- **ALAP** is treated identically to ASAP for actual date computation in this version — both are lower-bounded only by predecessors, with no backward slack-filling pass. A true ALAP (schedule as late as possible without delaying a successor) would need the same latest-start machinery `computeCriticalPath()` already computes for leaf tasks, just applied continuously rather than only behind the critical-path toggle; deferred as a genuine v1 scope cut rather than built halfway. No violation warning is shown for ALAP since there's nothing here to violate yet.

### Gantt rendering

Position math is plain day-number arithmetic (`dayNumber()`/`dayNumberToIso()`, UTC-based via `Date.UTC()`) rather than local-time `Date` arithmetic — the same reasoning Pulse's own Dashboard Gantt chart uses: two devices in different timezones must compute the identical pixel position from the same ISO date string, which a local-time parse doesn't reliably guarantee across a DST boundary. Display-facing formatting (`fmtDate()`/`fmtDateY()`) still parses as local time, matching how every other date renders in this app.

The grid pane (task table) and the Gantt pane share one implicit vertical scroll position: the grid's own row list is `overflow: hidden` (never user-scrollable directly) and its `scrollTop` is driven programmatically from the Gantt pane's real scroll container, with wheel events over the grid forwarded into the Gantt pane's scroll instead (`wireScrollSync()`). This works because CSS `overflow: hidden` still permits *programmatic* `scrollTop` — it only suppresses the scrollbar UI and user-initiated wheel/touch scrolling — so the two panes' rows stay pixel-aligned with only one real scrollable element.

**In Gantt view, the grid pane is deliberately a compact label sidebar (ID/Name/Start/End only), not Task view's full spreadsheet** — `renderGrid()`'s `full` flag (`currentView === 'tasks'`) decides which cells actually get built (the CSS column templates for the two views already differ: the base `.grid-header`/`.grid-row` rule is the 4-column compact one, `.main.view-tasks` overrides it to the full 8-column one), so the two views never share a template with mismatched cell counts. Its width is a resizable, per-device preference (`gridPaneWidth`, default 360px, clamped to `[240, 720]`) — `#gridResizeHandle` (a thin drag strip pinned to the pane's right edge, only active in Gantt view — see `.main.view-tasks .grid-resize-handle`) drives it live via a CSS custom property (`--grid-pane-width`) during the drag and persists on mouseup, the same "update live, commit once" shape the Gantt bar drag handlers already use. Task view ignores the variable entirely (`width: auto; flex: 1`), since its pane is always meant to fill the screen.

Bar color (`statusColorVar()`) is either the task's own explicit `color` override, or derived from status: complete (100%) → `--status-complete`, overdue (end date in the past, not complete) → `--danger`, in-progress (progress > 0) → `--accent`, otherwise `--status-not-started`. A bar's unfilled portion is `color-mix(in srgb, var(--bar-color) 22%, var(--panel))` and its progress fill is the solid color — this is why dbPlanner's own color-scheme port only needs one solid hex per token rather than Pulse's paired solid/`-bg` tokens (see "Color scheme system" below).

Dependency arrows are a single `<svg>` overlay (`#ganttDeps`) redrawn each render, one elbow-routed `<path>` per predecessor link between two currently-visible tasks (a link to/from a task hidden behind a collapsed ancestor is simply not drawn). Drag-to-link (the small circle handle on a bar's right edge) draws a temporary dashed preview path during the drag and resolves the drop target via `document.elementFromPoint()` against `data-row-id`/`data-id` attributes on the row background and bar elements.

### Color scheme system

Ported from Pulse's own two-axis design (`data-theme` light/dark × `data-scheme` picks a palette) — same five schemes (Standard, Modern/VS Code, Dracula/Alucard, GitHub, GitHub Dark Dimmed), same real, verified hex values Pulse already fetched from each source product. **One deliberate difference from Pulse's own token set**: Pulse pairs every color with a separate `-bg` tint token (`--ws-blue`/`--ws-blue-bg`); dbPlanner computes tints on the fly with CSS `color-mix()` instead (`color-mix(in srgb, var(--task-blue) 22%, var(--panel))`), so only one solid hex per color needs porting per scheme rather than two. This is a Chrome/Edge-only CSS feature — an acceptable trade-off given this app's File System Access sync feature is already Chrome/Edge-only for the same reason Pulse's is.

`THEME_SCHEMES` (top of the `<script>` block) is the single source of truth for the picker UI; each entry's `id` must match a `[data-scheme="..."]` selector in the CSS. To add a scheme: add its light+dark CSS variable block (19 tokens: `bg/panel/panel-2/border/text/text-dim/text-faint/accent/danger` + 8 `task-*` colors + `status-not-started/status-complete`), then add a `THEME_SCHEMES` entry.

### Data durability

Same shape as Pulse/mytasks, sized down for a single-entity (`tasks`, not items+milestones+workstreams) data model:

- **Tombstones**: `deletedTaskIds` (`{id, deletedAt}[]`). `deleteTaskFlow()` cascades to the full descendant subtree, tombstones every id, and its undo toast restores the whole subtree *and* any predecessor links that were stripped from surviving tasks pointing at the deleted set (captured before the strip, replayed on undo) — a plain "restore the deleted tasks" undo without this would silently leave a surviving task's dependency broken even after the delete itself was undone.
- **Merge** (`mergeData(data, opts)`): flat, single-entity last-write-wins by `task.updatedAt`, tombstone-aware (respecting `opts.respectTombstones`, defaulting true — `applyImport('merge')` and a linked-file read both use the default; `applyImport('replace')`/backup restore skip merge entirely and overwrite). No per-field merge is needed the way Pulse's milestones-within-an-item needed one — a dbPlanner task has no nested sub-collection of its own.
- **Local backups**: one rolling snapshot per calendar day in `localStorage["dbplanner-backups"]`, capped at 7, via `maybeSnapshotBackup()` called from every `save()`.
- **File System Access API sync**: single-file (not Pulse's later folder/multi-file split — that split exists specifically for *concurrent multi-workstream* editing, which doesn't apply to dbPlanner's single-project model). `linkNewFile()`/`linkExistingFile()` pick a `FileSystemFileHandle` via `showSaveFilePicker()`/`showOpenFilePicker()`, persisted across reloads in IndexedDB (`dbplanner-fs`). Writes are queued (`queueFileSyncWrite()`/`fileSyncWriteInFlight`/`fileSyncWritePending`) so a burst of rapid saves collapses to the minimum necessary writes and always reflects the latest state, not a stale queued snapshot — same mechanism Pulse's own file sync uses. Background polling every 45s (`FILE_SYNC_POLL_MS`) picks up changes made by another device sharing the same file (e.g. via iCloud Drive/OneDrive/Dropbox). Linking is entirely optional — never mandatory the way Pulse's is, since dbPlanner has no multi-role/team concept to enforce a shared source of truth for.

### PWA

`manifest.json` + `sw.js` (cache-first app shell with network-first navigation, same shape as Pulse's own service worker) + `icons/` (`icon.svg` source, three PNG sizes generated via Pillow rather than an SVG rasterizer — none was available in this environment; regenerate from `icon.svg` with any SVG-to-PNG tool if the icon ever changes). `start-dbplanner.command`/`stop-dbplanner.command` mirror Pulse's own local-server launch scripts, on port 8937 (Pulse's own is 8936 — kept distinct so both apps' dev servers can run at once).

## Known v1 limitations

- Critical path slack treats every dependency as Finish-to-Start (see "Scheduling engine" above).
- ALAP behaves identically to ASAP — no backward slack-filling pass yet (see "Task constraints" above).
- SNLT/FNLT (Start/Finish No Later Than) are flagged when violated, never enforced — this app's cascade is forward-push-only.
- No automated test suite yet.
- No RBAC/roles, no daily-backup-to-a-linked-folder, no multi-file sync split — all deliberately out of scope for a single-user, single-project local planner (unlike Pulse, which is a multi-role team dashboard).
