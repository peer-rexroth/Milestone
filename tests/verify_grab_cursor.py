from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
res = []
def check(n, c, d=""): res.append(bool(c)); print(("PASS  " if c else "FAIL  ") + n + (f"  [{d}]" if not c else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1300, "height": 800}); errs = []
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate("""() => { tasks.length = 0; selectedTaskId = null;
      ['One','Two','Three'].forEach((n,i) => tasks.push({id: genId(), name:n, parentId:null, order:i, startDate:'2026-09-21', endDate:'2026-09-23', progress:0, milestone:false, color:null, notes:'', predecessors:[], collapsed:false, updatedAt:1, constraintType:'ASAP', constraintDate:null, taskMode:'auto'}));
      save(); render(); }""")
    row = lambda n: pg.locator(".grid-row", has_text=n).first
    cur = lambda n: row(n).evaluate("e => getComputedStyle(e).cursor")
    names = lambda: pg.evaluate("() => visibleTaskList().map(x => x.task.name)")
    box = row("Two").bounding_box(); x, y = box["x"] + 700, box["y"] + 16

    pg.mouse.move(x, y)
    check("at rest the row shows the normal cursor", cur("Two") == "default", cur("Two"))
    pg.mouse.down(); pg.wait_for_timeout(80)
    check("pressed only briefly: still the normal cursor", cur("Two") == "default", cur("Two"))
    pg.wait_for_timeout(350)
    check("kept pressed: grabbing cursor", cur("Two") == "grabbing", cur("Two"))
    pg.mouse.up(); pg.wait_for_timeout(50)
    check("released: back to the normal cursor", cur("Two") == "default", cur("Two"))

    # a plain click never shows it
    pg.mouse.down(); pg.mouse.up(); pg.wait_for_timeout(350)
    check("a quick click never leaves the grab cursor behind", pg.locator(".grid-row.grabbing").count() == 0)

    # drag still works, and no stale cursor class afterwards
    src = row("Three"); src.drag_to(row("One"), source_position={"x": 700, "y": 16}, target_position={"x": 120, "y": 6}); pg.wait_for_timeout(200)
    check("dragging still reorders", names() == ["Three", "One", "Two"], names())
    check("no grab class left after a drag", pg.locator(".grid-row.grabbing").count() == 0)

    # hold, then drag
    box = row("Two").bounding_box(); pg.mouse.move(box["x"] + 700, box["y"] + 16); pg.mouse.down(); pg.wait_for_timeout(400)
    t = row("Three").bounding_box(); pg.mouse.move(t["x"] + 120, t["y"] + 5, steps=8); pg.mouse.up(); pg.wait_for_timeout(250)
    check("press-hold-then-drag reorders", names() == ["Two", "Three", "One"], names())
    check("no grab class left after hold+drag", pg.locator(".grid-row.grabbing").count() == 0)

    # a row being edited is not draggable and gets no grab cursor
    one = pg.evaluate("() => tasks.find(t => t.name === 'One').id"); erow = pg.locator(f".grid-row[data-id='{one}']")
    erow.locator(".name-text").click(); pg.wait_for_selector(".inline-edit")
    bx = erow.bounding_box(); pg.mouse.move(bx["x"] + 700, bx["y"] + 16); pg.mouse.down(); pg.wait_for_timeout(400)
    check("the row being edited never shows grabbing", pg.locator(".grid-row.grabbing").count() == 0)
    pg.mouse.up()
    print("errors:", errs); print(f"{sum(res)}/{len(res)}"); b.close()
