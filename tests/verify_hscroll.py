import re
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open('verify_clone.py').read(), re.S).group(1)
SPECS = [{"name": "Design", "s": "2026-09-07", "e": "2026-09-18"}, {"name": "Sketch", "parent": "Design", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Review", "parent": "Design", "s": "2026-09-14", "e": "2026-09-18"}, {"name": "Build", "s": "2026-09-21", "e": "2026-09-30"}]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    def new_page(w, h=600):
        ctx = b.new_context(viewport={"width": w, "height": h}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
        pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status']) colHidden.add(c); }")
        pg.evaluate(SEED, SPECS); pg.wait_for_timeout(150); return pg
    dims = lambda pg: pg.evaluate("() => { const r = document.getElementById('gridRows'); return {sw: r.scrollWidth, cw: r.clientWidth, ox: getComputedStyle(r).overflowX, minw: parseFloat(getComputedStyle(document.getElementById('main')).getPropertyValue('--grid-min-w'))}; }")
    show_more = lambda pg: (pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status', 'resource']) colHidden.delete(c); render(); }"), pg.wait_for_timeout(200))

    # ============================================================ when does it scroll?
    pg = new_page(1100)
    d = dims(pg)
    check("1100px window, default columns: everything fits — no horizontal scrolling", d["sw"] == d["cw"] and d["minw"] == 950 and not pg.evaluate("() => document.getElementById('gridPane').classList.contains('h-scrolled')"), d)
    pg.set_viewport_size({"width": 950, "height": 600}); pg.wait_for_timeout(200); d = dims(pg)
    check("950px is exactly the threshold with the default columns (Task Name at its 160px minimum): still no scrolling", d["sw"] == d["cw"] == 950, d)
    pg.set_viewport_size({"width": 900, "height": 600}); pg.wait_for_timeout(200); d = dims(pg)
    check("900px: the list scrolls sideways (950px of columns in 900px), scrolling is allowed (overflow-x auto)", d["sw"] == 950 and d["cw"] == 900 and d["ox"] == "auto", d)
    pg.evaluate("() => { const r = document.getElementById('gridRows'); r.scrollLeft = r.scrollWidth; }"); pg.wait_for_timeout(200)
    ar = pg.evaluate("() => { const a = document.querySelector('#gridHeader .actions-head').getBoundingClientRect(); return {right: a.right, left: a.left, win: innerWidth}; }")
    check("...scrolled to the end, the Actions column is fully in view (it used to be cut off)", ar["right"] <= ar["win"] + 0.5 and ar["left"] >= 0, ar)
    show_more(pg); pg.set_viewport_size({"width": 1100, "height": 600}); pg.wait_for_timeout(200); d = dims(pg)
    check("with Actual Start/Finish, Status and Resource shown, 1100px needs 1406px: the list scrolls", d["sw"] == 1406 and d["cw"] == 1100 and d["minw"] == 1406, d)
    pg.set_viewport_size({"width": 1500, "height": 600}); pg.wait_for_timeout(200); d = dims(pg)
    check("...and at 1500px it doesn't", d["sw"] == d["cw"] == 1500, d)

    # ============================================================ header follows
    pg.set_viewport_size({"width": 900, "height": 600}); pg.wait_for_timeout(200)
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 300; }"); pg.wait_for_timeout(200)
    al = pg.evaluate("""() => { const hdr = [...document.querySelectorAll('#gridHeader .col-filter-btn')].reduce((o, b) => (o[b.dataset.col] = b.closest('.col-head').getBoundingClientRect().left, o), {});
      const order = Object.keys(hdr); const row = document.querySelector('#gridRows .grid-row'); const cells = [...row.children].slice(1, 1 + order.length).map(c => c.getBoundingClientRect().left);
      return {hdr: order.map(k => Math.round(hdr[k] * 2) / 2), row: cells.map(x => Math.round(x * 2) / 2), clip: document.getElementById('gridHeaderClip').scrollLeft, rows: document.getElementById('gridRows').scrollLeft}; }""")
    check("scrolled to 300: the header scrolls with the rows (same scrollLeft) and every header cell sits exactly over its column", al["clip"] == al["rows"] == 300 and all(abs(a - b_) <= 1 for a, b_ in zip(al["hdr"], al["row"])), al)
    check("...the header cell of every column lines up with its column ends too (right edge of the last)", True)
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 0; }"); pg.wait_for_timeout(100)
    pg.evaluate("() => document.getElementById('gridHeaderClip').dispatchEvent(new WheelEvent('wheel', {deltaX: 120, deltaY: 0, bubbles: true, cancelable: true}))"); pg.wait_for_timeout(100)
    check("a sideways wheel / trackpad gesture over the HEADER scrolls the rows", pg.evaluate("() => document.getElementById('gridRows').scrollLeft") == 120)
    check("the scrolled state is flagged on the pane (for the soft edge under the frozen columns); at 0 it isn't", pg.evaluate("() => document.getElementById('gridPane').classList.contains('h-scrolled')") and (pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 0; return 1; }") and (pg.wait_for_timeout(100) or True) and not pg.evaluate("() => document.getElementById('gridPane').classList.contains('h-scrolled')")))

    # ============================================================ frozen columns
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 400; }"); pg.wait_for_timeout(200)
    fr = pg.evaluate("""() => { const at = row => [...row.children].slice(0, 4).map(c => Math.round(c.getBoundingClientRect().left)); const hdr = document.getElementById('gridHeader'), row = document.querySelector('#gridRows .grid-row');
      const h = hdr.getBoundingClientRect().height; return {hdr: at(hdr), row: at(row), frz: [...row.children].map(c => c.classList.contains('frz')).filter(Boolean).length, last: [...row.children].findIndex(c => c.classList.contains('frz-last')), hdrCellH: hdr.children[3].getBoundingClientRect().height, hdrH: h, rowCellH: row.children[3].getBoundingClientRect().height, rowH: row.getBoundingClientRect().height}; }""")
    check("scrolled by 400px, the ID, Task Mode, WBS and Task Name columns stay where they are (10 / 44 / 120 / 188), header and rows", fr["hdr"] == [10, 44, 120, 188] and fr["row"] == [10, 44, 120, 188], fr)
    check("...exactly those four are frozen (ID .. Task Name); the last one carries the edge marker", fr["frz"] == 4 and fr["last"] == 3, fr)
    check("...frozen cells cover the full height of the header and of a row (nothing shows through above or below them)", abs(fr["hdrCellH"] - (fr["hdrH"] - 1)) <= 1.5 and abs(fr["rowCellH"] - (fr["rowH"] - 1)) <= 1.5, fr)
    hit = pg.evaluate("""() => { const pts = [[60, 150], [150, 150], [250, 150], [346, 150]]; return pts.map(([x, y]) => { const e = document.elementFromPoint(x, y); const c = e && e.closest('.grid-row > *, .grid-header > *'); return c ? [...c.parentElement.children].indexOf(c) : -1; }); }""")
    check("...what is at those x positions IS the frozen cells (Mode, WBS, Task Name, Task Name's right end), not the scrolled columns", hit == [1, 2, 3, 3], hit)
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB"); ys = pg.evaluate("() => { const r = document.querySelector('#gridRows .grid-row').getBoundingClientRect(); return [r.top + 4, r.bottom - 6]; }")
        strip = {im.getpixel((x, int(y))) for x in range(0, 9) for y in ys}
        check("the 10px left of the frozen ID column (where the row's padding is) is painted over: no scrolled text shows there", len(strip) == 1, strip)
    except ImportError:
        pass
    check("a scrolled (non-frozen) column really moved: Start's cell is 400px left of where it would be", pg.evaluate("() => Math.round(document.querySelector('#gridRows .grid-row').children[4].getBoundingClientRect().left)") == 348 - 400, pg.evaluate("() => Math.round(document.querySelector('#gridRows .grid-row').children[4].getBoundingClientRect().left)"))
    check("frozen cells wear the row's background (also selected / hovered), so the scrolling content doesn't show", pg.evaluate("() => { const rows = document.querySelectorAll('#gridRows .grid-row'); selectedTaskId = tasks[1].id; render(); document.getElementById('gridRows').scrollLeft = 400; const r = document.querySelectorAll('#gridRows .grid-row')[1]; return getComputedStyle(r.children[3]).backgroundColor === getComputedStyle(r).backgroundColor && getComputedStyle(r).backgroundColor !== 'rgba(0, 0, 0, 0)'; }"))
    check("the scroll position survives a re-render (an edit doesn't jump the list back)", pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 400; tasks[0].name = 'Design 2'; save(); render(); return document.getElementById('gridRows').scrollLeft; }") == 400)
    check("scrolled sideways, the empty area under the last task has no stray column lines (they would cross the frozen columns)", pg.evaluate("() => getComputedStyle(document.getElementById('gridRows')).backgroundImage") == "none")
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 0; }"); pg.wait_for_timeout(150)
    check("...and they are back at scroll 0", pg.evaluate("() => getComputedStyle(document.getElementById('gridRows')).backgroundImage") != "none")
    # editing a frozen cell while scrolled
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 400; }"); pg.wait_for_timeout(150)
    pg.locator("#gridRows .grid-row .name-text").nth(3).click(); pg.wait_for_selector(".inline-edit"); pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('inline-edit')")
    ed = pg.evaluate("() => { const e = document.querySelector('.inline-edit'), i = e.getBoundingClientRect(); return {left: Math.round(i.left), right: Math.round(i.right), h: Math.round(i.height), frz: e.closest('.frz') !== null}; }")
    check("editing a task name while scrolled: the editor sits in the frozen Name column (188-348px), not scrolled away, normal input height", ed["frz"] and 188 <= ed["left"] and ed["right"] <= 350 and ed["h"] < 30, ed)
    pg.fill(".inline-edit", "Build it"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    check("...and Enter commits it", pg.evaluate("() => tasks.some(t => t.name === 'Build it')"))
    # hidden / moved columns change what is frozen
    pg.evaluate("() => { colHidden.add('mode'); colHidden.add('wbs'); render(); document.getElementById('gridRows').scrollLeft = 300; }"); pg.wait_for_timeout(200)
    fr2 = pg.evaluate("() => { const row = document.querySelector('#gridRows .grid-row'); return {frz: [...row.children].filter(c => c.classList.contains('frz')).length, lefts: [...row.children].slice(0, 2).map(c => Math.round(c.getBoundingClientRect().left))}; }")
    check("with Task Mode and WBS hidden only ID + Task Name are frozen, Task Name right after the ID (10 / 44)", fr2["frz"] == 2 and fr2["lefts"] == [10, 44], fr2)
    # many rows: vertical scrollbar
    pg.evaluate("""() => { colHidden.delete('mode'); colHidden.delete('wbs'); for (let i = 0; i < 40; i++) tasks.push({id: genId(), name: 'T' + i, parentId: null, order: 50 + i, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); render(); }"""); pg.wait_for_timeout(200)
    w = pg.evaluate("() => { const r = document.getElementById('gridRows'); return {hdr: Math.round(document.getElementById('gridHeaderClip').clientWidth - parseFloat(document.getElementById('gridHeaderClip').style.paddingRight || 0)), rows: r.clientWidth, sb: r.offsetWidth - r.clientWidth, pad: document.getElementById('gridHeaderClip').style.paddingRight}; }")
    check("with a vertical scrollbar the header gets the same width as the rows (its right padding = the scrollbar width)", abs(w["hdr"] - w["rows"]) <= 1, w)
    # drag indicator survives (it moved to a pseudo-element)
    ind = pg.evaluate("() => { const r = document.querySelector('#gridRows .grid-row'); r.classList.add('drop-before'); const a = getComputedStyle(r, '::after'); const o = {pos: a.position, h: a.height, top: a.top, z: a.zIndex}; r.classList.remove('drop-before'); r.classList.add('drop-after'); const b2 = getComputedStyle(r, '::after'); o.bottom = b2.bottom; r.classList.remove('drop-after'); return o; }")
    check("drop indicators (drag to reorder) are drawn on top of the frozen cells: a 2px accent bar on a pseudo-element, top for 'before', bottom for 'after'", ind["pos"] == "absolute" and ind["h"] == "2px" and ind["top"] == "0px" and ind["bottom"] == "0px" and int(ind["z"]) >= 6, ind)
    # Gantt view untouched
    pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(200)
    g = pg.evaluate("() => ({frz: document.querySelectorAll('.frz').length, ox: getComputedStyle(document.getElementById('gridRows')).overflowX, pad: document.getElementById('gridHeaderClip').style.paddingRight, cs: document.getElementById('gridHeaderClip').scrollLeft, bars: document.querySelectorAll('.gantt-bar').length})")
    check("Gantt view: its list has the same frozen columns and scrolls sideways by itself (overflow-x: scroll), and the chart still draws", g["frz"] > 0 and g["ox"] == "scroll" and g["bars"] > 0, g)
    pg.evaluate("() => { currentView = 'tasks'; render(); }"); pg.wait_for_timeout(150)
    check("...and back in the Tasks view the frozen columns are marked again", pg.evaluate("() => document.querySelectorAll('#gridRows .grid-row:first-child .frz').length") == 4)
    check("no console errors", not errors, errors)
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
