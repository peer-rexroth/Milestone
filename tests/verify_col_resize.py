# -*- coding: utf-8 -*-
"""Resizable columns (drag a header edge, double-click to fit, right-click -> Fit / Default width, saved on the device),
the Resource cell's percentage chips, and change highlighting (the cells the last edit changed are shaded, MS Project style).
See "Resizable columns, change highlighting, Resource chips" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => { historyCoalesceMs = 0; project.workDays = [1,2,3,4,5]; }")
    SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; delete project.resources; colWidths = {}; changeMarks = new Map();
      const mk = (id, name, s, e, extra) => Object.assign({ id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
      tasks.push(mk('a', 'Design', '2026-09-07', '2026-09-11', { resource: 'Anna[50%], Ben, Christopher Longname[25%]' }),
                 mk('b', 'Build', '2026-09-14', '2026-09-18', { resource: 'Ben', predecessors: [{ id: 'a', type: 'FS', lag: 0 }] }),
                 mk('c', 'Test', '2026-09-21', '2026-09-25', { resource: 'Ben', predecessors: [{ id: 'b', type: 'FS', lag: 0 }] }));
      normalizeData(); save(); setSelection([]); render(); resetHistory(); }"""
    seed = lambda: ev(SEED)
    cellw = lambda col: ev("c => { const k = visibleTaskCols().indexOf(c) + 1; return document.querySelector('#gridRows .grid-row').children[k].getBoundingClientRect().width; }", col)
    marks = lambda: ev("() => Object.fromEntries([...changeMarks].map(([k, v]) => [k, [...v].sort()]))")
    seed(); ev("() => { historyCoalesceMs = 0; }")

    # ------------------------------------------------------------ Resource chips
    html = ev("() => document.querySelectorAll('#gridRows .grid-row')[0].querySelector('.res-a') ? [...document.querySelectorAll('#gridRows .grid-row')[0].querySelectorAll('.res-p')].map(x => x.textContent) : null")
    check("a share other than 100% shows as a chip next to the name; 100% shows nothing", html == ["50%", "25%"], html)
    check("a task with only full-time resources keeps the plain text", ev("() => document.querySelectorAll('#gridRows .grid-row')[1].querySelector('.res-a') === null && document.querySelectorAll('#gridRows .grid-row')[1].textContent.includes('Ben')"))
    check("the cell's tooltip still carries the raw text", "Anna[50%]" in ev("() => document.querySelectorAll('#gridRows .grid-row')[0].querySelector('[title*=\"Anna\"]').title"))
    ev("() => { colWidths.resource = 120; render(); }")
    check("in a narrow column the chips are never cut off (the names give way)", ev("() => [...document.querySelectorAll('#gridRows .grid-row')[0].querySelectorAll('.res-p')].every(c => { const cell = c.closest('.grid-cell-dim').getBoundingClientRect(), r = c.getBoundingClientRect(); return r.right <= cell.right + 1; })"))
    seed()

    # ------------------------------------------------------------ resizing
    w0 = cellw("resource")
    box = pg.locator('#gridHeader .col-resizer[data-col="resource"]').bounding_box()
    pg.mouse.move(box["x"] + 3, box["y"] + box["height"] / 2); pg.mouse.down(); pg.mouse.move(box["x"] + 63, box["y"] + 5, steps=4)
    check("while dragging the column follows the mouse", abs(cellw("resource") - (w0 + 60)) <= 2, (w0, cellw("resource")))
    pg.mouse.up(); pg.wait_for_timeout(150)
    check("after the drag the width is stored", abs(ev("() => colWidths.resource") - (w0 + 60)) <= 2, ev("() => colWidths"))
    check("it is saved with the device prefs", abs(ev("() => JSON.parse(localStorage.getItem('milestone-prefs')).cw.resource") - (w0 + 60)) <= 2)
    ev("() => { colWidths.start = 5; render(); }"); check("a width below the minimum is held at it", ev("() => cellw = visibleTaskCols().indexOf('start') + 1") and cellw("start") >= 35, cellw("start"))
    ev("() => { colWidths.resource = 60 + 60; delete colWidths.start; save(); render(); }")
    pg.reload(); pg.wait_for_selector("#undoBtn"); ev("() => { historyCoalesceMs = 0; }")
    check("it survives a reload", ev("() => colWidths.resource") == 120 and abs(cellw("resource") - 120) <= 2, (ev("() => colWidths"), cellw("resource")))
    check("the Gantt view uses the same widths", (lambda: (ev("() => { setView('gantt'); }"), pg.wait_for_timeout(200), abs(cellw("name") - cellw("name")) < 1 and ev("() => colWidths.resource") == 120)[2])())
    ev("() => setView('tasks')")
    check("widths of unknown columns in saved prefs are ignored", ev("() => { localStorage.setItem('milestone-prefs', JSON.stringify(Object.assign(JSON.parse(localStorage.getItem('milestone-prefs')), { cw: { nope: 200, start: 'x', resource: 99999 } }))); loadPrefs(); return JSON.stringify(colWidths); }") == '{"resource":700}')
    seed()

    # ------------------------------------------------------------ fit / default
    pg.mouse.click(box["x"] + 3, box["y"] + 20); pg.mouse.click(box["x"] + 3, box["y"] + 20); pg.wait_for_timeout(200)
    fit = ev("() => colWidths.resource")
    check("a double-click on the edge fits the column to its widest cell", fit and fit > w0, (fit, w0))
    check("...and all of that cell's text is visible (nothing cut)", ev("() => { const c = document.querySelector('#gridRows .grid-row').children[visibleTaskCols().indexOf('resource') + 1]; return c.scrollWidth <= c.clientWidth + 1; }"))
    pg.mouse.click(box["x"] + 3, box["y"] + 20); pg.mouse.click(box["x"] + 3, box["y"] + 20)
    pg.click('#gridHeader .col-head >> nth=3', button="right"); pg.wait_for_timeout(100)
    check("right-click on a header opens Fit to content / Default width", pg.locator("#colWidthMenu.open").count() == 1 and "Fit to content" in pg.inner_text("#colWidthMenu") and "Default width" in pg.inner_text("#colWidthMenu"))
    check("Default width is disabled for a column nobody resized", pg.locator("#colWidthMenu button:has-text('Default width')").is_disabled())
    pg.keyboard.press("Escape"); pg.mouse.click(700, 600); pg.wait_for_timeout(100)
    check("clicking elsewhere closes it", pg.locator("#colWidthMenu.open").count() == 0)
    ev("() => { colWidths.resource = 300; render(); }")
    pg.click('#gridHeader .col-head:has(.col-resizer[data-col="resource"])', button="right"); pg.click("#colWidthMenu button:has-text('Default width')"); pg.wait_for_timeout(150)
    check("Default width brings the column back", ev("() => colWidths.resource") is None and abs(cellw("resource") - 140) <= 2, cellw("resource"))
    ev("() => { colWidths.resource = 300; colWidths.start = 150; render(); }")
    pg.click('#gridHeader .col-head >> nth=1', button="right"); pg.click("#colWidthMenu button:has-text('Reset all')"); pg.wait_for_timeout(150)
    check("Reset all column widths clears every one", ev("() => Object.keys(colWidths).length") == 0)
    ev("() => { colWidths.name = 200; render(); }")
    check("a resized Task Name keeps the width you gave it", abs(cellw("name") - 200) <= 2, cellw("name"))
    ev("() => { colWidths = {}; save(); render(); }")
    pg.click("#columnsBtn"); check("the Columns menu has Reset column widths (disabled when none is resized)", pg.locator("#columnsMenu button:has-text('Reset column widths')").is_disabled()); pg.keyboard.press("Escape"); pg.mouse.click(700, 600)
    pg.click('#gridHeader .col-head >> nth=1', button="right"); pg.click("#colWidthMenu button:has-text('Fit all columns')"); pg.wait_for_timeout(200)
    cw = ev("() => ({ ...colWidths })")
    check("Fit all columns fits every shown column but leaves Task Name filling the pane", "name" not in cw and all(k in cw for k in ["start", "end", "duration", "progress", "preds", "resource", "status"]), cw)
    check("...and each one shows all its text", ev("() => visibleTaskCols().filter(c => c !== 'name').every(c => { const k = visibleTaskCols().indexOf(c) + 1; return [...document.querySelectorAll('#gridRows .grid-row')].every(r => r.children[k].scrollWidth <= r.children[k].clientWidth + 1); })"))
    ev("() => { colWidths = {}; save(); render(); }")
    pg.click("#columnsBtn"); pg.click("#columnsMenu button:has-text('Fit all columns')"); pg.wait_for_timeout(200)
    check("the Columns menu has Fit all columns too", ev("() => Object.keys(colWidths).length") > 5)
    ev("() => { colWidths = {}; save(); render(); }")

    # ------------------------------------------------------------ change highlighting
    seed()
    ev("() => { startInlineEdit('a', 'duration'); }"); pg.wait_for_timeout(80)
    pg.fill("#gridRows .inline-edit", "8"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    m = marks()
    check("an edit shades what changed because of it: the later tasks' dates", m.get("b") == ["end", "start"] and m.get("c") == ["end", "start"], m)
    check("...and Work on the task itself (recalculated), but not the cell you typed", m.get("a") and "duration" not in m["a"] and "work" in m["a"] and "end" in m["a"], m)
    check("shaded cells carry the chg class in the list", ev("() => document.querySelectorAll('#gridRows .grid-row > .chg').length") >= 4)
    check("the shade is a different background from a plain cell", ev("() => { const c = document.querySelector('#gridRows .grid-row > .chg'), n = document.querySelector('#gridRows .grid-row > .grid-cell-dim:not(.chg)'); return getComputedStyle(c).backgroundColor !== getComputedStyle(n).backgroundColor; }"))
    ev("() => { startInlineEdit('c', 'progress'); }"); pg.wait_for_timeout(80)
    pg.fill("#gridRows .inline-edit", "40"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("the next edit replaces the marks (Test's own % is the edit; nothing else changed)", marks() == {}, marks())
    ev("() => { startInlineEdit('a', 'start'); }"); pg.wait_for_timeout(80)
    pg.fill("#gridRows .inline-edit", "2026-09-08"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("moving a Start later shades the Duration it shortened (not the Start you typed)", marks().get("a") == ["duration"], marks())
    ev("() => historyUndo()"); pg.wait_for_timeout(150)
    check("Undo clears the marks", marks() == {})
    # the Task Form: what you typed there is not shaded either
    seed(); ev("() => { setSelection(['a']); render(); }")
    pg.click("#taskFormBtn"); pg.wait_for_timeout(120)
    pg.fill("#tfDur", "8"); pg.click("#tfOkBtn"); pg.wait_for_timeout(250)
    m = marks()
    check("a Task Form edit: Duration (typed) is not shaded, Finish and the follower's dates are", m.get("a") and "duration" not in m["a"] and "end" in m["a"] and m.get("b") == ["end", "start"], m)
    pg.click("#taskFormBtn")
    # the toggle
    pg.click("#columnsBtn"); pg.click("#columnsMenu button:has-text('Highlight what the last edit changed')"); pg.keyboard.press("Escape"); pg.mouse.click(700, 600); pg.wait_for_timeout(100)
    check("switched off in the Columns menu, nothing is shaded (and it is remembered)", ev("() => document.querySelectorAll('#gridRows .chg').length") == 0 and ev("() => JSON.parse(localStorage.getItem('milestone-prefs')).showChanges") is False)
    ev("() => { showChanges = true; save(); render(); }")
    check("no console errors", not errors, errors)
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
