# -*- coding: utf-8 -*-
"""Minute/hour-level scheduling precision: baselines carry a time-of-day too. A baseline snapshot (task.baselines[slot] =
[start, finish]) grows two optional trailing elements, [start, finish, startTime, endTime] — only in a minute-mode plan,
and only when there's a real time to keep (day-mode baselines, and a minute-mode baseline captured before its task ever
had a time, stay the plain 2-element array they always were — normalizeData() enforces this, so old plans and files are
byte-for-byte unaffected). baselineDates()/scheduleVariance() read it; a GROUP's baseline is always a day-only rollup
(varianceIsMinutes() is false for it), so only a leaf task's baseline/variance gets minute precision — see "Scheduling
precision (minute mode)" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1700, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    def seed(start_time, end_time):
        ev("""([st, et]) => {
            tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0;
            delete project.workDays; delete project.holidays; delete project.workHours; delete project.baselines; delete project.compareBaseline; project.timeUnit = 'minute';
            const t = { id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-07', startTime: st, endTime: et,
              progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null,
              taskMode: 'auto', resource: '', actualStart: null, actualFinish: null };
            tasks.push(t);
            for (const c of ['baselineStart','baselineFinish','baselineDuration','startVariance','finishVariance','durationVariance']) colHidden.delete(c);
            currentView = 'tasks'; normalizeData(); save(); render();
        }""", [start_time, end_time])
    move = lambda st, et: ev("([st, et]) => { const t = tasks[0]; t.startTime = st; t.endTime = et; normalizeData(); save(); render(); }", [st, et])
    setBaseline = lambda: ev("() => { applyBaselineChange(0, 'all', false); }")
    hc = lambda: pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col)")
    def cell(col): return pg.locator(".grid-row").first.locator(":scope > div").nth(1 + hc().index(col))
    txt = lambda col: cell(col).inner_text().strip()

    # ---------------------------------------------------------------- capture: a baseline keeps the task's own time
    seed("09:00", "11:00"); setBaseline()
    bl = ev("() => tasks[0].baselines[0]")
    check("a baseline captured on a minute-mode task keeps its start/end time as a 3rd/4th array element", bl == ["2026-09-07", "2026-09-07", "09:00", "11:00"], bl)

    # ---------------------------------------------------------------- day-mode baselines are untouched (still exactly 2 elements)
    ev("() => { project.timeUnit = 'day'; normalizeData(); save(); }")
    bl2 = ev("() => tasks[0].baselines[0]")
    check("switching back to day mode collapses the baseline back to the plain [start, finish] it always was", bl2 == ["2026-09-07", "2026-09-07"], bl2)
    ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); }")

    # ---------------------------------------------------------------- a baseline with no time captured (untouched task) never grows to 4 elements
    seed(None, None); setBaseline()
    bl3 = ev("() => tasks[0].baselines[0]")
    check("a baseline taken on a task that never had its own time stays a plain 2-element array too (nothing to keep)", bl3 == ["2026-09-07", "2026-09-07"], bl3)

    # ---------------------------------------------------------------- variance: minutes, not days, for a leaf task
    seed("09:00", "11:00"); setBaseline()
    move("09:30", "11:45")
    sv = ev("() => scheduleVariance(tasks[0].id)")
    check("moving a leaf task's time gives a variance in working MINUTES (30 start, 45 finish, 15 duration), not days", sv == {"start": 30, "finish": 45, "duration": 15, "baseDuration": 120}, sv)
    check("varianceIsMinutes() is true for this leaf task in a minute-mode plan", ev("() => varianceIsMinutes(tasks[0].id)") is True)

    # ---------------------------------------------------------------- variance formatting
    vtxt = ev("() => ({ start: fmtVarianceFor(tasks[0].id, scheduleVariance(tasks[0].id).start), finish: fmtVarianceFor(tasks[0].id, scheduleVariance(tasks[0].id).finish) })")
    check("variance formats in minute units, not days — 30 min as the exact half-hour fmtDurationMinutes() prefers ('+0.5 hrs'), 45 min as raw minutes ('+45 min')", vtxt == {"start": "+0.5 hrs", "finish": "+45 min"}, vtxt)
    check("fmtDurationMinutes(0) reads '0 min', not the misleading '0 days' (0 is trivially divisible by anything)", ev("() => fmtDurationMinutes(0)") == "0 min")

    # ---------------------------------------------------------------- the grid shows baseline date+time and minute-formatted variance/duration
    ev("() => { toggleBaseline(); toggleBaseline(); render(); }")  # no-op, just ensure a render happened after the move
    check("the grid's Baseline Start cell shows the baseline's own date and time", txt("baselineStart") == "07.09.2026 09:00", txt("baselineStart"))
    check("...Baseline Finish too", txt("baselineFinish") == "07.09.2026 11:00", txt("baselineFinish"))
    check("...Baseline Duration in minute units ('2 hrs', the 09:00-11:00 span)", txt("baselineDuration") == "2 hrs", txt("baselineDuration"))
    check("...Start Variance in minute units", txt("startVariance") == "+0.5 hrs", txt("startVariance"))
    check("...Finish Variance in minute units", txt("finishVariance") == "+45 min", txt("finishVariance"))
    check("...Duration Variance in minute units ('+15 min', the task grew by 15 working minutes)", txt("durationVariance") == "+15 min", txt("durationVariance"))
    bsi, bfi = hc().index("baselineStart"), hc().index("baselineFinish")
    tracks = ev("() => getComputedStyle(document.getElementById('main')).getPropertyValue('--task-cols')").strip().split()
    check("Baseline Start/Finish widen to 150px like Start/Finish do", tracks[1 + bsi] == "150px" and tracks[1 + bfi] == "150px", (bsi, bfi, tracks))

    # ---------------------------------------------------------------- the task dialog's baseline-info box, live as you type
    pg.click(".grid-row .icon-btn[title=Edit]"); pg.wait_for_selector("#taskModalBg.open")
    box = pg.inner_text("#taskBaselineInfo")
    check("the dialog's baseline box shows the baseline's own time and the live minute variance", "09:00" in box and "11:00" in box and "+0.5 hrs" in box and "+45 min" in box, box)
    pg.fill("#taskStartTimeInput", "09:15"); pg.dispatch_event("#taskStartTimeInput", "change")
    box2 = pg.inner_text("#taskBaselineInfo")
    check("...and it updates live as the time is edited, before saving", "+15 min" in box2, box2)
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- groups: baseline variance stays day-only even in a minute-mode plan
    ev("""() => {
        tasks.length = 0; delete project.baselines; delete project.compareBaseline;
        const mk = (id, name, parentId, extra) => Object.assign({ id, name, parentId, order: 0, startDate: '2026-09-07', endDate: '2026-09-07', startTime: null, endTime: null,
          progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
        tasks.push(mk('p', 'Parent', null), mk('c', 'Child', 'p', { startTime: '09:00', endTime: '11:00' }));
        normalizeData(); save(); render();
        applyBaselineChange(0, 'all', false);
        const child = tasks.find(t => t.name === 'Child'); child.startTime = '09:30'; child.endTime = '11:30'; normalizeData(); save();
    }""")
    check("a group's variance is never computed in minutes, even in a minute-mode plan (its baseline is always a day rollup)", ev("() => varianceIsMinutes(tasks.find(t => t.name === 'Parent').id)") is False)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
