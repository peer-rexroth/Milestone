"""A bad break or working-hours row in the Calendar sheet is marked on its field (red border + bubble) as well as in the toast; retyping clears it."""
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
    ev = pg.evaluate; ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    ev("() => { openPlanSettings('calendar'); }"); pg.wait_for_timeout(300)
    ev("() => { const r = document.getElementById('precisionMinute'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); onPrecisionChange(); }"); pg.wait_for_timeout(150)
    bad = lambda sel: ev("(s) => document.querySelector(s).classList.contains('dt-err')", sel)
    bubble = lambda: ev("() => !!document.querySelector('.dt-err-bubble.show')")
    ev("() => { document.getElementById('whBreakFrom').value = '13:00'; document.getElementById('whBreakTo').value = '12:00'; addWorkBreak(); }"); pg.wait_for_timeout(150)
    check("a break that ends before it starts marks its end field, with a bubble and the toast", bad("#whBreakTo") and bubble() and "break must end" in pg.inner_text("#toastMsg"))
    ev("() => { document.getElementById('whBreakFrom').value = ''; document.getElementById('whBreakTo').value = ''; document.getElementById('whBreakFrom').classList.remove('dt-err'); document.getElementById('whBreakTo').classList.remove('dt-err'); addWorkBreak(); }"); pg.wait_for_timeout(150)
    check("an empty break marks its first empty field", bad("#whBreakFrom"))
    ev("() => { document.getElementById('whDayAddSelect').value = '6'; addHoursDay(); }"); pg.wait_for_timeout(150)
    ev("() => { const r = document.querySelector('#whDayRows .whd-row .whd-breaks'); r.value = 'nonsense'; }")
    ev("() => { try { readHoursByDay(); } catch (e) {} }"); pg.wait_for_timeout(150)
    check("a day row whose hours or breaks cannot be read marks that field", ev("() => !!document.querySelector('#whDayRows .whd-row .dt-err')"))
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
