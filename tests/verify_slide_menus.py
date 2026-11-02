"""Chart for Slides: the Save As menu opens right above its button (right edges aligned) at any window size, although the dialog's blur is the reference of fixed
positions (scPlace corrects for it), and the Levels box starts on All."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); errors = []
    for vw, vh in ((1500, 900), (1100, 700), (800, 600)):
        pg = b.new_page(viewport={"width": vw, "height": vh}); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
        pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(400)
        pg.evaluate("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
        pg.evaluate("() => { const mk = (id, name, order) => ({ id, name, parentId: null, order, startDate: '2027-01-04', endDate: '2027-02-12', progress: 0, predecessors: [], taskMode: 'auto', updatedAt: 1 }); tasks = [mk('a', 'Alpha', 0), mk('b', 'Beta', 1)]; normalizeData(); save(); render(); openSlideChart(); }"); pg.wait_for_timeout(500)
        if vw == 1500: check("Levels starts on All", pg.evaluate("() => document.getElementById('scLevels').selectedOptions[0].textContent") == "All")
        pg.click("#scSaveBtn"); pg.wait_for_timeout(250)
        r = pg.evaluate("() => { const m = document.getElementById('scSaveMenu').getBoundingClientRect(), b = document.getElementById('scSaveBtn').getBoundingClientRect(); return { dr: m.right - b.right, gap: b.top - m.bottom }; }")
        check(f"{vw}x{vh}: the Save As menu sits right above its button, right edges aligned", abs(r["dr"]) <= 2 and 4 <= r["gap"] <= 12, r)
        pg.close()
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
