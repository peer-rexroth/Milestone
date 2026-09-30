# -*- coding: utf-8 -*-
"""The Task Form — MS Project's Task Form (View -> Details there): a pane under the task list / chart, switched on and
off from the toolbar, editing the selected task (Name, Duration, Effort driven, Manually Scheduled, Start, Finish, Task
Type, % Complete, Resources with Units/Work, Predecessors with Type/Lag) as a draft applied by OK (one Undo step) or
thrown away by Cancel. See "Task Form" in CLAUDE.md."""
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
    SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; delete project.resources;
      const mk = (id, name, s, e, extra) => Object.assign({ id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
      tasks.push(mk('a', 'Design', '2026-09-07', '2026-09-11', { resource: 'Anna[50%], Ben' }),
                 mk('b', 'Build', '2026-09-15', '2026-09-28', { resource: 'Ben', predecessors: [{ id: 'a', type: 'FS', lag: 1 }] }),
                 mk('c', 'Launch', '2026-09-29', '2026-09-29', { milestone: true, predecessors: [{ id: 'b', type: 'FS', lag: 0 }] }),
                 mk('g', 'Phase', '2026-09-07', '2026-09-08'), mk('k', 'Kid', '2026-09-07', '2026-09-08', { parentId: 'g' }));
      normalizeData(); save(); setSelection([]); render(); resetHistory(); }"""
    seed = lambda: ev(SEED)
    pane_open = lambda: pg.locator("#taskFormPane:not(.hidden)").count() == 1
    task = lambda i: ev("i => { const t = byId(i); return { res: t.resource, s: t.startDate, e: t.endDate, pct: t.progress, name: t.name, mode: t.taskMode, preds: t.predecessors, tt: t.taskType || null, ed: t.effortDriven || null }; }", i)
    def select(i): ev("i => { setSelection([i]); render(); }", i); pg.wait_for_timeout(80)

    # ---------------------------------------------------------------- toggle, placement, persistence
    seed()
    check("off by default: the pane is hidden, the toolbar button is there and not pressed", not pane_open() and pg.get_attribute("#taskFormBtn", "aria-pressed") == "false")
    pg.click("#taskFormBtn"); pg.wait_for_timeout(100)
    check("the toolbar button switches it on (pressed state shown)", pane_open() and pg.get_attribute("#taskFormBtn", "aria-pressed") == "true")
    box_main, box_pane = pg.locator("#main").bounding_box(), pg.locator("#taskFormPane").bounding_box()
    check("it sits below the list, full width (a bottom split pane)", box_pane["y"] >= box_main["y"] + box_main["height"] - 1 and abs(box_pane["width"] - 1440) <= 2, (box_main, box_pane))
    check("with nothing selected it says to select a task", "Select a task" in pg.inner_text("#taskFormBody"))
    pg.reload(); pg.wait_for_selector("#undoBtn")
    check("the on/off choice is remembered on this device (a display preference)", pane_open())
    ev("() => { historyCoalesceMs = 0; }")
    ev("() => setView('resources')"); pg.wait_for_timeout(80)
    check("hidden in the Resources view, and its button with it", not pane_open() and ev("() => document.getElementById('taskFormBtn').classList.contains('hidden')"))
    ev("() => setView('gantt')"); pg.wait_for_timeout(80)
    check("shown in the Gantt view as well", pane_open())
    ev("() => setView('tasks')")

    # ---------------------------------------------------------------- what it shows
    ev("() => { setSelection(['b']); render(); }"); pg.wait_for_timeout(80)
    lines = ev("""() => { const row = document.querySelector('#tfResRows .tf-row'), head = document.querySelector('.tf-res .tf-row-head');
      const edges = el => [...el.children].slice(0, -1).map(c => Math.round(c.getBoundingClientRect().right));
      const colored = [...row.children].slice(0, -1).every(c => getComputedStyle(c).borderRightColor !== 'rgba(0, 0, 0, 0)');
      return { same: JSON.stringify(edges(row)) === JSON.stringify(edges(head)), colored }; }""")
    check("the tables are real lists: a data row's column lines sit exactly under the header's, and every cell (editable ones too) draws its line", lines == {"same": True, "colored": True}, lines)
    seed(); select("b")
    check("it shows the selected task: header, name, duration, start, finish, % complete, type",
          "#2 Build" in pg.inner_text("#tfTaskLabel") and pg.input_value("#tfName") == "Build" and pg.input_value("#tfDur") == "10 days"
          and ev("() => document.getElementById('tfStart').value") == "2026-09-15" and ev("() => document.getElementById('tfFinish').value") == "2026-09-28"
          and pg.input_value("#tfPct") == "0%" and pg.input_value("#tfType") == "fixedUnits", pg.inner_text("#tfTaskLabel"))
    check("Effort driven unticked (the default), Manually Scheduled unticked (an Auto task)", not pg.is_checked("#tfEffort") and not pg.is_checked("#tfManual"))
    res_rows = pg.locator("#tfResRows .tf-row:not(.tf-row-head)")
    check("the Resources table lists its assignment with Units and Work, plus a blank row to add one",
          res_rows.count() == 2 and res_rows.nth(0).locator("input[aria-label='Resource name']").input_value() == "Ben" and res_rows.nth(0).locator("input[aria-label='Units']").input_value() == "100%" and res_rows.nth(0).locator(".tf-work").inner_text() == "10 days")
    pred_rows = pg.locator("#tfPredRows .tf-row:not(.tf-row-head)")
    check("the Predecessors table lists its link: ID 1, Design, FS, +1 — plus a blank row",
          pred_rows.count() == 2 and pred_rows.nth(0).locator("input[aria-label='Predecessor task number']").input_value() == "1" and pred_rows.nth(0).locator(".tf-pred-name").inner_text() == "Design"
          and pred_rows.nth(0).locator("select").input_value() == "FS" and pred_rows.nth(0).locator("input[aria-label='Lead or lag']").input_value() == "+1")
    check("OK and Cancel are disabled while nothing has changed", not pg.is_enabled("#tfOkBtn") and not pg.is_enabled("#tfCancelBtn"))
    select("a")
    check("selecting another task shows that one (nothing pending)", pg.input_value("#tfName") == "Design" and pg.locator("#tfResRows .tf-row:not(.tf-row-head)").nth(0).locator("input[aria-label='Units']").input_value() == "50%")

    # ---------------------------------------------------------------- edit several fields, OK = one Undo step
    select("b")
    pg.fill("#tfName", "Build it")
    pg.fill("#tfDur", "5")
    pg.fill("#tfPct", "40")
    pg.select_option("#tfType", "fixedDuration")
    pg.locator("#tfResRows .tf-row:not(.tf-row-head)").nth(1).locator("input[aria-label='Resource name']").fill("Carl")
    pg.locator("#tfResRows .tf-row:not(.tf-row-head)").nth(1).locator("input[aria-label='Units']").fill("50")
    check("editing shows 'not applied yet' and enables OK / Cancel", "Not applied" in pg.inner_text("#tfNote") and pg.is_enabled("#tfOkBtn"))
    check("nothing is written to the plan before OK", task("b")["name"] == "Build" and task("b")["res"] == "Ben")
    pg.click("#tfOkBtn"); pg.wait_for_timeout(200)
    tb = task("b")
    check("OK applies it all: name, a 5-day duration (Finish moves, Start stays), %, Task Type, the new resource at 50% (MS Project's Name[NN%])",
          tb["name"] == "Build it" and tb["s"] == "2026-09-15" and tb["e"] == "2026-09-21" and tb["pct"] == 40 and tb["tt"] == "fixedDuration" and tb["res"] == "Ben, Carl[50%]", tb)
    check("...and the cascade ran: Launch (FS after Build) moved up to the day after", task("c")["s"] == "2026-09-22", task("c"))
    check("...the form refreshes from the saved task (nothing pending, Carl's Work now filled in)",
          "Not applied" not in pg.inner_text("#tfNote") and pg.locator("#tfResRows .tf-row:not(.tf-row-head)").nth(1).locator(".tf-work").inner_text() not in ("", "—"))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(200)
    check("one Ctrl+Z takes the whole OK back (Build and Launch)", task("b")["name"] == "Build" and task("b")["e"] == "2026-09-28" and task("b")["res"] == "Ben" and task("c")["s"] == "2026-09-29", (task("b"), task("c")))
    check("...and the form shows the restored task", pg.input_value("#tfName") == "Build")

    # ---------------------------------------------------------------- Start moves keep the duration; a typed Finish is a pin like in the dialog
    ev("() => { document.getElementById('tfStart').value = '2026-09-17'; }"); pg.dispatch_event("#tfStart", "input")
    pg.click("#tfOkBtn"); pg.wait_for_timeout(200)
    tb = task("b")
    check("a later Start keeps the 10-day duration and becomes Start No Earlier Than (a delay past its links), like a typed Start anywhere",
          tb["s"] == "2026-09-17" and tb["e"] == "2026-09-30" and ev("() => byId('b').constraintType") == "SNET", (tb, ev("() => byId('b').constraintType")))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)

    # ---------------------------------------------------------------- Cancel, Escape, Enter
    select("b")
    pg.fill("#tfName", "Nope")
    pg.click("#tfCancelBtn"); pg.wait_for_timeout(100)
    check("Cancel throws the changes away and shows the task as saved", pg.input_value("#tfName") == "Build" and task("b")["name"] == "Build" and not pg.is_enabled("#tfOkBtn"))
    pg.fill("#tfName", "Nope again"); pg.press("#tfName", "Escape"); pg.wait_for_timeout(100)
    check("Escape in the form cancels too — and does not clear the task selection", pg.input_value("#tfName") == "Build" and ev("() => selectedTaskId") == "b")
    pg.fill("#tfName", "Build (Enter)"); pg.press("#tfName", "Enter"); pg.wait_for_timeout(200)
    check("Enter in a field applies (like OK)", task("b")["name"] == "Build (Enter)")
    pg.focus("#tfManual"); pg.keyboard.press("Delete"); pg.wait_for_timeout(100)
    check("the list's Delete shortcut does nothing while focus is in the form", ev("() => !!byId('b')"))

    # ---------------------------------------------------------------- pending edits stay on their task
    select("b"); pg.fill("#tfName", "Pending")
    select("a")
    check("with unapplied changes, selecting another row keeps the form on its task (and says so)",
          pg.input_value("#tfName") == "Pending" and "#2" in pg.inner_text("#tfTaskLabel") and "stays on this task" in pg.inner_text("#tfNote"), pg.inner_text("#tfNote"))
    pg.click("#tfCancelBtn"); pg.wait_for_timeout(100)
    check("...after Cancel it follows the selection again", pg.input_value("#tfName") == "Design")

    # ---------------------------------------------------------------- Previous / Next
    select("a")
    pg.click("#tfNextBtn"); pg.wait_for_timeout(150)
    check("Next moves to the next task in the list and selects it", pg.input_value("#tfName") == "Build (Enter)" and ev("() => selectedTaskId") == "b")
    pg.fill("#tfPct", "25")
    pg.click("#tfNextBtn"); pg.wait_for_timeout(200)
    check("Next with changes applies them first, then moves on", task("b")["pct"] == 25 and pg.input_value("#tfName") == "Launch")
    pg.click("#tfPrevBtn"); pg.wait_for_timeout(150)
    check("Previous goes back", pg.input_value("#tfName") == "Build (Enter)")
    select("a")
    check("Previous is disabled on the first task", not pg.is_enabled("#tfPrevBtn"))

    # ---------------------------------------------------------------- predecessors: add, change, remove, refuse
    select("c")
    prow = lambda i: pg.locator("#tfPredRows .tf-row:not(.tf-row-head)").nth(i)
    prow(1).locator("input[aria-label='Predecessor task number']").fill("1")
    check("typing an ID shows that task's name right away", prow(1).locator(".tf-pred-name").inner_text() == "Design")
    prow(1).locator("select").select_option("SS"); prow(1).locator("input[aria-label='Lead or lag']").fill("-2")
    pg.click("#tfOkBtn"); pg.wait_for_timeout(200)
    check("a new predecessor is added with its type and a lead", [(x["id"], x["type"], x["lag"]) for x in task("c")["preds"]] == [("b", "FS", 0), ("a", "SS", -2)], task("c")["preds"])
    prow(0).locator(".tf-remove").click(); pg.click("#tfOkBtn"); pg.wait_for_timeout(200)
    check("✕ removes one", [x["id"] for x in task("c")["preds"]] == ["a"], task("c")["preds"])
    for num, msg in [("99", "No task #99"), ("3", "itself"), ("4", "summary task")]:
        prow(1).locator("input[aria-label='Predecessor task number']").fill(num)
        pg.click("#tfOkBtn"); pg.wait_for_timeout(120)
        check(f"a predecessor #{num} is refused ('{msg}') and nothing changes", msg in pg.inner_text("#toastMsg") and [x["id"] for x in task("c")["preds"]] == ["a"], pg.inner_text("#toastMsg"))
    pg.click("#tfCancelBtn")

    # ---------------------------------------------------------------- resources: validation, remove
    select("a")
    rrow = lambda i: pg.locator("#tfResRows .tf-row:not(.tf-row-head)").nth(i)
    rrow(0).locator("input[aria-label='Units']").fill("900")
    pg.click("#tfOkBtn"); pg.wait_for_timeout(120)
    check("Units outside 1–800% are refused", "1%–800%" in pg.inner_text("#toastMsg") and task("a")["res"] == "Anna[50%], Ben")
    rrow(0).locator("input[aria-label='Units']").fill("50%"); rrow(1).locator("input[aria-label='Resource name']").fill("anna")
    pg.click("#tfOkBtn"); pg.wait_for_timeout(120)
    check("the same resource twice is refused", "listed twice" in pg.inner_text("#toastMsg") and task("a")["res"] == "Anna[50%], Ben")
    pg.click("#tfCancelBtn"); pg.wait_for_timeout(80)
    rrow(1).locator(".tf-remove").click(); pg.click("#tfOkBtn"); pg.wait_for_timeout(150)
    check("✕ removes a resource from the task", task("a")["res"] == "Anna[50%]", task("a"))
    pg.fill("#tfPct", "150"); pg.click("#tfOkBtn"); pg.wait_for_timeout(120)
    check("% Complete outside 0–100 is refused", "0–100" in pg.inner_text("#toastMsg") and task("a")["pct"] == 0)
    pg.click("#tfCancelBtn")

    # ---------------------------------------------------------------- adding a row the way a person does: click, type, click the next box, type
    select("b")
    rrow(1).locator("input[aria-label='Resource name']").click(); pg.keyboard.type("Dana")
    rrow(1).locator("input[aria-label='Units']").click(); pg.keyboard.type("25")
    check("clicking from the new row's name into its Units keeps both (the next blank row is added below, nothing is rebuilt under the cursor)",
          rrow(1).locator("input[aria-label='Resource name']").input_value() == "Dana" and rrow(1).locator("input[aria-label='Units']").input_value() == "25" and pg.locator("#tfResRows .tf-row:not(.tf-row-head)").count() == 3)
    pg.click("#tfOkBtn"); pg.wait_for_timeout(150)
    check("...and OK saves it as Dana[25%]", "Dana[25%]" in task("b")["res"], task("b"))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)

    # ---------------------------------------------------------------- effort driven through the form
    ev("() => { byId('a').resource = 'Anna'; byId('a').work = null; normalizeData(); save(); render(); }")
    select("a"); pg.wait_for_timeout(80)
    pg.check("#tfEffort"); rrow(1).locator("input[aria-label='Resource name']").fill("Ben")
    pg.click("#tfOkBtn"); pg.wait_for_timeout(200)
    check("Effort driven ticked + a second person: Fixed Units finishes faster (5 days -> 3)", ev("() => durationDays(byId('a').startDate, byId('a').endDate)") == 3 and task("a")["ed"] is True, ev("() => [byId('a').startDate, byId('a').endDate]"))

    # ---------------------------------------------------------------- manual mode, milestone, group, empty line
    select("b"); pg.check("#tfManual"); pg.click("#tfOkBtn"); pg.wait_for_timeout(150)
    check("Manually Scheduled switches the task to Manual", task("b")["mode"] == "manual")
    pg.uncheck("#tfManual"); pg.click("#tfOkBtn"); pg.wait_for_timeout(150)
    check("...and back to Auto", task("b")["mode"] == "auto")
    select("c")
    check("a milestone: Duration and Finish read-only, Task Type and Effort driven off", pg.is_disabled("#tfDur") and pg.is_disabled("#tfFinish") and pg.is_disabled("#tfType") and pg.is_disabled("#tfEffort"))
    select("g")
    check("a group: dates and % read-only (rolled up), no Resources/Predecessors tables, a note saying why",
          pg.is_disabled("#tfStart") and pg.is_disabled("#tfPct") and pg.locator("#tfResRows").count() == 0 and "rolls up" in pg.inner_text("#taskFormBody"))
    pg.fill("#tfName", "Phase 1"); pg.click("#tfOkBtn"); pg.wait_for_timeout(150)
    check("...its name can still be changed", task("g")["name"] == "Phase 1")
    ev("() => { tasks.push({ id: 'sp', name: '', spacer: true, parentId: null, order: 99, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', resource: '', actualStart: null, actualFinish: null }); normalizeData(); save(); }")
    select("sp")
    check("an empty line has nothing to edit", "nothing to edit" in pg.inner_text("#taskFormBody"))

    GEOM = """() => { const r = s => document.querySelector(s).getBoundingClientRect();
      return { okR: Math.round(r('#tfOkBtn').right), predR: Math.round(r('.tf-pred').right), resL: Math.round(r('.tf-res').left), nameL: Math.round(r('label[for=tfName]').left),
               resW: Math.round(r('.tf-res').width), predW: Math.round(r('.tf-pred').width), durW: r('#tfDur').width, nameW: r('#tfName').width }; }"""
    def geom_ok(g): return abs(g["okR"] - g["predR"]) <= 1 and abs(g["resL"] - g["nameL"]) <= 1 and abs(g["resW"] - g["predW"]) <= 1 and g["durW"] < g["nameW"] * 0.6
    seed(); select("b"); g = ev(GEOM)
    check("day plan: both tables the same width, the right one ending exactly where the OK button does, the left one under 'Name:'; Duration short, Name wide", geom_ok(g), g)
    # ---------------------------------------------------------------- Hours & minutes plan: times
    seed(); ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); render(); }"); select("a")
    g = ev(GEOM)
    check("Hours & minutes plan: the same alignment holds with the wider date + time columns", geom_ok(g), g)
    check("in an Hours & minutes plan Start and Finish get a time box and Duration reads in working time",
          pg.locator("#tfStartTime").count() == 1 and ev("() => document.getElementById('tfStartTime').value") == "08:00" and pg.input_value("#tfDur") == "5 days", pg.input_value("#tfDur"))
    pg.fill("#tfDur", "4h"); pg.click("#tfOkBtn"); pg.wait_for_timeout(200)
    check("...a typed '4h' makes it a 4-hour task (08:00-12:00, finishing as the lunch break starts)", ev("() => [byId('a').startDate, taskMoment(byId('a'), 'start') % 1440, byId('a').endDate, byId('a').endTime]") == ["2026-09-07", 480, "2026-09-07", "12:00"], ev("() => [byId('a').startDate, byId('a').startTime, byId('a').endDate, byId('a').endTime]"))
    layout = ev("""() => { const items = [...document.querySelectorAll('.tf-top > *, .tf-top .tf-pair > *, .tf-top .tf-dt > *, .tf-top .tf-btns > *')].map(e => e.getBoundingClientRect());
      const right = document.getElementById('taskFormBody').getBoundingClientRect().right, bad = [];
      for (const a of items) for (const c of items) if (a !== c && Math.abs(a.top - c.top) < 8 && c.left > a.left && c.left < a.right - 1 && !(c.right <= a.right)) bad.push([a.left, c.left]);
      return { overlaps: bad.length, past: items.filter(r => r.right > right + 1).length }; }""")
    check("Hours & minutes: the date + time boxes don't run into the next label, and nothing is cut off at the right (1440px)", layout == {"overlaps": 0, "past": 0}, layout)
    pg.set_viewport_size({"width": 1100, "height": 900}); pg.wait_for_timeout(150)
    layout = ev("""() => { const items = [...document.querySelectorAll('.tf-top > *, .tf-top .tf-pair > *, .tf-top .tf-dt > *, .tf-top .tf-btns > *')].map(e => e.getBoundingClientRect());
      const right = document.getElementById('taskFormBody').getBoundingClientRect().right, bad = [];
      for (const a of items) for (const c of items) if (a !== c && Math.abs(a.top - c.top) < 8 && c.left > a.left && c.left < a.right - 1 && !(c.right <= a.right)) bad.push([a.left, c.left]);
      return { overlaps: bad.length, past: items.filter(r => r.right > right + 1).length }; }""")
    check("...nor at a 1100px window", layout == {"overlaps": 0, "past": 0}, layout)
    pg.set_viewport_size({"width": 1440, "height": 900}); pg.wait_for_timeout(150)
    ev("() => { delete project.timeUnit; normalizeData(); save(); render(); }")

    # ---------------------------------------------------------------- resizing, switching off
    before_h = pg.locator("#taskFormPane").bounding_box()["height"]
    hb = pg.locator("#taskFormResize").bounding_box()
    pg.mouse.move(hb["x"] + 200, hb["y"] + 4); pg.mouse.down(); pg.mouse.move(hb["x"] + 200, hb["y"] - 100); pg.mouse.up(); pg.wait_for_timeout(100)
    after_h = pg.locator("#taskFormPane").bounding_box()["height"]
    check("dragging its top edge makes the pane taller, and the height is remembered", after_h > before_h + 80 and ev("() => JSON.parse(localStorage.getItem('milestone-prefs')).taskFormHeight") >= after_h - 2, (before_h, after_h))
    select("a"); pg.fill("#tfName", "unsaved")
    pg.click("#taskFormBtn"); pg.wait_for_timeout(100)
    check("switching it off with unapplied changes asks first", ev("() => document.getElementById('confirmModalBg').classList.contains('open')"))
    pg.click("#confirmModalBg .btn-primary"); pg.wait_for_timeout(100)
    check("...discarding closes it and changes nothing", not pane_open() and task("a")["name"] == "Design")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
