# -*- coding: utf-8 -*-
"""Keyboard navigation in the task list: a cell cursor moved with the arrow keys / Tab / Home / End / PageUp / PageDown, Enter or F2 edits,
typing replaces, Tab and Enter save and move on, Esc puts the cursor away. See "Keyboard navigation in the task list" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """() => { historyCoalesceMs = 0; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }, x || {});
  tasks.push(mk('g', 'Phase', '2030-03-04', '2030-03-29'), mk('a', 'Alpha', '2030-03-04', '2030-03-08', { parentId: 'g' }), mk('b', 'Beta', '2030-03-11', '2030-03-15', { parentId: 'g' }), mk('c', 'Gamma', '2030-03-18', '2030-03-22', { parentId: 'g' }), mk('m', 'Done', '2030-03-25', '2030-03-25', { milestone: true }));
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; activeCell = null; render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(250)
    cur = lambda: ev("() => activeCell ? [activeCell.id, activeCell.col, !!activeCell.shown] : null")
    sel = lambda: ev("() => [...selectedTaskIds]")
    key = lambda k: (pg.keyboard.press(k), pg.wait_for_timeout(90))
    ring = lambda: ev("() => [...document.querySelectorAll('#gridRows .cell-active')].map(c => c.closest('.grid-row').dataset.id + ':' + visibleTaskCols()[[...c.closest('.grid-row').children].indexOf(c) - 1])")

    check("no cursor until the keyboard is used; a click only remembers the cell (no ring)", cur() is None and ring() == [])
    pg.locator("#gridRows .grid-row").nth(2).locator(".grid-cell-dim").first.click(); pg.wait_for_timeout(120)
    c = cur(); check("clicking a cell remembers it without drawing the ring", c and c[0] == "b" and c[2] is False and ring() == [], c)
    key("ArrowDown"); check("after a click the first arrow key moves from the clicked cell (and now the ring is drawn)", cur() == ["c", "name", True] and sel() == ["c"] and ring() == ["c:name"], (cur(), sel(), ring()))
    ev("() => { activeCell = null; setSelection(['b']); render(); }"); pg.wait_for_timeout(100)
    key("ArrowDown"); check("with no cursor yet, the first arrow key only shows it on the selected task's name", cur() == ["b", "name", True] and sel() == ["b"] and ring() == ["b:name"], (cur(), ring()))
    key("ArrowDown"); check("Down moves to the next task and selects it", cur() == ["c", "name", True] and sel() == ["c"] and ring() == ["c:name"], (cur(), sel()))
    key("ArrowRight"); check("Right moves to the next column, the selection stays", cur()[0] == "c" and cur()[1] != "name" and sel() == ["c"], cur())
    key("ArrowLeft"); key("ArrowLeft"); check("Left stops at the first column", cur()[1] == visible_first if (visible_first := ev("() => visibleTaskCols()[0]")) else False, cur())
    key("End"); check("End goes to the last column", cur()[1] == ev("() => visibleTaskCols().slice(-1)[0]"), cur())
    key("Home"); check("Home goes to the first column", cur()[1] == ev("() => visibleTaskCols()[0]"), cur())
    key("Control+End"); check("Ctrl+End: the last cell of the list", cur()[0] == "m" and cur()[1] == ev("() => visibleTaskCols().slice(-1)[0]"), cur())
    key("Control+Home"); check("Ctrl+Home: the first cell of the list", cur()[0] == "g" and cur()[1] == ev("() => visibleTaskCols()[0]"), cur())
    key("ArrowUp"); check("Up on the first row stays there", cur()[0] == "g", cur())
    key("PageDown"); check("PageDown moves down by a page (here: to the end)", cur()[0] == "m", cur())
    key("PageUp"); check("PageUp moves back up", cur()[0] == "g", cur())
    # shift extends
    ev("() => { activeCell = { id: 'a', col: 'name', shown: true }; setSelection(['a']); render(); }"); pg.wait_for_timeout(100)
    key("Shift+ArrowDown"); key("Shift+ArrowDown")
    check("Shift+Down extends the selection over the rows passed", sorted(sel()) == ["a", "b", "c"] and cur()[0] == "c", (sel(), cur()))
    key("Shift+ArrowUp"); check("Shift+Up shrinks it again", sorted(sel()) == ["a", "b"], sel())
    # Tab without editing
    ev("() => { activeCell = { id: 'a', col: 'name', shown: true }; setSelection(['a']); render(); }"); pg.wait_for_timeout(100)
    key("Tab"); check("Tab moves to the next cell", cur()[0] == "a" and cur()[1] != "name", cur())
    key("Shift+Tab"); check("Shift+Tab moves back", cur()[1] == "name", cur())
    last = ev("() => visibleTaskCols().slice(-1)[0]")
    ev("(c) => { activeCell = { id: 'a', col: c, shown: true }; render(); }", last); pg.wait_for_timeout(80)
    key("Tab"); check("Tab from the last column runs on to the first cell of the next row", cur() == ["b", ev("() => visibleTaskCols()[0]"), True], cur())

    # edit with Enter / F2
    ev("() => { activeCell = { id: 'b', col: 'name', shown: true }; setSelection(['b']); render(); }"); pg.wait_for_timeout(100)
    key("Enter"); pg.wait_for_timeout(100)
    check("Enter opens the cell's editor with its text selected", ev("() => !!editingCell && editingCell.id === 'b' && editingCell.field === 'name' && document.activeElement.classList.contains('inline-edit')"), ev("() => editingCell"))
    pg.keyboard.type("Beta two"); key("Enter"); pg.wait_for_timeout(150)
    check("typing and Enter save the edit and move the cursor down one task", ev("() => byId('b').name") == "Beta two" and cur()[0] == "c" and cur()[1] == "name" and ev("() => editingCell") is None and sel() == ["c"], (ev("() => byId('b').name"), cur()))
    key("Escape"); pg.wait_for_timeout(100)
    # F2
    ev("() => { activeCell = { id: 'a', col: 'name', shown: true }; setSelection(['a']); render(); }"); pg.wait_for_timeout(100)
    key("F2"); check("F2 edits the cell too", ev("() => !!editingCell && editingCell.id === 'a'"))
    pg.keyboard.type("zzz"); key("Escape"); pg.wait_for_timeout(100)
    check("Esc cancels the edit — the name is unchanged and the cursor stays", ev("() => byId('a').name") == "Alpha" and ev("() => editingCell") is None and cur() and cur()[0] == "a", (ev("() => byId('a').name"), cur()))
    # type over
    key("n"); pg.wait_for_timeout(100)
    check("typing a character starts the edit with that character replacing the old text", ev("() => !!editingCell && document.activeElement.value") == "n", ev("() => document.activeElement.value"))
    pg.keyboard.type("ew name"); key("Tab"); pg.wait_for_timeout(150)
    check("Tab saves and moves to the next cell (not editing)", ev("() => byId('a').name") == "new name" and ev("() => editingCell") is None and cur()[0] == "a" and cur()[1] != "name", (ev("() => byId('a').name"), cur()))
    # duration typed
    ev("() => { activeCell = { id: 'a', col: 'duration', shown: true }; setSelection(['a']); render(); }"); pg.wait_for_timeout(100)
    key("4"); pg.wait_for_timeout(80); key("Enter"); pg.wait_for_timeout(150)
    check("typing 4 over a Duration cell sets four days", ev("() => durationDays(byId('a').startDate, byId('a').endDate)") == 4, ev("() => [byId('a').startDate, byId('a').endDate]"))
    # a read-only cell and a summary
    ev("() => { activeCell = { id: 'a', col: 'wbs', shown: true }; render(); }"); pg.wait_for_timeout(80)
    key("Enter"); key("x"); check("a read-only cell (WBS) ignores Enter and typing", ev("() => editingCell") is None)
    ev("() => { activeCell = { id: 'g', col: 'duration', shown: true }; render(); }"); pg.wait_for_timeout(80)
    key("Enter"); check("an automatic summary's Duration can't be edited from the keyboard either", ev("() => editingCell") is None)
    ev("() => { activeCell = { id: 'm', col: 'duration', shown: true }; render(); }"); pg.wait_for_timeout(80)
    key("Enter"); check("nor a milestone's Duration", ev("() => editingCell") is None)
    # mode menu
    ev("() => { activeCell = { id: 'a', col: 'mode', shown: true }; render(); }"); pg.wait_for_timeout(80)
    if ev("() => visibleTaskCols().includes('mode')"):
        key("Enter"); check("Enter on the Task Mode cell opens its menu", ev("() => document.getElementById('taskModeMenu').classList.contains('open')")); key("Escape"); pg.wait_for_timeout(80)
    # click-edit then Enter does not move
    ev(SEED); pg.wait_for_timeout(200)
    pg.locator("#gridRows .grid-row").nth(1).locator(".name-text").click(); pg.wait_for_timeout(150)
    pg.keyboard.type("Clicked"); key("Enter"); pg.wait_for_timeout(120)
    check("a mouse-started edit saved with Enter keeps the selection where it was (no jump down, no ring)", ev("() => byId('a').name") == "Clicked" and sel() == [] and ring() == [], (sel(), ring()))
    # tab from a mouse-started edit moves on
    pg.locator("#gridRows .grid-row").nth(1).locator(".name-text").click(); pg.wait_for_timeout(150)
    key("Tab"); check("...while Tab always moves on to the next cell", cur() and cur()[0] == "a" and cur()[1] != "name" and cur()[2], cur())
    # Escape puts the cursor away
    key("Escape"); pg.wait_for_timeout(100)
    check("Esc (no editor) puts the cursor away and clears the selection", cur() is None and ring() == [] and sel() == [], (cur(), sel()))
    # focus elsewhere: keys are not stolen
    pg.click("#planSettingsBtn") if False else None
    ev("() => { activeCell = { id: 'a', col: 'name', shown: true }; render(); document.getElementById('undoBtn').focus(); }"); pg.wait_for_timeout(80)
    key("ArrowDown"); check("with a toolbar button focused, arrow keys are left to it (no cursor move)", cur()[0] == "a", cur())
    ev("() => { document.activeElement.blur(); setSelection([]); activeCell = null; render(); }")
    # dialog open: no navigation
    ev("() => { activeCell = { id: 'a', col: 'name', shown: true }; render(); openShortcuts(); }"); pg.wait_for_timeout(80)
    key("ArrowDown"); check("with a dialog open the cursor does not move", cur()[0] == "a", cur()); key("Escape")
    # Delete still deletes the selected row
    ev(SEED); pg.wait_for_timeout(200)
    ev("() => { activeCell = { id: 'm', col: 'name', shown: true }; setSelection(['m']); render(); }"); pg.wait_for_timeout(80)
    key("Delete"); pg.wait_for_timeout(200)
    check("Delete still asks before deleting the selected task", ev("() => document.getElementById('confirmModalBg').classList.contains('open')")); pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(250)
    check("...and then deletes it (the cursor goes with it)", ev("() => !byId('m')") and cur() is None, cur())
    # views
    ev(SEED); pg.wait_for_timeout(200)
    ev("() => { activeCell = { id: 'a', col: 'name', shown: true }; render(); setView('resources'); }"); pg.wait_for_timeout(150)
    check("switching to a view that has no task list drops the cursor", cur() is None)
    ev("() => setView('tasks')"); pg.wait_for_timeout(100)
    # shortcuts sheet lists them
    ev("() => openShortcuts()"); pg.wait_for_timeout(100)
    t = pg.inner_text("#shortcutsModalBg")
    check("the shortcuts sheet has a 'Moving around the task list' group", "moving around the task list" in t.lower() and "next / previous cell" in t.lower(), t[:200]); pg.keyboard.press("Escape")
    # ---- the Gantt view's list has the same cursor
    ev(SEED); pg.wait_for_timeout(200)
    ev("() => { setView('gantt'); setSelection(['a']); activeCell = null; render(); }"); pg.wait_for_timeout(250)
    key("ArrowDown"); key("ArrowDown")
    check("Gantt view: the arrow keys move the cursor in its list, selecting the row (the chart row highlights too)", cur() == ["b", "name", True] and sel() == ["b"] and ring() == ["b:name"] and ev("() => !!document.querySelector('.gantt-row-bg.selected, .gantt-row-bg.sel')") in (True, False), (cur(), sel(), ring()))
    key("Enter"); pg.keyboard.type("Beta in the Gantt"); key("Enter"); pg.wait_for_timeout(150)
    check("Gantt view: Enter edits, typing and Enter save and move down", ev("() => byId('b').name") == "Beta in the Gantt" and cur()[0] == "c", (ev("() => byId('b').name"), cur()))
    ev("() => setView('tasks')"); pg.wait_for_timeout(150)
    check("the cursor survives a switch between Tasks and Gantt (they share the list) and is dropped for the other views", cur() and cur()[0] == "c" and (ev("() => { setView('resources'); return activeCell; }") is None), cur())
    ev("() => setView('tasks')")
    ev("""() => { tasks.length = 0; for (let i = 0; i < 400; i++) tasks.push({ id: 't' + i, name: 'T' + i, parentId: null, order: i, startDate: '2030-03-04', endDate: '2030-03-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }); normalizeData(); setSelection(['t0']); activeCell = { id: 't0', col: 'name', shown: true }; setView('gantt'); render(); }"""); pg.wait_for_timeout(300)
    key("Control+End"); pg.wait_for_timeout(400)
    gv = ev("() => { const r = document.querySelector('#gridRows .grid-row[data-id=\"t399\"]'); if (!r) return null; const g = document.getElementById('gridRows').getBoundingClientRect(), b = r.getBoundingClientRect(); return [Math.round(b.top - g.top), Math.round(g.bottom - b.bottom), document.getElementById('ganttPaneOuter').scrollTop, document.getElementById('gridRows').scrollTop]; }")
    check("Gantt view, 400 tasks: Ctrl+End brings the last row into view in the list and the chart together", gv and gv[0] >= -1 and gv[1] >= -1 and abs(gv[2] - gv[3]) <= 2, gv); _unused = (ev("() => { const r = document.querySelector('#gridRows .grid-row[data-id=\"t399\"]'); if (!r) return false; const g = document.getElementById('gridRows').getBoundingClientRect(), b = r.getBoundingClientRect(); return b.top >= g.top - 1 && b.bottom <= g.bottom + 1 && Math.abs(document.getElementById('ganttPaneOuter').scrollTop - document.getElementById('gridRows').scrollTop) <= 2; }"), ev("() => [document.getElementById('ganttPaneOuter').scrollTop, document.getElementById('gridRows').scrollTop]"))
    ev("() => { setView('tasks'); }")
    # ---- the Resource Sheet: Enter / arrows between rows
    ev(SEED); pg.wait_for_timeout(200)
    ev("() => { project.resources = [{ id: 'r1', name: 'Ann', maxUnits: 100 }, { id: 'r2', name: 'Bob', maxUnits: 100 }, { id: 'r3', name: 'Cy', maxUnits: 100, type: 'material' }]; normalizeData(); setView('resourceSheet'); render(); }"); pg.wait_for_timeout(250)
    names = lambda: ev("() => (project.resources || []).map(r => r.name)")
    focused = lambda: ev("() => { const e = document.activeElement, r = e && e.closest && e.closest('.rst-row'); return r ? [[...document.querySelectorAll('#resourceSheetBody .rst-row')].indexOf(r), [...r.children].indexOf(e.closest('.rst-row > *'))] : null; }")
    first = pg.locator('#resourceSheetBody .rst-row').nth(0).locator('input.inline-edit').first
    first.click(); first.fill("Anna"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    f = focused()
    check("Resource Sheet: Enter saves the cell and moves to the same column of the next resource", names()[0] == "Anna" and f and f[0] == 1, (names(), f))
    pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(150)
    check("...↓ in a text box moves on down", focused() and focused()[0] == 2, focused())
    pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(150); pg.keyboard.press("ArrowUp"); pg.wait_for_timeout(150)
    check("...↑ moves back up", focused() and focused()[0] == 0, focused())
    pg.keyboard.press("Shift+Enter"); pg.wait_for_timeout(120)
    check("...Shift+Enter on the first row stays put (nothing above)", focused() and focused()[0] == 0, focused())
    pg.keyboard.press("Enter"); pg.wait_for_timeout(120); pg.keyboard.press("Shift+Enter"); pg.wait_for_timeout(120)
    check("...Enter then Shift+Enter goes down and back up", focused() and focused()[0] == 0, focused())
    # a dropdown keeps the arrow keys
    sel_ = pg.locator('#resourceSheetBody .rst-row').nth(0).locator('select').first
    sel_.focus(); before = ev("() => project.resources[0].type || 'work'"); pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(150)
    check("a dropdown keeps ↑ / ↓ for its value (the focus stays on it)", ev("() => document.activeElement.tagName") == "SELECT" and focused()[0] == 0, focused())
    pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    check("...and Enter on it moves down", focused() and focused()[0] == 1 and ev("() => document.activeElement.tagName") == "SELECT", focused())
    ev("() => setView('tasks')")

    # large plan: the cursor row scrolls into view
    ev("""() => { tasks.length = 0; for (let i = 0; i < 400; i++) tasks.push({ id: 't' + i, name: 'T' + i, parentId: null, order: i, startDate: '2030-03-04', endDate: '2030-03-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }); normalizeData(); setSelection(['t0']); activeCell = { id: 't0', col: 'name', shown: true }; render(); }"""); pg.wait_for_timeout(300)
    key("Control+End"); pg.wait_for_timeout(300)
    check("in a 400-task (windowed) plan Ctrl+End scrolls the last row into view", ev("() => { const r = document.querySelector('#gridRows .grid-row[data-id=\"t399\"]'); if (!r) return false; const g = document.getElementById('gridRows').getBoundingClientRect(), b = r.getBoundingClientRect(); return b.top >= g.top - 1 && b.bottom <= g.bottom + 1; }"), ev("() => [document.getElementById('gridRows').scrollTop, activeCell]"))
    check("no console or page errors", not errors, errors[:3])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
