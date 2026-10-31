"""A refusal in the Edit Tasks dialog is shown on the field that is wrong (red border + bubble), not only as a toast; retyping clears it."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1400, "height": 900}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => { tasks.length = 0; for (const n of ['A','B']) tasks.push(Object.assign({id: genId(), name: n, parentId: null, order: tasks.length, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: []})); currentView = 'tasks'; normalizeData(); save(); render(); setSelection(tasks.map(t => t.id)); openBulkModal(); }"); pg.wait_for_timeout(300)
    pg.check("#bulkOn-pred"); pg.fill("#bulkVal-predId", "999"); pg.click("#bulkApplyBtn"); pg.wait_for_timeout(200)
    check("a wrong predecessor number marks its field", ev("() => document.getElementById('bulkVal-predId').classList.contains('dt-err')"))
    check("...with a bubble beside it", ev("() => !!document.querySelector('.dt-err-bubble.show')"))
    check("...and the toast too", "No task" in pg.inner_text("#toastMsg"))
    pg.fill("#bulkVal-predId", "1"); pg.wait_for_timeout(100)
    check("retyping clears the mark", ev("() => !document.getElementById('bulkVal-predId').classList.contains('dt-err') && !document.querySelector('.dt-err-bubble.show')"))
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
