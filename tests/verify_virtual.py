# -*- coding: utf-8 -*-
"""Large plans: only the rows in view (plus a buffer) are built — in the list and in the chart — and stay correct while scrolling, jumping, selecting,
editing and switching views; small plans are built whole; a redraw of thousands of tasks stays fast."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """(n) => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); colFilters = newColFilters(); filterPinned.clear(); editingCell = null; delete project.holidays; delete project.workDays; historyCoalesceMs = 0; currentView = 'tasks';
  let k = 0; const groups = Math.ceil(n / 20);
  for (let g = 0; g < groups; g++) { const gid = 'g' + g; tasks.push({ id: gid, name: 'Group ' + g, parentId: null, order: g, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
    for (let i = 0; i < 19 && k < n; i++, k++) tasks.push({ id: 't' + k, name: 'Task ' + k, parentId: gid, order: i, startDate: addDays('2026-09-07', (k % 60) * 2), endDate: addDays('2026-09-07', (k % 60) * 2 + 4), progress: k % 100, milestone: false, color: null, predecessors: i ? [{ id: 't' + (k - 1), type: 'FS', lag: 0 }] : [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: 'Anna', actualStart: null, actualFinish: null }); }
  normalizeData(); save(); render(); resetHistory(); return tasks.length; }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    rows = lambda: ev("() => [...document.querySelectorAll('#gridRows .grid-row')].map(r => r.dataset.id)")
    scroll = lambda y, sel="#gridRows": (ev("([s, y]) => { document.querySelector(s).scrollTop = y; }", [sel, y]), pg.wait_for_timeout(200))
    first_idx = lambda: ev("() => { const r = document.querySelector('#gridRows .grid-row'); return visibleTaskList().findIndex(v => v.task.id === r.dataset.id); }")

    # ---------------------------------------------------------------- the threshold
    ev(SEED, 100); pg.wait_for_timeout(100)
    check("a small plan (about 105 rows) is built whole, with no spacers", len(rows()) == ev("() => visibleTaskList().length") and pg.locator(".virt-spacer").count() == 0, len(rows()))
    ev(SEED, 140); n1 = ev("() => visibleTaskList().length")
    check("...up to 150 rows it stays whole", len(rows()) == n1 and n1 <= 150, (len(rows()), n1))
    ev(SEED, 1000); pg.wait_for_timeout(200)
    n = ev("() => visibleTaskList().length")
    check("a plan of 1,000 rows builds only the rows in view plus a buffer (well under 100), between two spacers", 20 < len(rows()) < 100 and pg.locator(".virt-spacer").count() == 1 and n == 1000, (len(rows()), n, pg.locator(".virt-spacer").count()))
    check("...the list is exactly as tall as 1,000 rows of 32px (the scrollbar is right), and every built row is 32px", ev("() => document.getElementById('gridRows').scrollHeight") == n * 32 and ev("() => [...document.querySelectorAll('#gridRows .grid-row')].every(r => Math.round(r.getBoundingClientRect().height) === 32)"), ev("() => document.getElementById('gridRows').scrollHeight"))
    check("...the frozen columns and column lines are on the built rows", ev("() => [...document.querySelectorAll('#gridRows .grid-row')].every(r => r.children[0].classList.contains('frz'))"))

    # ---------------------------------------------------------------- scrolling
    ok = True
    for y in (3000, 9000, 16000, 25000, 33000, 200, 0):
        scroll(y); r = rows(); a = min(y // 32, n - 30)
        idx = {tid: i for i, tid in enumerate(ev("() => visibleTaskList().map(v => v.task.id)"))}
        if not (min(idx[i] for i in r) <= a and max(idx[i] for i in r) >= a + 20): ok = False; print("   gap at", y, min(idx[i] for i in r), max(idx[i] for i in r))
    check("scrolling to the middle, the end and back always leaves rows under the viewport (no blank area)", ok)
    scroll(16000); r = rows()
    check("...the rows built follow the scroll position (around row 500 now, not row 0)", 400 < first_idx() < 520 and len(r) < 100, first_idx())
    check("...the spacers add up (rows built + both spacers = the whole list)", ev("() => { const el = document.getElementById('gridRows'); return [...el.children].reduce((h, c) => h + c.getBoundingClientRect().height, 0); }") == n * 32)
    scroll(16000 + 32 * 5); r2 = rows()
    check("a small scroll does not rebuild the rows (they are only rebuilt near the edge of what is built)", r2 == r)
    ev("() => { window.__builds = 0; const o = renderGrid; window.renderGrid = function () { window.__builds++; return o.apply(this, arguments); }; }")
    for y in range(16160, 16160 + 32 * 60, 96): scroll(y)
    check("...a long slow scroll rebuilds a handful of times, not on every step", 1 <= ev("() => window.__builds") <= 8, ev("() => window.__builds"))
    ev("() => { window.renderGrid = window.renderGrid; }")

    # ---------------------------------------------------------------- selecting, editing, jumping
    scroll(16000)
    tid = ev("() => { const box = document.getElementById('gridRows').getBoundingClientRect(); const r = [...document.querySelectorAll('#gridRows .grid-row')].find(x => { const b = x.getBoundingClientRect(); return b.top > box.top + 200 && b.bottom < box.bottom - 100; }); return r.dataset.id; }"); nm = ev("(i) => byId(i).name", tid)
    pg.locator(f".grid-row[data-id='{tid}'] > div").first.click(); pg.wait_for_timeout(200)
    check("clicking a row selects it and keeps the scroll position and the window", ev("() => selectedIds().length") == 1 and abs(ev("() => document.getElementById('gridRows').scrollTop") - 16000) < 40 and tid in rows())
    ev("() => { setSelection(visibleTaskList().map(v => v.task.id)); render(); }"); pg.wait_for_timeout(150)
    check("select-all selects every task, built or not ('1000 selected')", "1000 selected" in pg.inner_text("#selChip") and ev("() => selectedIds().length") == n, pg.inner_text("#selChip"))
    ev("() => { setSelection([]); render(); }")
    pg.locator(f".grid-row[data-id='{tid}'] .name-text").click(); pg.wait_for_selector("#gridRows .inline-edit"); pg.wait_for_timeout(150)
    scroll(16000 + 32 * 25)
    check("an open editor keeps its rows while you scroll (its input is not rebuilt away)", pg.locator("#gridRows .inline-edit").count() == 1 and ev("() => !!editingCell"))
    pg.fill("#gridRows .inline-edit", "Edited far away"); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    check("...and Enter saves the edit", ev("(i) => byId(i).name", tid) == "Edited far away")
    scroll(0)
    far = "t900"
    ev("(id) => jumpToTask(id)", far); pg.wait_for_timeout(500)
    check("Find / jump to a task far outside the built rows scrolls there, builds its row and flashes it", far in rows() and ev("(id) => document.querySelector(`.grid-row[data-id='${id}']`).classList.contains('jump-flash')", far) and ev("() => document.getElementById('gridRows').scrollTop") > 20000)
    r = pg.locator(f".grid-row[data-id='{far}']").bounding_box(); box = pg.locator("#gridRows").bounding_box()
    check("...and the row is in view", box["y"] <= r["y"] and r["y"] + r["height"] <= box["y"] + box["height"] + 2, (r, box))

    # ---------------------------------------------------------------- the Gantt view
    ev("() => setView('gantt')"); pg.wait_for_timeout(500)
    bars = lambda: ev("() => document.querySelectorAll('#ganttRows .gantt-bar').length")
    check("the chart builds only the bars of the rows in view too (not 1,050 of them)", 20 < bars() < 100 and ev("() => Object.keys(barGeom).length") == n - 0 or 20 < bars() < 100, (bars(), ev("() => Object.keys(barGeom).length")))
    check("...but knows the geometry of every task (arrows and Find need it)", ev("() => Object.keys(barGeom).length") >= 1000, ev("() => Object.keys(barGeom).length"))
    scroll(20000, "#ganttPaneOuter")
    ids = rows(); mid = ev("(i) => visibleTaskList().findIndex(v => v.task.id === i)", ids[len(ids) // 2])
    check("scrolling the chart scrolls the list with it and builds the rows for both", 500 < mid < 700 and ev("() => document.querySelectorAll('#ganttRows .gantt-row-bg').length") > 20 and abs(ev("() => document.getElementById('gridRows').scrollTop") - 20000) < 40, mid)
    tid2 = ids[len(ids) // 2]
    yl = pg.locator(f".grid-row[data-id='{tid2}']").bounding_box()["y"]; yc = pg.locator(f".gantt-row-bg[data-row-id='{tid2}']").bounding_box()["y"]
    check("a task's list row and its chart row are level (same y)", abs(yl - yc) <= 1.5, (yl, yc))
    check("...its bar exists and the arrow of a link touching the built rows is drawn (paths in the arrow layer)", pg.locator(f".gantt-bar[data-id='{tid2}']").count() == 1 and ev("() => document.querySelectorAll('#ganttDeps path').length") > 5)
    box = pg.locator("#ganttPaneOuter").bounding_box(); bar = pg.locator(f".gantt-row-bg[data-row-id='{tid2}']").bounding_box()
    pg.mouse.click(box["x"] + 60, bar["y"] + 16, button="right"); pg.wait_for_timeout(150)
    check("a right-click on a chart row far down belongs to that task (the menu selects it)", ev("() => selectedIds()") == [tid2], ev("() => selectedIds()"))
    pg.keyboard.press("Escape")
    ev("() => setView('tasks')"); pg.wait_for_timeout(300)
    check("switching back to the Tasks view keeps the list working", len(rows()) > 20 and pg.locator("#gridRows .grid-row").first.is_visible())

    # ---------------------------------------------------------------- filters shrink it, edits keep working
    ev("() => { filterPinned.clear(); colFilters.name = { type: 'rule', rule: 'begins', a: 'Task 12', b: '' }; render(); }"); pg.wait_for_timeout(200)
    nf = ev("() => visibleTaskList().length")
    check("a filter that leaves under 150 rows builds them all (no spacers) and the rows are those that match", nf < 150 and len(rows()) == nf and pg.locator(".virt-spacer").count() == 0 and all(ev("(i) => byId(i).name.startsWith('Task 12') || hasChildren(i)", i) for i in rows()), (nf, len(rows())))
    ev("() => { colFilters = newColFilters(); render(); }")
    check("clearing it brings the windowed list back", pg.locator(".virt-spacer").count() >= 1 and len(rows()) < 100)

    # ---------------------------------------------------------------- speed
    ev(SEED, 2000)
    t = ev("() => { const a = performance.now(); render(); const b = performance.now(); currentView = 'gantt'; render(); const c = performance.now(); currentView = 'tasks'; return [b - a, c - b]; }")
    check("a full redraw of a 2,000-task plan takes well under a quarter of a second in the Tasks view and under half a second in the Gantt view", t[0] < 250 and t[1] < 500, t)
    s = ev("() => { const a = performance.now(); save(); return performance.now() - a; }")
    check("...and saving it (normalise, history, browser copy) under a quarter of a second", s < 250, s)
    ev(SEED, 100)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
