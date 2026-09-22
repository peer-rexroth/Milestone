import re
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1700, "height": 700}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate(SEED, [{"name": "Auto", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Man", "s": "2026-09-07", "e": "2026-09-11", "extra": {"taskMode": "manual"}}])
    pg.evaluate("() => { project.fieldNames = { date1: 'Due' }; normalizeData(); for (const c of ['actualStart', 'actualFinish', 'date1']) colHidden.delete(c); render(); }"); pg.wait_for_timeout(150)
    hc = lambda: pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col)")
    tid = lambda n: pg.evaluate("n => tasks.find(t => t.name === n).id", n)
    def open_editor(name, col):
        pg.locator(f".grid-row[data-id='{tid(name)}']").locator(":scope > div").nth(1 + hc().index(col)).click(); pg.wait_for_selector(".inline-edit"); pg.wait_for_timeout(120)
    def close_editor(): pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    cols = [("start", "Start"), ("end", "Finish"), ("actualStart", "Actual Start"), ("actualFinish", "Actual Finish"), ("date1", "custom Date1")]
    for name in ("Auto", "Man"):
        for col, label in cols:
            open_editor(name, col)
            m = pg.evaluate("""() => { const w = document.querySelector('.inline-wrap'); const i = document.querySelector('.inline-edit');
              const box = (w || i).getBoundingClientRect(), row = (w || i).parentElement.getBoundingClientRect();
              const cal = document.querySelector('.inline-cal'); const cr = cal && cal.getBoundingClientRect();
              return {type: i.type, wrapped: !!w, width: box.width, clipped: i.scrollWidth > i.clientWidth + 1, insideRow: box.right <= row.right + 0.5, intoNeighbour: box.right - ((w || i).nextElementSibling.getBoundingClientRect().left), gapL: box.left - (w || i).previousElementSibling.getBoundingClientRect().right, gapR: (w || i).nextElementSibling.getBoundingClientRect().left - box.right, h: box.height, outline: getComputedStyle(i).outlineStyle,
                      calInside: cal ? cr.right <= box.right + 0.5 && cr.left >= box.left : true, topmost: document.elementFromPoint(box.right - 8, box.top + box.height / 2) !== null && (w || i).contains(document.elementFromPoint(box.right - 8, box.top + box.height / 2))}; }""")
            check(f"{name}: {label} editor is a {'typed box + calendar button' if name == 'Man' else 'native date input'}", (m["type"] == "text" and m["wrapped"]) if name == "Man" else m["type"] == "date", m)
            check(f"{name}: {label} editor is compact (about 100px, one 21px-ish row) yet holds a date and its picker icon", 95 <= m["width"] <= 101 and m["h"] <= 24 and m["calInside"], m)
            check(f"{name}: {label} editor sits INSIDE its column (no spill into the next cell), with the same space on the left and on the right, and has a single focus ring (no browser outline on top of the accent border)", m["intoNeighbour"] <= 0 and abs(m["gapL"] - m["gapR"]) <= 0.6 and 1.5 <= m["gapL"] <= 3, m)
            check(f"{name}: {label} editor's right end is on top of the neighbouring cell (clickable), inside the row", m["topmost"] and m["insideRow"], m)
            close_editor()
    # the picker button of the typed editor really opens/commits a date
    open_editor("Man", "actualFinish")
    check("the calendar button opens the picker (a hidden native date input is created and used)", pg.locator(".inline-cal").count() == 1)
    pg.evaluate("() => { const i = document.querySelector('.inline-wrap input[type=text]'); i.value = '15.09.2026'; }"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    check("...a picked/typed date lands in the cell as dd.mm.yyyy", pg.evaluate("n => tasks.find(t => t.name === n).actualFinish", "Man") == "2026-09-15")
    # normal (closed) cells keep their narrow layout
    check("closed cells are unaffected: every date column (Start, Finish, Actual Start/Finish, custom Date) is the same 104px wide", pg.evaluate("() => { const h = [...document.querySelectorAll('#gridHeader .col-filter-btn')].filter(b => ['start', 'end', 'actualStart', 'actualFinish', 'date1'].includes(b.dataset.col)).map(b => b.closest('.col-head').getBoundingClientRect().width); return h.length === 5 && h.every(w => w === 104); }"))
    # the dialog also uses real date inputs
    pg.evaluate("n => openTaskModal(tasks.find(t => t.name === n).id)", "Auto"); pg.wait_for_selector("#taskModalBg.open")
    check("task dialog: Actual Start and Actual Finish are date inputs (with the browser's picker)", pg.get_attribute("#taskActualStartInput", "type") == "date" and pg.get_attribute("#taskActualFinishInput", "type") == "date")
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
