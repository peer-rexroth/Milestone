# -*- coding: utf-8 -*-
"""Cost tracking — an explicit user request ("build 1, 2 and 3" against a suggested feature list naming this "cost
tracking: rate per resource × work → task/rollup cost"). A plan-level daily rate per resource name and a currency
symbol (project.resourceRates / project.currency), a task's Cost = the sum of its assigned resources' rates × its
duration, rolled up bottom-up for a group; Cost to Date scales each leaf by its own % complete before summing. The
Resource rates dialog (plan menu), two new columns, the task dialog's Cost row, and the Excel export."""
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
    # ---------------------------------------------------------------- taskCost(): rate × duration, one resource
    seed("() => { tasks.push({id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null}); project.resourceRates = {Anna: 500}; }")
    cost = lambda n: ev("n => taskCost(tasks.find(t => t.name === n).id)", n)
    costToDate = lambda n: ev("n => taskCostToDate(tasks.find(t => t.name === n).id)", n)
    check("one resource: cost = rate × duration in working days (500 × 5)", cost("A") == 2500, cost("A"))

    # ---------------------------------------------------------------- two resources on one task: both rates, same days
    seed("() => { tasks.push({id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 50, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna, Ben', actualStart: null, actualFinish: null}); project.resourceRates = {Anna: 500, Ben: 300}; }")
    check("two resources on one task: both rates count for the same days (500+300) × 5", cost("A") == 4000, cost("A"))
    check("Cost to Date scales by the task's OWN % complete (4000 × 50%)", costToDate("A") == 2000, costToDate("A"))
    check("a resource with no rate set contributes nothing (not an error)", (lambda: (ev("() => { delete project.resourceRates.Ben; render(); }"), cost("A"))[1])() == 2500)

    # ---------------------------------------------------------------- milestones and TBD tasks cost nothing
    seed("() => { tasks.push({id: genId(), name: 'M', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: true, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null}); project.resourceRates = {Anna: 500}; }")
    check("a milestone costs nothing, even with a resource and a rate assigned", cost("M") == 0, cost("M"))
    seed("() => { tasks.push({id: genId(), name: 'T', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', startText: 'TBD', endText: null, durText: null, resource: 'Anna', actualStart: null, actualFinish: null}); project.resourceRates = {Anna: 500}; }")
    check("a TBD (free-text, unscheduled) task costs nothing — there is no duration to rate against", cost("T") == 0, cost("T"))

    # ---------------------------------------------------------------- rollup: a group is the SUM of its leaves, bottom-up
    seed("""() => {
      const g = {id: genId(), name: 'Group', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null};
      const a = {id: genId(), name: 'A', parentId: g.id, order: 0, startDate: '2026-09-07', endDate: '2026-09-09', progress: 100, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null};
      const c = {id: genId(), name: 'B', parentId: g.id, order: 1, startDate: '2026-09-10', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Ben', actualStart: null, actualFinish: null};
      tasks.push(g, a, c);
      project.resourceRates = {Anna: 500, Ben: 300};
    }""")
    check("a group's cost is the sum of its leaves (Anna 3d@500 + Ben 2d@300)", cost("Group") == 500 * 3 + 300 * 2, cost("Group"))
    check("...cost to date sums each leaf's OWN progress, not the group's rolled-up average", costToDate("Group") == 500 * 3 * 1.0 + 300 * 2 * 0, costToDate("Group"))

    # ---------------------------------------------------------------- the Resource rates dialog: lists resources in use, saves, updates the plan menu hint
    seed("() => { tasks.push({id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna, Ben', actualStart: null, actualFinish: null}); }")
    pg.click("#planBtnName"); pg.wait_for_timeout(100)
    check("the plan menu shows 'Resource rates…' with 'None set' until any are saved", "None set" in pg.inner_text("#planRatesItem"))
    pg.click("#planRatesItem"); pg.wait_for_selector("#ratesModalBg.open")
    check("it lists every resource USED on a task (Anna, Ben), even with no rate yet", pg.locator("#ratesList .rate-name").all_inner_texts() == ["Anna", "Ben"], pg.locator("#ratesList .rate-name").all_inner_texts())
    pg.fill("#ratesCurrencyInput", "€")
    inputs = pg.locator("#ratesList .rate-input"); inputs.nth(0).fill("500"); inputs.nth(1).fill("300")
    pg.click("#ratesModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("Save writes project.resourceRates and project.currency", ev("() => [project.resourceRates, project.currency]") == [{"Anna": 500, "Ben": 300}, "€"], ev("() => [project.resourceRates, project.currency]"))
    check("...and the task's cost now reflects it (500+300)×5", cost("A") == 4000, cost("A"))
    pg.click("#planBtnName"); pg.wait_for_timeout(100)
    check("the plan menu hint now says how many rates are set", "2 rates set" in pg.inner_text("#planRatesItem"))
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- a blank / zero rate is not stored, and is not an error
    pg.click("#planBtnName"); pg.wait_for_timeout(100); pg.click("#planRatesItem"); pg.wait_for_selector("#ratesModalBg.open")
    pg.locator("#ratesList .rate-input").nth(1).fill("0")
    pg.click("#ratesModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("a rate cleared to 0 is dropped from storage, not kept as a zero entry", ev("() => project.resourceRates") == {"Anna": 500}, ev("() => project.resourceRates"))

    # ---------------------------------------------------------------- columns: Cost / Cost to Date, formatted with the currency, filterable, and in the task dialog
    ev("() => { toggleColumn('cost', true); toggleColumn('costToDate', true); }"); pg.wait_for_timeout(150)
    grid_text = pg.evaluate("() => document.getElementById('gridRows').innerText")
    check("the grid shows Cost / Cost to Date formatted with the currency symbol", "€2,500" in grid_text or "€4,000" in grid_text or "€" in grid_text, grid_text[:300])
    check("Cost is a filterable number column", ev("() => FILTER_COLS.cost.kind") == "number")
    pg.click(".grid-row"); pg.dblclick(".grid-row .grid-name"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(150)
    check("the task dialog shows the Cost row once the plan has rates set", not pg.evaluate("() => document.getElementById('taskCostRow').classList.contains('hidden')"))
    check("...with the right values", pg.inner_text("#taskCostInfo") == "€2,500", pg.inner_text("#taskCostInfo"))
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- with no rates set at all, the dialog's Cost row stays hidden
    seed("() => { tasks.push({id: genId(), name: 'A', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null}); }")
    pg.click(".grid-row"); pg.dblclick(".grid-row .grid-name"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(150)
    check("the Cost row is hidden when the plan has never set a rate", pg.evaluate("() => document.getElementById('taskCostRow').classList.contains('hidden')"))
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- default position, and the migration for an install that already had columns saved
    check("Cost / Cost to Date default right after Resource, before the baseline/variance columns, in BOTH views", ev("() => { const t = DEFAULT_COL_ORDER.indexOf('resource'), g = GANTT_DEFAULT_ORDER.indexOf('resource'); return DEFAULT_COL_ORDER.slice(t, t + 3).join() === 'resource,cost,costToDate' && GANTT_DEFAULT_ORDER.slice(g, g + 3).join() === 'resource,cost,costToDate'; }"))
    stale_order = ["mode", "wbs", "name", "start", "end", "actualStart", "actualFinish", "duration", "progress", "preds", "remaining", "status", "baselineStart", "baselineFinish", "baselineDuration", "startVariance", "finishVariance", "durationVariance", "resource", "text1"]
    pg.evaluate("o => localStorage.setItem('milestone-prefs', JSON.stringify({theme: 'light', cols: {order: o, hidden: [], rev: 1}, gcols: {order: o, hidden: []}}))", stale_order)
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(150)
    check("a Tasks-view order saved BEFORE cost tracking existed (with a custom field already placed) is corrected once: Cost/Cost to Date land right after Resource, not after the custom field", ev("() => colOrder.slice(colOrder.indexOf('resource'), colOrder.indexOf('resource') + 3).join()") == "resource,cost,costToDate", ev("() => colOrder"))
    check("...the same correction reaches the Gantt view's own saved order (gcols never had a revision counter before this)", ev("() => gColOrder.slice(gColOrder.indexOf('resource'), gColOrder.indexOf('resource') + 3).join()") == "resource,cost,costToDate", ev("() => gColOrder"))
    ev("() => { moveColumn('cost', 1); moveColumn('cost', 1); save(); }")   # the user is then free to move it again themselves
    moved_to = ev("() => colOrder.indexOf('cost')")
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(150)
    check("...and a later reload does not fight that manual move back (the migration only ever runs once, gcols now saves its own revision)", ev("() => colOrder.indexOf('cost')") == moved_to)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
