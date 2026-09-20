# -*- coding: utf-8 -*-
"""A task's colour colours its ROW (a stripe at the left edge and a light tint) in the list, behind the chart row, in the printout and in the Excel export;
the Gantt BARS keep their status colours whatever colour the task has."""
from playwright.sync_api import sync_playwright
import os, io, base64, openpyxl
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); editingCell = null; delete project.holidays; delete project.workDays; historyCoalesceMs = 0; theme = 'light'; applyTheme();
  const t = todayStr(), mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: addDays(t, -4), endDate: addDays(t, 6), progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', resource: '', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('g', 'Design', 0, { color: 'purple' }), mk('a', 'Wireframes', 0, { parentId: 'g' }), mk('b', 'Visuals', 1, { parentId: 'g', color: 'red', progress: 100 }), mk('c', 'Build', 1, { color: 'teal' }), mk('d', 'Test', 2), mk('e', 'Launch', 3, { color: 'amber', progress: 40 }));
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(150)
    bg = lambda id_: ev("(i) => getComputedStyle(document.querySelector(`.grid-row[data-id='${i}']`)).getPropertyValue('--row-bg').trim()", id_)
    cell_bg = lambda id_: ev("(i) => getComputedStyle(document.querySelector(`.grid-row[data-id='${i}'] > :first-child`)).backgroundColor", id_)
    shadow = lambda id_: ev("(i) => getComputedStyle(document.querySelector(`.grid-row[data-id='${i}'] > :first-child`)).boxShadow", id_)
    # ------------------------------------------------------------------ the list
    check("a coloured task's row is marked (class 'colored' and its accent colour), an uncoloured one is not", ev("() => ['g', 'b', 'c', 'e'].every(i => document.querySelector(`.grid-row[data-id='${i}']`).classList.contains('colored')) && ['a', 'd'].every(i => !document.querySelector(`.grid-row[data-id='${i}']`).classList.contains('colored'))"))
    check("...the row is tinted with its colour (a colour-mix of the accent over the panel) and an uncoloured row is plain", "color-mix" in bg("c") and "color-mix" not in bg("d"), (bg("c"), bg("d")))
    check("...the frozen cells paint the same tint (no white cells in a tinted row)", cell_bg("c") != cell_bg("d") and cell_bg("c") not in ("rgba(0, 0, 0, 0)", "transparent"), (cell_bg("c"), cell_bg("d")))
    check("...a 4px stripe of the colour sits at the row's left edge (teal for Build), none on an uncoloured row", "27, 124, 131" in shadow("c") and "-10px" in shadow("c") and "27, 124, 131" not in shadow("d"), shadow("c"))
    check("a group can be coloured too (Design: purple stripe) and its sub-tasks stay plain unless coloured themselves", "130, 80, 223" in shadow("g") and "130, 80, 223" not in shadow("a"), shadow("g"))
    ev("() => { setSelection(['c']); render(); }"); pg.wait_for_timeout(100)
    sel_bg = cell_bg("c"); ev("() => { setSelection([]); render(); }"); pg.wait_for_timeout(100)
    check("a selected coloured row still looks selected (its tint changes)", sel_bg != cell_bg("c"), (sel_bg, cell_bg("c")))
    pg.hover(".grid-row[data-id='c'] .name-text"); pg.wait_for_timeout(150)
    check("hover changes the tint too", cell_bg("c") != sel_bg and ev("() => getComputedStyle(document.querySelector(`.grid-row[data-id='c'] > :first-child`)).backgroundColor") != "rgba(0, 0, 0, 0)")
    # ------------------------------------------------------------------ the chart: bars keep their STATUS colour
    ev("() => setView('gantt')"); pg.wait_for_timeout(350)
    bar = lambda id_: ev("(i) => document.querySelector(`.gantt-bar[data-id='${i}']`).style.getPropertyValue('--bar-color')", id_)
    check("bars are coloured by status only: Visuals (red row colour, 100 %) is the 'complete' colour, not red", bar("b") == "var(--status-complete)", bar("b"))
    check("...Build (teal row colour, not started) is the 'not started' colour, Launch (amber, 40 %) is 'in progress', Test (no colour) is 'not started'", bar("c") == "var(--status-not-started)" and bar("d") == "var(--status-not-started)" and bar("e") == "var(--accent)", (bar("c"), bar("d"), bar("e")))
    check("statusColorVar never returns a task colour", ev("() => tasks.every(t => !/--task-/.test(statusColorVar(t)))"))
    check("the chart's row behind a coloured task is tinted too, the others are not", ev("() => document.querySelector(\".gantt-row-bg[data-row-id='c']\").classList.contains('colored') && !document.querySelector(\".gantt-row-bg[data-row-id='d']\").classList.contains('colored')") and ev("() => getComputedStyle(document.querySelector(\".gantt-row-bg[data-row-id='c']\")).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent"))
    ev("() => setView('tasks')"); pg.wait_for_timeout(250)
    # ------------------------------------------------------------------ the dialog and bulk edit
    ev("() => openTaskModal('d')"); pg.wait_for_timeout(300)
    check("the dialog calls it 'Row colour', with a 'No colour' choice and eight colours", "Row colour" in pg.inner_text("#taskModalBg .modal-body") and pg.locator("#taskColorSwatches .swatch").count() == 9 and pg.get_attribute("#taskColorSwatches .swatch.auto", "title") == "No colour")
    pg.click("#taskColorSwatches .swatch:nth-child(4)"); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(300)
    check("picking a colour and saving colours the row (Purple, the 3rd colour)", ev("() => byId('d').color") == "purple" and ev("() => document.querySelector(\".grid-row[data-id='d']\").classList.contains('colored')"), ev("() => byId('d').color"))
    ev("() => openTaskModal('d')"); pg.wait_for_timeout(300); pg.click("#taskColorSwatches .swatch.auto"); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(300)
    check("'No colour' takes it away again", ev("() => byId('d').color") is None and ev("() => !document.querySelector(\".grid-row[data-id='d']\").classList.contains('colored')"))
    ev("() => { setSelection(['a', 'd']); render(); openBulkModal(); }"); pg.wait_for_timeout(250)
    check("bulk edit: 'Row colour' with 'No colour' as the first choice", "Row colour" in pg.inner_text("#bulkModalBg") and pg.locator("#bulkVal-color option").first.inner_text() == "No colour")
    pg.select_option("#bulkVal-color", "green"); pg.click("#bulkModalBg .modal-footer .btn-primary"); pg.wait_for_timeout(300)
    check("...applying it colours both rows", ev("() => [byId('a').color, byId('d').color]") == ["green", "green"])
    # ------------------------------------------------------------------ Excel and print
    ev(SEED); pg.wait_for_timeout(150)
    b64 = ev("""async () => { const blob = buildXlsx({ scope: 'all', gantt: true, columns: 'shown' }); const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (const c of buf) s += String.fromCharCode(c); return btoa(s); }""")
    wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(b64))); ws = wb["Tasks"]
    heads = {ws.cell(4, c).value: c for c in range(1, ws.max_column + 1)}; nc = heads["Task Name"]
    rows = {ws.cell(r, nc).value.strip("◆ "): ws.cell(r, nc) for r in range(5, ws.max_row + 1) if ws.cell(r, nc).value}
    def tint(hexc, k): return "".join(f"{round(int(hexc[i:i + 2], 16) * k + 255 * (1 - k)):02X}" for i in (0, 2, 4))
    fill = lambda name: ws.cell(rows[name].row, nc).fill.fgColor.rgb
    check("Excel: the list cells of a coloured task carry a light tint of its colour (Build: teal)", fill("Build") == "FF" + tint("1B7C83", .18), fill("Build"))
    check("...an uncoloured task has no tint (Test) and Wireframes (no colour, in a coloured group) none either", fill("Test") in (None, "00000000") or ws.cell(rows["Test"].row, nc).fill.fill_type is None, fill("Test"))
    ev("() => openPrintModal()"); pg.wait_for_timeout(600)
    svg = ev("() => (document.querySelector('#printModalBg svg') || {outerHTML: ''}).outerHTML").lower()
    check("Print: a coloured row gets its stripe and tint on the page (teal #1b7c83)", "#1b7c83" in svg and "2.6" in svg, svg[:200])
    ev("() => closePrintModal()")
    check("the Help explains the row colour", "Row colour" in ev("() => { openHelpModal(); return document.getElementById('helpModalBg').textContent; }")); pg.keyboard.press("Escape")
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
