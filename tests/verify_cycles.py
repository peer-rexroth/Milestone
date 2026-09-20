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
  currentView = 'tasks'; normalizeData(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seed = lambda specs: pg.evaluate(SEED, specs)
    cyc = lambda: sorted(pg.evaluate("() => [...taskCycleSet()].map(id => byId(id).name)"))
    dates = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    T = lambda n, s, e, preds=None, extra=None: {"name": n, "s": s, "e": e, **({"preds": preds} if preds else {}), **({"extra": extra} if extra else {})}

    seed([T("A", "2026-09-07", "2026-09-08", [["B", "FS", 0]]), T("B", "2026-09-09", "2026-09-10", [["A", "FS", 0]]), T("C", "2026-09-11", "2026-09-11", [["B", "FS", 0]]), T("U", "2026-09-07", "2026-09-07")])
    seed([T("A", "2026-09-07", "2026-09-08"), T("B", "2026-09-09", "2026-09-10", [["A", "FS", 0]]), T("C", "2026-09-11", "2026-09-11", [["B", "FS", 0]]), T("U", "2026-09-07", "2026-09-07")])
    pg.evaluate("() => { const a = tasks.find(t => t.name === 'A'), b = tasks.find(t => t.name === 'B'); a.predecessors = [{ id: b.id, type: 'FS', lag: 0 }]; }")
    check("a two-task cycle: exactly its two members are flagged", cyc() == ["A", "B"], cyc())
    check("...a task DOWNSTREAM of the cycle (C, after B) is not a member, nor is an unrelated one", "C" not in cyc() and "U" not in cyc())
    seed([T("P", "2026-09-07", "2026-09-07"), T("A", "2026-09-08", "2026-09-08", [["P", "FS", 0], ["C", "FS", 0]]), T("B", "2026-09-09", "2026-09-09", [["A", "FS", 0]]), T("C", "2026-09-10", "2026-09-10", [["B", "FS", 0]])])
    check("a task UPSTREAM of a three-task cycle (P) is not a member either", cyc() == ["A", "B", "C"], cyc())
    seed([T("A", "2026-09-07", "2026-09-07", [["B", "FS", 0]]), T("B", "2026-09-08", "2026-09-08", [["A", "FS", 0]]), T("X", "2026-09-07", "2026-09-07", [["Y", "SS", 1]]), T("Y", "2026-09-08", "2026-09-08", [["X", "FF", 0]])])
    check("two separate cycles are both found", cyc() == ["A", "B", "X", "Y"], cyc())
    seed([T("A", "2026-09-07", "2026-09-07", [["B", "FS", 0], ["C", "FS", 0]]), T("B", "2026-09-08", "2026-09-08", [["A", "FS", 0]]), T("C", "2026-09-09", "2026-09-09")])
    check("a task that is in a cycle AND feeds a task outside it: only the cycle is flagged", cyc() == ["A", "B"], cyc())

    # order independence
    seed([T("A", "2026-09-07", "2026-09-07", [["B", "FS", 0]]), T("B", "2026-09-08", "2026-09-08", [["A", "FS", 0]]), T("C", "2026-09-09", "2026-09-09", [["B", "FS", 0]]), T("D", "2026-09-10", "2026-09-10", [["C", "FS", 0]])])
    ref = cyc()
    ok = pg.evaluate("""() => { const base = [...taskCycleSet()].map(id => byId(id).name).sort().join(); const orig = tasks.slice();
      for (let k = 0; k < 24; k++) { const sh = orig.slice().sort(() => Math.random() - .5); tasks = sh; const r = [...taskCycleSet()].map(id => byId(id).name).sort().join(); if (r !== base) { tasks = orig; return false; } }
      tasks = orig; return true; }""")
    check("the answer does not depend on the order of the tasks (24 shuffles)", ok and ref == ["A", "B"], ref)

    # scheduling
    seed([T("A", "2026-09-07", "2026-09-08"), T("B", "2026-09-09", "2026-09-10", [["A", "FS", 0]]), T("C", "2026-09-30", "2026-09-30", [["B", "FS", 0]])])
    pg.evaluate("() => { const a = tasks.find(t => t.name === 'A'), b = tasks.find(t => t.name === 'B'); a.predecessors = [{ id: b.id, type: 'FS', lag: 0 }]; normalizeData(); const c = tasks.find(t => t.name === 'C'); applyConstraints(c.id); }")
    check("a task after a cycle is placed by its links (C: the working day after B's finish, 11.09.), the cycle members are left alone", dates("C") == ["2026-09-11", "2026-09-11"] and dates("A") == ["2026-09-07", "2026-09-08"] and dates("B") == ["2026-09-09", "2026-09-10"], (dates("A"), dates("B"), dates("C")))
    pg.evaluate("() => { const b = tasks.find(t => t.name === 'B'); editingCell = { id: b.id, field: 'predecessors' }; commitInlineEdit(b.id, 'predecessors', ''); }")
    check("clearing B's links breaks the cycle: A (which follows B) is released and placed after B", dates("A")[0] == "2026-09-11" or dates("A")[0] >= "2026-09-11", dates("A"))
    check("...and the warning is gone", cyc() == [])

    # depth
    n = pg.evaluate("""() => { tasks.length = 0; for (let i = 0; i < 2500; i++) tasks.push({ id: 'q' + i, name: 'Q' + i, parentId: null, order: i, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: i ? [{ id: 'q' + (i - 1), type: 'FS', lag: 0 }] : [{ id: 'q2499', type: 'FS', lag: 0 }], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
      const t0 = performance.now(); const s = taskCycleSet(); return [s.size, performance.now() - t0]; }""")
    check("a 2500-task ring is one cycle, found without overflowing the stack, quickly", n[0] == 2500 and n[1] < 1500, n)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
