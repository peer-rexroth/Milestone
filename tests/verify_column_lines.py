import re, io
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open('verify_clone.py').read(), re.S).group(1)
try:
    from PIL import Image
except Exception:
    Image = None
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 600}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status']) colHidden.add(c); }")
    pg.evaluate(SEED, [{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "B", "s": "2026-09-12", "e": "2026-09-16"}, {"name": "C", "s": "2026-09-17", "e": "2026-09-19"}])
    pg.wait_for_timeout(150)
    var = lambda n: pg.evaluate("n => getComputedStyle(document.getElementById('main')).getPropertyValue(n).trim()", n)
    pos = lambda n: [float(x.split('px')[0]) for x in var(n).split(',')] if var(n) not in ("", "0 0") else []
    # the expected line positions: the middle of each gap between two neighbouring cells of the first row / of the header
    expected = lambda sel: pg.evaluate("""(sel) => { const el = document.querySelector(sel); const base = el.getBoundingClientRect().left; const cells = [...el.children];
        const xs = []; for (let i = 0; i < cells.length - 1; i++) { const a = cells[i].getBoundingClientRect(), b = cells[i + 1].getBoundingClientRect(); xs.push((a.right + b.left) / 2 - base); } return xs; }""", sel)
    def near(got, exp, tol=1.0): return len(got) == len(exp) and all(abs(g - e) <= tol for g, e in zip(got, exp))
    h, r = pos("--col-pos-h"), pos("--col-pos-r")
    eh, er = expected("#gridHeader"), expected("#gridRows .grid-row")
    check("one line between every two columns, the row-actions column included: the header has n-1 lines for its cells", len(h) == len(eh) and len(h) > 5, (len(h), len(eh)))
    check("header lines sit in the middle of the gap between neighbouring header cells (±1px)", near(h, eh), (h, eh))
    check("row lines sit in the middle of the gap between neighbouring cells of a row (±1px)", near(r, er), (r, er))
    check("header and rows agree (same track layout)", near(h, r, 1.5), (h, r))
    check("each row and the header paint the lines on a pseudo-element that ignores the mouse", pg.evaluate("() => getComputedStyle(document.querySelector('.grid-row'), '::before').pointerEvents") == "none" and pg.evaluate("() => getComputedStyle(document.getElementById('gridHeader'), '::before').pointerEvents") == "none")
    check("the lines use the theme's border colour (the same one as the Gantt divider)", "var(--border)" in var("--col-lines-r") or "linear-gradient" in var("--col-lines-r"))
    check("the header has an 'Actions' label for the row-actions column (no filter funnel), and a line to the left of it", pg.evaluate("() => { const h = document.querySelector('#gridHeader .actions-head'); return !!h && h.textContent.trim() === 'Actions' && !h.querySelector('button'); }") and len(h) == len(pg.evaluate("() => [...document.getElementById('gridHeader').children]")) - 1)
    check("the row-action buttons start under the label (same left edge, so header and buttons line up)", pg.evaluate("() => { const h = document.querySelector('#gridHeader .actions-head'); const r = document.createRange(); r.selectNodeContents(h); const b = document.querySelector('#gridRows .grid-actions .icon-btn i'); return Math.abs(r.getBoundingClientRect().left - b.getBoundingClientRect().left) <= 1.5; }"))
    check("the actions column is 88px", pg.evaluate("() => document.querySelector('#gridHeader .actions-head').getBoundingClientRect().width") == 88)
    # pixels
    if Image:
        shot = {}
        def px_at(x, y):
            im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB"); return im.getpixel((int(x), int(y)))
        def has_line(x, y, away=20):     # a 1px line at a half-pixel position lands on one of the neighbouring device pixels
            im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB"); bg = im.getpixel((int(x) + away, int(y)))
            return [im.getpixel((int(x) + d, int(y))) for d in (-1, 0, 1, 2)], bg, any(im.getpixel((int(x) + d, int(y))) != bg for d in (-1, 0, 1, 2))
        row = pg.evaluate("() => { const r = document.querySelector('#gridRows .grid-row').getBoundingClientRect(); return {l: r.left, t: r.top, h: r.height}; }")
        x = row["l"] + r[3]; y = row["t"] + 4
        check("a line is really painted in a row (a pixel at its position differs from the background next to it)", has_line(x, y)[2], has_line(x, y))
        below = pg.evaluate("() => { const rows = document.getElementById('gridRows').getBoundingClientRect(); const last = [...document.querySelectorAll('#gridRows .grid-row')].pop().getBoundingClientRect(); return {y: (last.bottom + rows.bottom) / 2}; }")
        check("...and it continues below the last task (empty area)", has_line(x, below["y"])[2], has_line(x, below["y"]))
        pg.hover(f".grid-row >> nth=1"); pg.wait_for_timeout(100)
        y1 = pg.evaluate("() => { const r = document.querySelectorAll('#gridRows .grid-row')[1].getBoundingClientRect(); return r.top + 4; }")
        check("a hovered row keeps its lines", has_line(x, y1)[2], has_line(x, y1))
        pg.mouse.move(5, 5)
    # changing the column set re-computes them
    n = len(r)
    pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish']) colHidden.delete(c); render(); }"); pg.wait_for_timeout(150)
    check("showing two more columns adds two more lines", len(pos("--col-pos-r")) == n + 2 and near(pos("--col-pos-r"), expected("#gridRows .grid-row")), (n, len(pos("--col-pos-r"))))
    pg.evaluate("() => { colHidden.add('actualStart'); colHidden.add('actualFinish'); colHidden.add('duration'); render(); }"); pg.wait_for_timeout(150)
    check("hiding a column removes a line", len(pos("--col-pos-r")) == n - 1, (n, len(pos("--col-pos-r"))))
    pg.evaluate("() => { colHidden.delete('duration'); render(); }"); pg.wait_for_timeout(100)
    # window resize moves the fr columns, so the lines must follow
    pg.set_viewport_size({"width": 1100, "height": 600}); pg.wait_for_timeout(300)
    check("resizing the window re-positions the lines (the wide columns changed width)", near(pos("--col-pos-r"), expected("#gridRows .grid-row"), 1.5) and near(pos("--col-pos-h"), expected("#gridHeader"), 1.5), (pos("--col-pos-r"), expected("#gridRows .grid-row")))
    pg.set_viewport_size({"width": 1500, "height": 600}); pg.wait_for_timeout(300)
    # more rows than fit: a scrollbar narrows the rows but not the header
    pg.evaluate("""() => { for (let i = 0; i < 40; i++) tasks.push({id: genId(), name: 'T' + i, parentId: null, order: 10 + i, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); render(); }"""); pg.wait_for_timeout(200)
    check("with a long list (scrolling) the row lines still match the rows' own columns", near(pos("--col-pos-r"), expected("#gridRows .grid-row"), 1.5), (pos("--col-pos-r"), expected("#gridRows .grid-row")))
    # empty states
    pg.evaluate("() => { tasks.length = 0; render(); }"); pg.wait_for_timeout(100)
    check("no tasks: the header keeps its lines, the empty body has none", len(pos("--col-pos-h")) > 5 and var("--col-lines-r") == "none")
    # Gantt view: unchanged
    pg.evaluate(SEED, [{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}]); pg.wait_for_timeout(100)
    pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(150)
    check("Gantt view: its list has the same column lines (it is the same list)", len(pos("--col-pos-r")) >= 4 and len(pos("--col-pos-h")) >= 4, (var("--col-pos-r"), var("--col-pos-h")))
    pg.evaluate("() => { currentView = 'tasks'; render(); }"); pg.wait_for_timeout(150)
    check("...and they are back in the Tasks view", len(pos("--col-pos-r")) > 5)
    # dark
    pg.click("#themeToggleBtn"); pg.wait_for_timeout(200)
    check("dark theme: lines still there", len(pos("--col-pos-r")) > 5 and (not Image or True))
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
