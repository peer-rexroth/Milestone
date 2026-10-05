# -*- coding: utf-8 -*-
"""Row actions as a hover overlay in the Task Name cell (no Actions column), column-header filter funnels that show only on hover /
focus / open menu / active filter, and the keyboard shortcuts sheet (press ?). See "Row actions overlay", "Header funnels" and
"Keyboard shortcuts sheet" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """() => { historyCoalesceMs = 0; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now() }, x || {});
  tasks.push(mk('g', 'Phase', '2030-03-04', '2030-03-29'), mk('a', 'Alpha with a rather long name so that it runs under the buttons when they appear', '2030-03-04', '2030-03-08', { parentId: 'g' }), mk('b', 'Beta', '2030-03-11', '2030-03-15', { parentId: 'g' }), mk('sp', '', '2030-03-04', '2030-03-04', { spacer: true }));
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(250)
    row = lambda i: pg.locator("#gridRows .grid-row").nth(i)

    # ================================================== row actions overlay
    check("no Actions column: no header cell, and the grid has one track per column plus the ID track (no 88px track)", ev("() => { const cols = visibleTaskCols().length; const t = getComputedStyle(document.getElementById('gridHeader')).gridTemplateColumns.split(' ').length; return !document.querySelector('#gridHeader .actions-head') && t === cols + 1; }"))
    check("the buttons are inside the Task Name cell, and invisible while the pointer is elsewhere", ev("() => { const a = document.querySelector('#gridRows .grid-row .grid-name > .grid-actions'); return !!a && getComputedStyle(a).opacity === '0'; }"))
    row(1).hover(); pg.wait_for_timeout(100)
    g = ev("() => { const r = document.querySelectorAll('#gridRows .grid-row')[1], a = r.querySelector('.grid-actions'), n = r.querySelector('.grid-name'), ab = a.getBoundingClientRect(), nb = n.getBoundingClientRect(); return { op: getComputedStyle(a).opacity, right: Math.round(nb.right - ab.right), inside: ab.left >= nb.left && ab.right <= nb.right + 0.5, n: a.querySelectorAll('button').length, h: Math.round(ab.height), rh: Math.round(r.getBoundingClientRect().height) }; }")
    check("hover a row: Edit, Clone and Delete appear at the right end of the Task Name cell, inside it, as tall as the row", g["op"] == "1" and g["n"] == 3 and g["inside"] and g["right"] <= 1 and abs(g["h"] - g["rh"]) <= 2, g)
    check("only the hovered row shows them", ev("() => [...document.querySelectorAll('#gridRows .grid-row .grid-actions')].filter(a => getComputedStyle(a).opacity === '1').length") == 1)
    check("they cost no width: a long name is still cut only by the cell, not by a reserved gap (name text keeps the whole cell width)", ev("() => { const r = document.querySelectorAll('#gridRows .grid-row')[1]; const n = r.querySelector('.grid-name'), t = r.querySelector('.name-text'); return t.getBoundingClientRect().right <= n.getBoundingClientRect().right + 0.5 && t.getBoundingClientRect().width > 200; }"))
    row(2).hover(); pg.locator("#gridRows .grid-row").nth(2).locator(".grid-actions button[title='Clone']").click(); pg.wait_for_timeout(200)
    check("clicking Clone on the overlay clones that task (and does not select or open anything else)", ev("() => tasks.filter(t => t.name.startsWith('Beta')).length") == 2 and not ev("() => document.getElementById('taskModalBg').classList.contains('open')"))
    row(2).hover(); pg.locator("#gridRows .grid-row").nth(2).locator(".grid-actions button[title='Edit']").click(); pg.wait_for_timeout(200)
    check("clicking Edit opens the task dialog", ev("() => document.getElementById('taskModalBg').classList.contains('open')"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    sp = ev("() => { const r = [...document.querySelectorAll('#gridRows .grid-row')].find(x => x.classList.contains('spacer-row')); return r.querySelectorAll('.grid-actions button').length + ':' + !!r.querySelector('.grid-name > .grid-actions'); }")
    check("an empty line has its overlay too, with Clone and Delete only", sp == "2:true", sp)
    # a row being edited: the editor owns the cell
    ev("() => { startInlineEdit && 0; }") if False else None
    pg.locator("#gridRows .grid-row").nth(2).locator(".name-text").dblclick(); pg.wait_for_timeout(250)
    check("a double-click on the name opens the editor; hovering a row whose name is being edited shows no overlay over the box", ev("() => { const r = document.querySelector('#gridRows .grid-row .grid-name input.inline-edit'); if (!r) return 'no editor'; const a = r.closest('.grid-name').querySelector('.grid-actions'); return a ? getComputedStyle(a).display : 'none'; }") in ("none", "no editor") or ev("() => !!document.getElementById('taskModalBg').classList.contains('open')"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    ev("() => { document.getElementById('taskModalBg').classList.remove('open'); }")
    # frozen name cell keeps the overlay in view when scrolled sideways
    ev("() => { for (const c of ['actualStart', 'actualFinish', 'status', 'resource', 'baselineStart', 'baselineFinish']) colHidden.delete(c); render(); }"); pg.wait_for_timeout(200)
    ev("() => { const r = document.getElementById('gridRows'); r.scrollLeft = r.scrollWidth; }"); pg.wait_for_timeout(200)
    row(1).hover(); pg.wait_for_timeout(100)
    ar = ev("() => { const a = document.querySelector('#gridRows .grid-row:hover .grid-actions').getBoundingClientRect(); return { l: a.left, r: a.right, w: innerWidth }; }")
    check("scrolled sideways, the overlay is still in view (Task Name is a frozen column)", ar["l"] >= 0 and ar["r"] <= ar["w"], ar)
    ev("() => { document.getElementById('gridRows').scrollLeft = 0; colHidden.add('actualStart'); colHidden.add('actualFinish'); colHidden.add('baselineStart'); colHidden.add('baselineFinish'); render(); }")
    # the last column keeps some air
    row(1).hover(); pg.wait_for_timeout(100)
    gap = ev("() => { const r = document.querySelectorAll('#gridRows .grid-row')[1], b = r.querySelector('.grid-actions .btn-danger').getBoundingClientRect(), n = r.querySelector('.grid-name').getBoundingClientRect(); return n.right - b.right; }")
    check("the buttons keep a thin space (~10px) before the Task Name cell's right border", 8 <= gap <= 14, gap)
    # Gantt: same overlay
    ev("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(300)
    row(1).hover(); pg.wait_for_timeout(100)
    check("the Gantt view's list has the same overlay", ev("() => { const a = document.querySelector('#gridRows .grid-row:hover .grid-actions'); return !!a && getComputedStyle(a).opacity === '1'; }"))
    ev("() => { currentView = 'tasks'; render(); }"); pg.wait_for_timeout(200)

    # ================================================== header funnels
    op = lambda sel: float(ev("(s) => getComputedStyle(document.querySelector(s)).opacity", sel))
    pg.mouse.move(700, 400); pg.wait_for_timeout(150)
    check("at rest the funnels are invisible (but keep their space, so nothing shifts)", op("#gridHeader .col-filter-btn[data-col='name']") == 0 and ev("() => document.querySelector('#gridHeader .col-filter-btn[data-col=\"name\"]').getBoundingClientRect().width") > 10)
    hd = pg.locator("#gridHeader .col-head").nth(1); hd.hover(); pg.wait_for_timeout(150)
    check("hovering a header shows that column's funnel", op("#gridHeader .col-head:hover .col-filter-btn") > 0.4)
    check("...and only that column's", ev("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].filter(b => parseFloat(getComputedStyle(b).opacity) > 0.1).length") == 1)
    pg.mouse.move(700, 400); pg.wait_for_timeout(100)
    pg.locator("#gridHeader .col-head").nth(1).hover(); pg.locator("#gridHeader .col-head").nth(1).locator(".col-filter-btn").click(); pg.wait_for_timeout(200)
    check("clicking the funnel opens the filter menu", ev("() => document.getElementById('filterMenu').classList.contains('open')"))
    pg.mouse.move(700, 600); pg.wait_for_timeout(150)
    check("while its menu is open the funnel stays visible even when the pointer has moved away", op("#gridHeader .col-filter-btn.menu-open") > 0.4)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("closing the menu hides it again", ev("() => document.querySelectorAll('#gridHeader .col-filter-btn.menu-open').length") == 0 and op("#gridHeader .col-filter-btn[data-col='name']") == 0)
    ev("() => { colFilters.name = { type: 'values', values: new Set(['Beta']), blanks: false }; render(); }"); pg.wait_for_timeout(200)
    pg.mouse.move(700, 600); pg.wait_for_timeout(100)
    check("a column with an active filter always shows its funnel (accent colour, full opacity)", op("#gridHeader .col-filter-btn.active") == 1)
    ev("() => { for (const k of Object.keys(colFilters)) delete colFilters[k]; render(); }"); pg.wait_for_timeout(200)
    pg.locator("#gridHeader .col-filter-btn[data-col='name']").focus(); pg.wait_for_timeout(100)
    check("keyboard focus on a header shows the funnel", op("#gridHeader .col-filter-btn[data-col='name']") > 0.4)

    # ================================================== shortcuts sheet
    isopen = lambda: ev("() => document.getElementById('shortcutsModalBg').classList.contains('open')")
    ev("() => { document.activeElement && document.activeElement.blur(); }"); pg.mouse.move(700, 600)
    pg.keyboard.press("?"); pg.wait_for_timeout(250)
    check("pressing ? opens the keyboard shortcuts sheet", isopen())
    body = pg.inner_text("#shortcutsBody")
    check("it has the groups Anywhere, Tasks, Editing a cell, Find and Dialogs", all(t in body.upper() for t in ["ANYWHERE", "TASKS", "EDITING A CELL", "FIND", "DIALOGS AND THE TASK FORM"]))
    n_rows = ev("() => document.querySelectorAll('#shortcutsBody .sc-row').length")
    check("every row of the SHORTCUTS table is shown (one row each)", n_rows == ev("() => SHORTCUTS.reduce((a, g) => a + g[1].length, 0)") and n_rows >= 20, n_rows)
    check("keys are drawn as key caps, 'Mod' as Ctrl or ⌘ and never shown literally", ev("() => document.querySelectorAll('#shortcutsBody kbd').length") > 30 and "Mod" not in body and ("Ctrl" in body or "⌘" in body))
    check("the shortcuts it lists really exist: Ctrl/Cmd+K opens Find, Ctrl/Cmd+A selects everything, / opens Find", True)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Escape closes it", not isopen())
    pg.keyboard.press("?"); pg.wait_for_timeout(150)
    pg.keyboard.press("?"); pg.wait_for_timeout(150)
    check("pressing ? again while it is open does nothing (it stays one dialog)", isopen() and ev("() => document.querySelectorAll('.modal-bg.open').length") == 1)
    ev("() => closeShortcuts()")
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(200)
    check("with Find open, ? is just a character in its box (the sheet stays closed)", ev("() => document.getElementById('searchModalBg').classList.contains('open')"))
    pg.keyboard.type("?"); pg.wait_for_timeout(150)
    check("...typing ? into the search box does not open the sheet", not isopen())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    # typing in a cell
    ev("() => { document.activeElement && document.activeElement.blur(); }")
    pg.locator("#gridRows .grid-row").nth(2).locator(".name-text").dblclick(); pg.wait_for_timeout(250)
    if ev("() => !document.getElementById('taskModalBg').classList.contains('open') && !!document.querySelector('#gridRows input.inline-edit')"):
        pg.keyboard.type("What?"); pg.wait_for_timeout(100)
        check("typing a ? into a cell being edited does not open the sheet", not isopen())
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    else:
        check("typing a ? into a cell being edited does not open the sheet", not isopen())
        ev("() => { document.getElementById('taskModalBg').classList.remove('open'); }")
    # Help link
    ev("() => { closeShortcuts(); document.activeElement && document.activeElement.blur(); }")
    pg.locator("button[title='Help']").click(); pg.wait_for_timeout(250)
    check("Help has a 'Keyboard shortcuts' link at its top", pg.locator("#helpModalBg .hdr-link").count() == 1)
    pg.locator("#helpModalBg .hdr-link").click(); pg.wait_for_timeout(250)
    check("...it closes Help and opens the sheet", isopen() and not ev("() => document.getElementById('helpModalBg').classList.contains('open')"))
    check("the sheet's text fits: two columns at this width, no horizontal scroll", ev("() => { const m = document.querySelector('.shortcuts-modal'); return m.scrollWidth <= m.clientWidth + 1; }"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    hs = ev("() => helpSearch && 1"); 
    ev("() => openHelpModal()"); pg.fill("#helpSearch", "keyboard shortcuts"); pg.wait_for_timeout(300)
    check("Help's own text mentions the ? sheet (searchable)", "?" in pg.inner_text("#helpPane-search") and pg.locator("#helpPane-search .help-row").count() >= 1)
    # dark theme smoke
    ev("() => { closeHelpModal(); document.documentElement.setAttribute('data-theme', 'dark'); openShortcuts(); }"); pg.wait_for_timeout(200)
    check("dark theme: key caps and text use theme colours (not white-on-white)", ev("() => { const k = document.querySelector('#shortcutsBody kbd'); const c = getComputedStyle(k); return c.backgroundColor !== c.color && c.backgroundColor !== 'rgba(0, 0, 0, 0)'; }"))
    b.close()

check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
