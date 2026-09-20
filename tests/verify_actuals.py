from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:250]}]" if not cond and detail else ""))

# spec: name, start, end, mode, preds=[[predName, type, lag]], extra
MK = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear();
  const ids = {}; let n = 0;
  for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: n++, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: sp.mode || 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) if (sp.preds) tasks.find(t => t.name === sp.name).predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag}));
  colHidden.delete('actualStart'); colHidden.delete('actualFinish'); colHidden.delete('date1'); project.fieldNames = { date1: 'Due' }; normalizeData(); currentView = 'tasks'; save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; }")
    make = lambda specs: (pg.evaluate(MK, specs), pg.wait_for_timeout(100))
    head_cols = lambda: pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col)")
    tid = lambda n: pg.evaluate("n => tasks.find(t => t.name === n).id", n)
    dates = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    def cell(name, col):
        return pg.locator(f".grid-row[data-id='{tid(name)}']").locator(":scope > div").nth(1 + head_cols().index(col))
    def wait_focus(): pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('inline-edit')")
    def set_actual(name, col, iso):                # through the list's inline editor, as a user would
        cell(name, col).click(); pg.wait_for_selector(".inline-edit"); wait_focus()
        pg.fill(".inline-edit", iso); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    A = {"name": "A", "s": "2026-09-07", "e": "2026-09-11"}
    def chain(type_="FS", lag=0, b_s="2026-09-12", b_e="2026-09-16", b_mode="auto"):
        return [A, {"name": "B", "s": b_s, "e": b_e, "mode": b_mode, "preds": [["A", type_, lag]]}, {"name": "C", "s": "2026-09-17", "e": "2026-09-19", "preds": [["B", "FS", 0]]}]

    # ================================================================= Finish-to-Start
    make(chain())
    set_actual("A", "actualFinish", "2026-09-18")
    check("FS: the predecessor actually finished later (18.09) -> the successor starts the day after (19.09), keeping its duration", dates("B") == ["2026-09-19", "2026-09-23"], dates("B"))
    check("...and that cascades down the chain (C after B)", dates("C") == ["2026-09-24", "2026-09-26"], dates("C"))
    check("...the moved tasks are stamped, so the change syncs", pg.evaluate("() => tasks.filter(t => t.name !== 'A').every(t => t.updatedAt > 1)"))
    make(chain())
    set_actual("A", "actualFinish", "2026-09-09")
    check("FS: an actual finish EARLIER than planned (09.09) pulls the Auto successor earlier: it starts the day after (10.09), keeping its duration", dates("B") == ["2026-09-10", "2026-09-14"], dates("B"))
    make(chain(b_mode="manual"))
    set_actual("A", "actualFinish", "2026-09-09")
    check("...but switching it to Auto Scheduled re-plans it from what actually happened: 10.09 (the one place a task is pulled earlier)", (pg.evaluate("n => setTaskMode(tasks.find(t => t.name === n).id, 'auto')", "B") or True) and dates("B") == ["2026-09-10", "2026-09-14"], dates("B"))
    make(chain())
    check("without any actual date the link reads the planned finish, exactly as before", pg.evaluate("() => constraintStart(tasks.find(t => t.name === 'B'), false)") == "2026-09-12")
    pg.evaluate("() => { tasks.find(t => t.name === 'A').actualFinish = '2026-09-16'; }")
    check("...and with an actual finish it reads that (16.09 + 1)", pg.evaluate("() => constraintStart(tasks.find(t => t.name === 'B'), false)") == "2026-09-17")
    # lag and lead
    make(chain("FS", 3)); set_actual("A", "actualFinish", "2026-09-18")
    check("FS with a 3-day lag: actual finish 18.09 + 1 + 3 = 22.09", dates("B")[0] == "2026-09-22", dates("B"))
    make(chain("FS", -2)); set_actual("A", "actualFinish", "2026-09-18")
    check("FS with a 2-day lead: 18.09 + 1 - 2 = 17.09", dates("B")[0] == "2026-09-17", dates("B"))
    # started but not finished
    make(chain()); set_actual("A", "actualStart", "2026-09-16")
    check("started late (16.09) and not finished: it is projected to run its planned 5 days from the real start (16.09-20.09), so the FS successor starts 21.09", dates("B") == ["2026-09-21", "2026-09-25"], dates("B"))
    check("...and the task's own schedule moves with it (MS Project): Start = the actual start 16.09, Finish keeps the 5-day duration -> 20.09", dates("A") == ["2026-09-16", "2026-09-20"], dates("A"))
    make(chain()); set_actual("A", "actualStart", "2026-09-08")
    check("started a day late (08.09): projected finish 12.09, so the successor starts 13.09 (MS Project: a late start finishes late)", dates("B") == ["2026-09-13", "2026-09-17"], dates("B"))
    make(chain()); set_actual("A", "actualStart", "2026-09-04")
    check("started early (04.09): the projection is earlier (08.09), and the Auto successor is pulled to the day after it (09.09)", dates("B") == ["2026-09-09", "2026-09-13"], dates("B"))
    check("...though the projection itself is 08.09 (what re-scheduling as Auto would use)", pg.evaluate("() => linkEnd(tasks.find(t => t.name === 'A'))") == "2026-09-08")
    make(chain(b_mode="manual")); set_actual("A", "actualStart", "2026-09-04"); pg.evaluate("n => setTaskMode(tasks.find(t => t.name === n).id, 'auto')", "B"); pg.wait_for_timeout(80)
    check("...and 'Auto Scheduled' on the successor picks it up: B starts 09.09", dates("B")[0] == "2026-09-09", dates("B"))
    make(chain()); set_actual("A", "actualStart", "2026-09-16"); set_actual("A", "actualFinish", "2026-09-17")
    check("once an Actual Finish exists it beats the projection (17.09): B, pushed to 21.09 by the projection, is pulled back to 18.09", pg.evaluate("() => linkEnd(tasks.find(t => t.name === 'A'))") == "2026-09-17" and dates("B")[0] == "2026-09-18", dates("B"))
    make(chain()); set_actual("A", "actualStart", "2026-09-04"); set_actual("A", "actualFinish", "2026-09-20")
    check("a later actual finish (20.09) beats the (earlier) projection -> B starts 21.09", dates("B")[0] == "2026-09-21", dates("B"))
    # both actuals: the actual finish wins
    make(chain()); pg.evaluate("() => { tasks.find(t => t.name === 'A').actualStart = '2026-09-20'; }"); set_actual("A", "actualFinish", "2026-09-22")
    check("both actual dates recorded: the actual finish is what an FS link reads (22.09 -> 23.09)", dates("B")[0] == "2026-09-23", dates("B"))

    # ================================================================= the other link types
    make([A, {"name": "B", "s": "2026-09-09", "e": "2026-09-13", "preds": [["A", "SS", 2]]}, {"name": "C", "s": "2026-09-14", "e": "2026-09-16", "preds": [["B", "FS", 0]]}])
    set_actual("A", "actualStart", "2026-09-10")
    check("SS + 2: the predecessor actually started on 10.09 -> the successor starts 12.09, and C follows", dates("B") == ["2026-09-12", "2026-09-16"] and dates("C")[0] == "2026-09-17", (dates("B"), dates("C")))
    make([A, {"name": "B", "s": "2026-09-12", "e": "2026-09-16", "preds": [["A", "FF", 0]]}])
    set_actual("A", "actualFinish", "2026-09-20")
    check("FF: the successor may not finish before the predecessor actually did (20.09) -> 16.09 to 20.09", dates("B") == ["2026-09-16", "2026-09-20"], dates("B"))
    make([A, {"name": "B", "s": "2026-09-12", "e": "2026-09-16", "preds": [["A", "SF", 0]]}])
    set_actual("A", "actualStart", "2026-09-20")
    check("SF: the successor may not finish before the predecessor actually started (20.09) -> 16.09 to 20.09", dates("B") == ["2026-09-16", "2026-09-20"], dates("B"))
    # several predecessors: the latest wins
    make([A, {"name": "X", "s": "2026-09-07", "e": "2026-09-20"}, {"name": "B", "s": "2026-09-21", "e": "2026-09-23", "preds": [["A", "FS", 0], ["X", "FS", 0]]}])
    set_actual("A", "actualFinish", "2026-09-18")
    check("two predecessors: the later constraint wins (X's planned finish 20.09 beats A's actual 18.09) -> B stays 21.09", dates("B")[0] == "2026-09-21", dates("B"))
    set_actual("A", "actualFinish", "2026-09-25")
    check("...and once A's actual finish is later (25.09) it takes over -> 26.09", dates("B")[0] == "2026-09-26", dates("B"))
    # milestone predecessor
    make([{"name": "M", "s": "2026-09-11", "e": "2026-09-11", "extra": {"milestone": True}}, {"name": "B", "s": "2026-09-12", "e": "2026-09-14", "preds": [["M", "FS", 0]]}])
    set_actual("M", "actualStart", "2026-09-15")
    check("a milestone reached on 15.09 (its actual date) -> its FS successor starts 16.09", dates("B")[0] == "2026-09-16" and pg.evaluate("() => { const m = tasks.find(t => t.name === 'M'); return m.actualFinish === m.actualStart; }"), dates("B"))

    # ================================================================= manual successors, warnings, safety
    make(chain(b_mode="manual")); set_actual("A", "actualFinish", "2026-09-18")
    check("a manually scheduled successor is not moved by the cascade (as always)", dates("B") == ["2026-09-12", "2026-09-16"], dates("B"))
    check("...but it now shows the 'starts before its predecessors allow' warning, computed from the actual date (19.09)", pg.evaluate("() => scheduleMismatch(tasks.find(t => t.name === 'B'))") == "2026-09-19" and pg.locator(".mismatch-warn").count() >= 1, pg.evaluate("() => scheduleMismatch(tasks.find(t => t.name === 'B'))"))
    make([{"name": "P", "s": "2026-09-07", "e": "2026-09-11", "preds": [["Q", "FS", 0]], "extra": {"actualFinish": "2026-09-12"}}, {"name": "Q", "s": "2026-09-13", "e": "2026-09-14", "preds": [["P", "FS", 0]], "extra": {"actualFinish": "2026-09-15"}}])
    set_actual("P", "actualFinish", "2026-09-20")
    check("a circular dependency with actual dates doesn't hang (cyclic tasks are skipped, as before)", pg.evaluate("() => tasks.length") == 2)
    make(chain()); pg.evaluate("() => { tasks.find(t => t.name === 'A').actualFinish = '2026-09-18'; computeCriticalPath(); render(); }")
    check("the critical path and the Gantt still draw with actual dates present", pg.locator(".gantt-bar, .grid-row").count() > 0 and not errors)
    # clearing after a push
    make(chain()); set_actual("A", "actualFinish", "2026-09-18"); set_actual("A", "actualFinish", "")
    check("clearing the actual finish afterwards doesn't pull the successor back (push-later only; nothing is pulled earlier behind your back)", dates("B") == ["2026-09-19", "2026-09-23"], dates("B"))
    check("...and clearing an actual date leaves the schedule where the actuals put it (Start 07.09 filled in, Finish 18.09)", dates("A") == ["2026-09-07", "2026-09-18"], dates("A"))

    # ================================================================= a task that has started/finished is history: it isn't rescheduled
    B_ACT = lambda **kw: pg.evaluate("kw => Object.assign(tasks.find(t => t.name === 'B'), kw)", kw)
    warn = lambda n: pg.locator(f".grid-row[data-id='{tid(n)}'] .mismatch-warn")
    make(chain()); B_ACT(actualStart="2026-09-12"); set_actual("A", "actualFinish", "2026-09-18")
    check("a successor that has ALREADY STARTED is not pushed when its predecessor slips (planned dates stay 12.09-16.09)", dates("B") == ["2026-09-12", "2026-09-16"], dates("B"))
    check("...so its own successor doesn't move either (C stays 17.09-19.09)", dates("C") == ["2026-09-17", "2026-09-19"], dates("C"))
    check("...but a warning triangle says its predecessors don't allow that start, naming 19.09.2026 and that started tasks aren't rescheduled", warn("B").count() == 1 and "19.09.2026" in (warn("B").get_attribute("title") or "") and "not rescheduled" in (warn("B").get_attribute("title") or ""), warn("B").get_attribute("title") if warn("B").count() else "no icon")
    check("...the actual dates are of course untouched, and the not-started task in the chain is still auto-planned (control below)", pg.evaluate("() => tasks.find(t => t.name === 'B').actualStart") == "2026-09-12")
    make(chain()); set_actual("A", "actualFinish", "2026-09-18")
    check("control: WITHOUT actual dates the successor is pushed as before (19.09-23.09) and shows no warning", dates("B") == ["2026-09-19", "2026-09-23"] and warn("B").count() == 0, dates("B"))
    make(chain()); B_ACT(actualStart="2026-09-12", actualFinish="2026-09-15", progress=100); set_actual("A", "actualFinish", "2026-09-18")
    check("a successor that has FINISHED is not pushed either (12.09-16.09), and is flagged", dates("B") == ["2026-09-12", "2026-09-16"] and warn("B").count() == 1, (dates("B"), warn("B").count()))
    make(chain()); B_ACT(actualStart="2026-09-19"); set_actual("A", "actualFinish", "2026-09-18")
    check("a started task that started AFTER its predecessors allow (19.09 >= 19.09) gets no warning", warn("B").count() == 0)
    make(chain()); B_ACT(actualStart="2026-09-12"); set_actual("A", "actualFinish", "2026-09-18"); pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(150)
    check("Gantt: the started, inconsistent task's bar gets the amber mismatch ring", pg.locator(f".gantt-bar.mismatch[data-id='{tid('B')}']").count() == 1)
    pg.evaluate("() => { currentView = 'tasks'; render(); }"); pg.wait_for_timeout(100)
    # switching mode / adding links / editing by hand
    make(chain(b_mode="manual")); B_ACT(actualStart="2026-09-12"); set_actual("A", "actualFinish", "2026-09-18")
    pg.evaluate("n => setTaskMode(tasks.find(t => t.name === n).id, 'auto')", "B")
    check("switching a started task to Auto Scheduled doesn't move its planned dates (a not-started one would jump to 19.09)", dates("B") == ["2026-09-12", "2026-09-16"], dates("B"))
    make([A, {"name": "B", "s": "2026-09-08", "e": "2026-09-10", "extra": {"actualStart": "2026-09-08"}}]); pg.evaluate("() => { const b = tasks.find(t => t.name === 'B'), a = tasks.find(t => t.name === 'A'); b.predecessors = [{id: a.id, type: 'FS', lag: 0}]; applyConstraints(b.id); }")
    check("adding a predecessor link to a started task doesn't move it either", dates("B") == ["2026-09-08", "2026-09-10"], dates("B"))
    make(chain()); B_ACT(actualStart="2026-09-12"); pg.evaluate("() => render()"); cell("B", "start").click(); pg.wait_for_selector(".inline-edit"); wait_focus(); pg.fill(".inline-edit", "2026-09-14"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    check("a user can still edit a started task's planned dates by hand", dates("B")[0] == "2026-09-14", dates("B"))
    make(chain()); B_ACT(actualStart="2026-09-12"); set_actual("A", "actualFinish", "2026-09-18"); B_ACT(actualStart=None); pg.evaluate("() => render()"); pg.wait_for_timeout(100)
    check("clearing the actual dates makes it a normal Auto task again: no warning, and the next push moves it", warn("B").count() == 0)
    set_actual("A", "actualFinish", "2026-09-19")
    check("...(A's finish changed again: B is pushed to 20.09-24.09)", dates("B") == ["2026-09-20", "2026-09-24"], dates("B"))
    # a manual, unstarted task keeps its old warning text
    make(chain(b_mode="manual")); set_actual("A", "actualFinish", "2026-09-18")
    check("the Manual-task warning keeps its own wording", "Manually scheduled" in (warn("B").get_attribute("title") or ""), warn("B").get_attribute("title") if warn("B").count() else "no icon")

    # ================================================================= from the task dialog
    make(chain())
    pg.evaluate("n => openTaskModal(tasks.find(t => t.name === n).id)", "A"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(80)
    pg.fill("#taskActualStartInput", "2026-09-08"); pg.fill("#taskActualFinishInput", "2026-09-18"); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("saving actual dates in the task dialog re-plans the successors too (B 19.09, C 24.09)", dates("B")[0] == "2026-09-19" and dates("C")[0] == "2026-09-24", (dates("B"), dates("C")))

    # ================================================================= Actual Finish completes the task (MS Project)
    prog = lambda n: pg.evaluate("n => tasks.find(t => t.name === n).progress", n)
    astart = lambda n: pg.evaluate("n => tasks.find(t => t.name === n).actualStart", n)
    make(chain()); set_actual("A", "actualFinish", "2026-09-10")
    check("recording an Actual Finish marks the task 100% complete", prog("A") == 100, prog("A"))
    check("...fills an empty Actual Start with the planned start (07.09)", astart("A") == "2026-09-07", astart("A"))
    check("...and says so in a toast", "100% complete" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    make([A]); set_actual("A", "actualFinish", "2026-09-03")
    check("a finish BEFORE the planned start fills the Actual Start with the finish itself (03.09), never a start after the finish", astart("A") == "2026-09-03", astart("A"))
    make([dict(A, extra={"actualStart": "2026-09-08"})]); set_actual("A", "actualFinish", "2026-09-12")
    check("an Actual Start that is already there is kept", astart("A") == "2026-09-08" and prog("A") == 100)
    make([dict(A, extra={"progress": 40})]); set_actual("A", "actualFinish", "2026-09-10")
    check("a task at 40% goes to 100%", prog("A") == 100, prog("A"))
    pg.evaluate("() => { tasks.find(t => t.name === 'A').progress = 60; save(); render(); }"); set_actual("A", "actualFinish", "2026-09-10")
    check("re-entering the SAME Actual Finish doesn't touch % complete again (only a new/changed finish completes)", prog("A") == 60, prog("A"))
    set_actual("A", "actualFinish", "2026-09-11")
    check("a CHANGED Actual Finish completes it again", prog("A") == 100, prog("A"))
    set_actual("A", "actualFinish", "")
    check("clearing the Actual Finish leaves % complete alone", prog("A") == 100)
    make([A]); set_actual("A", "actualStart", "2026-09-08")
    check("recording only an Actual Start doesn't complete a normal task", prog("A") == 0 and pg.evaluate("() => tasks[0].actualFinish") is None)
    make([{"name": "M", "s": "2026-09-11", "e": "2026-09-11", "extra": {"milestone": True}}]); set_actual("M", "actualStart", "2026-09-11")
    check("a milestone's actual date is its actual finish, so recording it completes the milestone", prog("M") == 100 and pg.evaluate("() => tasks[0].actualFinish") == "2026-09-11", prog("M"))
    make([{"name": "G", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-11", "extra": {"parentId": "G"}}])
    pg.evaluate("() => { const g = tasks.find(t => t.name === 'G'), k = tasks.find(t => t.name === 'K'); k.parentId = g.id; save(); render(); }")
    pg.evaluate("() => { const k = tasks.find(t => t.name === 'K'); k.actualFinish = '2026-09-10'; recordActualFinish(k, null); const g = tasks.find(t => t.name === 'G'); g.actualFinish = '2026-09-10'; recordActualFinish(g, null); }")
    check("a summary task is never completed by its own (rolled-up) actual finish", prog("G") == 0 and prog("K") == 100 and astart("G") is None, (prog("G"), prog("K")))
    # the dialog
    make([A])
    pg.evaluate("n => openTaskModal(tasks.find(t => t.name === n).id)", "A"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(80)
    pg.fill("#taskActualFinishInput", "2026-09-10"); pg.dispatch_event("#taskActualFinishInput", "change")
    check("dialog: typing an Actual Finish shows 100% and the filled Actual Start (07.09) right away", pg.input_value("#taskProgressInput") == "100" and pg.input_value("#taskActualStartInput") == "2026-09-07", (pg.input_value("#taskProgressInput"), pg.input_value("#taskActualStartInput")))
    pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("...and saving stores both", prog("A") == 100 and astart("A") == "2026-09-07")
    pg.evaluate("n => openTaskModal(tasks.find(t => t.name === n).id)", "A"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(80)
    pg.fill("#taskProgressInput", "50"); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(150)
    check("dialog: lowering % complete afterwards (same Actual Finish) is respected", prog("A") == 50, prog("A"))
    make([{"name": "M", "s": "2026-09-11", "e": "2026-09-11", "extra": {"milestone": True}}])
    pg.evaluate("n => openTaskModal(tasks.find(t => t.name === n).id)", "M"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(80)
    pg.fill("#taskActualStartInput", "2026-09-11"); pg.dispatch_event("#taskActualStartInput", "change")
    check("dialog: a milestone's actual date completes it live", pg.input_value("#taskProgressInput") == "100", pg.input_value("#taskProgressInput"))
    pg.keyboard.press("Escape"); pg.wait_for_selector("#confirmModalBg.open")   # (edited: Escape asks before throwing the changes away)
    pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(200)

    # ================================================================= the date editors are the ones Start/Finish use
    make([{"name": "Auto1", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Man1", "s": "2026-09-07", "e": "2026-09-11", "mode": "manual"}])
    cell("Auto1", "actualStart").click(); pg.wait_for_selector(".inline-edit")
    check("auto task: Actual Start opens the native date picker input, like its Start", pg.get_attribute(".inline-edit", "type") == "date"); pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    cell("Man1", "actualStart").click(); pg.wait_for_selector(".inline-wrap"); wait_focus()
    check("manual task: a typed box with a calendar button (the Start/Finish editor), asking for dd.mm.yyyy", pg.locator(".inline-wrap .inline-cal").count() == 1 and pg.get_attribute(".inline-wrap input[type=text]", "placeholder") == "dd.mm.yyyy", pg.get_attribute(".inline-wrap input[type=text]", "placeholder"))
    pg.fill(".inline-wrap input[type=text]", "18.09.2026"); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("...typing 18.09.2026 is understood (stored as 2026-09-18, shown dd.mm.yyyy)", pg.evaluate("() => tasks.find(t => t.name === 'Man1').actualStart") == "2026-09-18" and cell("Man1", "actualStart").inner_text().strip() == "18.09.2026")
    cell("Man1", "actualFinish").click(); wait_focus(); pg.fill(".inline-wrap input[type=text]", "2026-09-25"); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("...and so is an ISO date", pg.evaluate("() => tasks.find(t => t.name === 'Man1').actualFinish") == "2026-09-25")
    cell("Man1", "actualFinish").click(); wait_focus(); pg.fill(".inline-wrap input[type=text]", "soon"); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("free text is NOT accepted for an actual date (unlike Start/Finish, an actual date has really happened): toast, nothing changes", pg.evaluate("() => tasks.find(t => t.name === 'Man1').actualFinish") == "2026-09-25" and "isn't a date" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    cell("Man1", "actualFinish").click(); wait_focus(); pg.fill(".inline-wrap input[type=text]", "01.09.2026"); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("an Actual Finish before the Actual Start is refused in the typed editor too", pg.evaluate("() => tasks.find(t => t.name === 'Man1').actualFinish") == "2026-09-25" and "before" in pg.inner_text("#toastMsg"))
    cell("Man1", "actualFinish").click(); wait_focus(); pg.fill(".inline-wrap input[type=text]", ""); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("a blank clears it", pg.evaluate("() => tasks.find(t => t.name === 'Man1').actualFinish") is None)
    # custom date fields: same editors
    cell("Auto1", "date1").click(); pg.wait_for_selector(".inline-edit")
    check("a custom Date field on an auto task uses the native date input", pg.get_attribute(".inline-edit", "type") == "date"); pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    cell("Man1", "date1").click(); pg.wait_for_selector(".inline-wrap"); wait_focus(); pg.fill(".inline-wrap input[type=text]", "24.12.2026"); pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
    check("...and on a manual task the typed box + calendar (24.12.2026 -> 2026-12-24)", pg.evaluate("() => tasks.find(t => t.name === 'Man1').custom.date1") == "2026-12-24" and cell("Man1", "date1").inner_text().strip() == "24.12.2026")
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
