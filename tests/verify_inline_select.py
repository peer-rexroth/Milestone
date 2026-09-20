# -*- coding: utf-8 -*-
"""Selecting text inside a cell being edited (double-click on a word, or a drag that ends outside the box) must not end the edit."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); editingCell = null; delete project.holidays; delete project.workDays;
  const mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna Meier and Ben', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('a', 'Design review with the customer', 0), mk('b', 'Second task here', 1, { taskMode: 'manual' }), mk('c', 'Third', 2, { custom: { text1: 'Cost centre seven' } }));
  colHidden.delete('resource'); colHidden.delete('text1'); currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1700, "height": 850}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    def fresh(): ev(SEED); pg.wait_for_timeout(150)
    state = lambda: ev("() => ({ editing: !!editingCell, field: editingCell && editingCell.field, input: !!document.querySelector('#gridRows .inline-edit'), modal: document.getElementById('taskModalBg').classList.contains('open'), sel: selectedIds().map(id => byId(id).name) })")
    def open_edit(task, field):
        """a real click on the cell, exactly as a person does it"""
        cell = {"name": ".name-text", "resource": None, "start": None}.get(field)
        row = pg.locator(f".grid-row[data-id='{task}']")
        if field == "name": row.locator(".name-text").click()
        else: row.locator(f"[onclick*=\"'{field}'\"]").click()
        pg.wait_for_timeout(300)
        return pg.locator("#gridRows .inline-edit").first.bounding_box()
    box = lambda: pg.locator("#gridRows .inline-edit").first.bounding_box()
    def drag(bb, dx, dy, from_x=10):
        y = bb["y"] + bb["height"] / 2; pg.mouse.click(bb["x"] + from_x, y); pg.wait_for_timeout(80)  # a plain click first: the editor opens with everything selected, and pressing on selected text would start dragging that text
        pg.mouse.move(bb["x"] + from_x, y); pg.mouse.down(); pg.mouse.move(bb["x"] + from_x + dx, y + dy, steps=10); pg.mouse.up(); pg.wait_for_timeout(300)

    # ------------------------------------------------------------ the name cell
    fresh(); bb = open_edit("a", "name")
    check("(setup) a click on the name opens the editor", state()["editing"] and state()["field"] == "name", state())
    pg.mouse.dblclick(bb["x"] + 30, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(300)
    s = state(); word = ev("() => { const i = document.querySelector('#gridRows .inline-edit'); return i.value.slice(i.selectionStart, i.selectionEnd); }")
    check("double-clicking a word selects it and the edit goes on — the task dialog does not open", s["editing"] and s["input"] and not s["modal"] and word.strip() == "Design", (s, word))
    pg.keyboard.type("Layout"); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    check("...typing replaces the selected word and Enter saves it ('Layout review with the customer')", ev("() => byId('a').name") == "Layout review with the customer", ev("() => byId('a').name"))
    fresh(); bb = open_edit("a", "name")
    drag(bb, bb["width"] + 250, 0)
    s = state()
    check("selecting text by dragging out of the box to the right (into the neighbouring cells) keeps the editor open", s["editing"] and s["input"] and not s["modal"], s)
    check("...and the row is not selected by that release (no re-render)", s["sel"] == [], s)
    sel_len = ev("() => { const i = document.querySelector('#gridRows .inline-edit'); return i.selectionEnd - i.selectionStart; }")
    check("...the text is selected (the whole name, dragged past its end)", sel_len > 20, sel_len)
    pg.keyboard.type("X"); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    check("...and typing replaces it as expected", ev("() => byId('a').name") == "X", ev("() => byId('a').name"))
    fresh(); bb = open_edit("a", "name")
    drag(bb, -(bb["width"] - 20), 0, from_x=bb["width"] - 30)
    check("dragging out to the LEFT keeps it open too", state()["editing"] and state()["input"], state())
    fresh(); bb = open_edit("a", "name")
    drag(bb, 80, 70)
    check("dragging down onto the row below keeps it open", state()["editing"] and not state()["modal"], state())
    fresh(); bb = open_edit("a", "name")
    drag(bb, 60, -110)
    check("dragging up out of the list (into the toolbar) keeps it open", state()["editing"], state())
    fresh(); bb = open_edit("a", "name")
    pg.mouse.click(bb["x"] + 10, bb["y"] + 8); pg.mouse.move(bb["x"] + 10, bb["y"] + 8); pg.mouse.down(); pg.mouse.move(bb["x"] + 400, bb["y"] + 8, steps=6); pg.mouse.move(bb["x"] + 400, 700, steps=6); pg.mouse.up(); pg.wait_for_timeout(300)
    check("dragging down and away over the empty part of the list keeps it open", state()["editing"], state())

    # ------------------------------------------------------------ other editors
    fresh(); bb = open_edit("a", "resource")
    pg.mouse.dblclick(bb["x"] + 40, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(250)
    check("Resource cell: double-click on a word keeps the editor and opens no dialog", state()["editing"] and state()["field"] == "resource" and not state()["modal"], state())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    fresh(); bb = open_edit("a", "resource"); drag(bb, bb["width"] + 200, 0)
    check("...and a drag out of the box keeps it", state()["editing"] and state()["field"] == "resource", state())
    fresh(); bb = open_edit("b", "start")
    check("(setup) a manually scheduled task's Start is the text editor with the calendar button", pg.locator("#gridRows .inline-wrap").count() == 1, state())
    pg.mouse.dblclick(bb["x"] + 20, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(250)
    check("date text editor: double-click on part of the date keeps the editor (no dialog)", state()["editing"] and state()["field"] == "start" and not state()["modal"], state())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    fresh(); bb = open_edit("b", "start"); drag(bb, bb["width"] + 150, 0)
    check("...and a drag out of it keeps the editor", state()["editing"] and state()["field"] == "start", state())
    fresh(); bb = open_edit("c", "text1")
    pg.mouse.dblclick(bb["x"] + 20, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(250)
    check("custom text field: double-click on a word keeps the editor", state()["editing"] and state()["field"] == "text1" and not state()["modal"], state())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    fresh(); open_edit("a", "duration"); bb = box()
    drag(bb, bb["width"] + 150, 0)
    check("Duration cell: a drag out of the box keeps the editor", state()["editing"] and state()["field"] == "duration", state())

    # ------------------------------------------------------------ the Gantt view's list is the same list
    fresh(); ev("() => setView('gantt')"); pg.wait_for_timeout(300)
    bb = open_edit("a", "name"); pg.mouse.dblclick(bb["x"] + 30, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(250)
    check("Gantt view: double-click on a word keeps the editor", state()["editing"] and not state()["modal"], state())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    bb = open_edit("a", "name"); drag(bb, bb["width"] + 120, 0)
    check("...and a drag out of the box keeps it", state()["editing"], state())
    ev("() => setView('tasks')"); pg.wait_for_timeout(200)

    # ------------------------------------------------------------ nothing else changed
    fresh(); bb = open_edit("a", "name"); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("Escape still cancels the edit", not state()["editing"] and ev("() => byId('a').name") == "Design review with the customer")
    fresh(); bb = open_edit("a", "name"); pg.keyboard.press("End"); pg.keyboard.type(" v2"); pg.locator(".grid-row[data-id='c'] > div").first.click(); pg.wait_for_timeout(300)
    check("clicking on another row still saves the edit and closes the editor", ev("() => byId('a').name") == "Design review with the customer v2" and not state()["editing"], (ev("() => byId('a').name"), state()))
    fresh(); bb = open_edit("a", "name"); pg.keyboard.press("End"); pg.keyboard.type("!"); pg.locator("#gridRows").click(position={"x": 300, "y": 400}); pg.wait_for_timeout(300)
    check("clicking on the empty area still saves the edit", ev("() => byId('a').name") == "Design review with the customer!" and not state()["editing"], ev("() => byId('a').name"))
    fresh(); pg.locator(".grid-row[data-id='a'] > div").first.click(); pg.wait_for_timeout(150)
    check("a single click on a row (no edit going on) still selects it", state()["sel"] == ["Design review with the customer"], state())
    pg.locator(".grid-row[data-id='b'] > div").first.dblclick(); pg.wait_for_timeout(350)
    check("a double-click on a row (no edit going on) still opens the task dialog", state()["modal"], state())
    ev("() => closeTaskModal()"); pg.wait_for_timeout(250)
    fresh(); bb = open_edit("a", "name"); pg.mouse.click(bb["x"] + 20, bb["y"] + 5); pg.wait_for_timeout(250)
    check("a plain click inside the box (moving the cursor) keeps the editor and does not select the row", state()["editing"] and state()["sel"] == [], state())
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
