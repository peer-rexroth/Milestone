"""The Resource Sheet works like the task grid: cells are plain text, the cell cursor (a ring) moves with the arrows, Return / F2 / a double-click / typing edits a
cell in a box like a task cell's, Tab moves on, Esc puts the text back and then lets go, Delete removes the row; Add Resource selects the new row and opens its name."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1400, "height": 800}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => { project.resources = [{id: 'r1', name: 'Ann', maxUnits: 100}, {id: 'r2', name: 'Ben', maxUnits: 100}, {id: 'r3', name: 'Cy', maxUnits: 100}]; save(); render(); setView('resourceSheet'); }"); pg.wait_for_timeout(300)
    names = lambda: ev("() => (project.resources || []).map(r => r.name)")
    rows = pg.locator("#resourceSheetBody .rst-row")
    cur = lambda: ev("() => rsCursor ? [[...document.querySelectorAll('#resourceSheetBody .rst-row')].findIndex(r => r.dataset.id === rsCursor.id), rsCursor.key] : null")   # (the remembered cell; the ring itself is checked separately)
    ring_on = lambda: ev("() => document.querySelectorAll('#resourceSheetBody .rst-cell.cursor').length")
    live = lambda: ev("() => document.querySelectorAll('#resourceSheetBody .rs-live').length")

    check("cells are plain text at rest: no box takes the pointer", ev("() => [...document.querySelectorAll('#resourceSheetBody .rst-cell input, #resourceSheetBody .rst-cell select')].every(e => getComputedStyle(e).pointerEvents === 'none')"))
    rows.nth(1).locator(".rst-cell").nth(1).click(); pg.wait_for_timeout(100)
    check("a click selects the row and puts the cursor ring on that cell, nothing is edited", cur() == [1, "name"] and live() == 0 and ev("() => document.activeElement === document.body"), cur())
    check("...but, as in the task list, a click only remembers the cell: the ring is not drawn yet", ring_on() == 0)
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(80)
    ring = ev("() => { const c = document.querySelector('#resourceSheetBody .rst-cell.cursor'); return c ? [getComputedStyle(c).outlineStyle, parseFloat(getComputedStyle(c).outlineWidth)] : null; }")
    check("once the keyboard is used the ring is drawn: the task list's 2px outline", ring and ring[0] == "solid" and ring[1] >= 2 and ring_on() == 1, ring)
    check("arrows move the cursor (↓ a row, → a column) without editing", cur() == [2, "type"] and live() == 0, cur())
    pg.keyboard.press("Home"); pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(80)
    check("Home goes to the first column; ↑ up a row", cur() == [1, "id"], cur())
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    check("Return edits the cell: the box takes the cursor, its text is selected", live() == 1 and ev("() => document.activeElement.value") == "Ben" and ev("() => document.activeElement.selectionStart === 0 && document.activeElement.selectionEnd === 3"), ev("() => document.activeElement.tagName"))
    box = ev("() => { const i = document.activeElement, cs = getComputedStyle(i); return [cs.borderTopColor, cs.borderTopWidth, cs.backgroundColor]; }")
    check("...and the box is a task cell's: a 1px accent border on the panel colour", box[1] == "1px" and box[0] != "rgba(0, 0, 0, 0)" and box[2] != "rgba(0, 0, 0, 0)", box)
    pg.keyboard.type("Benno"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Esc puts the typed text back (nothing saved), the box stays", names()[1] == "Ben" and ev("() => document.activeElement.value") == "Ben")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("a second Esc ends the edit: the ring stays on the cell, the focus is on the page", live() == 0 and cur() == [1, "name"] and ev("() => document.activeElement === document.body"), (live(), cur()))
    pg.keyboard.type("Bo"); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    check("typing on a cell replaces its text; Tab saves it and edits the next cell", names()[1] == "Bo" and cur()[0] == 1 and cur()[1] != "name" and live() == 1, (names(), cur()))
    pg.keyboard.press("Escape"); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    rows.nth(2).locator(".rst-cell").nth(1).dblclick(); pg.wait_for_timeout(100)
    check("a double-click edits the cell", live() == 1 and cur()[0] == 2 and ev("() => document.activeElement.value") == "Cy", cur())
    pg.keyboard.type("Cyrus"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("Return saves and edits the same column of the next row (here: nowhere further, it stays)", names()[2] == "Cyrus" and cur()[0] == 2 and live() == 1, (names(), cur()))
    pg.keyboard.press("Escape"); pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    rows.nth(0).locator(".rst-cell").nth(0).click(); pg.keyboard.press("Delete"); pg.wait_for_timeout(200)
    check("Delete removes the selected resource (Undo is in the toast) and selects its neighbour", names() == ["Bo", "Cyrus"] and "Removed" in pg.inner_text("#toastMsg") and ev("() => document.querySelectorAll('#resourceSheetBody .rst-row.selected').length") == 1, names())

    # Add Resource: the new resource is the selection and its name is open (the pool stays sorted by name, so it lands where its name sorts)
    ev("() => { project.resources = [{id: 'r1', name: 'Ann', maxUnits: 100}, {id: 'r2', name: 'Ben', maxUnits: 100}, {id: 'r3', name: 'Cy', maxUnits: 100}]; rstSelId = null; rsCursor = null; save(); render(); }"); pg.wait_for_timeout(200)
    pg.locator(".rst-add-row").click(); pg.wait_for_timeout(250)
    check("Add Resource selects the new resource and opens its name for typing", len(names()) == 4 and ev("() => document.activeElement.value").startswith("New resource") and live() == 1 and ev("() => document.querySelectorAll('#resourceSheetBody .rst-row.selected').length") == 1, (names(), cur()))
    pg.keyboard.type("Bea"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("...typing names it at once", "Bea" in names(), names())
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
