"""Chart for Slides, More Options > Solid bars: a task that has not started is drawn in full colour (not a pale 22% track), and the done part is the same bar a shade darker."""
from playwright.sync_api import sync_playwright
import os, re
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
SEED = """() => { const mk = (id, name, parent, order, s, e, p) => ({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: p || 0, predecessors: [], taskMode: 'auto', updatedAt: 1 });
  tasks = [mk('a','Alpha',null,0,'2027-01-04','2027-02-26'), mk('a1','A one','a',0,'2027-01-04','2027-01-29'), mk('a2','A two','a',1,'2027-02-01','2027-02-26',50)];
  normalizeData(); save(); render(); openSlideChart(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 950}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(400)
    pg.evaluate("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))"); ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(500); ev("() => scMore(true)"); pg.wait_for_timeout(200)
    svg = lambda: ev("() => scBuilt.charts[0]")
    check("the switch 'Solid bars' exists and is off by default", pg.is_visible("#scSolid") and not pg.is_checked("#scSolid"))
    check("off: bars are a pale track (opacity .22)", 'opacity=".22"' in svg())
    pg.check("#scSolid", force=True); pg.wait_for_timeout(400)
    check("on: no pale track any more, the bars are in full colour", 'opacity=".22"' not in svg())
    check("on: the done part is a darker overlay of the same width logic (one overlay for the 50% task)", svg().count('fill="#000" opacity=".25"') == 1, svg().count('fill="#000" opacity=".25"'))
    pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(300)
    ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); openSlideChart(); scMore(true); }"); pg.wait_for_timeout(400)
    check("the choice is remembered", pg.is_checked("#scSolid"))
    ev("""() => { tasks.push({ id: 'f', name: 'Finish only', parentId: 'a', order: 2, startDate: '2027-02-12', endDate: '2027-02-12', progress: 0, predecessors: [], taskMode: 'manual', startText: 'TBD', endText: null, updatedAt: 1 },
      { id: 's', name: 'Start only', parentId: 'a', order: 3, startDate: '2027-02-05', endDate: '2027-02-05', progress: 0, predecessors: [], taskMode: 'manual', startText: null, endText: 'TBD', updatedAt: 1 },
      { id: 'n', name: 'No dates', parentId: 'a', order: 4, startDate: '2027-02-05', endDate: '2027-02-05', progress: 0, predecessors: [], taskMode: 'manual', startText: 'TBD', endText: 'TBD', updatedAt: 1 }); normalizeData(); scChanged ? scChanged() : 0; render(); closeSlideChart(); openSlideChart(); }"""); pg.wait_for_timeout(500)
    sv = svg()
    check("a task with only a start or only a finish is on the chart; one with no date at all is not", "Finish only" in sv and "Start only" in sv and "No dates" not in sv, [n for n in ("Finish only", "Start only", "No dates") if n in sv])
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
