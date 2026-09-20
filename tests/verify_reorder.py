from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1300, "height": 800})
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")

    def seed():
        pg.evaluate("""() => {
            tasks.length = 0; selectedTaskId = null;
            const mk = (name, parent, preds) => { const t = {id: genId(), name, parentId: parent || null, order: tasks.filter(x => (x.parentId||null) === (parent||null)).length,
                startDate: '2026-09-21', endDate: '2026-09-23', progress: 0, milestone: false, color: null, notes: '', predecessors: preds || [], collapsed: false,
                updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}; tasks.push(t); return t.id; };
            const a = mk('One'); mk('Two', null, [{id: a, type: 'FS', lag: 0}]); mk('Three');
            const g = mk('Group'); mk('Kid A', g); mk('Kid B', g); mk('Four');
            save(); render(); }""")
    def names(): return pg.evaluate("() => visibleTaskList().map(x => x.task.name)")
    def row(name): return pg.locator(".grid-row", has_text=name).first
    def row_attr(name): return row(name).get_attribute("draggable")
    def handle(name): return row(name).locator(".grid-cell-dim").nth(2)   # a Start-date cell: any part of the line should drag
    def drag(src, dst, where):
        """where: 'top' or 'bottom' half of the destination row"""
        box = row(dst).bounding_box()
        y = box["height"] * (0.2 if where == "top" else 0.8)
        handle(src).drag_to(row(dst), target_position={"x": 120, "y": y})
        pg.wait_for_timeout(150)

    seed(); print("start:", names())
    check("the whole row is draggable", row("One").get_attribute("draggable") == "true")

    drag("Four", "One", "top")
    check("drag to the very top", names()[0] == "Four", names())
    seed(); drag("One", "Three", "bottom")
    check("drag a task down (below another)", names()[:3] == ["Two", "Three", "One"], names())
    seed(); drag("Three", "One", "top")
    check("drag a task up (above another)", names()[:3] == ["Three", "One", "Two"], names())

    # summary moves with its children
    seed(); drag("Group", "One", "top")
    check("dragging a summary moves its whole subtree", names()[:3] == ["Group", "Kid A", "Kid B"] and names()[-1] == "Four", names())

    # into a group: bottom half of an expanded summary header = its first sub-task
    seed(); drag("One", "Group", "bottom")
    check("bottom half of an expanded summary -> first sub-task", names()[names().index("Group"):][:4] == ["Group", "One", "Kid A", "Kid B"], names())
    check("...and its parent really is the group", pg.evaluate("() => byId(tasks.find(t=>t.name==='One').id).parentId === tasks.find(t=>t.name==='Group').id"))

    # between two children of a group
    seed(); drag("One", "Kid B", "top")
    check("drop between sub-tasks joins the group at that spot", names()[2:6] == ["Group", "Kid A", "One", "Kid B"], names())

    # out of a group
    seed(); drag("Kid A", "One", "bottom")
    check("drag a sub-task out of its group", names()[:3] == ["One", "Kid A", "Two"] and pg.evaluate("() => tasks.find(t=>t.name==='Kid A').parentId") is None, names())

    # invalid drops
    seed(); before = names(); drag("Group", "Kid A", "top")
    check("cannot drop a summary into its own subtree", names() == before, names())
    drag("One", "One", "top")
    check("dropping a task on itself changes nothing", names() == before, names())

    # blank area at the bottom -> end of the list
    seed(); pg.click("text=Gantt"); pg.wait_for_timeout(200)
    grid = pg.locator("#gridRows").bounding_box()
    handle("One").drag_to(pg.locator("#gridRows"), target_position={"x": 150, "y": grid["height"] - 20})
    pg.wait_for_timeout(200)
    check("drop in the empty area -> end of the list (Gantt view grid)", names()[-1] == "One", names())
    pg.click("text=Tasks"); pg.wait_for_timeout(150)

    # data integrity after moves
    seed(); drag("Three", "One", "top")
    orders = pg.evaluate("() => childrenOf(null).map(t => t.order)")
    check("top-level orders stay contiguous", orders == list(range(len(orders))), orders)
    check("predecessor links survive a move (by id)", pg.evaluate("() => { const two = tasks.find(t=>t.name==='Two'); return two.predecessors.length === 1 && byId(two.predecessors[0].id).name === 'One'; }"))
    check("the dragged task ends up selected", pg.evaluate("() => byId(selectedTaskId).name") == "Three")
    pg.reload(); pg.wait_for_selector("#addTaskBtn")
    check("new order survives a reload", names()[:3] == ["Three", "One", "Two"], names())

    # Escape clears the selection
    seed(); pg.evaluate("() => { selectedTaskId = tasks.find(t=>t.name==='Two').id; render(); }")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape clears the selection", pg.evaluate("() => selectedTaskId") is None)
    check("...and the row loses its highlight", pg.locator(".grid-row.selected").count() == 0)

    # Escape while typing an inline edit cancels the edit, keeps selection
    pg.evaluate("() => { selectedTaskId = tasks.find(t=>t.name==='Two').id; render(); }")
    row("Two").locator(".name-text").click(); pg.wait_for_selector(".inline-edit")
    pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('inline-edit')")   # focus arrives a frame after the input
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape inside an inline edit only cancels the edit (selection kept)", pg.evaluate("() => selectedTaskId") is not None and pg.locator(".inline-edit").count() == 0)

    # Escape with a dialog open closes the dialog first, selection stays
    pg.evaluate("() => { selectedTaskId = tasks.find(t=>t.name==='Two').id; render(); }")
    row("Two").locator(".icon-btn").first.click(); pg.wait_for_selector("#taskModalBg.open")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Escape with a dialog open closes the dialog, keeps the selection", not pg.eval_on_selector("#taskModalBg", "e => e.classList.contains('open')") and pg.evaluate("() => selectedTaskId") is not None)

    # Add Task with nothing selected -> bottom of the list
    seed(); pg.evaluate("() => { selectedTaskId = tasks.find(t=>t.name==='Two').id; render(); }")
    pg.keyboard.press("Escape")
    pg.click("#addTaskBtn"); pg.wait_for_selector("#taskModalBg.open"); pg.fill("#taskNameInput", "AT-BOTTOM")
    pg.click("#taskModalBg button:has-text('Save')"); pg.wait_for_selector("#taskModalBg:not(.open)")
    check("after Escape, Add Task appends at the bottom of the list", names()[-1] == "AT-BOTTOM", names())
    check("...at the top level, below the last group too", pg.evaluate("() => tasks.find(t=>t.name==='AT-BOTTOM').parentId") is None)


    # ---- whole-line behaviour: drag from other spots on the line, and nothing else broke ----
    seed()
    row("Four").locator(".name-text").drag_to(row("One"), target_position={"x": 120, "y": 6}); pg.wait_for_timeout(150)
    check("drag from the task-name text", names()[0] == "Four", names())
    seed()
    row("Four").locator(".grid-cell-dim").nth(4).drag_to(row("One"), target_position={"x": 120, "y": 6}); pg.wait_for_timeout(150)
    check("drag from the % cell", names()[0] == "Four", names())
    seed()
    row("Four").drag_to(row("One"), source_position={"x": 700, "y": 20}, target_position={"x": 120, "y": 6}); pg.wait_for_timeout(150)
    check("drag from empty space in the line (past the last column)", names()[0] == "Four", names())

    seed()
    two_id = pg.evaluate("() => tasks.find(t => t.name === 'Two').id")
    by_id = lambda i: pg.locator(f".grid-row[data-id='{i}']")
    row("Two").locator(".name-text").click(); pg.wait_for_selector(".inline-edit")
    check("a plain click on a name still starts inline editing", pg.locator(".inline-edit").count() == 1)
    check("the row being edited is NOT draggable (so text can be selected in the box)", by_id(two_id).get_attribute("draggable") == "false")
    check("other rows stay draggable while one is being edited", row("One").get_attribute("draggable") == "true")
    pg.fill(".inline-edit", "Renamed"); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    check("editing then Enter still saves", "Renamed" in names(), names())
    check("the row is draggable again after the edit", by_id(two_id).get_attribute("draggable") == "true")

    seed(); row("One").locator("> div").first.dblclick(); pg.wait_for_selector("#taskModalBg.open")
    check("double-click on the line still opens the task dialog", True)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)

    seed(); row("Three").locator(".grid-cell-dim").first.click(); pg.wait_for_timeout(100)
    check("a plain click on the line still selects it", pg.evaluate("() => byId(selectedTaskId).name") == "Three")

    seed(); row("Two").locator(".task-mode-cell").click(); pg.wait_for_selector("#taskModeMenu.open")
    check("the Task Mode cell still opens its menu (click, not drag)", True)
    pg.keyboard.press("Escape")

    seed(); row("Group").locator(".chevron").click(); pg.wait_for_timeout(100)
    check("the collapse chevron still works", "Kid A" not in names(), names())

    print("console errors:", errors)
    print(f"{sum(results)}/{len(results)} passed")
    b.close()
