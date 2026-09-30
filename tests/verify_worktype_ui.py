# -*- coding: utf-8 -*-
"""Task Type / Work, Stage 3 — the task dialog UI and grid columns. The dialog gets a `.field-grid-tt` row (Task Type
select, Effort-driven checkbox, a typed Work field reusing `parseDurationMinutes`/`fmtDurationMinutes`) next to Task
Mode/Resource, hidden for a milestone or a group (no Duration/Work of their own). The grid gets `worktype` (an
icon-with-popup cell, `openTaskTypeMenu`/`pickTaskType`, the same shared-popup pattern Task Mode's own cell already
uses) and `work` (typed text, same convention as the Duration cell) columns in `TASK_COLS`/`FILTER_COLS`, both hidden
by default and both blank for a milestone/group. See "Task Type / Work" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    SEED = ("specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.workDays; delete project.holidays; "
            "const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, "
            "progress: 0, milestone: !!sp.ms, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', "
            "actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }")
    seed = lambda specs: ev(SEED, specs)
    openDialog = lambda i=0: (ev(f"() => openTaskModal(tasks[{i}].id, false)"), pg.wait_for_selector("#taskModalBg.open"), pg.wait_for_timeout(50))

    # ---------------------------------------------------------------- dialog: populated correctly, saved correctly
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedDuration", "effortDriven": False}}])
    openDialog()
    check("Task Type select shows the task's own type", pg.input_value("#taskTypeInput") == "fixedDuration")
    check("Effort-driven checkbox reflects the task", pg.is_checked("#effortDrivenInput") is False)
    check("Work field shows the bootstrapped value, formatted", pg.input_value("#taskWorkInput") == "4 days", pg.input_value("#taskWorkInput"))
    check("the row is visible for an ordinary task", "hidden" not in pg.get_attribute("#taskTypeRow", "class"))
    pg.select_option("#taskTypeInput", "fixedWork")
    pg.check("#effortDrivenInput")
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")
    check("saving persists Task Type and Effort-driven", ev("() => [tasks[0].taskType, tasks[0].effortDriven]") == ["fixedWork", True], ev("() => [tasks[0].taskType, tasks[0].effortDriven]"))

    # ---------------------------------------------------------------- dialog: hidden for a milestone, live
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    openDialog()
    check("visible for an ordinary task", "hidden" not in pg.get_attribute("#taskTypeRow", "class"))
    pg.check("#taskMilestoneInput")
    check("hidden the moment Milestone is checked (live, no save needed)", "hidden" in pg.get_attribute("#taskTypeRow", "class"))
    pg.uncheck("#taskMilestoneInput")
    check("...and visible again once unchecked", "hidden" not in pg.get_attribute("#taskTypeRow", "class"))
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")

    seed([{"name": "M", "s": "2026-09-07", "e": "2026-09-07", "ms": True}])
    openDialog()
    check("hidden for a task that's already a milestone at open", "hidden" in pg.get_attribute("#taskTypeRow", "class"))
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")

    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-10"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-10", "parent": "G", "r": "Anna"}])
    ev("() => openTaskModal(tasks.find(t => t.name === 'G').id, false)")
    pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(50)
    check("hidden for a group (rollup, no Duration/Work of its own)", "hidden" in pg.get_attribute("#taskTypeRow", "class"))
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")

    # ---------------------------------------------------------------- dialog: an unreadable Work value is refused, doesn't block the rest of the save
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    openDialog()
    pg.fill("#taskWorkInput", "not a duration")
    pg.fill("#taskNameInput", "Renamed")
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")
    check("an unreadable Work value is refused with a toast", "Can't read" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    check("...but the rest of the save still goes through", ev("() => tasks[0].name") == "Renamed")

    # ---------------------------------------------------------------- dialog: the generic dirty-check picks up the new fields for free
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    openDialog()
    check("not dirty when untouched", ev("() => taskModalDirty()") is False)
    pg.select_option("#taskTypeInput", "fixedDuration")
    check("changing Task Type marks the dialog dirty", ev("() => taskModalDirty()") is True)
    pg.click("#taskModalBg button:has-text('Cancel')")

    # ---------------------------------------------------------------- grid: the Task Type popup cell
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedWork"}}])
    ev("() => { toggleColumn('worktype', true); toggleColumn('work', true); render(); }")
    check("both new columns are listed in Columns menu", (ev("() => toggleColumnsMenu()"), [t for t in ev("() => [...document.querySelectorAll('#columnsMenu .cols-check span')].map(e => e.textContent)")]) and {"Task Type", "Work"} <= set(ev("() => [...document.querySelectorAll('#columnsMenu .cols-check span')].map(e => e.textContent)")))
    ev("() => toggleColumnsMenu()")
    rowA = ev("() => tasks[0].id")
    check("the cell shows the task's own type", ev(f"() => document.querySelector(\"[data-id='{rowA}'] .task-mode-cell[title^='Fixed Work']\")") is not None)
    ev(f"() => openTaskTypeMenu({{stopPropagation(){{}}, currentTarget: document.querySelector(\"[data-id='{rowA}'] .task-mode-cell[title^='Fixed Work']\")}}, '{rowA}')")
    check("the popup lists all three types with the current one active", ev("() => document.getElementById('taskTypeMenu').querySelectorAll('.dropdown-item').length") == 3 and "active" in ev("() => document.getElementById('taskTypeMenu').querySelector('.dropdown-item:nth-child(3)').className"))
    ev("() => pickTaskType('fixedUnits')")
    check("picking a type applies it (fixedUnits cleans to absent — it's the default)", ev("() => tasks[0].taskType") is None)

    # ---------------------------------------------------------------- grid: the Work cell, inline text edit like Duration
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    ev("() => { toggleColumn('work', true); render(); }")
    w0 = ev("() => tasks[0].work")
    check("the cell shows the formatted value", ev("() => { const t = tasks[0], row = document.querySelector(`[data-id='${t.id}']`); return [...row.querySelectorAll('.grid-cell-dim')].some(el => el.textContent.trim() === fmtDurationMinutes(t.work)); }"))
    ev("() => { const t = tasks[0]; editingCell = { id: t.id, field: 'work' }; commitInlineEdit(t.id, 'work', String(t.work / 2 / workMinutesPerDay()) + 'd'); }")
    check("editing it recalculates Duration (Fixed Units default)", ev("() => durationDays(tasks[0].startDate, tasks[0].endDate)") == 2, ev("() => durationDays(tasks[0].startDate, tasks[0].endDate)"))

    # ---------------------------------------------------------------- grid: both columns are blank for a milestone/group
    seed([{"name": "M", "s": "2026-09-07", "e": "2026-09-07", "ms": True, "r": "Anna"}, {"name": "G", "s": "2026-09-07", "e": "2026-09-10"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-10", "parent": "G", "r": "Anna"}])
    ev("() => { toggleColumn('worktype', true); toggleColumn('work', true); render(); }")
    mId, gId = ev("() => [tasks.find(t=>t.name==='M').id, tasks.find(t=>t.name==='G').id]")
    # every row always has one .task-mode-cell (the Task Mode column itself); a second one would be the Task Type cell, absent for a milestone/group
    check("a milestone's Task Type/Work cells are blank, not an error", ev(f"() => document.querySelectorAll(\"[data-id='{mId}'] .task-mode-cell\").length") == 1)
    check("a group's Task Type/Work cells are blank too", ev(f"() => document.querySelectorAll(\"[data-id='{gId}'] .task-mode-cell\").length") == 1)

    # ---------------------------------------------------------------- filters: the new columns' funnels work without crashing
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna", "extra": {"taskType": "fixedWork"}}, {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "r": "Ben"}])
    ev("() => { toggleColumn('worktype', true); render(); }")
    ev("() => { colFilters.worktype = { type: 'values', values: new Set(['fixedWork']), blanks: false }; render(); }")
    check("a Task Type filter narrows the list to just that type", ev("() => tasks.filter(t => filterShows(t)).map(t => t.name)") == ["A"], ev("() => tasks.filter(t => filterShows(t)).map(t => t.name)"))
    ev("() => { colFilters = newColFilters(); filterPinned.clear(); render(); }")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
