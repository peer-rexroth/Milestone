from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """(specs) => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); delete project.workDays; delete project.holidays;
  const ids = {};
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag})); }
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seed = lambda specs: pg.evaluate(SEED, specs)
    dates = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return t ? [t.startDate, t.endDate] : null; }", n)
    names = lambda: pg.evaluate("() => tasks.map(t => t.name).sort()")
    edit = lambda n, field, v: pg.evaluate("([n, f, v]) => { const t = tasks.find(x => x.name === n); editingCell = { id: t.id, field: f }; commitInlineEdit(t.id, f, v); }", [n, field, v])
    steps = lambda: pg.evaluate("() => [undoStack.length, redoStack.length]")
    toast = lambda: pg.inner_text("#toastMsg")
    pg.evaluate("() => { historyCoalesceMs = 0; }")   # every save is its own step in the tests (a human's gestures are further apart than the 300 ms window)
    chain = lambda: seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "B", "s": "2026-09-14", "e": "2026-09-16", "preds": [["A", "FS", 0]]}, {"name": "C", "s": "2026-09-17", "e": "2026-09-18", "preds": [["B", "FS", 0]]}])

    # ---------------------------------------------------------------- basics
    chain()
    check("a fresh plan has nothing to undo or redo, and both buttons are disabled", steps() == [0, 0] and pg.evaluate("() => document.getElementById('undoBtn').disabled && document.getElementById('redoBtn').disabled"))
    edit("A", "duration", "3")
    check("an edit is one undo step, and the Undo button is enabled", steps() == [1, 0] and not pg.evaluate("() => document.getElementById('undoBtn').disabled"), steps())
    check("...the edit moved A, B and C (cascade)", dates("A")[1] == "2026-09-09" and dates("B")[0] == "2026-09-10")
    pg.evaluate("() => historyUndo()")
    check("Undo restores A AND everything the cascade moved (B and C) exactly", dates("A") == ["2026-09-07", "2026-09-11"] and dates("B") == ["2026-09-14", "2026-09-16"] and dates("C") == ["2026-09-17", "2026-09-18"], [dates("A"), dates("B"), dates("C")])
    check("...the toast names the task you edited (not one a cascade moved) and offers Redo", toast().startswith('Undid: Finish of "A" and 2 other tasks') and pg.inner_text("#toastUndoBtn") == "Redo", toast())
    check("...one step moved to redo; Redo is enabled", steps() == [0, 1] and not pg.evaluate("() => document.getElementById('redoBtn').disabled"))
    pg.evaluate("() => historyRedo()")
    check("Redo puts it all back (A 3 days, B and C pulled earlier)", dates("A")[1] == "2026-09-09" and dates("B") == ["2026-09-10", "2026-09-14"] and steps() == [1, 0], [dates("A"), dates("B"), steps()])
    pg.evaluate("() => historyUndo()"); edit("B", "duration", "2")
    check("a new change after an undo clears the redo stack", steps()[1] == 0, steps())

    # ---------------------------------------------------------------- add / delete
    chain()
    pg.evaluate("() => { selectedTaskId = tasks[0].id; addTask(); closeTaskModal(); }")
    check("adding a task is undoable: undo removes it", len(names()) == 4 and (pg.evaluate("() => historyUndo()"), names())[1] == ["A", "B", "C"], names())
    check("...the removed task is tombstoned so a sync cannot bring it back", pg.evaluate("() => deletedTaskIds.length") == 1)
    pg.evaluate("() => historyRedo()")
    check("...redo brings it back and lifts the tombstone", len(names()) == 4 and pg.evaluate("() => deletedTaskIds.length") == 0)
    chain()
    pg.evaluate("() => { deleteTaskFlow(tasks.find(t => t.name === 'B').id); confirmModalAction(); }")
    check("deleting B: B gone, C lost its predecessor", names() == ["A", "C"])
    pg.evaluate("() => historyUndo()")
    check("Undo brings B back with its links and dates (and C's link to it)", names() == ["A", "B", "C"] and dates("B") == ["2026-09-14", "2026-09-16"] and pg.evaluate("() => { const c = tasks.find(t => t.name === 'C'); return c.predecessors.length === 1 && c.predecessors[0].id === tasks.find(t => t.name === 'B').id; }"))
    check("...and the toast's own 'Undo' (delete) is gone so it can't restore twice", not pg.evaluate("() => !!toastUndoAction && document.getElementById('toastUndoBtn').textContent === 'Undo' && /deleted/.test(document.getElementById('toastMsg').textContent)"))

    # ---------------------------------------------------------------- sync safety
    chain()
    pg.evaluate("() => { deleteTaskFlow(tasks.find(t => t.name === 'B').id); confirmModalAction(); historyUndo(); }")
    survived = pg.evaluate("""() => { const B = tasks.find(t => t.name === 'B');
      const theirs = { version: 1, project: JSON.parse(JSON.stringify(project)), tasks: tasks.filter(t => t.name !== 'B').map(t => JSON.parse(JSON.stringify(t))), deletedTaskIds: [{ id: B.id, deletedAt: Date.now() - 1000 }] };
      mergeData(theirs, { respectTombstones: true }); return !!tasks.find(t => t.name === 'B'); }""")
    check("an undone delete is NOT deleted again by a file that still carries the old tombstone (restored tasks are stamped newer)", survived)
    chain(); edit("A", "duration", "3")
    pg.evaluate("() => { const t = JSON.parse(canonicalText()); t.tasks.find(x => x.name === 'C').resource = 'Ann'; mergeFromFile(t, 'poll'); }")
    check("merging in another device's changes empties the history (undo can never revert their work)", steps() == [0, 0], steps())

    # ---------------------------------------------------------------- what is not a step
    chain()
    pg.evaluate("() => { save(); save(); }")
    check("a save that changes nothing is not a step", steps() == [0, 0], steps())
    pg.evaluate("() => { tasks[0].updatedAt = Date.now() + 5; save(); }")
    check("...nor is one that only re-stamps updatedAt", steps() == [0, 0], steps())
    pg.evaluate("() => { setView('gantt'); setZoom && setZoom('month'); }")
    check("...nor are view, zoom and column changes (they are not part of the plan)", steps() == [0, 0], steps())
    pg.evaluate("() => { historyCoalesceMs = 300; }")
    chain(); pg.evaluate("() => { historyCoalesceMs = 300; }")
    edit("A", "duration", "3"); edit("A", "duration", "4")
    check("two saves within one gesture (300 ms) share one undo step", steps()[0] == 1, steps())
    pg.wait_for_timeout(400); edit("A", "duration", "2")
    check("...a later one is its own step", steps()[0] == 2, steps())
    pg.evaluate("() => { historyCoalesceMs = 0; }")

    # ---------------------------------------------------------------- limits and reset
    chain()
    pg.evaluate("() => { for (let i = 0; i < 130; i++) { tasks[0].progress = i % 100 + 1; tasks[0].name = 'n' + i; save(); } }")
    check("the history keeps the last 100 steps", steps()[0] == 100, steps())
    chain()
    edit("A", "duration", "3")
    pg.evaluate("() => { const idx = readPlansIndex(); }")
    check("undo and redo survive nothing across a reload (memory only)", (pg.reload(), pg.wait_for_selector("#addTaskBtn"), steps())[2] == [0, 0], steps())
    pg.evaluate("() => { historyCoalesceMs = 0; }")

    # ---------------------------------------------------------------- keyboard
    chain(); edit("A", "duration", "3")
    pg.keyboard.press("Control+z")
    check("Ctrl+Z undoes", dates("A") == ["2026-09-07", "2026-09-11"], dates("A"))
    pg.keyboard.press("Control+Shift+z")
    check("Ctrl+Shift+Z redoes", dates("A")[1] == "2026-09-09", dates("A"))
    pg.keyboard.press("Control+z"); pg.keyboard.press("Control+y")
    check("Ctrl+Y redoes too", dates("A")[1] == "2026-09-09", dates("A"))
    chain(); edit("A", "duration", "3")
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'A'); startInlineEdit(t.id, 'name'); }"); pg.wait_for_timeout(200)
    pg.keyboard.press("Control+z")
    check("in a text field Ctrl+Z is left to the browser (the plan is not undone)", dates("A")[1] == "2026-09-09", dates("A"))
    pg.keyboard.press("Escape")
    pg.evaluate("() => openTaskModal(tasks[0].id)"); pg.wait_for_timeout(250)
    pg.keyboard.press("Control+z")
    check("with a dialog open Ctrl+Z does not touch the plan", dates("A")[1] == "2026-09-09", dates("A"))
    pg.evaluate("() => closeTaskModal()")

    # ---------------------------------------------------------------- the buttons
    chain(); edit("A", "duration", "3")
    pg.click("#undoBtn"); pg.wait_for_timeout(100)
    check("the Undo button undoes", dates("A") == ["2026-09-07", "2026-09-11"])
    pg.click("#redoBtn"); pg.wait_for_timeout(100)
    check("the Redo button redoes", dates("A")[1] == "2026-09-09")
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(100)
    check("the toast after a Redo offers Undo, which works", dates("A") == ["2026-09-07", "2026-09-11"], toast())

    # ---------------------------------------------------------------- plan settings and other plans
    chain()
    pg.evaluate("() => { project.workDays = [1,2,3,4]; project.updatedAt = Date.now(); save(); }")
    pg.evaluate("() => historyUndo()")
    check("plan settings (the working calendar) are undoable too", pg.evaluate("() => project.workDays === undefined"))
    check("...and the toast names them", "settings" in toast().lower(), toast())
    chain(); edit("A", "duration", "3")
    pg.evaluate("() => resetTransientUI()")
    check("switching plans starts the history over", steps() == [0, 0])
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
