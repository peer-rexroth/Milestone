# -*- coding: utf-8 -*-
"""Resource Sheet, Stages 4-5 — the view itself: a new 4th view tab (Tasks | Gantt | Resources | Resource Sheet), a flat,
not-virtualized spreadsheet-style grid (one row per pool resource, every cell always a live input/select), direct/
immediate editing through the ordinary save()/render()/history cycle, Add/Remove, the shared rename/remove cascade
(renameResourceEverywhere()/removeResourceEverywhere()), the Days-off link opening the Days off dialog
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
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate

    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.currencyCode; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }"
    seed = lambda specs: ev(SEED, specs)

    # ---------------------------------------------------------------- reached from the top bar's Resources button, not a view tab
    check("the Resource Sheet is not a view tab: the tabs are Tasks, Gantt | Resource Plan", ev("() => MAIN_VIEWS.map(v => v.id)") == ["tasks", "gantt", "resources"] and [t.strip() for t in pg.locator("#mainViewTabs .view-tab").all_inner_texts()] == ["Tasks", "Gantt", "Resource Plan"])
    ev("() => setView('gantt')"); pg.wait_for_timeout(80)
    pg.click("#resourcesBtn"); pg.wait_for_timeout(100)
    check("the top bar's Resources button opens it: marked pressed, no view tab active, the toolbar titled 'Resources'",
          pg.get_attribute("#resourcesBtn", "aria-pressed") == "true" and pg.locator("#mainViewTabs .view-tab.active").count() == 0 and "Resources" in pg.inner_text("#resourceSheetTitle"))
    check("clicking it switches currentView and tags #main with .view-resourceSheet", ev("() => currentView") == "resourceSheet" and ev("() => document.getElementById('main').classList.contains('view-resourceSheet')"))
    check("...the pane is actually visible, the task grid pane and the two other timeline panes are hidden", ev("() => getComputedStyle(document.getElementById('resourceSheetPaneOuter')).display") != "none"
          and ev("() => getComputedStyle(document.getElementById('gridPane')).display") == "none" and ev("() => getComputedStyle(document.getElementById('ganttPaneOuter')).display") == "none" and ev("() => getComputedStyle(document.getElementById('resourcePaneOuter')).display") == "none")
    vis = lambda i: ev("i => document.getElementById(i).offsetParent !== null", i)
    check("the toolbar is the Resource Sheet's own: Add Resource and Currency — no zoom, no Gantt toggles, no task buttons (Add Task, Find, Columns)",
          vis("addResourceBtn") and pg.locator("#rsCurrencyInput").count() == 0 and not any(vis(i) for i in ["zoomTabs", "criticalPathBtn", "addTaskBtn", "searchBtn", "columnsBtn"]))
    check("...and there is no third bar above the sheet any more", pg.locator(".rst-toolbar").count() == 0)

    pg.click("#resourcesBtn"); pg.wait_for_timeout(100)
    check("the button again goes back to the view you came from (Gantt)", ev("() => currentView") == "gantt" and pg.get_attribute("#resourcesBtn", "aria-pressed") == "false")
    pg.click("#resourcesBtn"); pg.wait_for_timeout(80); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("...and so does Escape", ev("() => currentView") == "gantt")
    pg.click("#resourcesBtn"); pg.wait_for_timeout(80); pg.click("#mainViewTabs .view-tab:has-text('Tasks')"); pg.wait_for_timeout(100)
    check("...and a view tab goes to that view", ev("() => currentView") == "tasks")
    pg.click("#resourcesBtn"); pg.wait_for_timeout(80)
    ev("() => document.querySelector('#resourceSheetBody input') && document.querySelector('#resourceSheetBody input').focus()")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    check("Escape while typing in a sheet cell does not leave the sheet", ev("() => currentView") == "resourceSheet" or ev("() => !document.querySelector('#resourceSheetBody input')"))
    ev("() => setView('resourceSheet')")

    # ---------------------------------------------------------------- header, empty state, one row per resource
    heads = pg.locator("#resourceSheetHeader > div")
    check("the header has MS Project's own column order: #, Resource Name, Type, Material Label, Group, Max Units, Std Rate, Ovt Rate, Cost/Use, Accrue At, Code, Days Off (CSS uppercases them for display)",
          [heads.nth(i).inner_text().split("(")[0].strip() for i in range(12)] == [s.upper() for s in ["#", "Resource Name", "Type", "Material Label", "Group", "Max Units", "Std Rate", "Ovt Rate", "Cost/Use", "Accrue At", "Code", "Days Off"]])
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
    # Only the two DROPDOWNS (Type, Accrue At) get the app's own dialog-field look — Bulk edit's .bulk-ctl, Calendar's .cal-sec (7px rounded corners, a real 1px border always visible,
    # a native focus ring). An earlier pass over-applied this to every text/number cell too and was scoped back to
    # just the dropdowns, per explicit feedback — text/number cells deliberately keep the task grid's own
    # .inline-edit look (minimal, borderless until interacted with), unchanged.
    select_style = ev("""() => { const el = document.querySelector('.rst-row select[aria-label="Type"]'); const cs = getComputedStyle(el);
      return [cs.borderRadius, cs.borderTopWidth, el.className]; }""")
    check("the Type dropdown has the dialog-field look: 7px rounded corners, a real 1px border, its own .rst-select class (not .inline-edit)",
          select_style[0] == "7px" and select_style[1] == "1px" and "rst-select" in select_style[2] and "inline-edit" not in select_style[2], select_style)
    type_select.evaluate("el => el.focus()")
    check("...and the native focus ring actually shows on a dropdown when focused (not suppressed)", type_select.evaluate("el => getComputedStyle(el).outlineStyle") != "none")
    type_select.evaluate("el => el.blur()")
    name_style = ev("""() => { const el = document.querySelector('.rst-row input[aria-label="Resource name"]'); return el.className; }""")
    check("...while a text cell (Resource Name) is deliberately UNCHANGED — still the task grid's own .inline-edit, not .rst-select/.rst-field", "inline-edit" in name_style and "rst-select" not in name_style and "rst-field" not in name_style, name_style)

    # ---------------------------------------------------------------- editing: rename cascades, type/rate cells, live enabling
    anna_row = rows.filter(has=pg.locator('input[aria-label="Resource name"][value="Anna"]'))
    anna_row.locator('input[aria-label="Resource name"]').fill("Anna Schmidt")
    anna_row.locator('input[aria-label="Resource name"]').press("Tab"); pg.wait_for_timeout(120)
    check("renaming inline rewrites every task's Resource text, keeping each one's own % (A keeps Ben's, both keep the %/bare distinction)",
          ev("() => tasks.find(t => t.name === 'A').resource") == "Anna Schmidt[50%], Ben" and ev("() => tasks.find(t => t.name === 'B').resource") == "Anna Schmidt", ev("() => tasks.map(t => t.resource)"))
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

    # Which cells have a box at all, per type: a field that doesn't apply is an empty cell, not a disabled box.
    boxes = ev("""() => { const r = project.resources.find(x => x.name === 'Anna Schmidt'), old = r.type, out = {};
      for (const t of ['work', 'material', 'cost']) { r.type = t; render(); const row = document.querySelector(`.rst-row[data-id="${r.id}"]`);
        out[t] = { na: [...row.querySelectorAll('.rst-na')].map(c => c.dataset.field), disabled: row.querySelectorAll('input:disabled, select:disabled').length }; }
      r.type = old; render(); return out; }""")
    check("a Work resource has a box for everything but Material Label", boxes["work"] == {"na": ["materialLabel"], "disabled": 0}, boxes["work"])
    check("a Material resource has no box for Max Units, Ovt Rate or Days off (as in MS Project)", boxes["material"] == {"na": ["maxUnits", "ovtRate", "daysOff"], "disabled": 0}, boxes["material"])
    check("a Cost resource has only Cost/Use — no Material Label, Max Units, Std/Ovt Rate or Days off", boxes["cost"] == {"na": ["materialLabel", "maxUnits", "stdRate", "ovtRate", "daysOff"], "disabled": 0}, boxes["cost"])
    check("...and no disabled boxes anywhere — a field you can't fill in isn't shown as a box", all(b["disabled"] == 0 for b in boxes.values()))

    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Standard rate per hour"]').fill("47.5")
    anna_row.locator('input[aria-label="Standard rate per hour"]').press("Tab"); pg.wait_for_timeout(120)
    check("Std Rate commits and normalizeData() keeps it (2 decimals kept)", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').stdRate") == 47.5)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    check("a Work resource's Max Units reads as a percentage ('100%')", anna_row.locator('input[aria-label="Max units, percent"]').input_value() == "100%", anna_row.locator('input[aria-label="Max units, percent"]').input_value())
    anna_row.locator('input[aria-label="Max units, percent"]').fill("9999")
    anna_row.locator('input[aria-label="Max units, percent"]').press("Tab"); pg.wait_for_timeout(120)
    check("Max Units is capped at 800%, with a toast saying so", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').maxUnits") == 800 and "at most 800%" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Max units, percent"]').fill("300")
    anna_row.locator('input[aria-label="Max units, percent"]').press("Tab"); pg.wait_for_timeout(120)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    check("above 100% is allowed, as in MS Project (300% = three people pooled into one resource), shown as '300%'", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').maxUnits") == 300 and anna_row.locator('input[aria-label="Max units, percent"]').input_value() == "300%")
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Max units, percent"]').fill("50 %")
    anna_row.locator('input[aria-label="Max units, percent"]').press("Tab"); pg.wait_for_timeout(120)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    check("'50 %' is read as 50 and shown back as '50%'", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').maxUnits") == 50 and anna_row.locator('input[aria-label="Max units, percent"]').input_value() == "50%")
    anna_row.locator('input[aria-label="Max units, percent"]').fill("lots")
    anna_row.locator('input[aria-label="Max units, percent"]').press("Tab"); pg.wait_for_timeout(120)
    check("something that isn't a number is refused and nothing changes", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').maxUnits") == 50 and "percentage" in pg.inner_text("#toastMsg"))
    # ---------------------------------------------------------------- switching type resets everything type-dependent
    ev("() => { historyCoalesceMs = 0; }")   # each edit its own Undo step, so Ctrl+Z below takes back exactly the type switch
    ev("() => { const r = project.resources.find(x => x.name === 'Anna Schmidt'); Object.assign(r, { ovtRate: 70, costPerUse: 12, daysOff: [{date: '2026-12-24'}] }); save(); render(); }")
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('select[aria-label="Type"]').select_option("material"); pg.wait_for_timeout(150)
    a = ev("() => project.resources.find(x => x.name === 'Anna Schmidt')")
    check("Work -> Material clears Std Rate (per hour isn't per unit), Ovt Rate, Cost/Use and days off, and Max Units goes back to 100%",
          a.get("type") == "material" and not any(k in a for k in ("stdRate", "ovtRate", "costPerUse", "daysOff")) and a["maxUnits"] == 100, a)
    check("...with a toast naming what was cleared", all(w in pg.inner_text("#toastMsg") for w in ("Material", "Std Rate", "Ovt Rate", "Cost/Use", "days off")), pg.inner_text("#toastMsg"))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    a = ev("() => project.resources.find(x => x.name === 'Anna Schmidt')")
    check("Ctrl+Z brings the type and every cleared value back in one step", "type" not in a and a.get("stdRate") == 47.5 and a.get("ovtRate") == 70 and a.get("costPerUse") == 12 and a.get("maxUnits") == 50 and a.get("daysOff"), a)
    ev("() => { const r = project.resources.find(x => x.name === 'Anna Schmidt'); r.type = 'material'; r.materialLabel = 'tons'; r.stdRate = 9; delete r.ovtRate; delete r.daysOff; save(); render(); }")
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('select[aria-label="Type"]').select_option("cost"); pg.wait_for_timeout(150)
    a = ev("() => project.resources.find(x => x.name === 'Anna Schmidt')")
    check("Material -> Cost clears Material Label, Std Rate and Cost/Use too", a.get("type") == "cost" and not any(k in a for k in ("materialLabel", "stdRate", "costPerUse")), a)
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    ev("() => { document.getElementById('toastMsg').textContent = ''; }")
    anna_row.locator('select[aria-label="Type"]').select_option("work"); pg.wait_for_timeout(150)
    check("switching a resource with nothing to clear shows no toast about clearing", "cleared" not in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    check("normalizeData() drops values that don't apply to the type, whatever route they came in by (import, a merge, a file)",
          ev("() => { const keep = JSON.stringify({ r: project.resources, t: tasks }); project.resources = [{id: genId(), name: 'Z', type: 'cost', maxUnits: 300, stdRate: 5, ovtRate: 6, costPerUse: 7, materialLabel: 'x', daysOff: [{date: '2026-12-24'}]}]; const t0 = tasks.splice(0); normalizeData(); const out = Object.keys(project.resources[0]).sort().join(','); const k = JSON.parse(keep); project.resources = k.r; tasks.push(...t0); normalizeData(); return out; }") == "costPerUse,id,maxUnits,name,type")
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('input[aria-label="Group"]').fill("Engineering")
    anna_row.locator('input[aria-label="Group"]').press("Tab"); pg.wait_for_timeout(120)
    check("a plain text field (Group) commits too", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').group") == "Engineering")
    anna_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Anna Schmidt"]'))
    anna_row.locator('select[aria-label="Accrue at"]').select_option("start")
    pg.wait_for_timeout(120)
    check("Accrue At commits", ev("() => project.resources.find(r => r.name === 'Anna Schmidt').accrueAt") == "start")

    # ---------------------------------------------------------------- currency picker
    heads = ev("() => [...document.querySelectorAll('#resourceSheetHeader > div')].filter(d => d.querySelector('.rst-cur')).map(d => d.textContent.trim())")
    check("the money columns name the currency in their header (Std Rate (€), Ovt Rate (€), Cost/Use (€))", heads == ["Std Rate(€)", "Ovt Rate(€)", "Cost/Use(€)"], heads)
    pg.locator("#resourceSheetHeader .rst-cur").first.click(); pg.wait_for_timeout(150)
    check("...clicking it opens Plan settings on the Currency tab (its one editor)", pg.locator("#currencyModalBg.open").count() == 1)
    pg.select_option("#planCurrencyInput", "USD"); pg.click("#currencyModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("the setting writes project.currencyCode and the headers follow ($)", ev("() => project.currencyCode") == "USD" and "($)" in pg.inner_text("#resourceSheetHeader"))
    ev("() => setCurrencyCode('EUR')"); pg.wait_for_timeout(100)
    check("...and switching back to EUR (the default) doesn't store it, same convention as everywhere else", ev("() => 'currencyCode' in project") == False)

    # ---------------------------------------------------------------- Days off link -> the Days off dialog for that one resource
    ben_row = pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Ben"]'))
    ben_row.locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    check("clicking Days off opens the Days off dialog for that resource (Ben, not the first row)",
          ev("() => document.getElementById('resourceDaysModalBg').classList.contains('open') && resourceDaysId === project.resources.find(r => r.name === 'Ben').id") and "Ben" in pg.inner_text("#resourceDaysModalBg h2"))
    pg.click("#resourceDaysModalBg .modal-header button"); pg.wait_for_timeout(120)

    # ---------------------------------------------------------------- Add / Remove, shared cascade, Undo
    before = ev("() => (project.resources||[]).length")
    pg.click('#addResourceBtn'); pg.wait_for_timeout(120)
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

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
