# -*- coding: utf-8 -*-
"""The high-value round: task Notes, a Deadline, the Total Slack column, sorting the list, and Today / Scroll to task.
See "Notes, Deadline, Total Slack, Sort, Today" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    SEED = """() => { historyCoalesceMs = 0; project.workDays = [1,2,3,4,5]; delete project.timeUnit; tasks.length = 0; deletedTaskIds.length = 0; sortSpec = null; colFilters = newColFilters();
      const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, x || {});
      tasks.push(mk('p', 'Phase', '2026-10-05', '2026-10-26'),
        mk('a', 'Design', '2026-10-05', '2026-10-09', { parentId: 'p', order: 0, notes: 'Agreed with the client.\\nSee mail.' }),
        mk('b', 'Build', '2026-10-12', '2026-10-23', { parentId: 'p', order: 1, predecessors: [{ id: 'a', type: 'FS', lag: 0 }], deadline: '2026-10-20' }),
        mk('c', 'Docs', '2026-10-12', '2026-10-14', { parentId: 'p', order: 2, predecessors: [{ id: 'a', type: 'FS', lag: 0 }], deadline: '2026-10-30' }),
        mk('d', 'Launch', '2026-10-26', '2026-10-26', { parentId: 'p', order: 3, milestone: true, predecessors: [{ id: 'b', type: 'FS', lag: 0 }] }),
        mk('m', 'Side job', '2026-10-05', '2026-10-06', { taskMode: 'manual' }));
      normalizeData(); for (const c of ['deadline', 'totalSlack', 'notes']) colHidden.delete(c); setSelection([]); currentView = 'tasks'; save(); render(); resetHistory(); }"""
    seed = lambda: ev(SEED)
    cell = lambda tid, col: ev("([t, c]) => { const k = visibleTaskCols().indexOf(c) + 1; return document.querySelector(`#gridRows .grid-row[data-id='${t}']`).children[k]; }", [tid, col])
    ctext = lambda tid, col: ev("([t, c]) => { const k = visibleTaskCols().indexOf(c) + 1; return document.querySelector(`#gridRows .grid-row[data-id='${t}']`).children[k].textContent.trim(); }", [tid, col])
    seed()

    # ---------------------------------------------------------------- Notes
    check("a task with notes shows a note icon by its name (the text as tooltip)", ev("() => { const i = document.querySelector(\"#gridRows .grid-row[data-id='a'] .note-ind\"); return !!i && i.title.startsWith('Agreed with the client.'); }"))
    check("the Notes column shows the first line", ctext("a", "notes") == "Agreed with the client.")
    pg.click("#gridRows .grid-row[data-id='a'] .note-ind"); pg.wait_for_timeout(150)
    check("clicking it opens the task dialog on its Notes tab", pg.locator("#taskModalBg.open").count() == 1 and pg.is_visible("#taskNotesInput") and pg.input_value("#taskNotesInput").startswith("Agreed"))
    check("...the tab carries a dot while there are notes", not ev("() => document.getElementById('taskNotesDot').classList.contains('hidden')"))
    pg.fill("#taskNotesInput", "New note\nsecond line"); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("Save keeps the new note", ev("() => byId('a').notes") == "New note\nsecond line")
    ev("() => openTaskModal('b')"); pg.click("#taskTabBtnNotes"); pg.fill("#taskNotesInput", "   "); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(120)
    check("blank notes are not stored (absent = none)", "notes" not in ev("() => byId('b')"))
    ev("() => historyUndo()"); ev("() => historyUndo()")
    check("Undo brings the old note back", ev("() => byId('a').notes") == "Agreed with the client.\nSee mail.")
    check("an empty line can't hold notes or a deadline", ev("() => { const t = { id: 'sp', spacer: true, name: '', parentId: null, order: 99, startDate: '2026-10-05', endDate: '2026-10-05', notes: 'x', deadline: '2026-10-09', predecessors: [] }; tasks.push(t); normalizeData(); const ok = !('notes' in t) && !('deadline' in t); tasks.pop(); return ok; }"))

    # ---------------------------------------------------------------- Deadline
    check("a deadline Finish runs past shows red in its column and a flag by the name", "deadline-late" in ev("() => { const k = visibleTaskCols().indexOf('deadline') + 1; return document.querySelector(\"#gridRows .grid-row[data-id='b']\").children[k].className; }") and ev("() => !!document.querySelector(\"#gridRows .grid-row[data-id='b'] .deadline-warn\")"))
    check("...one it keeps is plain (no flag)", ctext("c", "deadline") == "30.10.2026" and not ev("() => !!document.querySelector(\"#gridRows .grid-row[data-id='c'] .deadline-warn\")"))
    ev("() => startInlineEdit('c', 'deadline')"); pg.wait_for_timeout(80); pg.fill("#gridRows input.inline-edit", "2026-10-13"); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("the Deadline cell is edited inline (a date picker) — and the deadline never moves the task", ev("() => [byId('c').deadline, byId('c').endDate]") == ["2026-10-13", "2026-10-14"] and ev("() => deadlineMissed(byId('c'))"))
    ev("() => startInlineEdit('c', 'deadline')"); pg.wait_for_timeout(80); pg.fill("#gridRows input.inline-edit", ""); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("...emptying it clears the deadline", "deadline" not in ev("() => byId('c')"))
    ev("() => historyUndo()"); ev("() => historyUndo()")
    ev("() => openTaskModal('b')"); pg.wait_for_timeout(120)
    check("the dialog has a Deadline field beside the constraint, saying how late it finishes", pg.input_value("#taskDeadlineInput") in ("2026-10-20", "20.10.2026") and "3 days late" in pg.inner_text("#taskDeadlineNote"), (pg.input_value("#taskDeadlineInput"), pg.inner_text("#taskDeadlineNote"), ev("() => byId('b').endDate")))
    pg.fill("#taskEndInput", "16.10.2026"); pg.press("#taskEndInput", "Tab"); pg.wait_for_timeout(120)
    check("...and it follows the Finish typed in the dialog ('on track')", "on track" in pg.inner_text("#taskDeadlineNote"))
    ev("() => closeTaskModal()")
    ev("() => setView('gantt')"); pg.wait_for_timeout(200)
    marks = ev("() => [...document.querySelectorAll('.gantt-deadline')].map(e => e.className)")
    check("the chart marks each deadline with an arrow — red when missed, green when kept", sorted(marks) == ["gantt-deadline", "gantt-deadline missed"], marks)
    ev("() => { byId('c').deadline = '2026-12-31'; save(); render(); }")
    check("the chart's range takes in a later deadline (its marker is inside the chart)", ev("() => dateRange.end >= dayNumber('2026-12-31')"))
    ev("() => historyUndo()")

    # ---------------------------------------------------------------- Total Slack
    ev("() => setView('tasks')"); pg.wait_for_timeout(120)
    check("Total Slack: 0 days on the critical chain, 8 days on Docs (it can slip to the Launch)", [ctext(i, "totalSlack") for i in "abcd"] == ["0 days", "0 days", "8 days", "0 days"], [ctext(i, "totalSlack") for i in "abcd"])
    check("...a group shows the least slack of its tasks; a manual task has none", ctext("p", "totalSlack") == "0 days" and ctext("m", "totalSlack") == "")
    ev("() => { byId('c').constraintType = 'FNLT'; byId('c').constraintDate = '2026-10-13'; delete project.honorConstraintDates; save(); render(); }")
    check("negative slack (a finish-no-later-than it can't keep) shows red", ev("() => taskTotalSlack(byId('c'))") < 0 and "var-late" in ev("() => { const k = visibleTaskCols().indexOf('totalSlack') + 1; return document.querySelector(\"#gridRows .grid-row[data-id='c']\").children[k].className; }"))
    ev("() => historyUndo()")
    ev("() => { project.timeUnit = 'minute'; save(); render(); }")
    check("in an Hours & minutes plan slack is working time (whole days read as days, the rest as hours)", ev("() => [taskTotalSlack(byId('c')), fmtSlack(taskTotalSlack(byId('c')))]") == [3840, "8 days"], ev("() => [taskTotalSlack(byId('c')), fmtSlack(taskTotalSlack(byId('c')))]"))
    ev("() => { delete project.timeUnit; save(); render(); }")

    # ---------------------------------------------------------------- Sort
    seed()
    pg.click("#gridHeader .col-filter-btn[data-col='end']"); pg.wait_for_timeout(120)
    check("a column's filter panel starts with Sort buttons (dates: oldest / newest first)", [x.strip() for x in pg.locator("#filterMenu .filter-sort-btn").all_inner_texts()] == ["Sort Oldest first", "Sort Newest first"])
    pg.click("#filterMenu .filter-sort-btn[data-dir='-1']"); pg.wait_for_timeout(150)
    order = ev("() => visibleTaskList().map(v => v.task.id)")
    check("sorting by Finish, newest first, keeps the outline: the phase's tasks are ordered inside it", order == ["p", "d", "b", "c", "a", "m"], order)
    check("...the IDs don't change (a task keeps its number)", ev("() => taskDisplayId('d')") == 5 and ev("() => document.querySelector(\"#gridRows .grid-row[data-id='d']\").children[0].textContent.trim()") == "5")
    check("...the plan's own order is untouched", ev("() => byId('a').order") == 0 and ev("() => byId('d').order") == 3)
    check("...the header shows an arrow, the status bar 'Sorted by Finish'", ev("() => !!document.querySelector('#gridHeader .sort-ind.fa-arrow-down-short-wide')") and "Sorted by Finish" in pg.inner_text("#filterBar"))
    ev("() => { setSelection(['b']); render(); }"); pg.click("#indentBtn"); pg.wait_for_timeout(120)
    check("while sorted, indenting is refused with a hint (rows aren't in plan order)", ev("() => byId('b').parentId") == "p" and "sorted" in pg.inner_text("#toast").lower())
    ev("() => setSort('deadline', 1)")
    check("blank values go last, whichever way", ev("() => visibleTaskList().filter(v => v.task.parentId === 'p').map(v => v.task.id)")[:2] == ["b", "c"])
    pg.click("#filterBar .sort-chip button"); pg.wait_for_timeout(120)
    check("the chip's × clears the sort: the plan's order is back", ev("() => visibleTaskList().map(v => v.task.id)") == ["p", "a", "b", "c", "d", "m"] and ev("() => sortSpec") is None)
    pg.click("#gridHeader .col-head:has(.col-resizer[data-col='name'])", button="right"); pg.wait_for_timeout(80)
    check("right-click on a header offers Sort ascending / descending", pg.locator("#colWidthMenu.open .dropdown-item:has-text('Sort ascending')").count() == 1)
    pg.click("#colWidthMenu .dropdown-item:has-text('Sort ascending')"); pg.wait_for_timeout(100)
    check("...A → Z by name (groups too)", ev("() => visibleTaskList().map(v => v.task.name)") == ["Phase", "Build", "Design", "Docs", "Launch", "Side job"])
    ev("() => setSort(null, 0)")

    # ---------------------------------------------------------------- Today / Scroll to task
    ev("() => { setSelection([]); setView('gantt'); zoom = 'week'; render(); }"); pg.wait_for_timeout(200)
    check("the status bar has Today and Scroll to task in the Gantt view", pg.is_visible("#sbTodayBtn") and pg.is_visible("#sbScrollTaskBtn"))
    check("...Scroll to task is off with nothing selected", pg.is_disabled("#sbScrollTaskBtn"))
    ev("() => { byId('d').startDate = byId('d').endDate = '2027-06-30'; byId('d').predecessors = []; byId('d').constraintType = 'MSO'; byId('d').constraintDate = '2027-06-30'; save(); render(); }"); pg.wait_for_timeout(150)
    ev("() => { setSelection(['d']); render(); document.getElementById('ganttPaneOuter').scrollLeft = 0; }"); pg.wait_for_timeout(100)
    pg.click("#sbScrollTaskBtn"); pg.wait_for_timeout(300)
    vis = ev("() => { const o = document.getElementById('ganttPaneOuter'), g = barGeom['d']; return g.left >= o.scrollLeft && g.left <= o.scrollLeft + o.clientWidth; }")
    check("Scroll to task brings the selected task's bar into view", vis)
    pg.click("#sbTodayBtn"); pg.wait_for_timeout(150)
    today_ok = ev("() => { const o = document.getElementById('ganttPaneOuter'), x = (dayNumber(todayStr()) - dateRange.start) * currentZoom().pxPerDay; return dayNumber(todayStr()) < dateRange.start || dayNumber(todayStr()) > dateRange.end ? 'outside' : (x >= o.scrollLeft && x <= o.scrollLeft + o.clientWidth); }")
    check("Today scrolls today into view (or says it's outside the plan)", today_ok is True or (today_ok == "outside" and "outside" in pg.inner_text("#toast")), today_ok)
    ev("() => setView('resources')"); pg.wait_for_timeout(120)
    check("the Resource Plan has Today, not Scroll to task", pg.is_visible("#sbTodayBtn") and not pg.is_visible("#sbScrollTaskBtn"))
    ev("() => setView('tasks')"); pg.wait_for_timeout(100)
    check("the Tasks view (no timeline) has neither", not pg.is_visible("#sbTodayBtn"))

    # ---------------------------------------------------------------- import / export
    seed()
    xml = ev("() => buildMspdi()")
    check("MS Project XML: a Deadline element, the task's own notes first in Notes", "<Deadline>2026-10-20T" in xml and "<Notes>Agreed with the client.\nSee mail.</Notes>" in xml)
    ev("() => { byId('a').custom = { text1: 'x' }; save(); }")
    xml2 = ev("() => buildMspdi()")
    check("...Milestone's extra details come after a marker line", "Agreed with the client.\nSee mail.\n\nDetails from Milestone:\nText1: x" in xml2)
    back = ev("(x) => { const r = parseMspdi(x); return r.tasks.map(t => [t.name, t.notes || null, t.deadline || null]); }", xml2)
    check("...and an import keeps the notes above the marker and the deadline", ["Design", "Agreed with the client.\nSee mail.", None] in back and ["Build", None, "2026-10-20"] in back, back)
    rows = ev("() => tasksFromTable([['Name', 'Start', 'Finish', 'Deadline', 'Notes'], ['X', '05.10.2026', '09.10.2026', '08.10.2026', 'from the sheet']]).tasks.map(t => [t.deadline, t.notes])")
    check("a CSV / pasted table brings Deadline and Notes columns in", rows == [["2026-10-08", "from the sheet"]], rows)
    clip = ev("() => ['deadline', 'totalSlack', 'notes'].map(c => clipCell(byId('a'), c, 0))")
    check("copying a row copies them too (notes on one line)", clip == ["", "0 days", "Agreed with the client. See mail."], clip)

    # ---------------------------------------------------------------- the column configurator's order (one-time move of the three new columns)
    ev("""() => { const d = JSON.parse(localStorage.getItem('milestone-prefs')); const old = DEFAULT_COL_ORDER.filter(c => !['deadline', 'totalSlack', 'notes'].includes(c));
      const mine = ['name', 'status', ...old.filter(c => c !== 'name' && c !== 'status'), 'deadline', 'totalSlack', 'notes'];
      d.cols = { order: mine, hidden: [], rev: 1 }; d.gcols = { order: [...mine], hidden: [] }; localStorage.setItem('milestone-prefs', JSON.stringify(d)); }""")
    pg.reload(); pg.wait_for_selector("#undoBtn")
    o = ev("() => colOrder"); g = ev("() => gColOrder")
    check("a saved order gets Deadline after Finish, Total Slack after Status, Notes after the variances — once, in both views", all(x[x.index("end") + 1] == "deadline" and x[x.index("status") + 1] == "totalSlack" and x[x.index("durationVariance") + 1] == "notes" for x in (o, g)), o)
    check("...and every other column stays where the user put it (Task Name, Status first)", o[:2] == ["name", "status"], o[:4])
    ev("() => { moveColumn('deadline', 1); }"); pg.reload(); pg.wait_for_selector("#undoBtn")
    check("...not again: a later move of those columns is kept", ev("() => colOrder.indexOf('deadline') !== colOrder.indexOf('end') + 1"))
    check("no console errors", not errors, errors[:5])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
