# -*- coding: utf-8 -*-
"""The Resources view — an explicit user request ("resource view / overallocation": the resource field existed but
nothing showed who was double-booked). A third main view, one card per resource named on some task: workload, cost
(once rates are set), overallocation grouped into ranges with the overlapping tasks named, a task list that jumps
back to Tasks view on click, and an empty state when no task has a resource yet."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    def seed(js):
        ev("() => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0; delete project.workDays; delete project.resourceRates; delete project.currency; }")
        ev(js)
        ev("() => { normalizeData(); save(); render(); }")
    goto_resources = lambda: (pg.click("button.view-tab:has-text('Resources')"), pg.wait_for_timeout(150))

    # ---------------------------------------------------------------- empty state
    seed("() => { tasks.push({id: genId(), name: 'X', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); }")
    goto_resources()
    check("with no task using Resource, the view shows an empty state", "No task has a Resource" in pg.inner_text("#resourcesPane"))
    check("...and hides the subbar (Add Task / Find / Columns don't apply here)", pg.evaluate("() => document.getElementById('subbar').classList.contains('hidden')"))
    check("...and the grid/Gantt panes are hidden", not pg.locator(".grid-pane").is_visible() and not pg.locator(".gantt-pane-outer").is_visible())

    # ---------------------------------------------------------------- workload and overallocation
    seed("""() => {
      tasks.push({id: genId(), name: 'Design', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null});
      tasks.push({id: genId(), name: 'Build', parentId: null, order: 1, startDate: '2026-09-10', endDate: '2026-09-16', progress: 0, milestone: false, color: 'blue', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna, Ben', actualStart: null, actualFinish: null});
      tasks.push({id: genId(), name: 'Launch', parentId: null, order: 2, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: true, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null});
      project.resourceRates = {Anna: 500, Ben: 300};
    }""")
    check("resourceWorkload sums duration across a resource's tasks (Design 5 + Build 5 = 10, milestone excluded)", ev("() => resourceWorkload('Anna').totalDays") == 10, ev("() => resourceWorkload('Anna').totalDays"))
    check("a milestone is excluded even though the resource is on it", ev("() => resourceWorkload('Anna').items.length") == 2)
    check("cost is THIS resource's own rate × duration, not the shared task's whole cost", ev("() => resourceWorkload('Anna').totalCost") == 500 * 10 and ev("() => resourceWorkload('Ben').totalCost") == 300 * 5, [ev("() => resourceWorkload('Anna').totalCost"), ev("() => resourceWorkload('Ben').totalCost")])
    check("overlapping tasks (Design & Build share 09-10/09-11) are flagged, Ben (one task only) is not", ev("() => resourceWorkload('Anna').overlapRanges.length") == 1 and ev("() => resourceWorkload('Ben').overlapRanges.length") == 0)
    check("the overlap range names both tasks", set(ev("() => resourceWorkload('Anna').overlapRanges[0].tasks.map(t => t.name)")) == {"Design", "Build"})
    check("the overlap range is exactly the two shared working days", ev("() => [resourceWorkload('Anna').overlapRanges[0].start, resourceWorkload('Anna').overlapRanges[0].end]") == ["2026-09-10", "2026-09-11"])

    goto_resources()
    cards = pg.locator(".res-card")
    check("one card per resource, Anna and Ben", cards.count() == 2 and pg.locator(".res-name").all_inner_texts() == ["Anna", "Ben"], pg.locator(".res-name").all_inner_texts())
    anna = cards.nth(0)
    check("Anna's card shows 2 tasks, 10 working days, $5,000 (not the shared task's combined $4,000+ for BOTH people)", "2" in anna.locator(".res-stat").nth(0).inner_text() and "10" in anna.locator(".res-stat").nth(1).inner_text() and "$5,000" in anna.locator(".res-stat").nth(2).inner_text(), anna.inner_text())
    check("...and a red double-booked badge", "double-booked" in anna.locator(".res-warn").inner_text())
    check("...with the overlap row naming the dates and both tasks", "Design" in anna.locator(".res-overlap-row").inner_text() and "Build" in anna.locator(".res-overlap-row").inner_text())
    ben = cards.nth(1)
    check("Ben's card has no overlap badge (only on one task)", ben.locator(".res-warn").count() == 0)
    check("Ben's total is his own rate only ($1,500), not inflated by Anna's rate on the same task", "$1,500" in ben.locator(".res-stat").nth(2).inner_text(), ben.inner_text())

    # ---------------------------------------------------------------- clicking a task jumps to Tasks view and selects it
    build_id = ev("() => tasks.find(t => t.name === 'Build').id")
    pg.locator(".res-task-row", has_text="Build").first.click()
    pg.wait_for_timeout(200)
    check("clicking a task row switches to Tasks view", ev("() => currentView") == "tasks")
    check("...and selects that task", ev("() => selectedTaskId") == build_id)
    check("...the row is visible (flashed) in the grid", pg.locator(f".grid-row[data-id='{build_id}']").count() == 1)

    # ---------------------------------------------------------------- no rates set: cost figures are hidden, not shown as $0
    seed("() => { tasks.push({id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Cara', actualStart: null, actualFinish: null}); }")
    goto_resources()
    check("with no resource rates set, no card shows a cost figure", pg.locator(".res-card .res-stat", has_text="$").count() == 0)
    check("...the task count and working days still show", "1" in pg.inner_text(".res-card .res-stat >> nth=0") and "5" in pg.inner_text(".res-card .res-stat >> nth=1"))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
