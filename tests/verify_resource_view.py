# -*- coding: utf-8 -*-
"""Resource levelling, Stage 4 — the Resources view. A third Tasks | Gantt | Resources tab (`MAIN_VIEWS`) sharing the
Gantt view's zoom tabs, pixel math (`ganttXAt`/`renderGanttHeaderTicks`) and shared `dateRange`; its own sticky-header/
sticky-name-column single-scroll-container layout (`#resourceScroll`) with its own independent row-virtualization
(`resourceRenderedWin`/`refreshResourceWindowIfNeeded`/`onResourceScroll`, mirroring but separate from the task grid's
own). `renderResourceUsage()` draws one row per pool resource with a load segment per working day, colored red where
`overallocatedResources()` flags it, plus the same non-working-time shading Gantt itself draws. See "Resource
levelling" in CLAUDE.md."""
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

    # ---------------------------------------------------------------- basic rendering: the tab, its rows, its segments
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09", "r": "Anna"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"}])
    pg.click("button.view-tab:has-text('Resource Plan')")
    check("the Resource Plan tab (id 'resources') is the last view tab, after Tasks and Gantt", ev("() => MAIN_VIEWS.map(v => v.id)") == ["tasks", "gantt", "resources"])
    check("switching to it sets the view-resources class", "view-resources" in pg.get_attribute("#main", "class"))
    check("zoom tabs are visible in the Resource Plan view (shared with Gantt), in the status bar", ev("() => document.getElementById('zoomTabs').offsetParent !== null"))
    check("...with Fit and 'Over-allocated only' beside them, and no task buttons", ev("() => ['fitZoomBtn', 'overOnlyBtn'].every(i => document.getElementById(i).offsetParent !== null) && document.getElementById('addTaskBtn').offsetParent === null"))
    check("the grid pane and Gantt pane are hidden", pg.locator(".grid-pane:visible").count() == 0 and pg.locator(".gantt-pane-outer:visible").count() == 0)
    check("one row for the one pool resource (Anna)", pg.locator("#resourceBody .resource-row").count() == 1)
    segs = ev("() => [...document.querySelectorAll('#resourceBody .res-load-seg')].map(e => [Number(e.dataset.d1) - Number(e.dataset.d0) + 1, e.classList.contains('over'), e.textContent.trim()])")
    check("the 4-day span is three runs of equal load — 100%, 200%, 100% — each labelled with its %", [(x[0], x[2]) for x in segs] == [(1, "100%"), (2, "200%"), (1, "100%")], segs)
    check("exactly the 2 truly-overlapping days are colored over (one red run)", [x[1] for x in segs] == [False, True, False], segs)
    pg.locator("#resourceBody .res-load-seg.over").click(); pg.wait_for_timeout(120)
    items = pg.locator("#loadMenu .dropdown-item").all_inner_texts()
    check("clicking the red run lists the tasks behind it (A and B, 100% each) and offers Level resources", pg.locator("#loadMenu.open").count() == 1 and any("A" in i and "100%" in i for i in items) and any("B" in i for i in items) and any("Level resources" in i for i in items), items)
    pg.locator("#loadMenu .dropdown-item", has_text="B").click(); pg.wait_for_timeout(150)
    check("...and a task there opens it in the Gantt, selected", ev("() => currentView") == "gantt" and ev("() => byId(selectedTaskId).name") == "B")
    ev("() => setView('resources')"); pg.wait_for_timeout(100)
    check("a legend explains the colours, and Level… is in this toolbar", ev("() => document.getElementById('resLegend').offsetParent !== null && document.getElementById('levelResBtn').offsetParent !== null"))
    check("the row itself is flagged over (red name)", "over" in pg.get_attribute("#resourceBody .resource-row", "class"))
    check("the name cell shows the resource's name", pg.inner_text("#resourceBody .resource-name-cell").strip() == "Anna")
    check("no console or page errors", not errors, errors[:5])

    # ---------------------------------------------------------------- the view survives a reload, like Tasks/Gantt already did
    pg.reload(); pg.wait_for_selector("#undoBtn")
    check("reloading while in the Resources view stays in it (not silently dropped back to Tasks)", ev("() => currentView") == "resources", ev("() => currentView"))
    check("...and the Resources tab is marked active again after the reload", "active" in pg.get_attribute("button.view-tab:has-text('Resource Plan')", "class"))

    # ---------------------------------------------------------------- the empty state
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08"}])
    ev("() => { delete project.resources; save(); render(); }")
    check("no pool -> the empty state, not a crash", pg.locator("#resourceBody .empty-state").count() == 1 and pg.locator("#resourceBody .resource-row").count() == 0)
    check("the empty state names where to add one", "Resource Sheet" in pg.inner_text("#resourceBody .empty-state"))

    # ---------------------------------------------------------------- zoom switching within the Resources view
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09", "r": "Anna"}])
    pg.click("button.view-tab:has-text('Resource Plan')")
    for label in ["Week", "Month", "Year"]:
        pg.click(f"#zoomTabs button:has-text('{label}')")
        pg.wait_for_timeout(50)
        check(f"{label} zoom renders the header ticks with no error", pg.locator("#resourceTimelineHead .gantt-tick").count() > 0, label)
    check("no errors across zoom switching", not errors, errors[:5])

    # ---------------------------------------------------------------- non-working-time shading (mirrors Gantt's own)
    seed([{"name": "A", "s": "2026-09-01", "e": "2026-09-25", "r": "Anna"}])
    pg.click("button.view-tab:has-text('Resource Plan')")
    pg.click("#zoomTabs button:has-text('Week')")
    pg.wait_for_timeout(50)
    check("Week zoom shades the weekends", pg.locator("#resourceBody .gantt-nonwork").count() > 0)
    pg.click("#zoomTabs button:has-text('Year')")
    pg.wait_for_timeout(50)
    check("Year zoom (1.5px/day) shows no shading (would just be noise, matching Gantt)", pg.locator("#resourceBody .gantt-nonwork").count() == 0)

    # ---------------------------------------------------------------- virtualization at scale (many pool resources)
    many = [{"name": f"T{i}", "s": "2026-09-07", "e": "2026-09-08", "r": f"Res{i:03d}"} for i in range(200)]
    seed(many)
    n_pool = ev("() => project.resources.length")
    check("200 distinct names -> 200 pool resources", n_pool == 200, n_pool)
    pg.click("button.view-tab:has-text('Resource Plan')")
    win = ev("() => resourceRenderedWin")
    check("virtualization kicks in past the threshold", win["virtual"] is True, win)
    built = pg.locator("#resourceBody .resource-row").count()
    check("only a window of rows is actually built, not all 200", 0 < built < 200, built)
    sc_h = ev("() => document.getElementById('resourceBody').style.height")
    check("the body's full height still reflects all 200 rows (32px each)", sc_h == "6400px", sc_h)
    # scroll to the middle and confirm the window follows, with no errors
    ev("() => { const sc = document.getElementById('resourceScroll'); sc.scrollTop = 3000; sc.dispatchEvent(new Event('scroll')); }")
    pg.wait_for_timeout(150)
    win2 = ev("() => resourceRenderedWin")
    check("scrolling moves the built window", win2["from"] > 0, win2)
    check("the row for a resource now in view is actually present", pg.locator(f"#resourceBody .resource-row[data-row-id=\"{ev('() => project.resources[100].id')}\"]").count() == 1)
    check("no errors from virtualized scrolling at scale", not errors, errors[:5])

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
