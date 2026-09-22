# -*- coding: utf-8 -*-
"""Empty lines (spacer rows): the toolbar button, where the line goes, what it is not (no WBS, dates, links, bar, filter match), the row, and every
feature that has to cope with one: clone, delete + undo, copy/paste, bulk edit, find, filters, print, Excel, history, reload, hand-made bad data."""
from playwright.sync_api import sync_playwright
import os, io, base64, openpyxl
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:600]}]" if not cond and detail else ""))

SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); colFilters = newColFilters(); filterPinned.clear(); editingCell = null; delete project.holidays; delete project.workDays; historyCoalesceMs = 0;
  const mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('g', 'Group', 0), mk('a', 'Alpha', 0, { parentId: 'g' }), mk('b', 'Beta', 1, { parentId: 'g', startDate: '2026-09-14', endDate: '2026-09-18', predecessors: [{ id: 'a', type: 'FS', lag: 0 }] }), mk('c', 'Gamma', 1, { startDate: '2026-09-21', endDate: '2026-09-25', resource: 'Anna' }), mk('d', 'Delta', 2, { startDate: '2026-09-28', endDate: '2026-10-02' }));
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
OUTLINE = "() => visibleTaskList().map(v => (v.task.spacer ? '·' : v.task.name) + (v.depth ? '@' + v.depth : ''))"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1700, "height": 850}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    def add_line(): pg.click("#addMenuBtn"); pg.click("#addSpacerBtn")   # the Add menu's "Add empty line"
    def fresh(): ev(SEED); pg.wait_for_timeout(120)
    def pick(name, mods=None):
        row = pg.locator(f".grid-row[data-id='{ev('(n) => tasks.find(t => t.name === n).id', name)}']"); row.locator("> div").first.click(modifiers=mods or []); pg.wait_for_timeout(80)
    def rowof(i): return pg.locator("#gridRows .grid-row").nth(i)
    sp = lambda: ev("() => tasks.filter(t => t.spacer).length")
    modal_open = lambda: ev("() => document.getElementById('taskModalBg').classList.contains('open')")
    toast = lambda: pg.inner_text("#toastMsg")

    # ---------------------------------------------------------------- the button and where the line goes
    fresh()
    pg.click("#addMenuBtn")
    check("the Add menu has an 'Add empty line' item", pg.locator("#addMenu.open #addSpacerBtn").is_visible() and "Add empty line" in pg.inner_text("#addSpacerBtn"))
    pg.keyboard.press("Escape")
    add_line(); pg.wait_for_timeout(200)
    check("nothing selected: the line goes to the end of the top level, and no dialog opens", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "Delta", "·"] and not modal_open(), ev(OUTLINE))
    t = ev("() => { const s = tasks.find(t => t.spacer); return { name: s.name, spacer: s.spacer, wbs: wbsCode(s.id), id: taskDisplayId(s.id), sel: selectedIds().map(id => byId(id).spacer === true), parent: s.parentId }; }")
    check("...it has no name and no WBS, takes an ID, is the selection", t["name"] == "" and t["spacer"] is True and t["wbs"] == "" and t["id"] == 6 and t["sel"] == [True], t)
    add_line(); pg.wait_for_timeout(150)
    check("pressing the button again stacks another line below it", ev(OUTLINE)[-2:] == ["·", "·"] and sp() == 2, ev(OUTLINE))
    fresh(); pick("Gamma"); add_line(); pg.wait_for_timeout(150)
    check("a task selected: the line goes right below it, at its level", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "·", "Delta"], ev(OUTLINE))
    fresh(); pick("Group"); add_line(); pg.wait_for_timeout(150)
    check("a group selected: the line goes after the whole group, not inside it", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "·", "Gamma", "Delta"], ev(OUTLINE))
    fresh(); pick("Alpha"); add_line(); pg.wait_for_timeout(150)
    check("a sub-task selected: the line goes below it inside the group", ev(OUTLINE) == ["Group", "Alpha@1", "·@1", "Beta@1", "Gamma", "Delta"], ev(OUTLINE))
    check("the WBS codes ignore the line (Beta stays 1.2) while the IDs count it (Beta is now #4)", ev("() => [wbsCode(byId('b').id), taskDisplayId('b')]") == ["1.2", 4], ev("() => [wbsCode('b'), taskDisplayId('b')]"))
    check("the link Alpha → Beta still reads correctly from the shifted numbers", ev("() => predecessorLabel(byId('b'))") == "2FS", ev("() => predecessorLabel(byId('b'))"))

    # ---------------------------------------------------------------- the row
    sid = ev("() => tasks.find(t => t.spacer).id"); row = pg.locator(f".grid-row[data-id='{sid}']")
    check("the row is a blank row: the ID and nothing else", row.get_attribute("class").count("spacer-row") == 1 and row.inner_text().strip() == "3", row.inner_text())
    check("...it has Clone and Delete but no Edit button", row.locator(".grid-actions button").count() == 2 and row.locator("[title='Edit']").count() == 0)
    for col in range(1, 6):
        row.locator("> div").nth(col).click(); pg.wait_for_timeout(60)
    check("clicking its cells selects it and starts no editing", ev("() => !editingCell") and pg.locator("#gridRows .inline-edit").count() == 0 and ev("() => selectedIds().length") == 1)
    row.locator("> div").nth(3).dblclick(); pg.wait_for_timeout(250)
    check("double-clicking it opens no dialog", not modal_open())
    ev("(id) => openTaskModal(id)", sid); pg.wait_for_timeout(200)
    check("openTaskModal on it does nothing either", not modal_open())
    check("the bar chart draws nothing for it", ev("(id) => { setView('gantt'); render(); return !document.querySelector(`.gantt-bar[data-id='${id}']`) && !barGeom[id] && !!document.querySelector(`.gantt-row-bg.spacer[data-row-id='${id}']`); }", sid))
    ev("() => setView('tasks')")

    # ---------------------------------------------------------------- what it is not
    fresh()
    ev("() => { const s = { id: 'sp', name: '', spacer: true, parentId: null, order: 5, startDate: '2031-01-01', endDate: '2031-02-01', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', resource: '', actualStart: null, actualFinish: null }; tasks.push(s); normalizeData(); save(); render(); }")
    check("an empty line dated years away does not stretch the Gantt's date range", ev("() => { const r = computeDateRange(); return dayNumberToIso(r.end) < '2027-01-01'; }"))
    check("...has no status, remaining duration or dates as far as the app is concerned", ev("() => { const e = effectiveDates('sp'); return e.start === null && taskStatus('sp') === null && remainingDays('sp') === null; }"))
    check("...is not on the critical path and the path is unchanged", ev("() => { const c = computeCriticalPath(); return !c.has('sp') && c.size > 0; }"))
    ev("() => { const s = byId('sp'); s.name = 'Some name'; s.progress = 50; s.resource = 'Anna'; s.milestone = true; s.predecessors = [{ id: 'a', type: 'FS', lag: 0 }]; s.actualStart = '2026-09-01'; s.color = 'red'; s.custom = { text1: 'x' }; s.baselines = { 0: ['2026-09-07', '2026-09-11'] }; s.taskMode = 'auto'; s.startText = 'TBD'; normalizeData(); }")
    check("normalize empties a damaged empty line (name, %, resource, links, actual dates, colour, custom values, baselines)", ev("() => { const s = byId('sp'); return s.name === '' && s.progress === 0 && s.resource === '' && !s.milestone && !s.predecessors.length && !s.actualStart && !s.color && !s.custom && !s.baselines && s.taskMode === 'manual' && s.startText === null; }"), ev("() => JSON.stringify(byId('sp'))"))
    ev("() => { byId('c').predecessors = [{ id: 'sp', type: 'FS', lag: 0 }]; byId('d').parentId = 'sp'; normalizeData(); }")
    check("a link to an empty line is dropped, and a task filed under one moves up to the line's parent", ev("() => byId('c').predecessors.length === 0 && byId('d').parentId === null"), ev("() => [byId('c').predecessors, byId('d').parentId]"))
    ev("() => { byId('d').parentId = 'sp'; byId('sp').parentId = 'g'; normalizeData(); }")
    check("...(a line inside a group: the task goes to the group)", ev("() => byId('d').parentId === 'g'"))
    ev("() => { byId('sp').parentId = null; normalizeData(); save(); render(); }")
    n1 = ev("() => stableStringify(tasks)"); ev("() => normalizeData()"); check("normalize is idempotent with empty lines", n1 == ev("() => stableStringify(tasks)"))
    fresh(); ev("() => { const s = { id: 'sp', name: '', spacer: true, parentId: null, order: 1, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', resource: '', actualStart: null, actualFinish: null }; tasks.push(s); byId('c').order = 2; byId('d').order = 3; normalizeData(); save(); render(); }")
    # predecessors typed by number
    num = ev("() => taskDisplayId('sp')"); dnum = ev("() => taskDisplayId('d')")
    ev("(id) => startInlineEdit(id, 'predecessors')", "d"); pg.wait_for_timeout(200)
    pg.fill("#gridRows .inline-edit", str(num)); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("typing an empty line's number as a predecessor is refused with a message", ev("() => byId('d').predecessors.length") == 0 and "empty line" in toast(), toast())
    # indent under a line
    ev("() => { setSelection(['c']); render(); }"); pg.click("#indentBtn"); pg.wait_for_timeout(200)
    check("Indent is refused when the row above is an empty line", ev("() => byId('c').parentId") is None and "empty line" in toast(), toast())
    ev("() => { setSelection(['sp']); render(); }"); pg.click("#indentBtn"); pg.wait_for_timeout(200)
    check("...but an empty line itself can be indented into the group above it", ev("() => byId('sp').parentId") == "g", ev("() => byId('sp').parentId"))
    pg.click("#outdentBtn"); pg.wait_for_timeout(200)
    check("...and outdented again", ev("() => byId('sp').parentId") is None)

    # ---------------------------------------------------------------- reordering
    ev("() => moveTask('sp', 'a', 'before')"); pg.wait_for_timeout(120)
    check("it can be moved like any row (moveTask before Alpha)", ev(OUTLINE)[:3] == ["Group", "·@1", "Alpha@1"], ev(OUTLINE))
    ev("() => moveTask('sp', 'd', 'after')"); pg.wait_for_timeout(120)
    check("...and moved to the end", ev(OUTLINE)[-1] == "·", ev(OUTLINE))

    # ---------------------------------------------------------------- clone, delete, undo
    fresh(); pick("Gamma"); add_line(); pg.wait_for_timeout(150)
    sid = ev("() => tasks.find(t => t.spacer).id"); before = ev(OUTLINE)
    pg.click("#cloneTaskBtn"); pg.wait_for_timeout(200)
    check("Clone copies the line (another empty line right below it, no ' (copy)' name)", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "·", "·", "Delta"] and ev("() => tasks.filter(t => t.spacer).every(t => t.name === '')") and "empty line" in toast(), (ev(OUTLINE), toast()))
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(200)
    check("...and its Undo removes it", ev(OUTLINE) == before, ev(OUTLINE))
    ev("(id) => { setSelection([id]); render(); }", sid); pg.click("#deleteTaskBtn"); pg.wait_for_timeout(200)
    check("Delete asks 'Delete this empty line?'", "empty line" in pg.inner_text("#confirmModalBody"), pg.inner_text("#confirmModalBody"))
    pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(200)
    check("...and removes it", sp() == 0 and ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "Delta"], ev(OUTLINE))
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(200)
    check("...Undo brings it back in place", ev(OUTLINE) == before, ev(OUTLINE))
    pg.keyboard.press("Escape")
    fresh(); pick("Gamma"); add_line(); pg.wait_for_timeout(200)
    ev("() => historyUndo()"); pg.wait_for_timeout(200)
    check("Undo removes an added line", sp() == 0 and "empty line" in toast(), (sp(), toast()))
    ev("() => historyRedo()"); pg.wait_for_timeout(200)
    check("Redo puts it back", sp() == 1 and ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "·", "Delta"], ev(OUTLINE))

    # ---------------------------------------------------------------- copy / paste
    ev("() => { const s = tasks.find(t => t.spacer); setSelection(['c', s.id, 'd'], 'c'); render(); }"); pg.wait_for_timeout(80)
    clip = ev("() => { const c = buildClip(); return { rows: c.tsv.split('\\n').length, lines: c.tsv.split('\\n'), n: c.json.tasks.filter(t => t.spacer).length }; }")
    check("copy: the table has a row for the line with only its ID, and the private format carries the flag", clip["rows"] == 4 and clip["lines"][2].replace("\t", "") == "5" and clip["n"] == 1, clip)
    ev("() => { window.__c = buildClip(); }")
    ev("() => { setSelection(['d']); pasteFrom(__c.tsv, JSON.stringify(__c.json)); }"); pg.wait_for_timeout(200)
    check("paste puts the empty line back with the tasks (Gamma, line, Delta pasted below Delta)", ev(OUTLINE)[-3:] == ["Gamma", "·", "Delta"] and sp() == 2, ev(OUTLINE))
    check("...the pasted line is a proper empty line", ev("() => tasks.filter(t => t.spacer).every(t => t.name === '' && t.spacer === true && !t.predecessors.length)"))
    ev("() => historyUndo()")

    # ---------------------------------------------------------------- bulk edit, find, filters
    fresh(); pick("Gamma"); add_line(); pg.wait_for_timeout(150)
    check("only an empty line selected: the bulk-edit button is disabled", pg.locator("#bulkEditBtn").is_disabled())
    sid = ev("() => tasks.find(t => t.spacer).id"); ev("(id) => { setSelection([id, 'c', 'd'], 'c'); render(); }", sid); pg.wait_for_timeout(80)
    pg.click("#bulkEditBtn"); pg.wait_for_timeout(200)
    check("with tasks selected too it opens and counts only the tasks", "Edit 2 tasks" in pg.inner_text("#bulkTitle"), pg.inner_text("#bulkTitle"))
    pg.fill("#bulkVal-resource", "Ben"); pg.click("#bulkModalBg .btn-primary"); pg.wait_for_timeout(250)
    check("...and changes only the tasks (the line stays empty)", ev("() => [byId('c').resource, byId('d').resource, tasks.find(t => t.spacer).resource]") == ["Ben", "Ben", ""], ev("() => [byId('c').resource, byId('d').resource]"))
    check("Find: '#n' of an empty line finds nothing, and a name search never lists one", ev("(n) => searchTasks('#' + n).length === 0 && searchTasks('a').every(r => !r.t.spacer) && searchTasks('2.').every(r => !r.t.spacer)", ev("(id) => taskDisplayId(id)", sid)))
    ev("() => { filterPinned.clear(); colFilters.name = { type: 'rule', rule: 'notcontains', a: 'zzz', b: '' }; render(); }"); pg.wait_for_timeout(150)
    check("a filter hides the empty lines (even one that keeps every task: 'name does not contain zzz')", ev(OUTLINE) == ["Group", "Alpha@1", "Beta@1", "Gamma", "Delta"], ev(OUTLINE))
    check("...and the chip's count leaves the lines out ('5 of 5 tasks')", "5 of 5 tasks" in pg.inner_text("#filterBar"), pg.inner_text("#filterBar"))
    ev("() => { colFilters = newColFilters(); filterPinned.clear(); render(); }")
    check("without a filter they are back", "·" in ev(OUTLINE))

    # ---------------------------------------------------------------- print and Excel
    b64 = ev("""async () => { const blob = buildXlsx({ scope: 'all', gantt: true, columns: 'shown' }); const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (const c of buf) s += String.fromCharCode(c); return btoa(s); }""")
    wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(b64))); ws = wb["Tasks"]
    heads = {ws.cell(4, c).value: c for c in range(1, ws.max_column + 1)}
    rows = [[ws.cell(r, c).value for c in range(1, ws.max_column + 1)] for r in range(5, ws.max_row + 1)]
    line = [r for r in rows if r[0] == 5]
    check("Excel Tasks sheet: the empty line is a row with its ID and nothing else", len(line) == 1 and all(v is None for v in line[0][1:]), line)
    check("...the tasks around it are all there (5 tasks + 1 line)", len([r for r in rows if r[0] is not None]) == 6, rows)
    check("Excel Gantt sheet builds too", "Gantt" in wb.sheetnames)
    o = ev("""() => { openPrintModal(); return { open: document.getElementById('printModalBg').classList.contains('open'), pages: document.querySelectorAll('#printModalBg svg').length }; }""")
    check("Print preview builds with empty lines in the plan", o["open"] and o["pages"] >= 1, o)
    ev("() => closePrintModal()")

    # ---------------------------------------------------------------- persistence and sync
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(300)
    check("the empty lines survive a reload", sp() == 1 and "·" in ev(OUTLINE), ev(OUTLINE))
    merged = ev("""() => { const before = stableStringify(tasks); const data = JSON.parse(JSON.stringify(syncPayload())); mergeData(data, { respectTombstones: true }); normalizeData(); return before === stableStringify(tasks); }""")
    check("merging the plan with itself changes nothing", merged)
    dc = ev("""() => { const a = JSON.parse(canonicalText()); const b = JSON.parse(canonicalText()); b.tasks.push({ id: 'zz', name: '', spacer: true, parentId: null, order: 9, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', resource: '', actualStart: null, actualFinish: null }); return describeChange(JSON.stringify(a), JSON.stringify(b)); }""")
    check("the history step for adding one reads 'Add an empty line'", dc == "Add an empty line", dc)

    # ---------------------------------------------------------------- help
    ev("() => openHelpModal()")
    pg.wait_for_timeout(200)
    txt = ev("() => document.getElementById('helpModalBg').innerText")
    check("the Help explains the empty line", "Add empty line" in txt or "empty line" in txt)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
