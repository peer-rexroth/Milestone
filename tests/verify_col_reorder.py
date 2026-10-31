# -*- coding: utf-8 -*-
"""Moving a column by dragging its header (the task list and the Resource Sheet): the order changes (per view, saved with the device prefs), a plain click or a drag of the funnel / the edge
handle does not, hidden columns keep their place, a ghost and a drop line show while dragging. See "Column reorder by drag" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """() => { historyCoalesceMs = 0; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }, x || {});
  tasks.push(mk('a', 'Alpha', '2030-03-04', '2030-03-08', { resource: 'Ann' }), mk('b', 'Beta', '2030-03-11', '2030-03-15'));
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 700}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(250)
    vis = lambda: ev("() => visibleTaskCols()")
    head = lambda c: pg.locator(f'#gridHeader .col-head:has(.col-resizer[data-col="{c}"])')
    def drag(src, dst, side="left", steps=8, hold=False):
        a = head(src).bounding_box(); d = head(dst).bounding_box()
        x = d["x"] + (d["width"] * 0.25 if side == "left" else d["width"] * 0.75)
        pg.mouse.move(a["x"] + 8, a["y"] + a["height"] / 2); pg.mouse.down()   # (the label's left end: the funnel sits just after the text)
        pg.mouse.move(x, a["y"] + a["height"] / 2, steps=steps)
        if hold: return
        pg.mouse.up(); pg.wait_for_timeout(200)
    v0 = vis(); check("the standard order has Start before Finish before Duration", v0.index("start") < v0.index("end") < v0.index("duration"), v0)
    # ---- drag Duration in front of Start
    drag("duration", "start", "left", hold=True)
    check("while dragging: a ghost with the column's name and a drop line show, the dragged header is dimmed", ev("() => !!document.querySelector('.col-ghost') && !!document.querySelector('.col-drop-line') && document.querySelector('.col-head.moving') !== null && document.body.classList.contains('col-moving')") and "duration" in pg.inner_text(".col-ghost").lower(), pg.inner_text(".col-ghost"))
    ln = pg.locator(".col-drop-line").bounding_box(); sb = head("start").bounding_box()
    check("...the line sits at the left edge of the column it will land before", abs(ln["x"] - sb["x"]) <= 3, (ln, sb))
    pg.mouse.up(); pg.wait_for_timeout(250)
    v1 = vis()
    check("dropping Duration on the left half of Start moves it right before Start", v1.index("duration") + 1 == v1.index("start"), v1)
    check("...nothing else changed order", [c for c in v1 if c != "duration"] == [c for c in v0 if c != "duration"], v1)
    check("the ghost and the line are gone, no leftover drag state", ev("() => !document.querySelector('.col-ghost') && !document.querySelector('.col-drop-line') && !document.body.classList.contains('col-moving')"))
    # ---- right half of the target = after it
    drag("duration", "end", "right")
    v2 = vis(); check("dropping on the right half of Finish puts it after Finish... i.e. before the next column", v2.index("duration") == v2.index("end") + 1, v2)
    # ---- the very end
    last = v2[-1]; a = head("duration").bounding_box(); lb = head(last).bounding_box()
    pg.mouse.move(a["x"] + 8, a["y"] + 10); pg.mouse.down(); pg.mouse.move(lb["x"] + lb["width"] - 2, a["y"] + 10, steps=8); pg.mouse.up(); pg.wait_for_timeout(200)
    check("dropping past the last column's middle makes it the last shown column", vis()[-1] == "duration", vis())
    # ---- clicks and other handles do nothing
    before = vis(); head("start").click(); pg.wait_for_timeout(120)
    check("a plain click on a header changes nothing", vis() == before)
    a = head("start").bounding_box(); pg.mouse.move(a["x"] + 20, a["y"] + 10); pg.mouse.down(); pg.mouse.move(a["x"] + 23, a["y"] + 10); pg.mouse.up(); pg.wait_for_timeout(120)
    check("a tiny wobble (under 5px) is not a drag", vis() == before and ev("() => !document.querySelector('.col-ghost')"))
    fb = pg.locator('#gridHeader .col-head:has(.col-resizer[data-col="start"]) .col-filter-btn'); fb.hover(); pg.wait_for_timeout(80)
    fbb = fb.bounding_box(); pg.mouse.move(fbb["x"] + 3, fbb["y"] + 3); pg.mouse.down(); pg.mouse.move(fbb["x"] + 200, fbb["y"] + 3, steps=5); pg.mouse.up(); pg.wait_for_timeout(150)
    check("dragging from the filter funnel does not move the column", vis() == before, vis())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    # ---- the edge handle still resizes
    w0 = ev("() => colWidths.resource || 0"); hb = pg.locator('#gridHeader .col-resizer[data-col="resource"]').bounding_box()
    rz = pg.locator('#gridHeader .col-resizer[data-col="resource"]').bounding_box()
    pg.mouse.move(rz["x"] + 3, rz["y"] + 10); pg.mouse.down(); pg.mouse.move(rz["x"] - 40, rz["y"] + 10, steps=4); pg.mouse.up(); pg.wait_for_timeout(150)
    check("the edge handle still resizes (and does not reorder)", ev("() => colWidths.resource || 0") != w0 and vis() == before, (w0, ev("() => colWidths.resource")))
    # ---- hidden columns keep their place, persists, per view
    ev("() => { colOrder = [...DEFAULT_COL_ORDER]; colHidden = new Set(DEFAULT_COL_ORDER.filter(c => !TASK_COLS[c].dflt)); save(); render(); }"); pg.wait_for_timeout(150)
    hid_before = ev("() => colOrder.filter(c => colHidden.has(c))")
    drag("progress", "start", "left"); 
    check("hidden columns keep their relative order when a shown one is moved", ev("() => colOrder.filter(c => colHidden.has(c))") == hid_before and vis().index("progress") < vis().index("start"), vis())
    sv = vis()
    pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(250)
    check("the order is saved with the device and survives a reload", vis() == sv, (vis(), sv))
    ev("() => { setView('gantt'); }"); pg.wait_for_timeout(250)
    gv = ev("() => visibleTaskCols('gantt')")
    check("the Gantt view keeps its own order (untouched by the Tasks view's move)", gv.index("start") < gv.index("progress") or "progress" not in gv, gv)
    if len(gv) > 3:
        g0 = gv[0]; g1 = gv[1]
        drag(g1, g0, "left"); gv2 = ev("() => visibleTaskCols('gantt')")
        check("dragging a header in the Gantt view's list moves it there too", gv2.index(g1) < gv2.index(g0), gv2)
        ev("() => setView('tasks')"); pg.wait_for_timeout(200)
        check("...and leaves the Tasks view's order alone", vis() == sv, vis())
    # Columns menu in sync
    ev("() => { setView('tasks'); }"); pg.wait_for_timeout(150)
    pg.click("#columnsBtn") if ev("() => !!document.getElementById('columnsBtn')") else None
    # ---- the Resource Sheet
    ev("() => { project.resources = [{ id: 'r1', name: 'Ann', maxUnits: 100 }, { id: 'r2', name: 'Bob', maxUnits: 100 }]; normalizeData(); setView('resourceSheet'); render(); }"); pg.wait_for_timeout(300)
    rs = lambda: ev("() => rsVisibleCols().map(c => c.key)")
    rh = lambda k: pg.locator(f'#resourceSheetHeader > div[data-rskey="{k}"]')
    def rdrag(src, dst, side="left", hold=False):
        a = rh(src).bounding_box(); d = rh(dst).bounding_box()
        x = d["x"] + (d["width"] * 0.25 if side == "left" else d["width"] * 0.75)
        pg.mouse.move(a["x"] + 8, a["y"] + a["height"] / 2); pg.mouse.down(); pg.mouse.move(x, a["y"] + a["height"] / 2, steps=8)
        if hold: return
        pg.mouse.up(); pg.wait_for_timeout(200)
    r0 = rs(); check("Resource Sheet standard order starts # · Resource Name · Type and ends with the remove column", r0[:3] == ["id", "name", "type"] and r0[-1] == "remove", r0)
    rdrag("group", "type", "left", hold=True)
    check("Resource Sheet: dragging a header shows the ghost and the drop line", ev("() => !!document.querySelector('.col-ghost') && !!document.querySelector('.col-drop-line') && !!document.querySelector('.rst-header > div.moving')"))
    pg.mouse.up(); pg.wait_for_timeout(200)
    r1 = rs(); check("...and dropping Group before Type moves it there (# and the remove column stay at the ends)", r1.index("group") + 1 == r1.index("type") and r1[0] == "id" and r1[-1] == "remove", r1)
    rdrag("stdRate", "accrueAt", "right")
    r2 = rs(); check("dropping on the right half of Accrue At puts the column after it", r2.index("stdRate") == r2.index("accrueAt") + 1, r2)
    a = rh("maxUnits").bounding_box(); lastb = rh(r2[-2]).bounding_box()
    pg.mouse.move(a["x"] + 8, a["y"] + 10); pg.mouse.down(); pg.mouse.move(lastb["x"] + lastb["width"] - 2, a["y"] + 10, steps=8); pg.mouse.up(); pg.wait_for_timeout(200)
    r3 = rs(); check("dropped past the last column it becomes the last data column (still before the remove column)", r3[-2] == "maxUnits" and r3[-1] == "remove", r3)
    rdrag("name", "type", "right")
    r4 = rs(); check("Resource Name can move too", r4.index("name") > r4.index("type") and r4[0] == "id", r4)
    # # and remove do not drag
    before = rs(); ib = rh("id").bounding_box(); pg.mouse.move(ib["x"] + 8, ib["y"] + 10); pg.mouse.down(); pg.mouse.move(ib["x"] + 300, ib["y"] + 10, steps=5); pg.mouse.up(); pg.wait_for_timeout(150)
    check("the # column does not drag", rs() == before and ev("() => !document.querySelector('.col-ghost')"))
    # the row cells follow
    check("the rows follow the header order", ev("() => { const hs = [...document.querySelectorAll('#resourceSheetHeader > div')].map(h => h.dataset.rskey), cells = [...document.querySelector('#resourceSheetBody .rst-row').children]; return hs.length === cells.length; }") and ev("() => { const row = document.querySelector('#resourceSheetBody .rst-row'), k = rsVisibleCols().findIndex(c => c.key === 'group'); return !!row.children[k].querySelector('input') && row.children[k].querySelector('input').getAttribute('aria-label') === 'Group'; }"))
    # edge handle and funnel-free: still resizes
    w0 = ev("() => rsColWidths.code || 0")
    gb = pg.locator('#resourceSheetHeader .col-resizer[data-rscol="group"]').bounding_box()
    pg.mouse.move(gb["x"] + 3, gb["y"] + 10); pg.mouse.down(); pg.mouse.move(gb["x"] + 40, gb["y"] + 10, steps=4); pg.mouse.up(); pg.wait_for_timeout(150)
    check("the edge handle still resizes a moved column", ev("() => rsColWidths.group || 0") > 0 and rs() == before, ev("() => rsColWidths"))
    sv = rs(); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(250)
    ev("() => setView('resourceSheet')"); pg.wait_for_timeout(200)
    check("the order is saved with the device and survives a reload", rs() == sv, (rs(), sv))
    ev("() => resetRsColumns()"); pg.wait_for_timeout(150)
    check("Reset to default (Columns menu) restores the standard order", rs()[:3] == ["id", "name", "type"], rs())
    ev("() => setView('tasks')")
    check("no console or page errors", not errors, errors[:3])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
