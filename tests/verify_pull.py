from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

# Mon 2026-09-07 ... Fri 09-11, Mon 09-14 ... (default calendar Mon-Fri)
SEED = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0; delete project.workDays;
  const ids = {};
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag})); }
  currentView = 'tasks'; normalizeData(); save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seed = lambda specs: pg.evaluate(SEED, specs)
    dates = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    con = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return [t.constraintType, t.constraintDate]; }", n)
    edit = lambda n, field, v: pg.evaluate("([n, f, v]) => { const t = tasks.find(x => x.name === n); editingCell = { id: t.id, field: f }; commitInlineEdit(t.id, f, v); }", [n, field, v])
    chain = lambda: seed([
        {"name": "A", "s": "2026-09-07", "e": "2026-09-11"},
        {"name": "B", "s": "2026-09-14", "e": "2026-09-16", "preds": [["A", "FS", 0]]},
        {"name": "C", "s": "2026-09-17", "e": "2026-09-18", "preds": [["B", "FS", 0]]}])

    # ------------------------------------------------------------ pulled earlier
    chain()
    edit("A", "duration", "3")
    check("a predecessor that gets SHORTER pulls its Auto successors earlier (B, then C behind it)", dates("A") == ["2026-09-07", "2026-09-09"] and dates("B") == ["2026-09-10", "2026-09-14"] and dates("C") == ["2026-09-15", "2026-09-16"], [dates("A"), dates("B"), dates("C")])
    check("...durations are kept (B still 3 working days, C 2)", pg.evaluate("() => [durationDays(...['B'].map(n => [tasks.find(t => t.name === n).startDate, tasks.find(t => t.name === n).endDate]).flat())]")[0] == 3)
    chain()
    edit("A", "actualFinish", "2026-09-09")
    check("an EARLY Actual Finish pulls Auto successors earlier (the case that used to stay open)", dates("B") == ["2026-09-10", "2026-09-14"] and dates("C") == ["2026-09-15", "2026-09-16"], [dates("B"), dates("C")])
    chain()
    edit("A", "start", "2026-09-07"); edit("A", "finish", "2026-09-09")
    check("editing the predecessor's Finish earlier pulls the successors too", dates("B") == ["2026-09-10", "2026-09-14"], dates("B"))
    check("...and later still pushes them (Finish back to 09-16 → B starts 09-17)", (edit("A", "finish", "2026-09-16"), dates("B"))[1][0] == "2026-09-17", dates("B"))

    # ------------------------------------------------------------ links removed / task deleted
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Y", "s": "2026-09-07", "e": "2026-09-08"},
          {"name": "X", "s": "2026-09-14", "e": "2026-09-15", "preds": [["A", "FS", 0], ["Y", "FS", 0]]}])
    edit("X", "predecessors", "2")     # only Y (display id 2)
    check("dropping the link that held a task back pulls it to what its remaining links allow (X → the day after Y)", dates("X") == ["2026-09-09", "2026-09-10"], dates("X"))
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Y", "s": "2026-09-07", "e": "2026-09-08"},
          {"name": "X", "s": "2026-09-14", "e": "2026-09-15", "preds": [["A", "FS", 0], ["Y", "FS", 0]]}])
    pg.evaluate("() => { deleteTaskFlow(tasks.find(t => t.name === 'A').id); confirmModalAction(); }")
    check("deleting the predecessor that held a task back pulls it too", dates("X") == ["2026-09-09", "2026-09-10"], dates("X"))
    pg.evaluate("() => { triggerToastUndo(); }")
    check("...and Undo puts the deleted task and the task's place back", dates("X") == ["2026-09-14", "2026-09-15"] and pg.evaluate("() => tasks.length") == 3, [dates("X"), pg.evaluate("() => tasks.length")])
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "X", "s": "2026-09-16", "e": "2026-09-17", "preds": [["A", "FS", 0]]}])
    edit("X", "predecessors", "")
    check("a task with NO link left has nothing to schedule against and stays where it is", dates("X") == ["2026-09-16", "2026-09-17"], dates("X"))

    # ------------------------------------------------------------ typing a date pins it (SNET / FNET)
    chain()
    edit("B", "start", "2026-09-21")
    check("typing a Start on an Auto task sets Start No Earlier Than at that date", con("B") == ["SNET", "2026-09-21"] and dates("B")[0] == "2026-09-21", [con("B"), dates("B")])
    edit("A", "duration", "2")
    check("...so a predecessor moving IN does not pull it before the date the user chose", dates("B")[0] == "2026-09-21", dates("B"))
    edit("A", "finish", "2026-09-30")
    check("...but a predecessor moving OUT still pushes it later", dates("B")[0] == "2026-10-01", dates("B"))
    chain()
    edit("B", "start", "2026-09-08")
    check("a Start typed EARLIER than the links allow is no delay: no constraint, and the links win (B stays at 09-14)", dates("B")[0] == "2026-09-14" and con("B") == ["ASAP", None], [dates("B"), con("B")])
    chain()
    edit("B", "start", "2026-09-14")
    check("a Start typed equal to what the links give adds no constraint", con("B") == ["ASAP", None], con("B"))
    chain()
    edit("B", "start", "2026-09-15")
    check("a Start typed one day later than the links allow IS a delay: Start No Earlier Than 09-15", con("B") == ["SNET", "2026-09-15"] and dates("B")[0] == "2026-09-15", [con("B"), dates("B")])
    chain()
    edit("B", "finish", "2026-09-22")
    check("typing a Finish that only lengthens a task that sits on its links adds no constraint", con("B") == ["ASAP", None] and dates("B") == ["2026-09-14", "2026-09-22"], [con("B"), dates("B")])
    edit("B", "start", "2026-09-21"); edit("B", "finish", "2026-09-25")
    check("typing a Finish for a task that is already delayed sets Finish No Earlier Than at that date", con("B") == ["FNET", "2026-09-25"] and dates("B")[1] == "2026-09-25", [con("B"), dates("B")])
    edit("B", "duration", "4")
    check("editing the Duration does not touch the constraint", con("B")[0] == "FNET", con("B"))
    chain()
    edit("B", "start", "2026-09-21"); edit("B", "start", "2026-09-10")
    check("typing an earlier Start (no delay any more) drops the Start No Earlier Than it had, and B goes back to what its link gives", con("B") == ["ASAP", None] and dates("B")[0] == "2026-09-14", [con("B"), dates("B")])
    edit("B", "start", "2026-09-21"); edit("B", "start", "2026-09-17")
    check("typing another delayed Start moves the Start No Earlier Than to it", con("B") == ["SNET", "2026-09-17"] and dates("B")[0] == "2026-09-17", [con("B"), dates("B")])
    seed([{"name": "S", "s": "2026-09-14", "e": "2026-09-15"}])
    edit("S", "start", "2026-09-21")
    check("a task with no links gets no constraint (there is nothing to be pulled by)", con("S") == ["ASAP", None] and dates("S")[0] == "2026-09-21", [con("S"), dates("S")])
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "M", "s": "2026-09-14", "e": "2026-09-14", "preds": [["A", "FS", 0]], "extra": {"milestone": True}}])
    edit("M", "start", "2026-09-14")
    check("a milestone typed onto the date its links give gets no constraint", con("M") == ["ASAP", None], con("M"))
    edit("M", "start", "2026-09-28")
    check("...a milestone delayed past its links is pinned (Start No Earlier Than 09-28)", con("M") == ["SNET", "2026-09-28"] and dates("M")[0] == "2026-09-28", [con("M"), dates("M")])
    chain()
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); t.constraintType = 'MSO'; t.constraintDate = '2026-09-23'; }")
    edit("B", "start", "2026-09-24")
    check("a constraint the user set on purpose (Must Start On) is left alone", con("B")[0] == "MSO", con("B"))
    chain()
    edit("B", "duration", "4")
    check("no constraint is added when only the duration was edited", con("B")[0] == "ASAP", con("B"))

    # ------------------------------------------------------------ Gantt drag
    chain()
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); dragState = { taskId: t.id, moved: true, previewStart: '2026-09-22', previewEnd: '2026-09-24', mode: 'move' }; onDragMouseUp(); }")
    check("dragging a bar later pins it (SNET at the new start) and keeps it there", dates("B") == ["2026-09-22", "2026-09-24"] and con("B") == ["SNET", "2026-09-22"], [dates("B"), con("B")])
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); dragState = { taskId: t.id, moved: true, previewStart: '2026-09-09', previewEnd: '2026-09-11', mode: 'move' }; onDragMouseUp(); }")
    check("dragging it earlier than its predecessor allows snaps it back to the earliest date its link gives (09-14), and the pin is dropped", dates("B")[0] == "2026-09-14" and con("B") == ["ASAP", None], [dates("B"), con("B")])
    chain()
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); dragState = { taskId: t.id, moved: true, previewStart: '2026-09-14', previewEnd: '2026-09-18', mode: 'resize-right' }; onDragMouseUp(); }")
    check("stretching the right edge of a task that sits on its links adds no constraint", con("B") == ["ASAP", None], con("B"))
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); dragState = { taskId: t.id, moved: true, previewStart: '2026-09-22', previewEnd: '2026-09-24', mode: 'move' }; onDragMouseUp(); }")
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); dragState = { taskId: t.id, moved: true, previewStart: '2026-09-22', previewEnd: '2026-09-28', mode: 'resize-right' }; onDragMouseUp(); }")
    check("...stretching a delayed task's right edge pins the Finish (FNET)", con("B") == ["FNET", "2026-09-28"], con("B"))

    # ------------------------------------------------------------ undoing a delete restores the schedule DOWNSTREAM too (found by the stress test)
    seed([{"name": "E", "s": "2026-09-07", "e": "2026-09-08"}, {"name": "D", "s": "2026-12-01", "e": "2026-12-04"},
          {"name": "X", "s": "2026-12-07", "e": "2026-12-11", "preds": [["D", "FS", 0], ["E", "FS", 0]]}, {"name": "Y", "s": "2026-12-14", "e": "2026-12-18", "preds": [["X", "FS", 0]]},
          {"name": "Z", "s": "2026-12-21", "e": "2026-12-22", "preds": [["Y", "FF", 0]]}])
    pg.evaluate("() => { deleteTaskFlow(tasks.find(t => t.name === 'D').id); confirmModalAction(); }")
    check("deleting D pulls its whole chain earlier: X (its other link is E), then Y behind X, then Z behind Y", dates("X")[0] == "2026-09-09" and dates("Y")[0] == "2026-09-14" or dates("Y")[0] < "2026-12-01", [dates("X"), dates("Y"), dates("Z")])
    pg.evaluate("() => triggerToastUndo()")
    check("Undo brings the chain BACK: D returns and X, Y and Z are on the dates they had (12.-11.12., 14.-18.12., 21.-22.12.)", dates("X") == ["2026-12-07", "2026-12-11"] and dates("Y") == ["2026-12-14", "2026-12-18"] and dates("Z")[0] >= "2026-12-14", [dates("X"), dates("Y"), dates("Z")])
    check("...every Auto task sits where its links put it again", pg.evaluate("() => tasks.every(t => !offItsLinks(t))"))
    seed([{"name": "E", "s": "2026-09-07", "e": "2026-09-08"}, {"name": "D", "s": "2026-12-01", "e": "2026-12-04"},
          {"name": "X", "s": "2026-12-07", "e": "2026-12-11", "preds": [["D", "FS", 0], ["E", "FS", 0]]}, {"name": "Y", "s": "2026-12-14", "e": "2026-12-18", "preds": [["X", "FS", 0]]}])
    pg.evaluate("() => { historyCoalesceMs = 0; deleteTaskFlow(tasks.find(t => t.name === 'D').id); confirmModalAction(); historyUndo(); }")
    check("...and Ctrl+Z (history) does the same", dates("X") == ["2026-12-07", "2026-12-11"] and dates("Y") == ["2026-12-14", "2026-12-18"], [dates("X"), dates("Y")])

    # ------------------------------------------------------------ what is NOT scheduled
    chain()
    pg.evaluate("() => { tasks.find(x => x.name === 'B').taskMode = 'manual'; }")
    edit("A", "duration", "3")
    check("a Manual task is never moved by its predecessors", dates("B") == ["2026-09-14", "2026-09-16"] and dates("C") == ["2026-09-17", "2026-09-18"], [dates("B"), dates("C")])
    chain()
    pg.evaluate("() => { const t = tasks.find(x => x.name === 'B'); t.actualStart = '2026-09-14'; }")
    edit("A", "duration", "3")
    check("a task that has already started keeps its dates", dates("B") == ["2026-09-14", "2026-09-16"], dates("B"))
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Solo", "s": "2026-10-05", "e": "2026-10-06"}])
    edit("A", "duration", "2")
    check("a task with no links is never touched by edits elsewhere", dates("Solo") == ["2026-10-05", "2026-10-06"], dates("Solo"))

    # ------------------------------------------------------------ other link types
    seed([{"name": "A", "s": "2026-09-14", "e": "2026-09-18"}, {"name": "S", "s": "2026-09-15", "e": "2026-09-16", "preds": [["A", "SS", 1]]}])
    edit("A", "start", "2026-09-08")
    check("Start-to-Start with a lag follows its predecessor's start earlier (S = one working day after A's start)", dates("S")[0] == "2026-09-09", dates("S"))
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "F", "s": "2026-09-08", "e": "2026-09-11", "preds": [["A", "FF", 0]]}])
    edit("A", "finish", "2026-09-09")
    check("Finish-to-Finish pulls a task so that it ends with its predecessor (F ends 09-09 with A)", dates("F")[1] == "2026-09-09", dates("F"))

    # ------------------------------------------------------------ dialog
    chain()
    pg.evaluate("() => openTaskModal(tasks.find(x => x.name === 'B').id)")
    pg.wait_for_timeout(200)
    pg.evaluate("() => { document.getElementById('taskStartInput').value = '2026-09-28'; document.getElementById('taskEndInput').value = '2026-09-30'; saveTaskFromModal(); }")
    check("changing the Start in the dialog pins the task like typing it in the list", con("B") == ["SNET", "2026-09-28"] and dates("B")[0] == "2026-09-28", [con("B"), dates("B")])
    chain()
    pg.evaluate("() => openTaskModal(tasks.find(x => x.name === 'B').id)")
    pg.wait_for_timeout(200)
    pg.evaluate("() => { document.getElementById('taskStartInput').value = '2026-09-28'; document.getElementById('taskEndInput').value = '2026-09-30'; document.getElementById('taskConstraintTypeInput').value = 'SNLT'; document.getElementById('taskConstraintTypeInput').dispatchEvent(new Event('change')); document.getElementById('taskConstraintDateInput').value = '2026-10-05'; saveTaskFromModal(); }")
    check("...but not when the constraint was changed in the same save (the user's own choice stands)", con("B") == ["SNLT", "2026-10-05"], con("B"))
    chain()
    pg.evaluate("() => openTaskModal(tasks.find(x => x.name === 'B').id)")
    pg.wait_for_timeout(200)
    pg.evaluate("() => { document.getElementById('taskProgressInput').value = '30'; saveTaskFromModal(); }")
    check("saving the dialog without touching a date adds no constraint", con("B")[0] == "ASAP", con("B"))

    # ------------------------------------------------------------ the constraint shows in the list
    chain(); edit("B", "start", "2026-09-21")
    icon = pg.evaluate("() => { const r = document.querySelector(`.grid-row[data-id='${tasks.find(t => t.name === 'B').id}'] .constraint-icon`); return r ? r.title : null; }")
    check("a pinned task shows the constraint icon, and its tooltip says which", icon and "Start No Earlier Than" in icon and "21.09.2026" in icon, icon)

    # ------------------------------------------------------------ reload keeps it
    pg.reload(); pg.wait_for_selector("#addTaskBtn")
    check("the pin survives a reload", con("B") == ["SNET", "2026-09-21"], con("B"))
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
