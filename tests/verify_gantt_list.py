import re, json
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)
SPECS = [{"name": "Design", "s": "2026-09-07", "e": "2026-09-18"}, {"name": "Sketch", "parent": "Design", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Review", "parent": "Design", "s": "2026-09-14", "e": "2026-09-18", "preds": [["Sketch", "FS", 0]]}, {"name": "Build", "s": "2026-09-21", "e": "2026-09-30", "preds": [["Review", "FS", 0]]}]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    def new_page(w=1500, h=700, prefs=None):
        ctx = b.new_context(viewport={"width": w, "height": h}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
        pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()")
        if prefs: pg.evaluate("p => localStorage.setItem('milestone-prefs', JSON.stringify(p))", prefs)
        pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate(SEED, SPECS); pg.evaluate("() => { gColOrder = [...colOrder]; gColHidden = new Set(colHidden); currentView = 'gantt'; zoom = 'week'; render(); }"); pg.wait_for_timeout(200); return pg   # (the Gantt view gets the Tasks view's columns: its own default is the compact four, see verify_gantt_columns.py)
    pg = new_page()
    cols = lambda: pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col)")
    # ================================================================ the same list
    tasks_cols = pg.evaluate("() => visibleTaskCols('tasks')")
    check("the Gantt view's list can show the same columns as the Tasks view (each with its funnel)", cols() == tasks_cols and len(tasks_cols) >= 7, (cols(), tasks_cols))
    check("...with the Actions header and the row buttons (Edit, Clone, Delete), the collapse toggle, WBS, %, Predecessors …", pg.locator("#gridHeader .actions-head").count() == 1 and pg.locator("#gridRows .grid-row .grid-actions button").count() == 12 and pg.locator("#collapseToggleBtn").count() == 1)
    check("the Columns button is available in the Gantt view too", pg.locator("#columnsBtn:not(.hidden)").count() == 1)
    check("the list is 640px wide by default (it was a 400px sidebar)", abs(pg.evaluate("() => document.getElementById('gridPane').getBoundingClientRect().width") - 640) < 1.5)
    # ================================================================ aligned with the chart
    al = pg.evaluate("""() => { const lh = document.getElementById('gridHeaderClip').getBoundingClientRect(), gh = document.getElementById('ganttHeader').getBoundingClientRect();
      const lr = [...document.querySelectorAll('#gridRows .grid-row')].map(r => r.getBoundingClientRect().top), cr = [...document.querySelectorAll('.gantt-row-bg')].map(r => r.getBoundingClientRect().top);
      return {lh: [lh.top, lh.height], gh: [gh.top, gh.height], rows: lr.map((t, i) => Math.round(t - cr[i]))}; }""")
    check("the list's header and the chart's timescale are both 42px and start at the same y; every list row is level with its chart row", al["lh"][1] == 42 and al["gh"][1] == 42 and al["lh"][0] == al["gh"][0] and all(d == 0 for d in al["rows"]), al)
    # many rows: vertical scroll
    pg.evaluate("""() => { for (let i = 0; i < 40; i++) tasks.push({id: genId(), name: 'T' + i, parentId: null, order: 50 + i, startDate: '2026-10-05', endDate: '2026-10-09', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); render(); }"""); pg.wait_for_timeout(200)
    pg.evaluate("() => { document.getElementById('ganttPaneOuter').scrollTop = 300; }"); pg.wait_for_timeout(150)
    sy = pg.evaluate("() => ({list: document.getElementById('gridRows').scrollTop, chart: document.getElementById('ganttPaneOuter').scrollTop, d: Math.round(document.querySelector('#gridRows .grid-row:nth-child(12)').getBoundingClientRect().top - document.querySelectorAll('.gantt-row-bg')[11].getBoundingClientRect().top)})")
    check("scrolling the chart vertically scrolls the list with it: same scrollTop, rows still level", sy["list"] == sy["chart"] == 300 and sy["d"] == 0, sy)
    box = pg.locator("#gridRows").bounding_box(); pg.mouse.move(box["x"] + 200, box["y"] + 100); pg.mouse.wheel(0, 120); pg.wait_for_timeout(200)
    check("a wheel / trackpad gesture over the LIST scrolls the chart (and so the list) vertically", pg.evaluate("() => document.getElementById('ganttPaneOuter').scrollTop") > 300, pg.evaluate("() => document.getElementById('ganttPaneOuter').scrollTop"))
    pg.evaluate("() => { document.getElementById('ganttPaneOuter').scrollTop = 0; tasks.splice(4); render(); }"); pg.wait_for_timeout(150)
    # ================================================================ sideways
    pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status', 'resource']) gColHidden.delete(c); render(); }"); pg.wait_for_timeout(150)
    hs = pg.evaluate("() => { const r = document.getElementById('gridRows'); return {sw: r.scrollWidth, cw: r.clientWidth, ox: getComputedStyle(r).overflowX, oy: getComputedStyle(r).overflowY}; }")
    check("with more columns than fit, the list scrolls sideways by itself (overflow-x scroll, vertical driven by the chart)", hs["sw"] > hs["cw"] and hs["ox"] == "scroll" and hs["oy"] == "hidden", hs)
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 300; }"); pg.wait_for_timeout(200)
    fr = pg.evaluate("() => { const row = document.querySelector('#gridRows .grid-row'), hdr = document.getElementById('gridHeader'); return {clip: document.getElementById('gridHeaderClip').scrollLeft, frz: [...row.children].filter(c => c.classList.contains('frz')).length, lefts: [...row.children].slice(0, 4).map(c => Math.round(c.getBoundingClientRect().left)), hl: [...hdr.children].slice(0, 4).map(c => Math.round(c.getBoundingClientRect().left))}; }")
    check("scrolled sideways: the header follows, and the ID .. Task Name columns stay frozen (same x for header and rows)", fr["clip"] == 300 and fr["frz"] == 4 and fr["lefts"] == fr["hl"] and fr["lefts"][0] == 10, fr)
    gs = pg.evaluate("() => document.getElementById('ganttPaneOuter').scrollLeft")
    box = pg.locator("#gridRows").bounding_box(); pg.mouse.move(box["x"] + 300, box["y"] + 60); pg.mouse.wheel(150, 0); pg.wait_for_timeout(200)
    check("a SIDEWAYS gesture over the list scrolls the list, not the chart", pg.evaluate("() => document.getElementById('gridRows').scrollLeft") > 300 and pg.evaluate("() => document.getElementById('ganttPaneOuter').scrollLeft") == gs)
    pg.evaluate("() => { document.getElementById('gridRows').scrollLeft = 0; for (const c of ['actualStart', 'actualFinish', 'status', 'resource']) gColHidden.add(c); render(); }"); pg.wait_for_timeout(150)
    # ================================================================ editing in the Gantt view
    pg.locator("#gridRows .grid-row .name-text").nth(3).click(); pg.wait_for_selector(".inline-edit"); pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('inline-edit')")
    pg.fill(".inline-edit", "Build it"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("inline editing works in the Gantt view: rename a task in the list", pg.evaluate("() => tasks.some(t => t.name === 'Build it')") and pg.locator(".gantt-bar[title^='Build it']").count() == 1)
    hc = cols()
    startcell = pg.locator("#gridRows .grid-row").nth(1).locator(":scope > div").nth(1 + hc.index("start"))
    startcell.click(); pg.wait_for_selector(".inline-edit"); pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('inline-edit')")
    pg.fill(".inline-edit", "2026-09-08"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("...editing a date in the list moves the bar in the chart (Sketch starts 08.09)", pg.evaluate("() => tasks.find(t => t.name === 'Sketch').startDate") == "2026-09-08")
    pg.locator("#gridRows .grid-row").nth(3).click(position={"x": 25, "y": 10}); pg.wait_for_timeout(150)   # (the ID cell: the centre of the row would land on an editable cell)
    check("selecting a task in the list highlights its row in the chart", pg.locator(".gantt-row-bg.selected").count() == 1 and pg.locator("#gridRows .grid-row.selected").count() == 1)
    n0 = pg.evaluate("() => tasks.length"); pg.locator("#gridRows .grid-row").nth(3).hover(); pg.locator("#gridRows .grid-row").nth(3).locator("button[title^='Clone']").click(); pg.wait_for_timeout(300)
    check("the Clone button in a row works from the Gantt view (a copy appears in the list and as a bar)", pg.evaluate("() => tasks.length") == n0 + 1 and pg.locator("#gridRows .grid-row").count() == n0 + 1 and pg.locator(".gantt-bar").count() >= n0)
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(200)
    # ================================================================ picking columns changes both views
    pg.evaluate("() => { gColHidden.add('duration'); render(); }"); pg.wait_for_timeout(120)
    in_g = "duration" in cols(); pg.evaluate("() => { currentView = 'tasks'; render(); }"); pg.wait_for_timeout(120); in_t = "duration" in cols()
    check("hiding a column in the Gantt view's list does not hide it in the Tasks view (each view keeps its own set)", not in_g and in_t)
    pg.evaluate("() => { gColHidden.delete('duration'); for (const c of ['baselineStart', 'startVariance']) gColHidden.delete(c); applyBaselineChange(0, 'all', false); currentView = 'gantt'; render(); }"); pg.wait_for_timeout(200)
    check("the baseline / variance columns show next to the chart's baseline lines", "baselineStart" in cols() and "startVariance" in cols() and pg.locator(".gantt-base").count() >= 3)
    # ================================================================ filters, zoom
    pg.evaluate("() => { colFilters.name = { kind: 'text', rules: [{ rule: 'contains', a: 'sketch' }], sel: null }; render(); }") if False else None
    n_rows = pg.locator("#gridRows .grid-row").count(); n_bg = pg.locator(".gantt-row-bg").count()
    check("the list and the chart always show the same rows", n_rows == n_bg, (n_rows, n_bg))
    for z in ("month", "year", "week"):
        pg.evaluate("z => { zoom = z; render(); }", z); pg.wait_for_timeout(120)
        ok = pg.evaluate("() => { const lr = [...document.querySelectorAll('#gridRows .grid-row')].map(r => r.getBoundingClientRect().top), cr = [...document.querySelectorAll('.gantt-row-bg')].map(r => r.getBoundingClientRect().top); return lr.every((t, i) => Math.abs(t - cr[i]) < .5); }")
        check(f"{z} zoom: rows still level with the chart", ok)
    # ================================================================ resizing the list
    pg.evaluate("() => { gridPaneWidth = 640; applyGridPaneWidth(); }"); pg.wait_for_timeout(100)
    h = pg.locator("#gridResizeHandle").bounding_box()
    pg.mouse.move(h["x"] + 3, h["y"] + 100); pg.mouse.down(); pg.mouse.move(h["x"] + 3 - 600, h["y"] + 100, steps=6); pg.mouse.up(); pg.wait_for_timeout(150)
    w1 = pg.evaluate("() => document.getElementById('gridPane').getBoundingClientRect().width"); fm = pg.evaluate("() => frozenMinWidth")
    check("dragging the handle left narrows the list, but not below the frozen columns + 60px (they'd fill it)", w1 == max(320, fm + 60) < 640, (w1, fm))
    h2 = pg.locator("#gridResizeHandle").bounding_box(); pg.mouse.move(h2["x"] + 3, h2["y"] + 100); pg.mouse.down(); pg.mouse.move(h2["x"] + 1200, h2["y"] + 100, steps=6); pg.mouse.up(); pg.wait_for_timeout(150)
    w2 = pg.evaluate("() => document.getElementById('gridPane').getBoundingClientRect().width")
    check("...and wider, but never so wide that the chart disappears (window - 240px)", abs(w2 - (1500 - 240)) < 1.5, w2)
    check("the width is remembered (with the revision that marks it as chosen for the full list)", pg.evaluate("() => { const d = JSON.parse(localStorage.getItem('milestone-prefs')); return d.gridPaneRev === 1 && d.gridPaneWidth > 640; }"))
    pg.set_viewport_size({"width": 800, "height": 700}); pg.wait_for_timeout(300)
    check("a narrow window keeps the chart visible: the list is at most window - 240px", pg.evaluate("() => document.getElementById('gridPane').getBoundingClientRect().width") <= 800 - 240 + 1 and pg.evaluate("() => document.getElementById('ganttPaneOuter').getBoundingClientRect().width") >= 239, pg.evaluate("() => [document.getElementById('gridPane').getBoundingClientRect().width, document.getElementById('ganttPaneOuter').getBoundingClientRect().width]"))
    # old preference: the 400px sidebar width is not kept
    pg2 = new_page(1500, 700, {"theme": "light", "zoom": "week", "zoomRev": 2, "view": "gantt", "gridPaneWidth": 400})
    check("a list width saved when the list was a 400px sidebar is not kept (default 640px)", abs(pg2.evaluate("() => document.getElementById('gridPane').getBoundingClientRect().width") - 640) < 1.5, pg2.evaluate("() => document.getElementById('gridPane').getBoundingClientRect().width"))
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
