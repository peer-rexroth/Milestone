from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """(specs) => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); delete project.workDays; delete project.holidays;
  const ids = {};
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag})); }
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seed = lambda specs: pg.evaluate(SEED, specs)
    crit = lambda: sorted(pg.evaluate("() => [...criticalPathAnalysis().critical].map(id => byId(id).name)"))
    flt = lambda n: pg.evaluate("n => criticalPathAnalysis().float.get(byId(tasks.find(t => t.name === n).id) && tasks.find(t => t.name === n).id)", n)
    T = lambda n, s, e, preds=None, extra=None: {"name": n, "s": s, "e": e, **({"preds": preds} if preds else {}), **({"extra": extra} if extra else {})}

    # ---------------------------------------------------- Finish-to-Start, the basics
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-14", "2026-09-16", [["A", "FS", 0]]), T("C", "2026-09-17", "2026-09-18", [["B", "FS", 0]]), T("D", "2026-09-07", "2026-09-08")])
    check("a Finish-to-Start chain is critical end to end; a parallel task that finishes early is not", crit() == ["A", "B", "C"], crit())
    check("...D's total float = working days between its finish (08.09.) and the project's (18.09.) = 8", flt("D") == 8, flt("D"))
    check("...critical tasks have float 0", flt("A") == 0 and flt("C") == 0)
    seed([T("A", "2026-09-07", "2026-09-07")])
    check("a single task is the critical path", crit() == ["A"])
    seed([])
    check("an empty plan has no critical path (and no error)", crit() == [])

    # ---------------------------------------------------- lag
    seed([T("A", "2026-09-07", "2026-09-08"), T("B", "2026-09-16", "2026-09-16", [["A", "FS", 5]]), T("C", "2026-09-09", "2026-09-14", [["A", "FS", 0]])])
    check("a lag counts: A -> B (lag +5) reaches the end of the project, the longer-but-lag-free C has 2 days of float", crit() == ["A", "B"] and flt("C") == 2, (crit(), flt("C")))

    # ---------------------------------------------------- Start-to-Start
    seed([T("A", "2026-09-07", "2026-09-18"), T("B", "2026-09-07", "2026-09-09", [["A", "SS", 0]])])
    check("Start-to-Start: B starts with A and ends long before the project does -> only A is critical (as an FS chain it would have made B critical)", crit() == ["A"] and flt("B") == 7, (crit(), flt("B")))
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-09", "2026-09-18", [["A", "SS", 2]])])
    check("Start-to-Start +2: A must start 2 days before B, B runs to the end -> both critical", crit() == ["A", "B"], crit())
    seed([T("A", "2026-09-07", "2026-09-08"), T("B", "2026-09-09", "2026-09-18", [["A", "SS", 2]]), T("X", "2026-09-07", "2026-09-07")])
    check("...and a task that could start earlier than its lagged successor requires has float only where it really has it (A: SS+2, B critical -> A's late start = B's late start - 2 = its own start)", "A" in crit() and "B" in crit(), crit())

    # ---------------------------------------------------- Finish-to-Finish
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-10", "2026-09-11", [["A", "FF", 0]]), T("D", "2026-09-14", "2026-09-16", [["B", "FS", 0]])])
    check("Finish-to-Finish: B finishes with A, D follows B -> the whole chain A, B, D is critical", crit() == ["A", "B", "D"], crit())
    seed([T("A", "2026-09-07", "2026-09-10"), T("B", "2026-09-10", "2026-09-11", [["A", "FF", 1]]), T("E", "2026-09-07", "2026-09-07")])
    check("...FF with a lag of 1: A (ends 10.09.) drives B (ends 11.09.); B is at the end, A must finish one day before it", crit() == ["A", "B"], crit())

    # ---------------------------------------------------- Start-to-Finish
    seed([T("X", "2026-09-14", "2026-09-18"), T("Y", "2026-09-10", "2026-09-14", [["X", "SF", 0]])])
    check("Start-to-Finish: Y must finish when X starts. X (the project's last task) is critical, Y (ends 14.09., 4 working days early) is not", crit() == ["X"] and flt("Y") == 4, (crit(), flt("Y")))

    # ---------------------------------------------------- a date the user pinned, the calendar, holidays
    seed([T("A", "2026-09-07", "2026-09-08"), T("B", "2026-09-16", "2026-09-17", [["A", "FS", 0]], {"constraintType": "SNET", "constraintDate": "2026-09-16"}), T("C", "2026-09-18", "2026-09-18", [["B", "FS", 0]])])
    check("a task pinned later than its links allow (SNET 16.09.) is critical with the tasks after it; the task before it has the gap as float", crit() == ["B", "C"] and flt("A") == 5, (crit(), flt("A")))
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-14", "2026-09-15", [["A", "FS", 0]])])
    check("weekends between tasks are not float (the chain over the weekend is critical)", crit() == ["A", "B"])
    pg.evaluate("() => { project.holidays = [{ date: '2026-09-14', to: '2026-09-15' }]; normalizeData(); }")
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-16", "2026-09-17", [["A", "FS", 0]])])
    pg.evaluate("() => { project.holidays = [{ date: '2026-09-14', to: '2026-09-15' }]; normalizeData(); render(); }")
    check("holidays are not float either (A, then two days off, then B: still critical)", crit() == ["A", "B"], crit())
    pg.evaluate("() => { delete project.holidays; }")

    # ---------------------------------------------------- who takes part
    seed([T("A", "2026-09-07", "2026-09-11"), T("M", "2026-09-14", "2026-09-30", [["A", "FS", 0]], {"taskMode": "manual"}), T("B", "2026-09-14", "2026-09-15", [["A", "FS", 0]])])
    check("a Manual task is left out (it neither is critical nor stretches the project end)", crit() == ["A", "B"], crit())
    seed([T("G", "2026-09-07", "2026-09-11"), T("K", "2026-09-07", "2026-09-11", None, {"parentId": "PLACEHOLDER"})])
    pg.evaluate("() => { const g = tasks.find(t => t.name === 'G'); tasks.find(t => t.name === 'K').parentId = g.id; normalizeData(); render(); }")
    check("a summary task is not on the path, its sub-task is", crit() == ["K"], crit())
    seed([T("A", "2026-09-07", "2026-09-08"), T("B", "2026-09-09", "2026-09-10", [["A", "FS", 0]])])
    pg.evaluate("() => { const a = tasks.find(t => t.name === 'A'), b = tasks.find(t => t.name === 'B'); a.predecessors = [{ id: b.id, type: 'FS', lag: 0 }]; }")
    check("a dependency cycle takes part in nothing and does not hang", crit() == [], crit())
    seed([T("A", "2026-09-07", "2026-09-11", None, {"actualStart": "2026-09-07", "actualFinish": "2026-09-11", "progress": 100}), T("B", "2026-09-14", "2026-09-16", [["A", "FS", 0]])])
    check("a finished task is part of the analysis (its actual dates drive the chain)", crit() == ["A", "B"], crit())
    seed([T("A", "2026-09-07", "2026-09-07"), T("MS", "2026-09-08", "2026-09-08", [["A", "FS", 0]], {"milestone": True})])
    check("milestones are one-day tasks in the chain", crit() == ["A", "MS"], crit())

    # ---------------------------------------------------- a bigger network
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-14", "2026-09-18", [["A", "FS", 0]]), T("C", "2026-09-14", "2026-09-16", [["A", "FS", 0]]),
          T("D", "2026-09-21", "2026-09-22", [["B", "FS", 0], ["C", "FS", 0]]), T("E", "2026-09-17", "2026-09-18", [["C", "SS", 3]])])
    check("a diamond: A, B, D are critical; C (2 days shorter than B) has 2 days of float; E (starts 3 days after C, ends 18.09.) has 2 days", crit() == ["A", "B", "D"] and flt("C") == 2 and flt("E") == 2, (crit(), flt("C"), flt("E")))
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-14", "2026-09-18", [["A", "FS", 0]]), T("C", "2026-09-14", "2026-09-16", [["A", "FS", 0]]),
          T("D", "2026-09-21", "2026-09-22", [["B", "FS", 0], ["C", "FS", 0]]), T("E", "2026-09-17", "2026-09-22", [["C", "SS", 3]])])
    check("...but when E runs to the end of the project, its Start-to-Start link makes C critical too (C may not start later than E allows)", crit() == ["A", "B", "C", "D", "E"] and flt("C") == 0, (crit(), flt("C")))

    # ---------------------------------------------------- the chart
    seed([T("A", "2026-09-07", "2026-09-11"), T("B", "2026-09-14", "2026-09-16", [["A", "FS", 0]]), T("D", "2026-09-07", "2026-09-08")])
    pg.evaluate("() => setView('gantt')"); pg.wait_for_timeout(200)
    pg.click("#criticalPathBtn"); pg.wait_for_timeout(200)
    marked = pg.evaluate("() => [...document.querySelectorAll('.gantt-bar.critical')].map(e => (byId(e.dataset.id) || {}).name).sort()")
    check("the critical-path button outlines exactly the critical bars", marked == ["A", "B"], marked)
    check("...and the arrow between two critical tasks is drawn critical", pg.evaluate("() => document.querySelectorAll('svg.gantt-deps path.critical').length") == 1)
    pg.click("#criticalPathBtn"); pg.wait_for_timeout(100)
    check("switching it off clears them", pg.evaluate("() => document.querySelectorAll('.gantt-bar.critical').length") == 0)

    # ---------------------------------------------------- speed
    t = pg.evaluate("""() => { tasks.length = 0; for (let i = 0; i < 400; i++) tasks.push({ id: 'p' + i, name: 'T' + i, parentId: null, order: i, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: i ? [{ id: 'p' + (i - 1 - (i % 3 === 0 ? 1 : 0)), type: ['FS','SS','FF','SF'][i % 4], lag: i % 5 }] : [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
      const t0 = performance.now(); const r = criticalPathAnalysis(); return [performance.now() - t0, r.critical.size >= 1]; }""")
    check("400 linked tasks with all four link types: the analysis takes well under a second", t[0] < 1000 and t[1], t)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
