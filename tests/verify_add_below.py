from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1300, "height": 800})
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")

    def seed():
        pg.evaluate("""() => {
            tasks.length = 0; selectedTaskId = null;
            const mk = (name, parent) => { const t = {id: genId(), name, parentId: parent || null, order: tasks.filter(x => (x.parentId||null) === (parent||null)).length,
                startDate: '2026-09-21', endDate: '2026-09-23', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false,
                updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}; tasks.push(t); return t.id; };
            mk('One'); mk('Two'); mk('Three');
            const g = mk('Group'); mk('Kid A', g); mk('Kid B', g); mk('Four');
            save(); render(); }""")
    def visible_names():
        return pg.evaluate("() => visibleTaskList().map(x => x.task.name || '(new)')")
    def add(name):
        pg.click("#addTaskBtn"); pg.wait_for_selector("#taskModalBg.open")
        pg.fill("#taskNameInput", name); pg.click("#taskModalBg button:has-text('Save')"); pg.wait_for_selector("#taskModalBg:not(.open)")
    def select(name):
        pg.evaluate("n => { selectedTaskId = tasks.find(t => t.name === n).id; render(); }", name)

    # 1) leaf selected in the middle -> new task directly below it
    seed(); select("Two"); add("NEW")
    check("leaf in the middle: new task directly below it", visible_names() == ["One", "Two", "NEW", "Three", "Group", "Kid A", "Kid B", "Four"], visible_names())
    check("the new task is now the selection", pg.evaluate("() => byId(selectedTaskId).name") == "NEW")

    # 2) chained adds keep stacking downward
    add("NEW2"); add("NEW3")
    check("repeated Add stacks downward (not reversed)", visible_names()[:6] == ["One", "Two", "NEW", "NEW2", "NEW3", "Three"], visible_names())

    # 3) last task at the top level
    seed(); select("Four"); add("LAST")
    check("last task: new task goes after it", visible_names()[-2:] == ["Four", "LAST"], visible_names())

    # 4) a sub-task selected -> sibling inside the same group, right below it
    seed(); select("Kid A"); add("KID-NEW")
    check("sub-task selected: new sibling in the same group directly below", visible_names() == ["One", "Two", "Three", "Group", "Kid A", "KID-NEW", "Kid B", "Four"], visible_names())
    check("...and it belongs to the group", pg.evaluate("() => byId(selectedTaskId).parentId === tasks.find(t => t.name === 'Group').id"))

    # 5) summary task selected -> first sub-task directly below it (expanded)
    seed(); select("Group"); add("FIRST-KID")
    check("summary selected: becomes its first sub-task, directly below", visible_names() == ["One", "Two", "Three", "Group", "FIRST-KID", "Kid A", "Kid B", "Four"], visible_names())

    # 6) collapsed summary is expanded so the new task is not hidden
    seed(); pg.evaluate("() => { tasks.find(t => t.name === 'Group').collapsed = true; save(); render(); }"); select("Group"); add("HIDDEN?")
    check("collapsed summary is expanded so the new task is visible", "HIDDEN?" in visible_names(), visible_names())

    # 7) nothing selected -> appended at the end of the top level (unchanged behaviour)
    seed(); add("APPENDED")
    check("nothing selected: appended at the end of the top level", visible_names()[-1] == "APPENDED", visible_names())

    # 8) orders stay clean and only moved tasks are re-stamped
    seed(); select("Two")
    stamps_before = pg.evaluate("() => Object.fromEntries(tasks.map(t => [t.name, t.updatedAt]))")
    add("NEW")
    orders = pg.evaluate("() => childrenOf(null).map(t => [t.name, t.order])")
    check("top-level orders are contiguous 0..n", [o for _, o in orders] == list(range(len(orders))), orders)
    after = pg.evaluate("() => Object.fromEntries(tasks.map(t => [t.name, t.updatedAt]))")
    check("tasks above the new one are untouched (updatedAt unchanged)", after["One"] == stamps_before["One"] and after["Two"] == stamps_before["Two"])
    check("tasks below it are re-stamped so the new order syncs", after["Three"] > stamps_before["Three"] and after["Four"] > stamps_before["Four"])
    check("sub-task order inside the group is untouched", after["Kid A"] == stamps_before["Kid A"])

    # 9) persists across reload in the same order
    pg.reload(); pg.wait_for_selector("#addTaskBtn")
    check("order survives a reload", visible_names() == ["One", "Two", "NEW", "Three", "Group", "Kid A", "Kid B", "Four"], visible_names())

    print("console errors:", errors)
    print(f"{sum(results)}/{len(results)} passed")
    b.close()
