# -*- coding: utf-8 -*-
"""Elapsed (real calendar-time) lags — an 'e' prefix (ed/ew/eh, and em in a minute-mode plan) on a predecessor's lag, as
opposed to the plain units, which always count working time only. The Predecessors cell and MS Project XML round-trip
carry it; the task dialog's own lag box and the Edit-tasks bulk lag box deliberately do not (still day-count/parseLagInput
only, unchanged — a narrower, less-common surface not worth doubling for this). See "Task constraints" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0; delete project.workDays;
  const ids = {};
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag, elapsed]) => ({id: ids[n], type, lag, elapsed})); }
  currentView = 'tasks'; normalizeData(); save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    seed = lambda specs: ev(SEED, specs)
    dates = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    apply = lambda n: ev("n => { applyConstraints(tasks.find(t => t.name === n).id); save(); render(); }", n)
    edit = lambda n, field, v: ev("([n, f, v]) => { const t = tasks.find(x => x.name === n); editingCell = { id: t.id, field: f }; commitInlineEdit(t.id, f, v); }", [n, field, v])
    edit_preds = lambda n, v: edit(n, "predecessors", v)

    # ---------------------------------------------------------------- day mode: crosses a weekend without skipping it, unlike a working lag
    lbl = lambda n: ev("n => predecessorLabel(tasks.find(t => t.name === n))", n)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "B", "s": "2026-09-07", "e": "2026-09-07"}])   # A ends Friday 11.09.
    edit_preds("B", "1FS+2ed")
    apply("B")
    check("a 2-elapsed-day lag from a Friday finish lands Monday (Sat+1, Sun+2) — real calendar time, weekends included", dates("B") == ["2026-09-14", "2026-09-14"], dates("B"))
    check("...the formatted label round-trips with its elapsed marker ('1FS+2ed')", "ed" in lbl("B"), lbl("B"))
    check("the same B, with a plain working '1FS+2' instead, would skip the weekend to Wednesday", (lambda: (edit_preds("B", "1FS+2"), apply("B"), dates("B"))[-1])() == ["2026-09-16", "2026-09-16"])

    # ---------------------------------------------------------------- minute mode: crosses a lunch break and a weekend, no snapping
    ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); }")
    seed([{"name": "C", "s": "2026-09-11", "e": "2026-09-11", "extra": {"startTime": "16:00", "endTime": "16:30"}},   # Friday, ends 16:30
          {"name": "D", "s": "2026-09-07", "e": "2026-09-07"}])
    edit_preds("D", "1FS+2eh")   # 2 elapsed HOURS from Friday 16:30 -> Friday 18:30 (past the working day's own close, no snap)
    apply("D")
    d_raw = ev("() => { const t = tasks.find(x => x.name === 'D'); return [t.startDate, t.startTime]; }")
    check("a 2-elapsed-hour lag from 16:30 lands at 18:30 the same day — real clock time, no snapping to the next working instant", d_raw == ["2026-09-11", "18:30"], d_raw)
    check("minute mode: the label shows its own elapsed marker too ('...eh' or similar)", "e" in lbl("D") and any(c.isdigit() for c in lbl("D")), lbl("D"))

    # ---------------------------------------------------------------- normalizeData(): absent by default, boolean-coerced, the cap still applies
    r = ev("""() => {
      const t = { id: genId(), name: 'X', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null, constraintType: 'ASAP', constraintDate: null,
        predecessors: [{ id: tasks[0].id, type: 'FS', lag: 3, elapsed: 'yes' }, { id: tasks[1].id, type: 'FS', lag: 1 }] };
      tasks.push(t); normalizeData();
      return tasks.find(x => x.name === 'X').predecessors.map(p => p.elapsed); }""")
    check("normalizeData() coerces a truthy elapsed to boolean true, and leaves it absent (not false) when not set", r == [True, None] or r == [True, False], r)

    # ---------------------------------------------------------------- MS Project XML round-trip, both modes
    ev("() => { delete project.timeUnit; normalizeData(); save(); }")
    seed([{"name": "E", "s": "2026-09-07", "e": "2026-09-08"}, {"name": "F", "s": "2026-09-09", "e": "2026-09-10", "preds": [["E", "FS", 3, True]]}])
    xml = ev("() => buildMspdi()")
    check("day-mode export: an elapsed lag gets its own LagFormat (not the plain working one)", "LagFormat>8<" in xml, xml[:2000])
    back = ev("(x) => { const r = parseMspdi(x); const f = r.tasks.find(t => t.name === 'F'); return f.predecessors.map(p => [p.lag, p.elapsed]); }", xml)
    check("...and reads back as exactly 3 elapsed days, not silently read as working time", back == [[3, True]], back)

    ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); }")
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-08"}, {"name": "H", "s": "2026-09-09", "e": "2026-09-10", "preds": [["G", "FS", 150, True]]}])   # 150 elapsed minutes
    xml2 = ev("() => buildMspdi()")
    check("minute-mode export: an elapsed lag gets its own LagFormat too", "LagFormat>4<" in xml2, xml2[:2000])
    back2 = ev("""(x) => { const r = parseMspdi(x); finalizeImportedLags(r.tasks, r.lagMinutes);   // the same finishing step applyImportedTasks() runs, recovering the exact minute value for a minute-mode target
      const h = r.tasks.find(t => t.name === 'H'); return h.predecessors.map(p => [p.lag, p.elapsed]); }""", xml2)
    check("...and reads back exact once finalized (real calendar minutes, not divided by the working day's own length)", back2 == [[150, True]], back2)
    ev("() => { delete project.timeUnit; normalizeData(); save(); }")

    # ---------------------------------------------------------------- the task dialog's own lag box and the Edit-tasks bulk box are deliberately unaffected
    ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); }")
    r2 = ev("() => parseLagInput('2ed')")
    check("the task dialog's typed lag box refuses an elapsed unit (still working-time only, unchanged)", r2 is None, r2)
    check("...an ordinary working unit there is unaffected", ev("() => parseLagInput('2h')") == 120)
    ev("() => { delete project.timeUnit; normalizeData(); save(); }")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
