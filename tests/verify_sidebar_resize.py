"""The sidebar's right edge is a drag handle (as in ClearDesk): drag changes the width within 220-480px, it is kept per device, a double-click resets it, the arrow keys nudge it."""
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
    ev = pg.evaluate; close = "() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))"; ev(close)
    w = lambda: ev("() => Math.round(document.getElementById('sidebar').getBoundingClientRect().width)")
    y = 400
    check("the handle has a 9px grab area and a col-resize cursor", ev("() => { const cs = getComputedStyle(document.getElementById('sidebarResizer'), '::before'); return cs.width === '9px' && cs.cursor === 'col-resize'; }"))
    check("the sidebar starts at 268px", w() == 268, w())
    pg.mouse.move(w(), y); pg.mouse.down(); pg.mouse.move(w() + 80, y, steps=5); pg.mouse.up(); pg.wait_for_timeout(100)
    check("dragging the edge 80px right widens it to 348px", w() == 348, w())
    pg.reload(); pg.wait_for_selector("#undoBtn"); ev(close)
    check("the width is kept after a reload", w() == 348, w())
    pg.mouse.move(w(), y); pg.mouse.down(); pg.mouse.move(2, y, steps=5); pg.mouse.up()
    check("it stops at 268px (the tools row never wraps)", w() == 268, w())
    pg.mouse.move(w(), y); pg.mouse.down(); pg.mouse.move(900, y, steps=5); pg.mouse.up()
    check("...and at 480px", w() == 480, w())
    pg.mouse.dblclick(w(), y); pg.wait_for_timeout(100)
    check("a double-click on the edge resets it to 268px", w() == 268, w())
    ev("() => document.getElementById('sidebarResizer').focus()"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("Shift+ArrowRight")
    check("→ nudges 16px, Shift+→ 48px", w() == 332, w())
    pg.keyboard.press("Home")
    check("Home resets it", w() == 268, w())
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
