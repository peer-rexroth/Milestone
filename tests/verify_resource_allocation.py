# -*- coding: utf-8 -*-
"""Resource levelling, Stage 3 — over-allocation detection. resourceLoadByDay() sums every non-group task's assigned %
across the working days it spans (uniform across the span — Milestone has no per-day Work-distribution profile the way
MS Project does, a deliberate simplification); overallocatedResources() flags a working day where the sum exceeds a
resource's own max units, or ANY load at all on a day the resource has taken off (capacity 0 that day, not merely
excluded). Surfaced via the Schedule menu's own "Level resources…" hint and the Resources view's red coloring — an
earlier top-bar badge (mirroring the sync-conflict badge) was removed at the user's request, one more thing in the bar
they didn't want to see. See "Resource levelling" in CLAUDE.md."""
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
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.workDays; delete project.holidays; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }"
    seed = lambda specs: ev(SEED, specs)
    # 2026-09-07 is a Monday
    resId = lambda name: ev("n => project.resources.find(r => r.name === n).id", name)

    # ---------------------------------------------------------------- basic overlap: two 100%-assigned tasks overlapping 2 days
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09", "r": "Anna"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"}])
    aid = resId("Anna")
    load = ev("id => [...resourceLoadByDay(id).values()].sort((a,b) => a-b)", aid)
    check("load sums across the overlap: 100, 100, 200, 200 across the four days", load == [100, 100, 200, 200], load)
    over = ev("() => overallocatedResources()")
    check("exactly the 2 truly-overlapping days are flagged, not the whole span", len(over) == 1 and over[0]["name"] == "Anna" and len(over[0]["days"]) == 2, over)
    check("there is no top-bar badge for it any more", pg.locator("#resourceOverallocBtn").count() == 0)
    check("the Schedule menu's Level resources… item shows the count instead", (pg.click("#scheduleMenuBtn"), "1 over-allocated" in pg.inner_text("#planLevelItem"))[1])
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- fixing the overlap clears it
    ev("() => { const b = tasks.find(t => t.name === 'B'); b.startDate = '2026-09-10'; b.endDate = '2026-09-11'; normalizeData(); save(); render(); }")
    check("no more overlap -> no over-allocation", ev("() => overallocatedResources()") == [])

    # ---------------------------------------------------------------- max units below 100% lowers the bar, above 100% raises it
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna:30%"}, {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna:20%"}])
    ev("() => { project.resources[0].maxUnits = 50; save(); render(); }")
    check("30% + 20% fit exactly within a 50% max-units resource — not over-allocated", ev("() => overallocatedResources()") == [])
    ev("() => { const t = { id: genId(), name: 'C', parentId: null, order: 2, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna:1%', actualStart: null, actualFinish: null }; tasks.push(t); normalizeData(); save(); render(); }")
    check("...but one percent more (51%) tips it over", len(ev("() => overallocatedResources()")) == 1)
    check("max units above 100% is allowed (several people pooled into one resource): 200% is kept", ev("() => { project.resources[0].maxUnits = 200; normalizeData(); return project.resources[0].maxUnits; }") == 200)
    check("...and at 200% the 51% that tipped it over now fits", ev("() => { save(); render(); return overallocatedResources(); }") == [])
    check("...but not above 800% — normalizeData() caps it", ev("() => { project.resources[0].maxUnits = 9999; normalizeData(); return project.resources[0].maxUnits; }") == 800)

    # ---------------------------------------------------------------- Material and Cost resources have no capacity
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Concrete:300%, Permit:250%"}])
    ev("() => { for (const r of project.resources) r.type = r.name === 'Concrete' ? 'material' : 'cost'; save(); render(); }")
    check("a Material or Cost resource is never over-allocated, however much is assigned (no Max Units, as in MS Project)", ev("() => overallocatedResources()") == [])

    # ---------------------------------------------------------------- a day off makes ANY assignment that day a conflict, even alone
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-07", "r": "Anna"}])
    ev("() => { normalizeData(); project.resources[0].daysOff = [{date: '2026-09-07'}]; save(); render(); }")
    over2 = ev("() => overallocatedResources()")
    check("a single 100% assignment on the resource's own day off is flagged (capacity is 0 that day, not merely excluded)", len(over2) == 1 and over2[0]["days"] == [ev("() => dayNumber('2026-09-07')")], over2)

    # ---------------------------------------------------------------- a group's assignment text never contributes load; weekends/non-working days are skipped
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-11", "r": "Anna"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-11", "parent": "G", "r": "Ben"}])
    check("only the leaf's assignment (Ben) counts — the group's own text does not create Anna load", ev("() => project.resources.map(r => r.name)") == ["Ben"], ev("() => project.resources"))
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-13", "r": "Anna"}])   # Mon 07 .. Sun 13, includes the weekend
    check("the weekend inside a task's span carries no load (not a working day)", ev("id => resourceLoadByDay(id).size", resId("Anna")) == 5, ev("id => [...resourceLoadByDay(id).keys()].length", resId("Anna")))

    # ---------------------------------------------------------------- no resource pool at all: nothing errors
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08"}])
    ev("() => { delete project.resources; save(); render(); }")
    check("with no pool nothing is flagged and nothing errors", ev("() => overallocatedResources()") == [])

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
