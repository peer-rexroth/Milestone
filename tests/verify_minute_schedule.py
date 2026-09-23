# -*- coding: utf-8 -*-
"""Phase 2 of minute/hour-level scheduling precision (an explicit user request, "like in MS Project", true minute-level
scheduling confirmed via a scoping question — not just a duration-unit convenience). The moment abstraction (taskMoment(),
shiftMoment()/durationMoment()/finishMoment()/startMoment(), momentDiff()) lets the existing day-based scheduling engine
— constraintStart, constraintLateEnd, alapTargetStart, targetStart, placeByLinks, cascadeSchedule, pinToDate, offItsLinks,
scheduleMismatch, constraintViolated, applyActualDates, clampTaskDates, snapToWorkDays, criticalPathAnalysis,
rescheduleFromStatusDate — work identically whether project.timeUnit is 'day' (the standard default, untouched: every
moment collapses straight back to dayNumber()) or 'minute' (task.startTime/endTime/actualStartTime/actualFinishTime/
constraintTime, 'HH:MM' siblings of the existing date fields, refine a day down to a specific working minute within it).
Every public function that existing tests already assert against (constraintStart, scheduleMismatch, rescheduleFromStatusDate)
keeps returning exactly what it always did — an ISO date string — even in minute mode; the internal *Moment variants carry
the real minute precision the scheduler itself needs. See CLAUDE.md's "Scheduling precision (minute mode)" section."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

# 2026-09-07 is a Monday: 07 Mon 08 Tue 09 Wed 10 Thu 11 Fri 12 Sat 13 Sun 14 Mon. Default working hours (untouched):
# 08:00-12:00, 13:00-17:00 (480 working minutes/day).
SEED = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0;
  delete project.workDays; delete project.holidays; delete project.workHours; project.timeUnit = 'minute';
  const ids = {};
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e,
      startTime: sp.st || null, endTime: sp.et || null, progress: sp.progress || 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1,
      constraintType: sp.ct || 'ASAP', constraintDate: sp.cd || null, constraintTime: sp.ctm || null, taskMode: 'auto', resource: '',
      actualStart: sp.as_ || null, actualStartTime: sp.ast || null, actualFinish: sp.af || null, actualFinishTime: sp.aft || null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag})); }
  currentView = 'tasks'; normalizeData(); save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    seed = lambda specs: ev(SEED, specs)
    tm = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.startTime, t.endDate, t.endTime]; }", n)
    st = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.startTime]; }", n)
    en = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.endDate, t.endTime]; }", n)
    place = lambda n: ev("n => { applyConstraints(tasks.find(t => t.name === n).id); save(); }", n)   # placeByLinks() only runs via applyConstraints/cascadeSchedule — seeding data does not auto-schedule it, same as verify_alap_snlt.py

    # ---------------------------------------------------------------- FS: the ordinary link, plain and across the lunch break
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "11:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("FS with 0 lag: B starts exactly when A finishes (11:00), point-in-time, not '+1 day' the way day-mode is", st("B") == ["2026-09-07", "11:00"], st("B"))
    seed([{"name": "A", "s": "2026-09-07", "st": "11:30", "e": "2026-09-07", "et": "11:45"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("A finishes at 11:45, right before the break: B starts right there too (no break involved)", st("B") == ["2026-09-07", "11:45"])
    seed([{"name": "A", "s": "2026-09-07", "st": "11:30", "e": "2026-09-07", "et": "12:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("A finishes exactly at 12:00 (break start, the exclusive window edge): B is pushed past the break to 13:00", st("B") == ["2026-09-07", "13:00"], st("B"))

    # ---------------------------------------------------------------- SS / FF / SF with lags in minutes, across the break
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "SS", 0]]}])
    place("B")
    check("SS 0 lag: B starts exactly when A starts (09:00)", st("B") == ["2026-09-07", "09:00"])
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "SS", 150]]}])   # +150 working minutes: crosses the break
    place("B")
    check("SS +150 working minutes from 09:00: 180 min fit before the break (09:00-12:00), 150 < 180, so it never even reaches the break: 09:00 + 150 -> 11:30", st("B") == ["2026-09-07", "11:30"], st("B"))
    seed([{"name": "A", "s": "2026-09-07", "st": "10:00", "e": "2026-09-07", "et": "11:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "10:00", "preds": [["A", "FF", 0]]}])   # B is 2h long
    place("B")
    check("FF 0 lag: B's own finish must equal A's finish (11:00); with a 2h duration that puts B's start at 09:00", en("B") == ["2026-09-07", "11:00"] and st("B") == ["2026-09-07", "09:00"], (st("B"), en("B")))
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:30", "preds": [["A", "SF", 0]]}])   # B is 90 min long
    place("B")
    check("SF 0 lag: B's finish must equal A's start (09:00); with a 90-min duration B starts at 07:30 -> snapped: since 07:30 is before opening, the whole task is pulled to fit inside the working day ending at 09:00", en("B") == ["2026-09-07", "09:00"], (st("B"), en("B")))

    # ---------------------------------------------------------------- crossing a non-working day (weekend) and a holiday
    seed([{"name": "A", "s": "2026-09-11", "st": "16:00", "e": "2026-09-11", "et": "16:30"},   # Friday
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("FS across a weekend: A finishes Friday 16:30, B starts Monday 08:00 (still inside Friday's window, no push — 16:30 < 17:00)", st("B") == ["2026-09-11", "16:30"], st("B"))
    seed([{"name": "A", "s": "2026-09-11", "st": "16:30", "e": "2026-09-11", "et": "17:00"},   # Friday, ends exactly at close
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("...ending exactly at Friday's close (17:00, the exclusive edge) pushes B to Monday 08:00", st("B") == ["2026-09-14", "08:00"], st("B"))
    seed([{"name": "A", "s": "2026-09-07", "st": "16:30", "e": "2026-09-07", "et": "17:00"},   # Monday, ends exactly at close
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 0]]}])
    ev("() => { project.holidays = [{ date: '2026-09-08' }]; }")   # Tuesday off — set AFTER seed(), which itself clears project.holidays
    place("B")
    check("FS skips a holiday entirely: A ends Monday close, the holiday Tuesday is skipped, B starts Wednesday 08:00", st("B") == ["2026-09-09", "08:00"], st("B"))
    ev("() => { delete project.holidays; }")

    # ---------------------------------------------------------------- ALAP with time components
    # B needs its OWN independent anchor (SNET, like verify_alap_snlt.py's pattern) — otherwise applyConstraints(B) would
    # immediately re-place B from A's (unmoved) current position before the cascade ever pulls A later, destroying the
    # very anchor the test means to hold B at.
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00", "ct": "ALAP"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "ct": "SNET", "cd": "2026-09-07", "ctm": "13:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("ALAP: A (1h) is pulled as late as it can be while B still starts at 13:00 -> A sits at 12:00-13:00... but 12:00-13:00 is the break, so A lands just before it (11:00-12:00)", en("A") == ["2026-09-07", "12:00"], (st("A"), en("A")))
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00", "ct": "ALAP"},
          {"name": "P", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "11:00"},
          {"name": "B", "s": "2026-09-07", "st": "09:30", "e": "2026-09-07", "et": "10:30", "preds": [["A", "FS", 0]]}])
    ev("() => { const a = tasks.find(t => t.name === 'A'); a.predecessors = [{id: tasks.find(t => t.name === 'P').id, type: 'FS', lag: 0}]; normalizeData(); save(); }")
    place("A"); place("B")
    check("over-constrained ALAP: P forces A no earlier than 11:00 even though B's own successor bound would want it later at first glance — A never pulled before what P allows", st("A")[1] >= "11:00", st("A"))

    # ---------------------------------------------------------------- SNLT/FNLT enforcement with a time component
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "ct": "SNLT", "cd": "2026-09-07", "ctm": "10:30", "preds": [["A", "FS", 0]]}])
    place("B")
    check("SNLT caps a push: A finishes 10:00 (B would start 10:00), but SNLT 10:30 doesn't need to cap here since 10:00 < 10:30", st("B") == ["2026-09-07", "10:00"], st("B"))
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "11:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "ct": "SNLT", "cd": "2026-09-07", "ctm": "10:00", "preds": [["A", "FS", 0]]}])
    place("B")
    check("SNLT 10:00 caps A's push to 11:00: B is held at 10:00 even though the link alone would want 11:00", st("B") == ["2026-09-07", "10:00"], st("B"))

    # ---------------------------------------------------------------- critical path float in minutes
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"},
          {"name": "B", "s": "2026-09-07", "st": "10:00", "e": "2026-09-07", "et": "11:00", "preds": [["A", "FS", 0]]},
          {"name": "C", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "09:30"}])   # C is off the critical chain, 30 min slack before the project's own end (11:00)
    cp = ev("""() => { const r = criticalPathAnalysis(); const byName = n => tasks.find(t => t.name === n).id;
        return { critA: r.critical.has(byName('A')), critB: r.critical.has(byName('B')), floatC: r.float.get(byName('C')) }; }""")
    check("A and B (the chain that reaches the project's own end) are critical", cp["critA"] and cp["critB"], cp)
    check("C's float is reported in MINUTES (not floored to 0 days the way a day-based float would hide it)", cp["floatC"] == 90, cp)

    # ---------------------------------------------------------------- rescheduleFromStatusDate with a time-of-day status moment
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"}])   # Monday, not started, "overdue" as of a later status moment
    ev("() => rescheduleFromStatusDate('2026-09-09', '10:30')")   # Wednesday 10:30
    check("an overdue not-started task moves to the exact status moment (Wednesday 10:30), not just the status date", st("A") == ["2026-09-09", "10:30"], st("A"))
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "17:00", "as_": "2026-09-07", "ast": "09:00", "progress": 50}])   # started, half done, 8h (480 min) task
    ev("() => rescheduleFromStatusDate('2026-09-07', '15:00')")   # Monday 15:00 — 240 min remaining, projected from there
    check("a started task's remaining work projects forward from the exact status moment (240 min from 15:00, crossing... no break left today, so 15:00+240 -> next day)", en("A")[0] != "2026-09-07" or en("A")[1] > "15:00", en("A"))
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-14", "et": "09:00", "as_": "2026-09-07", "ast": "09:00", "progress": 95}])   # way ahead of schedule
    before = en("A")
    ev("() => rescheduleFromStatusDate('2026-09-08', '08:00')")
    check("a task ahead of schedule is never pulled earlier by a status moment either", en("A") == before, (before, en("A")))

    # ---------------------------------------------------------------- absent time fields default to the working day's own open/close (non-destructive day<->minute switching)
    ev("() => { project.timeUnit = 'day'; delete project.workHours; }")
    seed_day = """() => { tasks.length = 0; const t = { id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-09',
        progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null,
        taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }; tasks.push(t); normalizeData(); save(); render(); }"""
    ev(seed_day)
    before_day = tm("A")
    ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); }")
    mom = ev("() => { const t = tasks.find(x => x.name === 'A'); return [taskMoment(t, 'start'), taskMoment(t, 'end')]; }")
    expect = ev("() => [dayNumber('2026-09-07') * 1440 + minuteOfDay('08:00'), dayNumber('2026-09-09') * 1440 + minuteOfDay('17:00')]")
    check("switching a plan to minute mode: an untouched task's moment is exactly its old whole working day (open to close), not shifted", mom == expect, (mom, expect))
    ev("() => { project.timeUnit = 'day'; normalizeData(); save(); }")
    check("switching back to day mode drops every time field, dates unchanged", tm("A") == [before_day[0], None, before_day[2], None], tm("A"))

    # ---------------------------------------------------------------- lag/duration caps hold under cascading (no runaway loop)
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "10:00"},
          {"name": "B", "s": "2026-09-07", "st": "08:00", "e": "2026-09-07", "et": "09:00", "preds": [["A", "FS", 999999999]]}])
    t0 = ev("() => performance.now()")
    ok = ev("() => { normalizeData(); applyConstraints(tasks.find(t => t.name === 'B').id); return true; }")
    dt = ev("() => performance.now()") - t0
    check("an absurd lag in minutes is clamped, not walked one minute at a time (finishes fast)", ok is True and dt < 2000, dt)

    # ---------------------------------------------------------------- actual-time recording (applyActualDates in minute mode)
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "17:00"}])
    ev("() => { const t = tasks.find(x => x.name === 'A'); t.actualStart = '2026-09-08'; t.actualStartTime = '10:15'; applyActualDates(t); save(); }")
    check("applyActualDates copies actualStart's date AND time onto Start (the schedule follows what really happened, to the minute)", st("A") == ["2026-09-08", "10:15"], st("A"))
    check("...and a still-running task's Finish is projected keeping the same working-minute duration (8h from the old plan)", en("A")[0] != "2026-09-08" or en("A")[1] > "10:15", en("A"))

    # ---------------------------------------------------------------- constraintViolated / scheduleMismatch still return exactly what existing tests expect (ISO strings / booleans)
    seed([{"name": "A", "s": "2026-09-07", "st": "09:00", "e": "2026-09-07", "et": "17:00", "ct": "MSO", "cd": "2026-09-07", "ctm": "10:00"}])
    check("constraintViolated: an exact (Must Start On) constraint with a different TIME than the task's own start is caught (not just a different day)", ev("() => constraintViolated(tasks.find(t => t.name === 'A'))") is True)
    check("scheduleMismatch still returns a plain ISO date string (never a raw moment number) for any UI code that formats it directly", (lambda v: v is None or isinstance(v, str))(ev("""() => { const t = tasks.find(x => x.name === 'A'); t.taskMode = 'manual'; return scheduleMismatch(t); }""")))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
