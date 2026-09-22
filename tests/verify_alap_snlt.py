# -*- coding: utf-8 -*-
"""True ALAP (As Late As Possible) and enforced SNLT/FNLT (Start/Finish No Later Than) — an explicit user request
("build 1, 2 and 3" against a suggested feature list naming both together). ALAP used to behave identically to ASAP;
SNLT/FNLT used to be flagged when violated but never enforced. See "Task constraints" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0; delete project.workDays;
  const ids = {};
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: sp.ct || 'ASAP', constraintDate: sp.cd || null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag})); }
  currentView = 'tasks'; normalizeData(); save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seed = lambda specs: pg.evaluate(SEED, specs)
    dates = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    violated = lambda n: pg.evaluate("n => constraintViolated(tasks.find(x => x.name === n))", n)
    edit = lambda n, field, v: pg.evaluate("([n, f, v]) => { const t = tasks.find(x => x.name === n); editingCell = { id: t.id, field: f }; commitInlineEdit(t.id, f, v); }", [n, field, v])

    # ---------------------------------------------------------------- true ALAP: pulled to the latest date a successor allows
    # C's own SNET floor (an independent anchor — a successor with no anchor of its own would just chase wherever B ends up,
    # which has no well-defined "as late as possible" answer at all: a documented degenerate case, not what this tests).
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "B", "s": "2026-09-10", "e": "2026-09-14", "ct": "ALAP", "preds": [["A", "FS", 0]]},
          {"name": "C", "s": "2026-09-10", "e": "2026-09-11", "ct": "SNET", "cd": "2026-09-30", "preds": [["B", "FS", 0]]}])
    pg.evaluate("() => { applyConstraints(tasks.find(t => t.name === 'C').id); save(); }")
    check("an ALAP task is pulled to the latest date that does not delay its successor (not just after its predecessor)", dates("B") == ["2026-09-25", "2026-09-29"], dates("B"))
    check("...its successor lands at its own anchor (the pull satisfies the link exactly, no oscillation)", dates("C") == ["2026-09-30", "2026-10-01"], dates("C"))
    check("...the ALAP task still respects its own predecessor as a floor (starts after A finishes, not before)", pg.evaluate("() => dayNumber(tasks.find(t=>t.name==='B').startDate) > dayNumber(tasks.find(t=>t.name==='A').endDate)"))

    # ---------------------------------------------------------------- multiple successors: the EARLIEST one binds
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "B", "s": "2026-09-10", "e": "2026-09-11", "ct": "ALAP", "preds": [["A", "FS", 0]]},
          {"name": "Early", "s": "2026-09-10", "e": "2026-09-11", "ct": "SNET", "cd": "2026-09-21", "preds": [["B", "FS", 0]]},
          {"name": "Late", "s": "2026-09-10", "e": "2026-09-11", "ct": "SNET", "cd": "2026-09-30", "preds": [["B", "FS", 0]]}])
    pg.evaluate("() => { applyConstraints(tasks.find(t => t.name === 'Early').id); applyConstraints(tasks.find(t => t.name === 'Late').id); save(); }")
    check("with two successors, the ALAP task is bounded by whichever needs it EARLIER, not the later one", dates("B") == ["2026-09-17", "2026-09-18"], dates("B"))

    # ---------------------------------------------------------------- over-constrained: the predecessor (a real dependency) wins, never violated silently
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-18"},   # long: A finishes 09-18, so B's own earliest (from A) is 09-21
          {"name": "B", "s": "2026-09-21", "e": "2026-09-22", "ct": "ALAP", "preds": [["A", "FS", 0]]},
          {"name": "C", "s": "2026-09-21", "e": "2026-09-22", "ct": "SNET", "cd": "2026-09-21", "preds": [["B", "FS", 0]]}])   # C "wants" 09-21 too — no room at all
    pg.evaluate("() => { applyConstraints(tasks.find(t => t.name === 'C').id); save(); }")
    check("over-constrained ALAP (predecessor needs it later than the successor has room for) keeps the predecessor's date", dates("B") == ["2026-09-21", "2026-09-22"], dates("B"))
    check("...and its ASAP successor is still pushed out to make room, exactly as for any ordinary predecessor", dates("C")[0] > "2026-09-21", dates("C"))

    # ---------------------------------------------------------------- no successors: falls back to the earliest bound (behaves like ASAP)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "B", "s": "2026-09-25", "e": "2026-09-25", "ct": "ALAP", "preds": [["A", "FS", 0]]}])
    edit("A", "duration", "3")   # trigger a cascade re-check on B
    check("an ALAP task with no successors sits at the earliest its own links allow (nothing local to be late against)", dates("B") == ["2026-09-10", "2026-09-10"], dates("B"))

    # ---------------------------------------------------------------- SNLT / FNLT now actually cap a forward push
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "X", "s": "2026-09-10", "e": "2026-09-11", "ct": "SNLT", "cd": "2026-09-10", "preds": [["A", "FS", 0]]}])
    edit("A", "duration", "10")   # would normally push X's start out past 09-10
    check("Start No Later Than caps a predecessor's forward push instead of only flagging it", dates("X")[0] == "2026-09-10", dates("X"))
    check("...and the task is no longer reported violated once the cap has been applied", not violated("X"))
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "Y", "s": "2026-09-10", "e": "2026-09-14", "ct": "FNLT", "cd": "2026-09-11", "preds": [["A", "FS", 0]]}])
    edit("A", "duration", "10")
    check("Finish No Later Than caps a forward push on the finish side too", dates("Y")[1] == "2026-09-11", dates("Y"))
    check("...(basis = finish, so the cap lands on the FINISH date, start is derived backward)", pg.evaluate("() => dayNumber(tasks.find(t=>t.name==='Y').startDate) < dayNumber('2026-09-11')"))

    # ---------------------------------------------------------------- a constraint alone (no push) still just flags, never moves the task on its own
    seed([{"name": "Z", "s": "2026-09-21", "e": "2026-09-22", "ct": "SNLT", "cd": "2026-09-10"}])
    check("an upper-bound constraint with nothing pushing the task does NOT yank it backward by itself", dates("Z") == ["2026-09-21", "2026-09-22"], dates("Z"))
    check("...but it IS reported violated (the residual case constraintViolated() still catches)", violated("Z"))

    # ---------------------------------------------------------------- reload persists whatever the engine computed
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "B", "s": "2026-09-10", "e": "2026-09-14", "ct": "ALAP", "preds": [["A", "FS", 0]]},
          {"name": "C", "s": "2026-09-10", "e": "2026-09-11", "ct": "SNET", "cd": "2026-09-30", "preds": [["B", "FS", 0]]}])
    pg.evaluate("() => { applyConstraints(tasks.find(t => t.name === 'C').id); save(); }")   # seed() alone never runs the cascade — trigger the ALAP pull first
    before = dates("B")
    check("...the seeded chain really did pull B (sanity check before reloading)", before != ["2026-09-10", "2026-09-14"], before)
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(150)
    check("reload keeps the ALAP placement (nothing recomputes it differently on load)", dates("B") == before, [before, dates("B")])

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
