# -*- coding: utf-8 -*-
"""The toolbar and the right-click menu: the Add Task split button and its menu (empty line, paste, how new tasks are scheduled), the selection
buttons that only appear while something is selected, and the row context menu on the list (Tasks and Gantt views)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); colFilters = newColFilters(); filterPinned.clear(); editingCell = null; delete project.holidays; delete project.workDays; project.newTaskMode = 'auto'; historyCoalesceMs = 0;
  const mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('g', 'Group', 0), mk('a', 'Alpha', 0, { parentId: 'g' }), mk('b', 'Beta', 1, { parentId: 'g' }), mk('c', 'Gamma', 1), mk('d', 'Delta', 2));
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
OUTLINE = "() => visibleTaskList().map(v => (v.task.spacer ? '·' : v.task.name) + (v.depth ? '@' + v.depth : ''))"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    def fresh(): ev(SEED); pg.wait_for_timeout(120)
    def row(name): return pg.locator(f".grid-row[data-id='{ev('(n) => tasks.find(t => t.name === n).id', name)}']")
    def pick(name, mods=None): row(name).locator("> div").first.click(modifiers=mods or []); pg.wait_for_timeout(80)
    def rclick(name, x=300): row(name).click(button="right", position={"x": x, "y": 10}); pg.wait_for_timeout(120)
    sel = lambda: ev("() => selectedIds().map(id => byId(id).name)")
    menu_open = lambda id_: ev("(i) => document.getElementById(i).classList.contains('open')", id_)
    items = lambda: [t.strip().split("\n")[0] for t in pg.locator("#rowMenu .dropdown-item").all_inner_texts()]
    modal = lambda: ev("() => document.getElementById('taskModalBg').classList.contains('open')")

    # ---------------------------------------------------------------- the bar
    fresh()
    check("the Print button is not in the toolbar any more (it is in the Data menu, and Ctrl/Cmd+P)", pg.locator("#printBtn").count() == 0 and pg.locator("#newTaskModeBtn").count() == 0)
    check("nothing selected: Indent / Outdent are disabled, and Edit / Duplicate / Copy / Delete are not shown", pg.is_disabled("#indentBtn") and all(not pg.locator("#" + i).is_visible() for i in ["bulkEditBtn", "cloneTaskBtn", "copyBtn", "deleteTaskBtn", "selChip"]))
    check("the visible toolbar: Undo, Redo, Add Task + arrow, Indent, Outdent … Find, Columns", all(pg.locator("#" + i).is_visible() for i in ["undoBtn", "redoBtn", "addTaskBtn", "addMenuBtn", "indentBtn", "outdentBtn", "searchBtn", "columnsBtn"]))
    check("...separators divide the groups", pg.locator(".subbar > .tb-sep").count() >= 2)
    pick("Gamma")
    check("a selection shows '1 selected' and four labelled buttons", pg.inner_text("#selChip").strip() == "1 selected" and [pg.inner_text("#" + i).strip() for i in ["bulkEditBtn", "cloneTaskBtn", "copyBtn", "deleteTaskBtn"]] == ["Edit", "Duplicate", "Copy", "Delete"])
    pick("Alpha"); pick("Beta", ["Meta"])
    check("...two selected: '2 selected'", pg.inner_text("#selChip").strip() == "2 selected")
    pg.click("#selChip"); pg.wait_for_timeout(80)
    check("the chip clears the selection and the buttons disappear again", sel() == [] and not pg.locator("#bulkEditBtn").is_visible())
    pick("Gamma"); pg.click("#bulkEditBtn"); pg.wait_for_timeout(250)
    check("Edit (one task) opens the task dialog", modal()); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    pg.click("#cloneTaskBtn"); pg.wait_for_timeout(200)
    check("Duplicate makes the copy below", "Gamma (copy)" in ev(OUTLINE), ev(OUTLINE))
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(200)

    # ---------------------------------------------------------------- the Add menu
    fresh()
    pg.click("#addMenuBtn"); pg.wait_for_timeout(100)
    check("the arrow next to Add Task opens a menu: Add empty line, Paste tasks, and how new tasks are scheduled", menu_open("addMenu") and pg.locator("#addMenu .dropdown-item").count() == 4 and "Add empty line" in pg.inner_text("#addSpacerBtn") and "Paste" in pg.inner_text("#pasteBtn"))
    check("...the current mode is ticked (Auto Scheduled), the other is not", "active" in (pg.get_attribute("#newModeAuto", "class") or "") and "active" not in (pg.get_attribute("#newModeManual", "class") or "") and pg.get_attribute("#newModeAuto", "aria-checked") == "true")
    check("...the paste hint shows the platform's shortcut", "V" in pg.inner_text("#pasteBtn") and ("⌘" in pg.inner_text("#pasteBtn") or "Ctrl" in pg.inner_text("#pasteBtn")))
    pg.click("#newModeManual"); pg.wait_for_timeout(120)
    check("choosing Manually Scheduled sets the project default and closes the menu", ev("() => project.newTaskMode") == "manual" and not menu_open("addMenu"))
    check("...the Add Task tooltip names the mode", "Manually Scheduled" in (pg.get_attribute("#addTaskBtn", "title") or ""), pg.get_attribute("#addTaskBtn", "title"))
    pg.click("#addTaskBtn"); pg.wait_for_selector("#taskModalBg.open"); check("...and a new task is Manual", ev("() => document.getElementById('taskModeInput').value") == "manual"); ev("() => closeTaskModal()")
    pg.click("#addMenuBtn"); pg.click("#newModeAuto"); pg.wait_for_timeout(100)
    check("...and back to Auto", ev("() => project.newTaskMode") == "auto")
    pg.click("#addMenuBtn"); pg.click("body", position={"x": 900, "y": 500}); pg.wait_for_timeout(100)
    check("a click elsewhere closes the menu", not menu_open("addMenu"))
    pg.click("#addMenuBtn"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes it", not menu_open("addMenu"))
    fresh(); pick("Gamma"); pg.click("#addMenuBtn"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("...without dropping the selection", sel() == ["Gamma"])
    pg.click("#addMenuBtn"); pg.click("#addSpacerBtn"); pg.wait_for_timeout(200)
    check("'Add empty line' adds it below the selection and closes the menu", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "·", "Delta"] and not menu_open("addMenu"), ev(OUTLINE))
    pg.click("#addMenuBtn"); pg.click("#dataMenuBtn"); pg.wait_for_timeout(100)
    check("opening the Data menu closes the Add menu", not menu_open("addMenu"))
    pg.keyboard.press("Escape")
    pg.click("#dataMenuBtn"); pg.click("#printItem"); pg.wait_for_selector("#printModalBg.open")
    check("Print / PDF is in the Data menu", True); ev("() => closePrintModal()")

    # ---------------------------------------------------------------- the right-click menu
    fresh()
    rclick("Beta")
    check("right-click on a row selects it and opens the menu at the pointer (the browser's own menu is not used)", sel() == ["Beta"] and menu_open("rowMenu"), sel())
    check("...the menu: Edit, Add task below, Add empty line, Duplicate, Copy, Cut, Paste, Indent, Outdent, Delete", items() == ["Edit task…", "Add task below", "Add empty line", "Duplicate", "Copy", "Cut", "Paste", "Indent", "Outdent", "Delete"], items())
    check("...it stays inside the window (bottom rows near the edge)", ev("() => { const r = document.getElementById('rowMenu').getBoundingClientRect(); return r.bottom <= innerHeight && r.right <= innerWidth && r.left >= 0 && r.top >= 0; }"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes it and keeps the selection", not menu_open("rowMenu") and sel() == ["Beta"])
    rclick("Beta"); pg.click("#rowMenu >> text=Edit task…"); pg.wait_for_timeout(250)
    check("Edit task… opens the task dialog", modal() and pg.input_value("#taskNameInput") == "Beta"); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    rclick("Gamma"); pg.click("#rowMenu >> text=Add empty line"); pg.wait_for_timeout(200)
    check("Add empty line puts a line below the clicked row", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "·", "Delta"], ev(OUTLINE))
    rclick("Delta"); pg.click("#rowMenu >> text=Duplicate"); pg.wait_for_timeout(200)
    check("Duplicate copies the clicked row", ev(OUTLINE)[-2:] == ["Delta", "Delta (copy)"], ev(OUTLINE))
    rclick("Alpha"); pg.click("#rowMenu >> text=Copy"); pg.wait_for_timeout(120)
    rclick("Delta"); pg.click("#rowMenu >> text=Paste"); pg.wait_for_timeout(300)
    check("Copy then Paste (menu) puts the copy below the clicked row", ev(OUTLINE).count("Alpha@1") == 1 and "Alpha" in ev(OUTLINE), ev(OUTLINE))
    fresh(); rclick("Beta"); pg.click("#rowMenu >> text=Cut"); pg.wait_for_timeout(300)
    check("Cut removes the row (Undo brings it back)", "Beta@1" not in ev(OUTLINE)); pg.click("#toastUndoBtn"); pg.wait_for_timeout(200)
    check("...Undo restores it", "Beta@1" in ev(OUTLINE))
    fresh(); rclick("Beta"); pg.click("#rowMenu >> text=Indent"); pg.wait_for_timeout(200)
    check("Indent (menu) nests the row under the one above (Beta under Alpha)", ev("() => byId('b').parentId") == "a", ev("() => byId('b').parentId"))
    rclick("Beta"); pg.click("#rowMenu >> text=Outdent"); pg.wait_for_timeout(200)
    check("Outdent (menu) takes it out again", ev("() => byId('b').parentId") == "g")
    rclick("Gamma"); pg.click("#rowMenu >> text=Delete"); pg.wait_for_timeout(200)
    check("Delete (menu) asks for confirmation as the toolbar does", "Delete" in pg.inner_text("#confirmModalTitle") and "Gamma" in pg.inner_text("#confirmModalBody"))
    pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(200)
    check("...and deletes the row", "Gamma" not in ev(OUTLINE))
    # several selected
    fresh(); pick("Alpha"); pick("Gamma", ["Meta"]); pick("Delta", ["Meta"]); rclick("Gamma")
    check("right-click on a row that is IN the selection keeps the whole selection", sel() == ["Alpha", "Gamma", "Delta"], sel())
    check("...and the menu speaks of the count (Edit 3 tasks…, Delete 3 tasks)", "Edit 3 tasks…" in items() and "Delete 3 tasks" in items(), items())
    pg.keyboard.press("Escape")
    rclick("Beta")
    check("right-click on a row that is NOT in the selection selects just that row", sel() == ["Beta"], sel())
    pg.keyboard.press("Escape")
    # an empty line
    fresh(); pick("Gamma"); pg.click("#addMenuBtn"); pg.click("#addSpacerBtn"); pg.wait_for_timeout(200)
    line = ev("() => tasks.find(t => t.spacer).id"); pg.locator(f".grid-row[data-id='{line}']").click(button="right", position={"x": 300, "y": 10}); pg.wait_for_timeout(120)
    check("an empty line's menu has no Edit item", "Edit task…" not in items() and "Duplicate" in items() and "Delete" in items(), items())
    pg.keyboard.press("Escape")
    # empty area
    fresh(); pick("Gamma"); pg.locator("#gridRows").click(button="right", position={"x": 300, "y": 600}); pg.wait_for_timeout(120)
    check("right-click on the empty part of the list offers only Add task, Add empty line and Paste", items() == ["Add task", "Add empty line", "Paste"], items())
    pg.click("#rowMenu >> text=Add task"); pg.wait_for_selector("#taskModalBg.open")
    check("...Add task adds one at the end (nothing to be 'below') and opens its dialog", modal()); ev("() => closeTaskModal()"); pg.wait_for_timeout(250)
    # native menu inside an editor
    fresh(); pg.locator(".grid-row[data-id='c'] .name-text").click(); pg.wait_for_timeout(250)
    pg.locator("#gridRows .inline-edit").first.click(button="right"); pg.wait_for_timeout(150)
    check("right-click inside a text box being edited leaves the browser's own menu (no Milestone menu, edit goes on)", not menu_open("rowMenu") and ev("() => !!editingCell"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    # dialogs
    fresh(); ev("() => openHelpModal()"); pg.wait_for_timeout(200)
    pg.locator(".grid-row[data-id='c']").click(button="right", position={"x": 300, "y": 10}, force=True); pg.wait_for_timeout(150)
    check("with a dialog open there is no row menu", not menu_open("rowMenu")); ev("() => closeHelpModal && closeHelpModal()"); pg.keyboard.press("Escape")
    # Gantt view
    fresh(); ev("() => setView('gantt')"); pg.wait_for_timeout(300)
    rclick("Delta", x=100)
    check("the list in the Gantt view has the same menu", menu_open("rowMenu") and sel() == ["Delta"] and "Duplicate" in items(), (sel(), items()))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    r = ev("() => { const r = document.querySelector(\".gantt-row-bg[data-row-id='c']\").getBoundingClientRect(); return { x: Math.max(r.left, document.getElementById('ganttPaneOuter').getBoundingClientRect().left) + 4, y: r.top + 16 }; }")
    pg.mouse.click(r["x"], r["y"], button="right"); pg.wait_for_timeout(150)
    check("...and so does a right-click on the chart's rows (it belongs to the row it is on)", menu_open("rowMenu") and sel() == ["Gamma"], (sel(), menu_open("rowMenu")))
    pg.keyboard.press("Escape")
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
