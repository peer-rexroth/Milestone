# -*- coding: utf-8 -*-
"""Navigation: (A) a top bar that holds only app-level things and a toolbar that belongs to the view you are in — with a
"More" menu instead of wrapping on a narrow window; (B) the view tabs Tasks · Gantt | Resource Sheet · Resource Plan;
(C) one Plan settings window with tabs (Calendar, Precision, Scheduling rules, Currency, Custom fields). See "Navigation:
top bar, toolbar, views, Plan settings" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("""() => { tasks.length = 0; const mk = (id, name, s, e, extra) => Object.assign({ id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
      tasks.push(mk('a', 'Design', '2026-09-07', '2026-09-18', { resource: 'Anna' }), mk('b', 'Build', '2026-09-14', '2026-09-25', { resource: 'Anna, Ben' }), mk('c', 'Launch', '2026-10-09', '2026-10-09', { milestone: true }));
      normalizeData(); save(); setSelection([]); render(); }""")
    vis = lambda i: ev("i => { const e = document.getElementById(i); return !!e && e.offsetParent !== null; }", i)
    def view(v): ev("v => setView(v)", v); pg.wait_for_timeout(120)

    # ---------------------------------------------------------------- A: the top bar holds only app-level things
    top = ev("() => [...document.querySelectorAll('.topbar button')].filter(e => e.offsetParent).map(e => e.id).filter(Boolean)")
    check("the top bar has the plan switcher, Schedule, Data, theme — and no zoom / baseline / critical path any more",
          all(i in top for i in ["planMenuBtn", "scheduleMenuBtn", "dataMenuBtn", "themeToggleBtn"]) and not any(i in top for i in ["zoomTabs", "baselineBtn", "criticalPathBtn"]), top)
    pos = {}
    for v in ["tasks", "gantt", "resourceSheet", "resources"]:
        view(v); pos[v] = ev("() => ['scheduleMenuBtn', 'dataMenuBtn', 'themeToggleBtn'].map(i => Math.round(document.getElementById(i).getBoundingClientRect().left))")
    check("...so its buttons stay put when you switch views (nothing appears or disappears there)", len({tuple(x) for x in pos.values()}) == 1, pos)
    for w in (1600, 1280, 1100, 1000, 900):
        pg.set_viewport_size({"width": w, "height": 800}); pg.wait_for_timeout(100)
        ok = ev("() => ['planMenuBtn', 'scheduleMenuBtn', 'dataMenuBtn', 'themeToggleBtn'].every(i => { const r = document.getElementById(i).getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; })")
        check(f"{w}px: every top-bar button is on screen (the wordmark and menu labels give way first)", ok)
    pg.set_viewport_size({"width": 1500, "height": 900})

    # ---------------------------------------------------------------- A: the toolbar belongs to the view
    view("tasks")
    check("Tasks: Add Task, Find, Columns, Task Form — no zoom, no Gantt toggles, no Add Resource", all(vis(i) for i in ["addTaskBtn", "searchBtn", "columnsBtn", "taskFormBtn"]) and not any(vis(i) for i in ["zoomTabs", "baselineBtn", "criticalPathBtn", "addResourceBtn"]))
    view("gantt")
    check("Gantt: the same plus the timescale, Fit, and labelled Baseline / Critical path toggles", all(vis(i) for i in ["addTaskBtn", "zoomTabs", "fitZoomBtn", "baselineBtn", "criticalPathBtn"]) and "Baseline" in pg.inner_text("#baselineBtn") and "Critical path" in pg.inner_text("#criticalPathBtn"))
    before = ev("() => showCriticalPath")
    pg.click("#criticalPathBtn")
    check("a toggle shows its state (aria-pressed)", ev("() => showCriticalPath") != before and pg.get_attribute("#criticalPathBtn", "aria-pressed") == ("true" if not before else "false"))
    pg.click("#criticalPathBtn")
    view("resourceSheet")
    check("Resource Sheet: Add Resource and Currency — no task buttons, and no third bar above the sheet", vis("addResourceBtn") and vis("rsCurrencyInput") and not any(vis(i) for i in ["addTaskBtn", "searchBtn", "zoomTabs"]) and pg.locator(".rst-toolbar").count() == 0)
    view("resources")
    check("Resource Plan: the timescale, Fit, 'Edit resources…' and 'Over-allocated only' — no task buttons", all(vis(i) for i in ["zoomTabs", "fitZoomBtn", "editResourcesBtn", "overOnlyBtn"]) and not vis("addTaskBtn"))
    rows = lambda: pg.locator("#resourceBody .resource-row").count()
    all_rows = rows()
    pg.click("#overOnlyBtn"); pg.wait_for_timeout(120)
    check("'Over-allocated only' narrows it to Anna (100% + 100% on overlapping days)", all_rows == 2 and rows() == 1 and "Anna" in pg.inner_text("#resourceBody"), (all_rows, rows()))
    ev("() => { byId('b').resource = 'Ben'; normalizeData(); save(); render(); }")
    check("...with nobody over-allocated it says so, with a way back", "Nobody is over-allocated" in pg.inner_text("#resourceBody"))
    pg.click("#resourceBody .btn-link"); pg.wait_for_timeout(120)
    check("...'show everyone' turns it off again", rows() == 2 and pg.get_attribute("#overOnlyBtn", "aria-pressed") == "false")

    # ---------------------------------------------------------------- Fit
    view("gantt"); ev("() => { zoom = 'year'; save(); render(); }")
    pg.click("#fitZoomBtn"); pg.wait_for_timeout(150)
    z = ev("() => currentZoom().id")
    fits = ev("() => { const r = computeDateRange(); return (r.end - r.start) * currentZoom().pxPerDay <= document.getElementById('ganttPaneOuter').clientWidth; }")
    check("Fit picks the most detailed scale that still shows the whole plan (a 5-week plan: Week or Month, not Year)", z in ("week", "month") and fits, (z, fits))

    # ---------------------------------------------------------------- A: a narrow window moves buttons into "More" instead of wrapping
    ev("() => { setSelection(['a']); render(); }")
    for w in (1500, 1100, 900, 760):
        pg.set_viewport_size({"width": w, "height": 800}); pg.wait_for_timeout(150)
        m = ev("""() => { const bar = document.getElementById('subbar'), R = e => e.getBoundingClientRect();
          const vis = [...bar.querySelectorAll('button, .view-tabs')].filter(e => e.offsetParent !== null);
          return { oneRow: R(bar).height < 60, inside: vis.every(e => R(e).right <= innerWidth + 1), more: !document.getElementById('moreWrap').classList.contains('hidden'), hidden: [...bar.querySelectorAll('.tb-over')].map(e => e.id) }; }""")
        check(f"{w}px: the toolbar stays one row, every visible button inside the window" + (" — the rest is under More" if m["more"] else ""), m["oneRow"] and m["inside"] and (m["more"] == bool(m["hidden"])), m)
        if w == 900:
            check("...buttons of one priority go together (Indent and Outdent)", ("indentBtn" in m["hidden"]) == ("outdentBtn" in m["hidden"]), m["hidden"])
            pg.click("#moreBtn"); pg.wait_for_timeout(100)
            items = pg.locator("#moreMenu .dropdown-item").all_inner_texts()
            check("More lists exactly what was moved out of the bar", len(items) >= len([h for h in m["hidden"] if h != "zoomTabs"]) and pg.locator("#moreMenu.open").count() == 1, (items, m["hidden"]))
            if "taskFormBtn" in m["hidden"]:
                pg.locator("#moreMenu .dropdown-item", has_text="Task Form").click(); pg.wait_for_timeout(120)
                check("...and an item there does what the button does (Task Form opens), closing the menu", ev("() => showTaskForm") and pg.locator("#moreMenu.open").count() == 0)
                ev("() => { showTaskForm = false; save(); render(); }")
    pg.set_viewport_size({"width": 1500, "height": 900}); ev("() => { setSelection([]); setView('tasks'); }"); pg.wait_for_timeout(150)
    check("back at 1500px (Tasks view, nothing selected) everything fits again: nothing under More", ev("() => document.getElementById('moreWrap').classList.contains('hidden') && !document.querySelector('#subbar .tb-over')"))

    # ---------------------------------------------------------------- B: view tabs
    tabs = [t.strip() for t in pg.locator("#mainViewTabs .view-tab").all_inner_texts()]
    check("view tabs: Tasks, Gantt | Resource Plan with a divider; the Resource Sheet is the top bar's Resources button", tabs == ["Tasks", "Gantt", "Resource Plan"] and pg.locator("#mainViewTabs .view-tab-sep").count() == 1 and pg.locator("#resourcesBtn").count() == 1, tabs)
    view("resourceSheet"); pg.reload(); pg.wait_for_selector("#undoBtn")
    check("the Resource Sheet is remembered across a reload too (it used to fall back to Tasks)", ev("() => currentView") == "resourceSheet")
    view("tasks")

    # ---------------------------------------------------------------- C: Plan settings
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    items = [t.split("\n")[0].strip() for t in pg.locator("#scheduleMenu .dropdown-item").all_inner_texts()]
    check("the Schedule menu holds just the three actions (Baseline, Reschedule, Level) — Plan settings is the gear next to the plan switcher", items == ["Baseline…", "Reschedule remaining work…", "Level resources…"] and pg.locator(".topbar #planSettingsBtn").count() == 1, items)
    pg.keyboard.press("Escape")
    pg.click("#planSettingsBtn"); pg.wait_for_timeout(150)
    open_bg = lambda: ev("() => [...document.querySelectorAll('.modal-bg.open')].map(e => e.id)")
    check("Plan settings opens on its Calendar tab, titled 'Plan settings', the five tabs across the top",
          open_bg() == ["calendarModalBg"] and pg.inner_text("#calendarModalBg h2") == "Plan settings"
          and [t.strip() for t in pg.locator("#calendarModalBg .settings-tab").all_inner_texts()] == ["Calendar", "Precision", "Scheduling rules", "Currency", "Custom fields"], open_bg())
    size = lambda bg: ev("bg => { const r = document.querySelector('#' + bg + ' .modal').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }", bg)
    s_cal = size("calendarModalBg")
    sizes = {}
    for tab, bg in [("precision", "precisionModalBg"), ("rules", "rulesModalBg"), ("currency", "currencyModalBg"), ("fields", "fieldsModalBg"), ("calendar", "calendarModalBg")]:
        pg.click(f".modal-bg.open [data-settings-tab='{tab}']"); pg.wait_for_timeout(120)
        sizes[tab] = (open_bg(), size(bg))
    check("each tab switches the window to that setting — one window at a time", all(v[0] == [bg] for (k, v), bg in zip(sizes.items(), ["precisionModalBg", "rulesModalBg", "currencyModalBg", "fieldsModalBg", "calendarModalBg"])), sizes)
    check("...and every tab is the same size, so switching never makes the window jump", len({tuple(v[1]) for v in sizes.values()} | {tuple(s_cal)}) == 1, sizes)
    check("the active tab is marked (aria-selected)", pg.get_attribute("#calendarModalBg .settings-tab[data-settings-tab='calendar']", "aria-selected") == "true")
    pg.locator("#calendarDays .cal-day", has_text="Sat").click()
    pg.click(".modal-bg.open [data-settings-tab='rules']"); pg.wait_for_timeout(120)
    check("switching tab with unsaved changes asks first", ev("() => document.getElementById('confirmModalBg').classList.contains('open')") and "working calendar" in pg.inner_text("#confirmModalBody"))
    pg.click("#confirmModalCancelBtn"); pg.wait_for_timeout(100)
    check("'Keep editing' stays on Calendar with the change still there", open_bg() == ["calendarModalBg"] and ev("() => [...document.querySelectorAll('#calendarDays input:checked')].length") == 6)
    pg.click(".modal-bg.open [data-settings-tab='rules']"); pg.wait_for_timeout(100); pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(150)
    check("'Discard changes' moves on to the tab, the calendar untouched", open_bg() == ["rulesModalBg"] and ev("() => project.workDays === undefined"))
    # scheduling rules
    check("Scheduling rules shows the plan's settings (constraints honored, new tasks Auto)", pg.is_checked("#honorConstraintDatesInput") and pg.is_checked("#rulesNewAuto"))
    pg.uncheck("#honorConstraintDatesInput"); pg.check("#rulesNewManual")
    pg.click("#rulesModalBg .modal-footer .btn-primary"); pg.wait_for_timeout(150)
    check("saving them sets both on the plan", ev("() => [project.honorConstraintDates, project.newTaskMode]") == [False, "manual"] and open_bg() == [])
    ev("() => { delete project.honorConstraintDates; project.newTaskMode = 'auto'; save(); render(); }")
    # currency
    pg.click("#planMenuBtn"); pg.wait_for_selector("#planMenu.open")
    check("the plan menu has Plan settings… too", pg.locator("#planMenuSettingsItem").count() == 1)
    pg.click("#planMenuSettingsItem"); pg.wait_for_timeout(150)
    check("...which reopens it on the tab last used (Scheduling rules)", open_bg() == ["rulesModalBg"])
    pg.click(".modal-bg.open [data-settings-tab='currency']"); pg.wait_for_timeout(120)
    check("Currency shows the plan's currency (EUR) with a preview", pg.input_value("#planCurrencyInput") == "EUR" and "€" in pg.inner_text("#planCurrencyPreview"))
    pg.select_option("#planCurrencyInput", "GBP")
    check("...the preview follows the choice", "£" in pg.inner_text("#planCurrencyPreview"), pg.inner_text("#planCurrencyPreview"))
    pg.click("#currencyModalBg .modal-footer .btn-primary"); pg.wait_for_timeout(150)
    check("saving sets the plan's currency (the same setting as the Resource Sheet's picker)", ev("() => project.currencyCode") == "GBP")
    ev("() => { delete project.currencyCode; save(); render(); }")
    # custom fields from the task dialog: stands alone, no tabs
    ev("() => openTaskModal('a')"); pg.wait_for_timeout(120)
    ev("() => openFieldsModal()"); pg.wait_for_timeout(120)
    check("Custom fields opened over the task dialog stands alone: titled 'Custom fields', no settings tabs", pg.inner_text("#fieldsModalTitle") == "Custom fields" and not pg.locator("#fieldsModalBg .settings-tabs").is_visible())
    ev("() => { closeFieldsModal(); closeTaskModal(); }")
    ev("() => openPlanSettings('fields')"); pg.wait_for_timeout(120)
    check("...but as a Plan settings tab it has the tabs and the Plan settings title", pg.inner_text("#fieldsModalTitle") == "Plan settings" and pg.locator("#fieldsModalBg .settings-tabs").is_visible())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes Plan settings", open_bg() == [])

    # ---------------------------------------------------------------- the UX round: Fit, labels, Work in hours, plan switcher, headers, Task Mode
    ev("""() => { localStorage.removeItem('milestone-prefs'); }"""); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev("""() => { tasks.length = 0; const mk = (id, name, s, e, extra) => Object.assign({ id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
      tasks.push(mk('a', 'A long discovery phase', '2026-09-07', '2026-10-30', { resource: 'Anna' }), mk('b', 'QA', '2026-09-21', '2026-09-22'), mk('c', 'Launch', '2026-11-02', '2026-11-02', { milestone: true }), mk('d', 'Manual one', '2026-09-07', '2026-09-08', { taskMode: 'manual' }));
      normalizeData(); save(); setView('gantt'); }"""); pg.wait_for_timeout(250)
    check("a fresh install opens the Gantt on Fit: the whole plan across the chart, no sideways scrolling",
          ev("() => zoom") == "fit" and ev("() => { const e = document.getElementById('ganttPaneOuter'); return e.scrollWidth <= e.clientWidth; }") and pg.get_attribute("#fitZoomBtn", "aria-pressed") == "true")
    ev("() => { zoom = 'year'; save(); render(); }"); pg.click("#fitZoomBtn"); pg.wait_for_timeout(150)
    check("the Fit button goes back to it from a fixed scale", ev("() => zoom") == "fit")
    pg.set_viewport_size({"width": 1100, "height": 900}); pg.wait_for_timeout(250)
    check("...and it follows the window: still no sideways scrolling after a resize", ev("() => { const e = document.getElementById('ganttPaneOuter'); return e.scrollWidth <= e.clientWidth; }"))
    pg.set_viewport_size({"width": 1500, "height": 900}); pg.wait_for_timeout(250)
    lab = ev("""() => ({ qaInside: !!document.querySelector('.gantt-bar[data-id="b"] .bar-label'), outside: [...document.querySelectorAll('.gantt-out-label')].map(e => e.textContent), longInside: !!document.querySelector('.gantt-bar[data-id="a"] .bar-label') })""")
    check("a bar too short for its name gets it beside the bar (QA), a milestone gets its name beside it (Launch), a long bar keeps it inside",
          not lab["qaInside"] and "QA" in lab["outside"] and "Launch" in lab["outside"] and lab["longInside"], lab)
    ev("() => setView('tasks')"); pg.wait_for_timeout(100)
    check("Work always reads in hours (a 40-day task at 100% = 320 hrs)", ev("() => fmtWorkHours(byId('a').work)") == "320 hrs", ev("() => fmtWorkHours(byId('a').work)"))
    check("the plan switcher reads as a menu: a folder icon, a border, a chevron", pg.locator("#planMenuBtn .plan-ico").count() == 1 and ev("() => getComputedStyle(document.getElementById('planMenuBtn')).borderTopWidth") == "1px")
    check("...with the plan's file status right beside it (not over by the menus)", ev("() => document.getElementById('planMenuBtn').closest('.dropdown-wrap').nextElementSibling.contains(document.getElementById('fileSyncBtn'))"))
    check("column headers use the dim text colour (readable), not the faint one", ev("() => getComputedStyle(document.getElementById('gridHeader')).color === getComputedStyle(document.documentElement).getPropertyValue('--text-dim').trim() || getComputedStyle(document.getElementById('gridHeader')).color !== getComputedStyle(document.querySelector('.tf-hint') || document.body).color"))
    ev("() => { colHidden.delete('mode'); render(); }")   # (Task Mode starts hidden)
    modes = ev("() => [...document.querySelectorAll('#gridRows .task-mode-cell .mode-word')].map(e => e.textContent)")
    check("Task Mode cells say Auto / Manual beside the icon, and explain themselves on hover", "Auto" in modes and "Manual" in modes and "kept exactly where you put it" in (pg.locator("#gridRows .task-mode-cell").nth(3).get_attribute("title") or ""), modes)
    check("...and the column header explains both modes", "Manual (pin)" in (pg.locator("#gridHeader .col-head").first.get_attribute("title") or ""))

    # ---------------------------------------------------------------- D: the status bar
    pg.set_viewport_size({"width": 1440, "height": 800}); ev("() => { zoom = 'fit'; setSelection([]); setView('gantt'); }"); pg.wait_for_timeout(200)
    sb = pg.locator("#statusbar").bounding_box()
    check("a status bar runs along the bottom of the window", sb is not None and abs(sb["y"] + sb["height"] - 800) <= 1 and sb["width"] >= 1439, sb)
    check("it shows the new-task mode and the task count", "New tasks: Auto Scheduled" in pg.inner_text("#sbMode") and pg.inner_text("#sbCount") == "4 tasks", pg.inner_text("#sbCount"))
    pg.click("#sbMode"); pg.wait_for_timeout(100)
    check("clicking the mode opens a small menu (upwards) with both modes", pg.locator("#sbModeMenu.open .dropdown-item").count() == 2 and pg.locator("#sbModeMenu").bounding_box()["y"] < sb["y"])
    pg.locator("#sbModeMenu .dropdown-item", has_text="Manually").click(); pg.wait_for_timeout(100)
    check("...choosing one sets the plan's default for new tasks", ev("() => project.newTaskMode") == "manual" and "Manually Scheduled" in pg.inner_text("#sbMode"))
    ev("() => setNewTaskMode('auto')")
    ev("() => { setSelection(['a', 'b']); render(); }")
    check("...and the selection ('4 tasks · 2 selected')", pg.inner_text("#sbCount") == "4 tasks · 2 selected", pg.inner_text("#sbCount"))
    order = ev("() => [...document.querySelectorAll('#statusbar button, #statusbar .sb-text')].filter(e => e.offsetParent).map(e => e.id).filter(Boolean)")
    check("the Task Form toggle is the first thing on the left of the status bar (then the new-task mode, the count), not in the toolbar", order[:3] == ["taskFormBtn", "sbMode", "sbCount"] and pg.locator("#subbar #taskFormBtn").count() == 0, order)
    check("...and the status bar has no copy of the file status (the plan name's own is enough)", pg.locator("#statusbar #sbFile").count() == 0)
    pg.click("#taskFormBtn"); pg.wait_for_timeout(150)
    tf = pg.locator("#taskFormPane").bounding_box()
    check("...it opens the pane right above it, and shows itself pressed", ev("() => showTaskForm") and pg.get_attribute("#taskFormBtn", "aria-pressed") == "true" and abs(tf["y"] + tf["height"] - sb["y"]) <= 1, (tf, sb))
    pg.click("#taskFormBtn"); pg.wait_for_timeout(100)
    check("no filter: no filter summary (and no stray divider)", not pg.locator("#statusbar .sb-views:has(#filterBar)").is_visible())
    ev("() => { colFilters.name = { type: 'rule', rule: 'contains', a: 'a' }; render(); }")
    check("the filter summary lives in the status bar now (chips, 'N of M tasks', Clear all), not the toolbar",
          pg.locator("#statusbar #filterBar .filter-chip").count() == 1 and "of 4 tasks" in pg.inner_text("#filterBar") and pg.locator("#subbar #filterBar").count() == 0)
    pg.click("#filterBar >> text=Clear all"); pg.wait_for_timeout(100)
    check("Fit shows as the zoom label, the slider set to Fit's own scale", pg.inner_text("#sbZoomLabel") == "Fit")
    pg.locator("#zoomSlider").fill("850"); pg.wait_for_timeout(200)
    check("dragging the zoom slider gives any scale between the presets ('Custom'), the presets and Fit all unmarked",
          ev("() => zoom").startswith("px:") and pg.inner_text("#sbZoomLabel") == "Custom" and pg.locator("#zoomTabs .view-tab.active").count() == 0 and pg.get_attribute("#fitZoomBtn", "aria-pressed") == "false")
    px1 = ev("() => currentZoom().pxPerDay"); pg.click("#statusbar .sb-icon[aria-label='Zoom in']"); pg.wait_for_timeout(150)
    check("+ zooms in, − zooms out", ev("() => currentZoom().pxPerDay") > px1)
    z = ev("() => zoom"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(200)
    check("...and the chosen zoom is remembered", ev("() => zoom") == z)
    pg.click("#zoomTabs .view-tab:has-text('Month')"); pg.wait_for_timeout(150)
    check("a preset still works and the label follows ('Month')", pg.inner_text("#sbZoomLabel") == "Month")
    ev("() => setView('tasks')"); pg.wait_for_timeout(100)
    check("the zoom controls only show where there is a timeline (not in Tasks)", not pg.locator("#statusbar .sb-zoom").is_visible())
    ev("() => setView('resourceSheet')"); pg.wait_for_timeout(100)
    check("in the resource views it counts resources instead of tasks", "resource" in pg.inner_text("#sbCount"), pg.inner_text("#sbCount"))
    ev("() => { zoom = 'fit'; setView('tasks'); }")

    # ---------------------------------------------------------------- the default columns and their sequence
    ev("() => localStorage.removeItem('milestone-prefs')"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev("() => setView('tasks')")
    check("a fresh install's Tasks view shows Task Name, Start, Finish, Duration, % Complete, Predecessors, Resource, Status — in that order",
          ev("() => visibleTaskCols('tasks')") == ["name", "start", "end", "duration", "progress", "preds", "resource", "status"], ev("() => visibleTaskCols('tasks')"))
    check("...the Gantt list just Name, Start, Finish, Duration, % Complete", ev("() => visibleTaskCols('gantt')") == ["name", "start", "end", "duration", "progress"], ev("() => visibleTaskCols('gantt')"))
    check("...Task Mode, WBS and the Actual dates start hidden, but come first / next to the planned dates when ticked", ev("() => DEFAULT_COL_ORDER.slice(0, 7)") == ["mode", "wbs", "name", "start", "end", "actualStart", "actualFinish"] and all(ev("c => !TASK_COLS[c].dflt", c) for c in ["mode", "wbs", "actualStart", "actualFinish"]))
    check("both views share one sequence (Resource before Status, then Remaining, Task Type / Work / Cost, the baseline group)", ev("() => JSON.stringify(GANTT_DEFAULT_ORDER) === JSON.stringify(DEFAULT_COL_ORDER)") and ev("() => DEFAULT_COL_ORDER.slice(10, 16)") == ["resource", "status", "remaining", "worktype", "work", "cost"])
    ev("() => { colHidden.add('resource'); colOrder = ['status', ...colOrder.filter(c => c !== 'status')]; save(); }"); pg.reload(); pg.wait_for_selector("#undoBtn")
    check("an install with a saved choice keeps it — the new defaults don't override it", "resource" not in ev("() => visibleTaskCols('tasks')") and ev("() => visibleTaskCols('tasks')")[0] == "status", ev("() => visibleTaskCols('tasks')"))
    ev("() => { resetColumns(); }")
    check("...and 'Reset to default' gives the new defaults", ev("() => visibleTaskCols('tasks')") == ["name", "start", "end", "duration", "progress", "preds", "resource", "status"])

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
