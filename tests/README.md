# Tests

Milestone has no build step, and its tests match: each `verify_*.py` / `drive_*.py` is a Playwright script that opens
`milestone.html` in headless Chromium, drives the real UI and internals, and prints `PASS` / `FAIL` lines and a
`N/M passed` summary (exit status 0 = passed).

```sh
pip install playwright openpyxl && python3 -m playwright install chromium   # once
python3 tests/run_all.py                    # everything + a short stress run
python3 tests/run_all.py pull undo          # only suites whose name contains "pull" or "undo"
python3 tests/run_all.py --stress 100       # a long stress run (seeds 1-100)
python3 tests/verify_stress.py 35 36        # one suite, or particular stress seeds, directly
```

The runner serves the repository on port 8937 if nothing is answering there (`start-milestone.command` does the same);
set `MILESTONE_URL` / `--url` to test another address. Suites run three at a time (`--jobs`).

| suite | covers |
|---|---|
| `verify_e2e` | a scripted user journey with real clicks: dialog, dependencies, inline edits, baseline, actual dates, calendar, filters, Gantt, columns, clone/delete/undo, Excel + JSON export, import, backups, plans, theme, reload |
| `verify_stress` | seeded random operations (add, delete, indent, move, edits, drags, clone, undo/redo, calendar and holidays, baselines …) with invariants after every step — structure, dates, links, Auto tasks exactly where their links put them, idempotent normalise/merge, stable save/load, critical path, Excel export |
| `verify_pull`, `verify_cycles`, `verify_actuals`, `verify_calendar`, `verify_holidays`, `verify_critical`, `verify_baseline` | scheduling: bidirectional Auto scheduling and the Start/Finish No Earlier Than pin, dependency cycles, actual dates, the working calendar and holidays, the critical path, baselines and variance |
| `verify_undo` | undo / redo history |
| `verify_help` | the tabbed Help dialog: topics, keyboard, contrast in both themes, narrow layout |
| `verify_sync`, `verify_plans` | file merge between two simulated devices, conflicts; plans, file linking, the write race |
| `verify_columns`, `verify_gantt_columns`, `verify_gantt_list`, `verify_custom_fields`, `verify_filters`, `verify_fixed_widths`, `verify_column_lines`, `verify_hscroll`, `verify_date_editors`, `verify_funnel_hover`, `verify_mode_header` | the task list: columns per view, custom fields, filters, widths, lines, scrolling, editors |
| `verify_excel`, `verify_excel_views` | the Excel export (package structure, values, per-view columns) |
| `verify_clone`, `verify_reorder`, `verify_add_below`, `verify_collapse_all`, `verify_auto_default`, `verify_gantt_scales`, `verify_dark_controls`, `verify_grab_cursor`, `drive_taskmode_*` | task operations, drag and drop, Task Mode, the Gantt scales, theming |

Older suites are written in calendar days: they pin `project.workDays = [0,1,2,3,4,5,6]` right after their first reload. When
a suite fails, its `FAIL` line names the check and shows the values it saw; the stress test prints the seed and the last
operations, so `python3 tests/verify_stress.py <seed>` reproduces it.
