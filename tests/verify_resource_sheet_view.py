# -*- coding: utf-8 -*-
"""Resource Sheet, Stages 4-5 — the view itself: a new 4th view tab (Tasks | Gantt | Resources | Resource Sheet), a flat,
not-virtualized spreadsheet-style grid (one row per pool resource, every cell always a live input/select), direct/
immediate editing through the ordinary save()/render()/history cycle, Add/Remove, the shared rename/remove cascade
(renameResourceEverywhere()/removeResourceEverywhere()), the Days-off link opening the existing Resource pool dialog
focused on one row, and the currency picker. See "Resource Sheet" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate

    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.currencyCode; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }"
    seed = lambda specs: ev(SEED, specs)

    # ---------------------------------------------------------------- the view tab itself
    check("MAIN_VIEWS has a 4th 'Resource Sheet' tab, after Resources", ev("() => MAIN_VIEWS.map(v => v.id)") == ["tasks", "gantt", "resources", "resourceSheet"])
    tabs = pg.locator("#mainViewTabs .view-tab")
    check("4 view tabs render, the 4th labelled 'Resource Sheet'", tabs.count() == 4 and tabs.nth(3).inner_text() == "Resource Sheet")
    tabs.nth(3).click(); pg.wait_for_timeout(100)
    check("clicking it switches currentView and tags #main with .view-resourceSheet", ev("() => currentView") == "resourceSheet" and ev("() => document.getElementById('main').classList.contains('view-resourceSheet')"))
    check("...the pane is actually visible, the task grid pane and the two other timeline panes are hidden", ev("() => getComputedStyle(document.getElementById('resourceSheetPaneOuter')).display") != "none"
          and ev("() => getComputedStyle(document.getElementById('gridPane')).display") == "none" and ev("() => getComputedStyle(document.getElementById('ganttPaneOuter')).display") == "none" and ev("() => getComputedStyle(document.getElementById('resourcePaneOuter')).display") == "none")
    check("the zoom tabs (no timescale here) and the Gantt-only controls are hidden in this view", ev("() => document.getElementById('zoomTabs').classList.contains('hidden')") and ev("() => document.getElementById('criticalPathBtn').classList.contains('hidden')"))

    # ---------------------------------------------------------------- header, empty state, one row per resource
    heads = pg.locator("#resourceSheetHeader > div")
    check("the header has MS Project's own column order: #, Resource Name, Type, Material Label, Initials, Group, Max Units, Std Rate, Ovt Rate, Cost/Use, Accrue At, Code, Days Off (CSS uppercases them for display)",
          [heads.nth(i).inner_text() for i in range(13)] == [s.upper() for s in ["#", "Resource Name", "Type", "Material Label", "Initials", "Group", "Max Units", "Std Rate", "Ovt Rate", "Cost/Use", "Accrue At", "Code", "Days Off"]])
    check("...no 'Base Calendar' column — Milestone has one calendar per plan, a per-resource selector would do nothing", "Base Calendar" not in [heads.nth(i).inner_text() for i in range(heads.count())])
    check("with no pool at all, the empty-state message shows", ev("() => document.querySelector('.rst-empty')") is not None and "Add Resource" in ev("() => document.querySelector('.rst-empty').textContent"))

    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna:50%, Ben"}, {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna"}])
    ev("() => render()")
    rows = pg.locator(".rst-row")
    check("one row per POOL resource (not per assignment) — Anna and Ben, two rows, not three or four", rows.count() == 2)
    names = [rows.nth(i).locator('input[aria-label="Resource name"]').input_value() for i in range(2)]
    check("row #s are 1, 2 and the names match the (alphabetically sorted) pool", sorted(names) == ["Anna", "Ben"] and [rows.nth(i).locator(".rst-id").inner_text() for i in range(2)] == ["1", "2"])

    # ---------------------------------------------------------------- alignment: a real grid (not a stray class-name collision with an unrelated ".rs-row"), header and rows agree pixel-for-pixel, no cell's own text overflows its column
    check("the header and every row are real CSS grids (not overridden by some other, unrelated rule sharing a class name — see updateResourceSheetColumnLines()'s own comment)",
          ev("() => getComputedStyle(document.getElementById('resourceSheetHeader')).display") == "grid" and ev("() => getComputedStyle(document.querySelector('.rst-row')).display") == "grid")
    cols = ev("""() => { const h = getComputedStyle(document.getElementById('resourceSheetHeader')).gridTemplateColumns, r = getComputedStyle(document.querySelector('.rst-row')).gridTemplateColumns; return [h, r]; }""")
    check("the header's and a row's own resolved column widths are identical, track for track (so the two can never drift out of alignment)", cols[0] == cols[1], cols)
    check("the column-line CSS variables are actually populated (not left at their 'none' fallback) after a render", ev("() => getComputedStyle(document.getElementById('main')).getPropertyValue('--rst-col-lines-h').trim()") not in ("", "none"))
    overflow_h = ev("""() => [...document.querySelectorAll('#resourceSheetHeader > div')].map(el => el.scrollWidth - el.clientWidth)""")
    check("no header cell's own label text overflows its column (would read as truncated/overlapping the next column, like 'MAX UNITS' once did)", all(d <= 0 for d in overflow_h), overflow_h)
    accrue_select = pg.locator(".rst-row select[aria-label='Accrue at']").first
    check("a select cell's own chosen option isn't clipped either (e.g. 'Prorated', once cut to 'Proratec')", accrue_select.evaluate("el => el.scrollWidth <= el.clientWidth + 1"))
    type_select = pg.locator(".rst-row select[aria-label='Type']").first
    type_select.evaluate("el => el.focus()")
    focus_bg = type_select.evaluate("el => { const cs = getComputedStyle(el); return [cs.backgroundRepeat, cs.backgroundSize, cs.backgroundPosition]; }")
    check("a select's own chevron keeps its single, right-aligned position when focused/hovered (the hover/focus rule sets background-COLOR only, never the `background` shorthand — that shorthand once silently reset the chevron's background-repeat/position/size to their initial values, tiling it across the whole box)",
          focus_bg[0] == "no-repeat" and focus_bg[1] == "11px 7px", focus_bg)
    type_select.evaluate("el => el.blur()")

    # ---------------------------------------------------------------- editing: rename cascades, type/rate cells, live enabling
    anna_row = rows.filter(has=pg.locator('input[aria-label="Resource name"][value="Anna"]'))
    anna_row.locator('input[aria-label="Resource name"]').fill("Anna Schmidt")
    anna_row.locator('input[aria-label="Resource name"]').press("Tab"); pg.wait_for_timeout(120)
    check("renaming inline rewrites every task's Resource text, keeping each one's own % (A keeps Ben's, both keep the %/bare distinction)",
          ev("() => tasks.find(t => t.name === 'A').resource") == "Anna Schmidt:50%, Ben" and ev("() => tasks.find(t => t.name === 'B').resource") == "Anna Schmidt", ev("() => tasks.map(t => t.resource)"))
    check("...and the pool entry itself is renamed", ev("() => project.resources.find(r => r.name === 'Anna Schmidt')") is not None)

    rows = pg.locator(".rst-row")
    anna_row = rows.filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Resource name"]').fill("Ben")
    anna_row.locator('input[aria-label="Resource name"]').press("Tab"); pg.wait_for_timeout(120)
    check("renaming to an existing name (case-insensitive) is refused, nothing changes", ev("() => project.resources.map(r => r.name).sort()") == ["Anna Schmidt", "Ben"], ev("() => project.resources"))

    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Resource name"]').fill("  ")
    anna_row.locator('input[aria-label="Resource name"]').press("Tab"); pg.wait_for_timeout(120)
    check("clearing the name entirely is refused too (not silently removed)", "Anna Schmidt" in ev("() => project.resources.map(r => r.name)"))

    anna_row.locator('select[aria-label="Type"]').select_option("material")
    pg.wait_for_timeout(120)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    check("switching Type to Material enables Material Label, disables Ovt Rate (matches real MS Project's own greyed-out behavior)",
          not anna_row.locator('input[aria-label="Material label"]').is_disabled() and anna_row.locator('input[aria-label="Overtime rate per hour"]').is_disabled())
    anna_row.locator('select[aria-label="Type"]').select_option("cost")
    pg.wait_for_timeout(120)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    check("switching to Cost also disables Std Rate (a Cost resource is billed only by Cost/Use)", anna_row.locator('input[aria-label="Standard rate per hour"]').is_disabled())
    anna_row.locator('select[aria-label="Type"]').select_option("work")
    pg.wait_for_timeout(120)

    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Standard rate per hour"]').fill("47.5")
    anna_row.locator('input[aria-label="Standard rate per hour"]').press("Tab"); pg.wait_for_timeout(120)
    check("Std Rate commits and normalizeData() keeps it (2 decimals kept)", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').stdRate") == 47.5)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Max units, percent"]').fill("9999")
    anna_row.locator('input[aria-label="Max units, percent"]').press("Tab"); pg.wait_for_timeout(120)
    check("Max Units is clamped to 800 by the same normalizeData() cleaning every other route already goes through", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').maxUnits") == 800)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Group"]').fill("Engineering")
    anna_row.locator('input[aria-label="Group"]').press("Tab"); pg.wait_for_timeout(120)
    check("a plain text field (Group) commits too", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').group") == "Engineering")
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('select[aria-label="Accrue at"]').select_option("start")
    pg.wait_for_timeout(120)
    check("Accrue At commits", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').accrueAt") == "start")

    # ---------------------------------------------------------------- currency picker
    pg.select_option("#rsCurrencyInput", "EUR")
    pg.wait_for_timeout(120)
    check("the currency select writes project.currencyCode", ev("() => project.currencyCode") == "EUR")
    pg.select_option("#rsCurrencyInput", "USD")
    pg.wait_for_timeout(120)
    check("...and switching back to USD (the default) doesn't store it, same convention as everywhere else", ev("() => 'currencyCode' in project") == False)

    # ---------------------------------------------------------------- Days off link -> the existing Resource pool dialog, focused
    ben_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Ben"]'))
    ben_row.locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    check("clicking Days off opens the existing Resource pool dialog", ev("() => document.getElementById('resourcePoolModalBg').classList.contains('open')"))
    check("...with Ben's own row already scrolled to and its days-off details open (not the first row)", ev("() => { const items = [...document.querySelectorAll('#resourceRows .res-item')]; const i = items.findIndex(el => el.querySelector('.res-name').value === 'Ben'); return items[i] && items[i].querySelector('.res-days').open; }"))
    pg.click("#resourcePoolModalBg .modal-header button"); pg.wait_for_timeout(120)

    # ---------------------------------------------------------------- Add / Remove, shared cascade, Undo
    before = ev("() => (project.resources||[]).length")
    pg.click('.rst-toolbar button:has-text("Add Resource")'); pg.wait_for_timeout(120)
    check("Add Resource appends a new, editable, immediately-saved row", ev("() => (project.resources||[]).length") == before + 1)
    new_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value^="New resource"]'))
    check("...its name field is focused and selected, ready to type over", ev("() => document.activeElement.getAttribute('aria-label')") == "Resource name")

    new_id = ev("() => project.resources.find(r => r.name.startsWith('New resource')).id")
    ev(f"(id) => removeResourceSheetRow(id)", new_id)
    pg.wait_for_timeout(120)
    check("removing an UNUSED resource needs no confirmation — it's just gone", ev("() => (project.resources||[]).length") == before and ev("() => document.getElementById('confirmModalBg').classList.contains('open')") == False)

    ben_id = ev("() => project.resources.find(r => r.name === 'Ben').id")
    ev("(id) => removeResourceSheetRow(id)", ben_id)
    pg.wait_for_timeout(120)
    check("removing a resource IN USE asks for confirmation, naming it", ev("() => document.getElementById('confirmModalBg').classList.contains('open')") and "Ben" in ev("() => document.getElementById('confirmModalBody').textContent"))
    pg.click("#confirmModalBg .btn-primary"); pg.wait_for_timeout(120)
    check("...confirming removes it from the pool and strips it from every task's text (A's own % for Ben is gone, Anna Schmidt's kept)",
          "Ben" not in [r["name"] for r in ev("() => project.resources")] and "Ben" not in ev("() => tasks.find(t => t.name === 'A').resource"), ev("() => tasks.find(t => t.name === 'A').resource"))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    check("Ctrl+Z (the app's generic history) restores both the pool entry and the task text", "Ben" in [r["name"] for r in ev("() => project.resources")] and "Ben" in ev("() => tasks.find(t => t.name === 'A').resource"))

    # ---------------------------------------------------------------- the existing Resource pool dialog is unaffected (Stage 3's refactor was zero behavior change)
    check("verify_resource_pool_ui.py's own dialog is still reachable and untouched by any of this", ev("() => typeof openResourcePoolModal === 'function' && typeof applyResourcePoolDraft === 'function'"))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
