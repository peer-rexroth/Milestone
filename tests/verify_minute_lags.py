# -*- coding: utf-8 -*-
"""Minute-mode scheduling precision: LAGS and IMPORT. A minute-mode plan counts a predecessor's lag/lead in working MINUTES
(project.lagUnit === 'minute'); every way of entering one used to take and store DAYS while the engine read minutes ("+2d" was
2 minutes). Now: a plan without the marker (one just switched in from day mode, or saved before this) is converted once
(days x the working day); the Predecessors cell, the task dialog and the Edit-tasks dialog take "2h", "-30m", "1d", "1w" (a bare
number is hours) and write them back with a unit; switching back to days converts (rounded). Paste and CSV import into a minute-
mode plan read the time of day of a date cell, a duration in working minutes and minute lags; copying rows to Excel keeps the times,
minute durations and lags (and a paste of that text restores them); a copy between plans of the two modes converts the lags; MS
Project XML export/import carries exact minute lags. A day-mode plan is unchanged in all of it."""
import os, re
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)
    f = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.startTime, t.endDate, t.endTime]; }", n)
    lag = lambda n, k=0: ev("([n, k]) => tasks.find(t => t.name === n).predecessors[k].lag", [n, k])
    toast = lambda: ev("() => document.getElementById('toastMsg').textContent")
    def plan(specs, minute=True):
        ev("m => { if (m) { project.timeUnit = 'minute'; normalizeData(); } else { delete project.timeUnit; delete project.workHours; delete project.lagUnit; } }", minute)
        ev(SEED, specs)
        ev("() => { normalizeData(); save(); render(); }")
    AB = [{"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "10:00"}},
          {"name": "B", "s": "2026-09-07", "e": "2026-09-07", "preds": [["A", "FS", 0]], "extra": {"startTime": "10:00", "endTime": "11:00"}}]
    def edit(name, col, text):
        idx = ev("c => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col).indexOf(c)", col)
        pg.locator(f".grid-row[data-id='{tid(name)}']").locator(":scope > div").nth(idx + 1).click(); pg.wait_for_selector(".inline-edit"); pg.fill(".inline-edit", text); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)

    # ---------------------------------------------------------------- conversion: a minute-mode plan without the marker holds DAYS
    plan(AB, minute=False)
    ev("() => { tasks.find(t => t.name === 'B').predecessors[0].lag = 2; save(); }")
    ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); render(); }")
    check("switching a plan into minute mode converts its lags from working days to minutes (2 days = 960 min) and stamps lagUnit", lag("B") == 960 and ev("() => project.lagUnit") == "minute", (lag("B"), ev("() => project.lagUnit")))
    ev("() => { normalizeData(); normalizeData(); }")
    check("...once: normalising again changes nothing", lag("B") == 960)
    ev("() => { delete project.lagUnit; tasks.find(t => t.name === 'B').predecessors[0].lag = 3; normalizeData(); }")
    check("a minute-mode plan saved before lags were minutes (no marker, lag 3) is read as 3 days = 1440 min", lag("B") == 1440, lag("B"))
    ev("() => { project.lagUnit = 'minute'; tasks.find(t => t.name === 'B').predecessors[0].lag = 90; normalizeData(); }")
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open"); pg.click("#precisionDay"); pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("a lag that won't round evenly (90 min) warns before switching to days", pg.locator("#confirmModalBg.open").count() == 1 and "round to whole working days" in pg.inner_text("#confirmModalBody"), pg.inner_text("#confirmModalBody") if pg.locator("#confirmModalBg.open").count() else None)
    pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(200)
    check("switching back to days converts minutes to days, rounded (90 min of an 8h day = 0), and drops the marker", lag("B") == 0 and ev("() => project.lagUnit") is None, (lag("B"), ev("() => project.lagUnit")))
    ev("() => { tasks.find(t => t.name === 'B').predecessors[0].lag = 2; save(); }")
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open"); pg.click("#precisionMinute"); pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("...and days -> minutes -> days round-trips whole-day lags (2 -> 960 -> 2)", lag("B") == 960)
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open"); pg.click("#precisionDay"); pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("(the day-mode lag is back to 2)", lag("B") == 2, lag("B"))

    # ---------------------------------------------------------------- the Predecessors cell
    plan(AB)
    def pred(text): edit("B", "preds", text); return lag("B")
    check("'1FS+2h' is 120 minutes", pred("1FS+2h") == 120)
    check("'+30m' is 30 minutes (minutes are a lag unit here)", pred("1FS+30m") == 30)
    check("'+1d' is one working day = 480", pred("1FS+1d") == 480)
    check("'+1w' is five working days = 2400", pred("1FS+1w") == 2400)
    check("a bare '+2' is hours, like Duration (120)", pred("1FS+2") == 120)
    check("a lead: '-1h' is -60", pred("1SS-1h") == -60 and ev("() => tasks.find(t => t.name === 'B').predecessors[0].type") == "SS")
    edit("B", "preds", "1FS+2ed")
    check("an elapsed lag ('2ed') is 2 real calendar days = 2880 minutes, not 2 working days' worth", lag("B") == 2880 and ev("() => tasks.find(t => t.name === 'B').predecessors[0].elapsed") == True, lag("B"))
    pred("1FS+2h")   # back to a plain working lag before the cap check below
    edit("B", "preds", "1FS+99999d")
    check("...and one over the cap is refused, unchanged", lag("B") == 120)
    pred("1FS+90m")
    lbl = lambda: ev("() => predecessorLabel(tasks.find(t => t.name === 'B'))")
    check("the cell writes a lag back with its unit: 90 min = '1FS+90m'", lbl() == "1FS+90m", lbl())
    check("...whole hours as hours ('+2h'), whole days as days ('+1d'), a lead with a minus", [ev("l => { tasks.find(t => t.name === 'B').predecessors[0].lag = l; return predecessorLabel(tasks.find(t => t.name === 'B')); }", l) for l in (120, 480, -30, 960)] == ["1FS+2h", "1FS+1d", "1FS-30m", "1FS+2d"])
    ev("() => { tasks.find(t => t.name === 'B').predecessors[0].lag = 60; save(); render(); }")
    check("what the label says reads back the same (a round trip through the cell)", ev("() => { const t = tasks.find(x => x.name === 'B'); const r = parsePredecessorString(predecessorLabel(t), t.id); return r && r[0].lag; }") == 60)

    # ---------------------------------------------------------------- scheduling with a minute lag
    plan(AB)
    ev("() => { const b = tasks.find(t => t.name === 'B'); b.predecessors[0].lag = 60; applyConstraints(b.id); save(); render(); }")
    check("FS +1h: B starts an hour after A finishes (10:00 -> 11:00)", f("B")[1] == "11:00", f("B"))
    ev("() => { const b = tasks.find(t => t.name === 'B'); b.predecessors[0].lag = 960; applyConstraints(b.id); save(); render(); }")
    check("FS +2 days (960 min): B starts two working days after A's finish", f("B")[0] == "2026-09-09" and f("B")[1] == "10:00", f("B"))
    ev("() => { const b = tasks.find(t => t.name === 'B'); b.predecessors[0].lag = -30; applyConstraints(b.id); save(); render(); }")
    check("a 30-minute lead: B starts 09:30, before A has finished", f("B")[:2] == ["2026-09-07", "09:30"], f("B"))

    # ---------------------------------------------------------------- the task dialog
    plan(AB)
    ev("() => { tasks.find(t => t.name === 'B').predecessors[0].lag = 90; save(); render(); }")
    pg.click(f".grid-row[data-id='{tid('B')}'] .icon-btn[title=Edit]"); pg.wait_for_selector("#taskModalBg.open")
    li = pg.locator("#predecessorRows .pred-lag-input")
    check("the dialog's lag box is a text box showing the lag with its unit ('+90m')", li.count() == 1 and li.input_value() == "+90m", li.input_value() if li.count() else None)
    li.fill("2h"); li.dispatch_event("change")
    check("typing '2h' shows '+2h'", li.input_value() == "+2h")
    li.fill("nonsense"); li.dispatch_event("change")
    check("nonsense is refused with a message and the box restores", li.input_value() == "+2h" and "Can't read" in toast(), (li.input_value(), toast()))
    pg.click("#taskModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("saved: 120 minutes", lag("B") == 120, lag("B"))
    plan(AB, minute=False)
    ev("() => { tasks.find(t => t.name === 'B').predecessors[0].lag = 3; save(); render(); }")
    pg.click(f".grid-row[data-id='{tid('B')}'] .icon-btn[title=Edit]"); pg.wait_for_selector("#taskModalBg.open")
    check("a day-mode plan keeps the number box (days)", pg.locator("#predecessorRows input[type=number][placeholder='Lead/Lag']").count() == 1 and pg.locator("#predecessorRows .pred-lag-input").count() == 0)
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- the Edit-tasks (bulk) dialog
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-08"}])
    ev("() => { setSelection([tasks.find(t => t.name === 'B').id]); openBulkModal(); }"); pg.wait_for_timeout(200)
    check("the bulk dialog's lag box takes a unit in a minute-mode plan", pg.get_attribute("#bulkVal-predLag", "type") == "text")
    pg.check("#bulkOn-pred"); pg.fill("#bulkVal-predId", "1"); pg.fill("#bulkVal-predLag", "-30m")
    ev("() => applyBulkEdit()") if ev("() => typeof applyBulkEdit") == "function" else pg.click("#bulkModalBg .modal-footer button.btn-primary")
    pg.wait_for_timeout(200)
    check("...and stores minutes (-30)", ev("() => tasks.find(t => t.name === 'B').predecessors.map(p => p.lag)") == [-30], ev("() => tasks.find(t => t.name === 'B').predecessors"))
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-08"}], minute=False)
    ev("() => { setSelection([tasks.find(t => t.name === 'B').id]); openBulkModal(); }"); pg.wait_for_timeout(200)
    check("a day-mode plan's bulk lag box is still a number box", pg.get_attribute("#bulkVal-predLag", "type") == "number")
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- paste rows / CSV into a minute-mode plan
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}])
    table = "ID\tTask Name\tStart\tFinish\tDuration\tPredecessors\n1\tA\t07.09.2026 09:00\t07.09.2026 11:30\t\t\n2\tB\t07.09.2026 13:00\t\t2 hrs\t1FS+30m\n3\tC\t07.09.2026\t\t1 day\t\n4\tD\t08.09.2026 2:30 PM\t08.09.2026 4:15 PM\t\t\n5\tE\t\t09.09.2026 12:00\t90 min\t\n6\tF\t10.09.2026 10:00\t\t0 min\t"
    n = ev("t => pasteTableText(t)", table)
    check("a pasted table becomes 6 tasks", n == 6, n)
    check("a date-time in Start/Finish keeps its time (A 09:00–11:30)", f("A") == ["2026-09-07", "09:00", "2026-09-07", "11:30"], f("A"))
    check("Start + a duration in hours: B 13:00 + 2 hrs = 15:00", f("B") == ["2026-09-07", "13:00", "2026-09-07", "15:00"], f("B"))
    check("...with the lag '+30m' read in minutes (30, not 30 days)", lag("B") == 30, lag("B"))
    check("a date alone with '1 day': C spans a working day (08:00 -> 17:00)", f("C")[0] == "2026-09-07" and f("C")[2] == "2026-09-07" and f("C")[3] in ("17:00", None), f("C"))
    check("AM/PM times: '2:30 PM' – '4:15 PM' = 14:30 – 16:15", f("D") == ["2026-09-08", "14:30", "2026-09-08", "16:15"], f("D"))
    check("Finish + a duration: E ends 12:00 and lasts 90 min, so it starts 10:30", f("E")[2:] == ["2026-09-09", "12:00"] and f("E")[1] == "10:30", f("E"))
    check("a '0 min' duration is a milestone at its own time", ev("() => { const t = tasks.find(x => x.name === 'F'); return [t.milestone, t.startTime, t.endTime]; }") == [True, "10:00", "10:00"], f("F"))

    # a day-mode plan reads the very same table exactly as before: dates only
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}], minute=False)
    ev("t => pasteTableText(t)", table)
    dm = ev("() => { const t = tasks.find(x => x.name === 'A'), b = tasks.find(x => x.name === 'B'); return [t.startDate, t.startTime, t.endDate, t.endTime, b.predecessors[0].lag, b.startTime]; }")
    check("in a day-mode plan the same table drops the times (as before) and reads '+30m' as under a day (0), not 30 days", dm == ["2026-09-07", None, "2026-09-07", None, 0, None], dm)

    # ---------------------------------------------------------------- copy rows out (Excel / text) and back in
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "11:30"}},
          {"name": "B", "s": "2026-09-07", "e": "2026-09-07", "preds": [["A", "FS", 90]], "extra": {"startTime": "13:00", "endTime": "15:00"}}])
    ev("() => { setSelection(tasks.map(t => t.id)); }")
    tsv = ev("() => buildClip().tsv")
    check("the copied text carries the time of day, the minute duration and the lag with its unit", "07.09.2026 09:00" in tsv and "07.09.2026 11:30" in tsv and "2.5 hrs" in tsv and "1FS+90m" in tsv, tsv)
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}])
    ev("t => pasteTableText(t)", tsv)
    check("pasting that text as rows into another minute-mode plan restores it: A 09:00–11:30 and the lag 90 — B, an Auto task, then sits where the link puts it (11:30 + 90 working minutes = 14:00, past lunch)", f("A") == ["2026-09-07", "09:00", "2026-09-07", "11:30"] and f("B")[1] == "14:00" and lag("B") == 90, (f("A"), f("B"), lag("B")))

    # ---------------------------------------------------------------- a private copy between plans of the two modes
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-08", "preds": [["A", "FS", 960]]}])
    ev("() => { setSelection(tasks.map(t => t.id)); }")
    payload = ev("() => buildClip().json")
    check("a copy from a minute-mode plan says so, and how long its working day is", payload["timeUnit"] == "minute" and payload["perDay"] == 480, (payload["timeUnit"], payload["perDay"]))
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}], minute=False)
    ev("pl => pasteTaskPayload(pl)", payload)
    check("pasted into a day-mode plan the 960-minute lag is 2 days", ev("() => tasks.filter(t => t.name === 'B').map(t => t.predecessors.map(p => p.lag))") == [[2]], ev("() => tasks.filter(t => t.name === 'B').map(t => t.predecessors)"))
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-08", "preds": [["A", "FS", 2]]}], minute=False)
    ev("() => { setSelection(tasks.map(t => t.id)); }")
    payload = ev("() => buildClip().json")
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}])
    ev("pl => pasteTaskPayload(pl)", payload)
    check("...and 2 days pasted into a minute-mode plan is 960 minutes", ev("() => tasks.filter(t => t.name === 'B').map(t => t.predecessors.map(p => p.lag))") == [[960]], ev("() => tasks.filter(t => t.name === 'B').map(t => t.predecessors)"))

    # ---------------------------------------------------------------- MS Project XML: exact minute lags
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "11:30"}},
          {"name": "B", "s": "2026-09-07", "e": "2026-09-07", "preds": [["A", "FS", 90]], "extra": {"startTime": "13:00", "endTime": "15:00"}}])
    xml = ev("() => buildMspdi()")
    check("the export writes the lag in tenths of a minute (90 min = 900) with the minute format", "<LinkLag>900</LinkLag><LagFormat>3</LagFormat>" in xml)
    res = ev("x => { const r = parseMspdi(x); return { lags: r.tasks.map(t => t.predecessors.map(p => p.lag)), n: r.lagMinutes.size, m: [...r.lagMinutes.values()], tu: r.project.timeUnit }; }", xml)
    check("the parser reads it exactly: 900 tenths = 90 minutes on the side, and rounds the day figure (0)", res["m"] == [90] and res["n"] == 1, res)
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}])
    ev("""x => { const r = parseMspdi(x); applyImportedTasks(r, 'add', { calendar: false }); }""", xml)
    check("imported into a minute-mode plan (calendar left alone) the lag is 90 minutes, not 0", ev("() => tasks.find(t => t.name === 'B').predecessors[0].lag") == 90, ev("() => tasks.find(t => t.name === 'B').predecessors"))
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}], minute=False)
    ev("""x => { const r = parseMspdi(x); applyImportedTasks(r, 'add', { calendar: true }); }""", xml)
    check("imported with its calendar into a day-mode plan the file turns it into a minute-mode one — and the lag comes in exact (90)", ev("() => project.timeUnit") == "minute" and ev("() => tasks.find(t => t.name === 'B').predecessors[0].lag") == 90, (ev("() => project.timeUnit"), ev("() => tasks.find(t => t.name === 'B').predecessors")))
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}, {"name": "B", "s": "2026-09-09", "e": "2026-09-09", "preds": [["A", "FS", 2]]}], minute=False)
    xml = ev("() => buildMspdi()")
    check("a day-mode export is byte-for-byte what it was: 2 days = 9600 with the day format", "<LinkLag>9600</LinkLag><LagFormat>7</LagFormat>" in xml)
    plan([{"name": "Seed", "s": "2026-09-01", "e": "2026-09-01"}])
    ev("""x => { const r = parseMspdi(x); applyImportedTasks(r, 'add', { calendar: false }); }""", xml)
    check("a day-only file imported into a minute-mode plan: 2 days become 960 minutes", ev("() => tasks.find(t => t.name === 'B').predecessors[0].lag") == 960, ev("() => tasks.find(t => t.name === 'B').predecessors"))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
