from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:250]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); ctx = b.new_context(viewport={"width": 1400, "height": 500}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status']) colHidden.add(c); }")
    pg.evaluate("""() => { tasks.length = 0; ['One', 'Two'].forEach((n, i) => tasks.push({id: genId(), name: n, parentId: null, order: i, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: i ? 'auto' : 'manual', resource: '', actualStart: null, actualFinish: null})); currentView = 'tasks'; save(); render(); }""")
    hdr = pg.locator("#gridHeader .col-head:has(.col-filter-btn[data-col='mode'])")
    check("Tasks view: the Task Mode column has a header label", " ".join(hdr.locator("span").text_content().split()).lower() == "task mode" or hdr.locator("span").inner_html().replace("<br>", " ").lower() == "task mode", hdr.inner_html())
    check("...not cut off, with its filter funnel beside it", pg.evaluate("() => { const s = document.querySelector(\"#gridHeader .col-head:has(.col-filter-btn[data-col='mode']) > span\"); return s.scrollWidth <= s.clientWidth; }") and hdr.locator(".col-filter-btn").count() == 1)
    check("...and no header label in the row is truncated", pg.evaluate("() => [...document.querySelectorAll('.grid-header .col-head > span')].every(e => e.scrollWidth <= e.clientWidth)"))
    geo = pg.evaluate("() => { const h = document.querySelector(\"#gridHeader .col-head:has(.col-filter-btn[data-col='mode']) > span\").getBoundingClientRect(), i = document.querySelector('#gridRows .grid-row .task-mode-cell i').getBoundingClientRect(); return {dx: Math.abs(h.left - i.left)}; }")
    check("the mode icon in each row sits under the start of the label", geo["dx"] <= 10, geo)
    pg.locator("#gridRows .grid-row").first.locator(".task-mode-cell").click(); pg.wait_for_selector("#taskModeMenu.open")
    check("clicking a mode cell still opens the Task Mode picker", True); pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    pg.locator(".col-filter-btn[data-col='mode']").click(); pg.wait_for_selector("#filterMenu.open")
    check("the filter on the column still works", "Manually Scheduled" in pg.inner_text("#filterTree")); pg.keyboard.press("Escape")
    pg.evaluate("() => { currentView = 'gantt'; render(); }")
    w = pg.evaluate("() => getComputedStyle(document.querySelector('.grid-row')).gridTemplateColumns.split(' ')[1]")
    check("the Gantt view's list is the same list: the same Task Mode column (76px, two-line header)", w == "76px", w)
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    pg.evaluate("() => { colOrder = colOrder.filter(c => c !== 'mode'); colOrder.unshift('mode'); colHidden.add('wbs'); render(); }")
    pg.screenshot(path="mode_header.png", clip={"x": 0, "y": 50, "width": 900, "height": 200})

    # ---------------- two-line headers
    pg.evaluate("() => { currentView = 'tasks'; for (const c of ['actualStart', 'actualFinish', 'remaining']) colHidden.delete(c); colHidden.delete('wbs'); save(); render(); }"); pg.wait_for_timeout(120)
    lines = lambda col: pg.evaluate("c => { const s = document.querySelector(`#gridHeader .col-head:has(.col-filter-btn[data-col='${c}']) > span`); const lh = parseFloat(getComputedStyle(s).lineHeight) || (parseFloat(getComputedStyle(s).fontSize) * 1.2); return {n: Math.round(s.getBoundingClientRect().height / lh), html: s.innerHTML, clipped: s.scrollHeight > s.clientHeight + 1 || s.scrollWidth > s.clientWidth + 1}; }", col)
    for col, want in (("mode", "Task<br>Mode"), ("actualStart", "Actual<br>Start"), ("actualFinish", "Actual<br>Finish"), ("remaining", "Remaining<br>Duration")):
        l = lines(col)
        check(f"header '{col}' is two lines ({want.replace('<br>', ' / ')}) and nothing is clipped", l["n"] == 2 and l["html"] == want and not l["clipped"], l)
    check("single-word headers stay one line (Start, Finish, Duration, Status)", all(lines(c)["n"] == 1 for c in ("start", "end", "duration")), [lines(c)["n"] for c in ("start", "end", "duration")])
    cols = pg.evaluate("() => getComputedStyle(document.querySelector('#gridHeader')).gridTemplateColumns.split(' ')")
    order = pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col)")
    w = {c: cols[1 + i] for i, c in enumerate(order)}
    check("the columns are as narrow as the two-line headers allow (header + funnel + the 8px inset on each side): Task Mode 76px, Actual Start/Finish 104px (a date column is sized for its editor)", w["mode"] == "76px" and w["actualStart"] == "104px" and w["actualFinish"] == "104px", w)
    check("the dates still fit their narrower columns (no cell is clipped)", pg.evaluate("() => [...document.querySelectorAll('#gridRows .grid-row > div')].every(e => e.scrollWidth <= e.clientWidth + 1 || e.querySelector('.name-text') || e.classList.contains('grid-name'))"))
    hh = pg.evaluate("() => [document.getElementById('gridHeader').getBoundingClientRect().height, document.querySelector('#gridRows .grid-row').getBoundingClientRect().height]")
    check("the header row is taller (42px) to make room; task rows keep their height (32px)", abs(hh[0] - 42) < .5 and abs(hh[1] - 32) < .5, hh)
    pg.evaluate("() => { project.fieldNames = {text1: 'A really quite long custom field name that goes on'}; colHidden.delete('text1'); save(); render(); }"); pg.wait_for_timeout(100)
    l = lines("text1")
    check("a long custom field name wraps to at most two lines, cut with an ellipsis, inside the header", l["n"] <= 2 and pg.evaluate("() => { const s = document.querySelector(\"#gridHeader .col-head:has(.col-filter-btn[data-col='text1']) > span\").getBoundingClientRect(), h = document.getElementById('gridHeader').getBoundingClientRect(); return s.top >= h.top - 1 && s.bottom <= h.bottom + 1; }"), l)
    pg.evaluate("() => { project.fieldNames = {}; normalizeData(); colHidden.add('text1'); save(); render(); }")
    pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(120)
    hg = pg.evaluate("() => [document.getElementById('gridHeader').getBoundingClientRect().height, document.getElementById('ganttHeader').getBoundingClientRect().height]")
    check("the Gantt view: its list header is two lines (42px) and lines up with the chart's timescale (also 42px)", abs(hg[0] - 42) < .5 and abs(hg[1] - 42) < .5, hg)
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    pg.locator("#gridRows .grid-row").first.locator(".task-mode-cell").click(); pg.wait_for_selector("#taskModeMenu.open")
    check("the narrow Task Mode column still opens its picker", True); pg.keyboard.press("Escape")
    pg.screenshot(path="two_line_headers.png", clip={"x": 0, "y": 50, "width": 1100, "height": 200})


    # ---------------- the Predecessors column is only as wide as its header
    pg.evaluate("""() => { tasks.length = 0; const mk = (n, i, p) => tasks.push({id: genId(), name: n, parentId: null, order: i, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: p, collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null});
        mk('A', 0, []); mk('B', 1, []); mk('C', 2, []); mk('D', 3, [{id: tasks[0].id, type: 'FS', lag: 2}, {id: tasks[1].id, type: 'SS', lag: -1}, {id: tasks[2].id, type: 'FF', lag: 12}]); colHidden.add('wbs'); currentView = 'tasks'; save(); render(); }""")
    pg.wait_for_timeout(120)
    geo = pg.evaluate("""() => {
      const head = document.querySelector("#gridHeader .col-head:has(.col-filter-btn[data-col='preds'])"), span = head.querySelector('span'), btn = head.querySelector('button');
      const clone = span.cloneNode(true); clone.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;display:inline-block;-webkit-line-clamp:unset;overflow:visible'; head.appendChild(clone);
      const need = clone.getBoundingClientRect().width + btn.getBoundingClientRect().width + parseFloat(getComputedStyle(head).columnGap); clone.remove();
      const cols = getComputedStyle(document.getElementById('gridHeader')).gridTemplateColumns.split(' '), order = [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col);
      return {need, w: head.getBoundingClientRect().width, clipped: span.scrollWidth > span.clientWidth + 1, oneLine: span.getBoundingClientRect().height < 20, nameW: parseFloat(cols[1 + order.indexOf('name')]), predW: parseFloat(cols[1 + order.indexOf('preds')])};
    }""")
    check("the Predecessors column is no wider than its header needs (header + funnel + 2x8px inset), with a little slack", geo["w"] >= geo["need"] + 16 and geo["w"] <= geo["need"] + 16 + 12, geo)
    check("...the header is on one line and not clipped", geo["oneLine"] and not geo["clipped"], geo)
    check("...and Task Name takes the space that freed up", geo["nameW"] > 300 and geo["nameW"] > geo["predW"] * 2, geo)
    pc = pg.evaluate("() => { const r = [...document.querySelectorAll('#gridRows .grid-row')][3], i = [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col).indexOf('preds'), c = r.children[1 + i]; return {text: c.innerText, title: c.title, clipped: c.scrollWidth > c.clientWidth}; }")
    check("a long predecessor list is cut with an ellipsis in the narrow cell, and the tooltip shows all of it", pc["clipped"] and pc["title"] == "1FS+2, 2SS-1, 3FF+12", pc)
    pg.locator("#gridRows .grid-row").nth(3).locator(":scope > div").nth(1 + pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col).indexOf('preds')")).click(); pg.wait_for_selector(".inline-edit")
    check("clicking the cell still opens the editor with the full text", pg.input_value(".inline-edit") == "1FS+2, 2SS-1, 3FF+12"); pg.keyboard.press("Escape")
    check("a normal reference fits without cutting", pg.evaluate("() => { tasks[3].predecessors = [{id: tasks[0].id, type: 'FS', lag: 2}]; render(); const r = [...document.querySelectorAll('#gridRows .grid-row')][3], i = [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col).indexOf('preds'), c = r.children[1 + i]; return c.scrollWidth <= c.clientWidth; }"))

    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
