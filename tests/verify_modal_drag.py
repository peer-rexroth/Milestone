"""A drag that starts inside a dialog (selecting text in a field) and is released on the backdrop does not close it; a plain click on the backdrop still does."""
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
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(500)
    ev = pg.evaluate
    opened = lambda: ev("() => document.getElementById('planModalBg').classList.contains('open')")
    def show():
        ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); openPlanModal('rename'); }"); pg.wait_for_timeout(400)
    show(); box = pg.locator("#planNameInput").bounding_box()
    pg.mouse.move(box["x"] + box["width"] - 6, box["y"] + box["height"] / 2); pg.mouse.down(); pg.mouse.move(8, 8, steps=8); pg.mouse.up(); pg.wait_for_timeout(200)
    check("selecting text in the plan name and releasing on the backdrop keeps the dialog open", opened())
    pg.mouse.click(8, 8); pg.wait_for_timeout(200)
    check("a plain click on the backdrop still closes it", not opened())
    check("no page errors", not errors, errors)
    b.close()
print(f"\n{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
