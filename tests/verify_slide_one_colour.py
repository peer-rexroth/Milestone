"""Chart for Slides, Palette > One Colour: every block in one colour, picked with a single well; the text colour stays free; Custom brings the five wells back."""
from playwright.sync_api import sync_playwright
import os, re
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
SEED = """() => { const mk = (id, name, parent, order, s, e) => ({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'auto', updatedAt: 1 });
  tasks = [mk('a','Alpha',null,0,'2027-01-04','2027-02-26'), mk('a1','A one','a',0,'2027-01-04','2027-01-29'), mk('b','Beta',null,1,'2027-03-01','2027-04-30'), mk('b1','B one','b',0,'2027-03-01','2027-03-31'), mk('c','Gamma',null,2,'2027-05-03','2027-05-28'), mk('c1','C one','c',0,'2027-05-03','2027-05-14')];
  normalizeData(); save(); render(); openSlideChart(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 950}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(400)
    pg.evaluate("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))"); ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(500)
    ev("() => scMore(true)"); pg.wait_for_timeout(200)
    fills = lambda: sorted(set(re.findall(r'fill="(#[0-9A-Fa-f]{6})"', ev("() => scBuilt.charts[0]"))))
    check("Palette offers One Colour between Corporate and Custom", ev("() => [...document.querySelectorAll('#scPalette option')].map(o => o.textContent).join()") == "Corporate,One Colour,Custom")
    corp = [f for f in fills() if f.upper() in ('#1E2A78', '#0069B1', '#34A6DC', '#3BB8B8', '#24778D')]
    check("Corporate draws several block colours", len(corp) >= 3, corp)
    pg.select_option("#scPalette", "one"); pg.wait_for_timeout(400)
    check("One Colour shows a single colour well, labelled Colour", ev("() => [...document.querySelectorAll('#scCol0, #scCol1, #scCol2, #scCol3, #scCol4')].filter(e => e.offsetParent).length") == 1 and ev("() => document.getElementById('scColsLbl').textContent") == "Colour")
    check("...and the text colour well is still there", ev("() => !!document.getElementById('scInk').offsetParent"))
    one = [f for f in fills() if f.upper() in ('#1E2A78', '#0069B1', '#34A6DC', '#3BB8B8', '#24778D')]
    check("every block is the first colour (#1E2A78) now", one == ['#1E2A78'] or [x.upper() for x in one] == ['#1E2A78'], one)
    ev("() => { const w = document.getElementById('scCol0'); w.value = '#25a62d'; w.dispatchEvent(new Event('input', { bubbles: true })); }"); pg.wait_for_timeout(400)
    check("picking a colour recolours every block and stays on One Colour", ev("() => document.getElementById('scPalette').value") == "one" and '#25A62D' in [f.upper() for f in fills()] and not [f for f in fills() if f.upper() == '#1E2A78'], fills())
    ev("() => { const w = document.getElementById('scInk'); w.value = '#222222'; w.dispatchEvent(new Event('input', { bubbles: true })); }"); pg.wait_for_timeout(300)
    check("changing the text colour does not leave One Colour", ev("() => document.getElementById('scPalette').value") == "one")
    ev("() => closeSlideChart()"); ev("() => openSlideChart()"); pg.wait_for_timeout(400); ev("() => scMore(true)")
    check("the choice is remembered (One Colour, the colour)", ev("() => [document.getElementById('scPalette').value, document.getElementById('scCol0').value]") == ["one", "#25a62d"])
    pg.select_option("#scPalette", "custom"); pg.wait_for_timeout(300)
    check("Custom brings back the five wells, starting from that colour", ev("() => [...document.querySelectorAll('#scCol0, #scCol1, #scCol2, #scCol3, #scCol4')].filter(e => e.offsetParent).length") == 5 and ev("() => document.getElementById('scColsLbl').textContent") == "Colours" and ev("() => document.getElementById('scCol3').value") == "#25a62d")
    pg.select_option("#scPalette", "corporate"); pg.wait_for_timeout(300)
    check("Corporate restores its five colours", ev("() => document.getElementById('scCol1').value.toLowerCase()") == "#0069b1")
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
