# -*- coding: utf-8 -*-
"""Task Type / Work, Stage 1 — the data model and pure engine. task.taskType ('fixedUnits' default, 'fixedDuration',
'fixedWork'), task.effortDriven (absent = true) and task.work (working minutes, bootstrapped once from the task's own
current Duration x Units the first time normalizeData() sees it without one). taskUnitsPercent(t) is the aggregate of
every assigned resource's own percentage (parseResourceAssignments, not the pool-resolved taskAssignments — no
ordering dependency on the pool); taskDurationMinutes(t) mirrors durationDays()/durationMoment() in working minutes
always. recalcTaskType(t, changed) is the engine: given which of Duration/Work/Units was just edited, recalculates
whichever the Task Type says is NOT fixed, keeping Work = Duration x Units/100 true — see the table in "Task Type /
Work" in CLAUDE.md. Effort-driven gates only the "a resource was added/removed" cell; an unassigned task has no text
to rescale, so it behaves like Fixed Units regardless of its own type. See CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    SEED = ("specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.workDays; delete project.holidays; delete project.timeUnit; "
            "const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, "
            "progress: 0, milestone: !!sp.ms, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', "
            "actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }")
    seed = lambda specs: ev(SEED, specs)

    # ---------------------------------------------------------------- normalizeData() cleaning: absence = default
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08"}])
    check("taskType absent by default (Fixed Units)", ev("() => tasks[0].taskType") is None)
    check("effortDriven absent by default (true)", ev("() => tasks[0].effortDriven") is None)
    ev("() => { tasks[0].taskType = 'bogus'; tasks[0].effortDriven = true; normalizeData(); }")
    check("garbage taskType and an explicit true (the default) both clean to absent", ev("() => tasks[0].taskType") is None and ev("() => tasks[0].effortDriven") is None)
    ev("() => { tasks[0].taskType = 'fixedWork'; tasks[0].effortDriven = false; normalizeData(); }")
    check("a real non-default value is kept", ev("() => [tasks[0].taskType, tasks[0].effortDriven]") == ["fixedWork", False])

    # ---------------------------------------------------------------- work bootstrap
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna:50%"}])   # 4 working days at 50%
    expected = ev("() => durationDays('2026-09-07', '2026-09-10') * workMinutesPerDay() * 0.5")
    check("work bootstraps from current Duration x Units on first touch", ev("() => tasks[0].work") == expected, (ev("() => tasks[0].work"), expected))
    check("taskUnitsPercent reads the aggregate percentage", ev("() => taskUnitsPercent(tasks[0])") == 50)
    check("an unassigned task's units is the implicit 100%", ev("() => taskUnitsPercent({resource: ''})") == 100)
    ev("() => { tasks[0].work = -5; normalizeData(); }")
    check("a garbage stored work re-bootstraps rather than staying negative", ev("() => tasks[0].work") == expected)
    ev("() => { tasks[0].work = 123.7; normalizeData(); }")
    check("a real work value is kept, rounded", ev("() => tasks[0].work") == 124)

    seed([{"name": "M", "s": "2026-09-07", "e": "2026-09-07", "ms": True}, {"name": "G", "s": "2026-09-07", "e": "2026-09-08"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-08", "parent": "G"}])
    check("a milestone never gets a work value", ev("() => tasks.find(t=>t.name==='M').work") is None)
    check("a group never gets a work value (rollup, not stored, like Duration)", ev("() => tasks.find(t=>t.name==='G').work") is None)
    check("its own leaf child does", ev("() => tasks.find(t=>t.name==='K').work") is not None)

    dates = lambda: ev("() => [tasks[0].startDate, tasks[0].endDate]")

    # ---------------------------------------------------------------- Fixed Units (default): editing Duration/Work/Units
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])   # 4 days, 100%, work = 1920 min
    work0 = ev("() => tasks[0].work")
    ev("() => { tasks[0].endDate = '2026-09-08'; recalcTaskType(tasks[0], 'duration'); }")   # shrink to 2 days
    check("Fixed Units: editing Duration recalculates Work", ev("() => tasks[0].work") == work0 / 2, (ev("() => tasks[0].work"), work0))
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    ev("() => { tasks[0].work = tasks[0].work / 2; recalcTaskType(tasks[0], 'work'); }")
    check("Fixed Units: editing Work recalculates Duration", ev("() => durationDays(tasks[0].startDate, tasks[0].endDate)") == 2)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    work1 = ev("() => tasks[0].work")
    ev("() => { tasks[0].resource = 'Anna, Ben'; recalcTaskType(tasks[0], 'units'); }")
    check("Fixed Units: adding a resource recalculates Duration, keeps Work — 'two people finish faster'", ev("() => durationDays(tasks[0].startDate, tasks[0].endDate)") == 2 and ev("() => tasks[0].work") == work1)

    # ---------------------------------------------------------------- Fixed Duration: never moves on its own
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedDuration"}}])
    d0 = dates(); w0 = ev("() => tasks[0].work")
    ev("() => { tasks[0].resource = 'Anna, Ben'; recalcTaskType(tasks[0], 'units'); }")
    check("Fixed Duration: adding a resource does NOT move the dates", dates() == d0, (dates(), d0))
    check("...Work increases instead (more capacity, same span)", ev("() => tasks[0].work") > w0)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedDuration"}}])
    d1 = dates()
    ev("() => { tasks[0].work = tasks[0].work * 2; recalcTaskType(tasks[0], 'work'); }")
    check("Fixed Duration: editing Work recalculates Units (resource text), not dates", dates() == d1 and ev("() => tasks[0].resource") != "Anna")
    check("...Anna's own share roughly doubled", ev("() => taskUnitsPercent(tasks[0])") == 200, ev("() => tasks[0].resource"))

    # ---------------------------------------------------------------- Fixed Work: the resource text rescales to preserve Work
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna:100%, Ben:100%", "extra": {"taskType": "fixedWork"}}])
    work2 = ev("() => tasks[0].work")
    msg = ev("() => { tasks[0].endDate = '2026-09-08'; return recalcTaskType(tasks[0], 'duration'); }")   # 4 days -> 2 days
    check("Fixed Work: shrinking Duration rescales Units (a message describing the change is returned)", isinstance(msg, str) and "→" in msg, msg)
    check("...aggregate units doubled to preserve Work at the shorter span", ev("() => taskUnitsPercent(tasks[0])") == 400)
    check("...Work itself is untouched", ev("() => tasks[0].work") == work2)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedWork"}}])
    work3 = ev("() => tasks[0].work")
    ev("() => { tasks[0].resource = 'Anna, Ben'; recalcTaskType(tasks[0], 'units'); }")
    check("Fixed Work: adding a resource recalculates Duration too (like Fixed Units) — also gets faster", ev("() => durationDays(tasks[0].startDate, tasks[0].endDate)") == 2 and ev("() => tasks[0].work") == work3)

    # ---------------------------------------------------------------- effort-driven off: a resource change never moves dates
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"effortDriven": False}}])
    d2 = dates()
    ev("() => { tasks[0].resource = 'Anna, Ben'; recalcTaskType(tasks[0], 'units'); }")
    check("effortDriven=false on a Fixed Units task: adding a resource does not shrink it", dates() == d2)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedWork", "effortDriven": False}}])
    d3 = dates()
    ev("() => { tasks[0].resource = 'Anna, Ben'; recalcTaskType(tasks[0], 'units'); }")
    check("...same for Fixed Work", dates() == d3)

    # ---------------------------------------------------------------- unassigned edge case: behaves like Fixed Units regardless of its own type
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "extra": {"taskType": "fixedDuration"}}])   # no resource at all
    ev("() => { tasks[0].work = tasks[0].work / 2; recalcTaskType(tasks[0], 'work'); }")
    check("unassigned Fixed Duration: editing Work has nothing to rescale, so Duration moves instead", ev("() => durationDays(tasks[0].startDate, tasks[0].endDate)") == 2)

    # ---------------------------------------------------------------- milestones and groups are never touched
    seed([{"name": "M", "s": "2026-09-07", "e": "2026-09-07", "ms": True, "r": "Anna"}])
    check("recalcTaskType on a milestone is a no-op", ev("() => recalcTaskType(tasks[0], 'units')") is None)
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-10"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-10", "parent": "G", "r": "Anna"}])
    check("recalcTaskType on a group is a no-op", ev("() => recalcTaskType(tasks.find(t=>t.name==='G'), 'units')") is None)

    # ---------------------------------------------------------------- minute mode: duration recalculation converts correctly (working minutes vs working days)
    ev("() => { project.timeUnit = 'minute'; save(); }")
    ev("""() => { tasks.length = 0; const t = { id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-07', startTime: '09:00', endTime: '11:00',
      progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null };
      tasks.push(t); normalizeData(); save(); render(); }""")
    check("minute mode: a 2h task's work bootstraps to 120 minutes", ev("() => tasks[0].work") == 120)
    ev("() => { tasks[0].resource = 'Anna, Ben'; recalcTaskType(tasks[0], 'units'); }")
    check("minute mode: adding a resource halves the duration to 1h (09:00-10:00), not a garbled multi-year date", ev("() => [tasks[0].startTime, tasks[0].endTime]") == ["09:00", "10:00"], ev("() => [tasks[0].startDate, tasks[0].endDate, tasks[0].startTime, tasks[0].endTime]"))
    check("...Work is unchanged", ev("() => tasks[0].work") == 120)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
