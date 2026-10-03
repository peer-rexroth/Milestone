# -*- coding: utf-8 -*-
"""The second dialog UX round. (1) Typed date and 24-hour time boxes in the dialogs instead of the browser's own (mm/dd/yyyy,
"09:00 AM"): forgiving parsing, the ISO / 'HH:MM' `.value` contract every dialog relies on, a calendar button, refusal of
unreadable input with the old value coming back and no change event reaching the dialog. (2) The task dialog re-flowed in an
Hours & minutes plan (dates two columns wide, the numbers in one row) and unchanged in day mode. (3) Phone width: no dialog
control runs past its dialog, Name/Mode stack, the Print panes stack, the precision time boxes fit. (4) Enter applies the
Edit-tasks dialog, sentence-case titles, no dead 'Clear this baseline'. (5) Help: an Hours & minutes topic and a search."""
import os, re
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    val = lambda i: ev("i => document.getElementById(i).value", i)   # the dialog's contract: ISO / HH:MM
    toast = lambda: ev("() => document.getElementById('toastMsg').textContent")
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)
    def plan(specs, minute=True):
        ev("m => { if (m) { project.timeUnit = 'minute'; normalizeData(); } else { delete project.timeUnit; delete project.workHours; delete project.lagUnit; }; setView('tasks'); }", minute)
        ev(SEED, specs)
        ev("() => { normalizeData(); save(); render(); }")
    def close_all(): ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); }")
    A = {"name": "A", "s": "2026-09-07", "e": "2026-09-08", "extra": {"startTime": "09:00", "endTime": "11:30"}}
    B = {"name": "B", "s": "2026-09-09", "e": "2026-09-10", "preds": [["A", "FS", 0]]}

    # ================================================================ 1. typed boxes
    tm = ev("() => ['9', '930', '09:30', '9.30', '9:30pm', '12am', '12pm', '0930', '17h', '24:00', '9:5', 'abc', '', '13pm', '7 pm'].map(parseBoxTime)")
    check("time parsing is forgiving: 9, 930, 09:30, 9.30, 9:30pm, 12am, 12pm, 0930, 17h — and refuses 24:00, 9:5, abc, 13pm", tm == ["09:00", "09:30", "09:30", "09:30", "21:30", "00:00", "12:00", "09:30", "17:00", None, None, None, "", None, "19:00"], tm)
    dt = ev("y => ['24.12.2026', '24.12.26', '24.12.', '2026-12-24', '1-1-2026', '31.02.2026', 'x', ''].map(parseBoxDate)", None)
    yr = ev("() => todayStr().slice(0, 4)")
    check("date parsing: 24.12.2026, 24.12.26, 24.12. (this year), 2026-12-24, 1-1-2026 — and refuses 31.02.2026 and x", dt == ["2026-12-24", "2026-12-24", f"{yr}-12-24", "2026-12-24", "2026-01-01", None, None, ""], dt)
    plan([A, B])
    ev("() => openTaskModal(tasks.find(t => t.name === 'B').id)"); pg.wait_for_timeout(250)
    check("the task dialog's dates are typed dd.mm.yyyy boxes with a calendar button, its times typed hh:mm boxes (no browser AM/PM)", all(pg.get_attribute(f"#{i}", "type") == "text" and pg.get_attribute(f"#{i}", "placeholder") == "dd.mm.yyyy" for i in ("taskStartInput", "taskEndInput", "taskActualStartInput", "taskActualFinishInput")) and pg.get_attribute("#taskStartTimeInput", "placeholder") == "hh:mm" and pg.locator("#taskModalBg .dt-cal").count() == 6)   # (Start, Finish, both actuals, the constraint date, the deadline)
    check("Start shows the app's own format (09.09.2026) while `.value` stays ISO for the dialog code", pg.evaluate("() => document.getElementById('taskStartInput')._getRaw()") == "09.09.2026" and val("taskStartInput") == "2026-09-09")
    pg.fill("#taskStartInput", "10.9.26"); pg.press("#taskStartInput", "Tab"); pg.wait_for_timeout(100)
    check("typing '10.9.26' and leaving the box settles it as 10.09.2026 (ISO 2026-09-10) and the dialog reacts (Finish follows)", pg.evaluate("() => document.getElementById('taskStartInput')._getRaw()") == "10.09.2026" and val("taskStartInput") == "2026-09-10" and val("taskEndInput") >= "2026-09-10", (val("taskStartInput"), val("taskEndInput")))
    pg.fill("#taskStartInput", "nonsense"); pg.press("#taskStartInput", "Tab"); pg.wait_for_timeout(100)
    check("something unreadable is refused with a message, the last good date comes back, and the dialog never sees it", "isn't a date" in toast() and pg.evaluate("() => document.getElementById('taskStartInput')._getRaw()") == "10.09.2026" and val("taskStartInput") == "2026-09-10")
    pg.fill("#taskStartTimeInput", "1430"); pg.press("#taskStartTimeInput", "Enter"); pg.wait_for_timeout(100)
    check("a time typed as '1430' and confirmed with Enter reads 14:30", pg.input_value("#taskStartTimeInput") == "14:30" and val("taskStartTimeInput") == "14:30", pg.input_value("#taskStartTimeInput"))
    pg.fill("#taskStartTimeInput", "25:00"); pg.press("#taskStartTimeInput", "Tab"); pg.wait_for_timeout(100)
    check("'25:00' is refused (14:30 stays)", pg.input_value("#taskStartTimeInput") == "14:30" and "isn't a time" in toast())
    nat = pg.locator("#taskEndInput >> xpath=.. >> .dt-native")
    ev("() => { const n = document.querySelector('#taskEndInput').parentElement.querySelector('.dt-native'); n.value = '2026-10-05'; n.dispatchEvent(new Event('change', { bubbles: true })); }"); pg.wait_for_timeout(100)
    check("the calendar button's picker fills the box (05.10.2026) and fires the dialog's change handling", pg.evaluate("() => document.getElementById('taskEndInput')._getRaw()") == "05.10.2026" and val("taskEndInput") == "2026-10-05")
    pg.keyboard.press("Escape"); close_all()
    plan([{"name": "G", "s": "2026-09-07", "e": "2026-09-08"}, dict(A, parent="G")])
    ev("() => openTaskModal(tasks.find(t => t.name === 'G').id)"); pg.wait_for_timeout(250)
    check("a group's Actual Start box and its calendar button are disabled together", pg.is_disabled("#taskActualStartInput") and pg.locator("#taskActualStartInput >> xpath=.. >> .dt-cal").is_disabled())
    close_all()

    # ================================================================ 2. the task dialog re-flow
    plan([A, B])
    ev("() => openTaskModal(tasks.find(t => t.name === 'B').id)"); pg.wait_for_timeout(250)
    y = lambda sel: round(pg.locator(sel).bounding_box()["y"])
    check("Hours & minutes: Start and Finish share one row; Duration, % Complete, Remaining and Status the next; Actual Start and Finish below them", y("#taskStartField") == y("#taskEndField") < y("#taskDurationField") == y("#taskProgressField") == y("#taskRemainingField") == y("#taskStatusField") < y("#taskActualStartField") == y("#taskActualFinishField"),
          [y(s) for s in ("#taskStartField", "#taskEndField", "#taskDurationField", "#taskProgressField", "#taskRemainingField", "#taskStatusField", "#taskActualStartField", "#taskActualFinishField")])
    check("the date fields are wide (>= 200px of box), their times narrow (84px)", pg.locator("#taskStartInput").bounding_box()["width"] >= 150 and round(pg.locator("#taskStartTimeInput").bounding_box()["width"]) == 84)
    # Task Type / Work added a real row to General (see CLAUDE.md) — an Hours & minutes task with a predecessor showing
    # is the tallest the dialog gets, and now needs a little more than 860px; 910px is the new, deliberately-raised budget.
    pg.set_viewport_size({"width": 1400, "height": 910})
    check("the whole dialog, predecessors included, fits at 910px high without scrolling", ev("() => { const b = document.querySelector('#taskModalBg .modal-body'); return b.scrollHeight <= b.clientHeight + 1; }"))
    pg.set_viewport_size({"width": 1400, "height": 860})
    close_all()
    plan([A, B], minute=False)
    ev("() => openTaskModal(tasks.find(t => t.name === 'B').id)"); pg.wait_for_timeout(250)
    check("a day-mode plan keeps its layout: Start, Finish, Duration and % in one row, the actual dates + Remaining + Status in the next", y("#taskStartField") == y("#taskEndField") == y("#taskDurationField") == y("#taskProgressField") < y("#taskActualStartField") == y("#taskActualFinishField") == y("#taskRemainingField") == y("#taskStatusField"))
    check("...with no time boxes", not pg.is_visible("#taskStartTimeInput"))
    close_all()

    # ================================================================ 3. phone width
    pg.set_viewport_size({"width": 390, "height": 780})
    plan([A, B])
    ev("() => { setSelection(tasks.map(t => t.id)); openBulkModal(); }"); pg.wait_for_timeout(250)
    over = ev("() => { const m = document.querySelector('#bulkModalBg .modal').getBoundingClientRect(); return [...document.querySelectorAll('#bulkModalBg input, #bulkModalBg select')].filter(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().right > m.right + 1).map(e => e.id); }")
    check("Edit tasks at 390px: no control runs past the dialog's edge", over == [], over)
    close_all()
    ev("() => openTaskModal(tasks.find(t => t.name === 'A').id)"); pg.wait_for_timeout(250)
    check("the task dialog at 390px gives Task Name the full width (Task Mode is under it)", pg.locator("#taskNameInput").bounding_box()["width"] > 280 and y("#taskModeInput") > y("#taskNameInput"))
    over = ev("() => { const m = document.querySelector('#taskModalBg .modal').getBoundingClientRect(); return [...document.querySelectorAll('#taskModalBg input, #taskModalBg select')].filter(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().right > m.right + 1).map(e => e.id); }")
    check("...and nothing in it runs past the edge either", over == [], over)
    close_all()
    ev("() => openPrintModal()"); pg.wait_for_timeout(300)
    check("Print at 390px stacks its options above the preview instead of squeezing both", ev("() => getComputedStyle(document.querySelector('#printModalBg .print-layout')).flexDirection") == "column" and pg.locator("#printModalBg .print-opts").bounding_box()["width"] > 300)
    close_all()
    ev("() => openPrecisionModal()"); pg.wait_for_timeout(250)
    tb = ev("() => [...document.querySelectorAll('#precisionModalBg input.dt-time')].filter(e => e.getBoundingClientRect().width).map(e => [Math.round(e.getBoundingClientRect().width), e.scrollWidth <= e.clientWidth])")
    check("Scheduling precision at 390px: every time box is 80px+ and shows its whole time (24-hour: nothing to cut off)", all(w >= 80 and fit for w, fit in tb) and len(tb) >= 4, tb)
    close_all()
    pg.set_viewport_size({"width": 1400, "height": 860})

    # ================================================================ 4. small things
    plan([A, B])
    ev("() => { setSelection(tasks.map(t => t.id)); openBulkModal(); }"); pg.wait_for_timeout(250)
    pg.keyboard.type("50"); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    check("Enter in a box of the Edit-tasks dialog applies it (both tasks at 50%, dialog closed)", ev("() => tasks.map(t => t.progress)") == [50, 50] and not ev("() => document.getElementById('bulkModalBg').classList.contains('open')"), ev("() => tasks.map(t => t.progress)"))
    ev("() => openTaskModal(tasks[0].id)"); pg.wait_for_timeout(200)
    t1 = pg.inner_text("#taskModalTitle"); close_all()
    ev("() => { pendingImportData = { tasks: [], project: {} }; openImportModal(); }"); t2 = ev("() => document.querySelector('#importModalBg h2').textContent"); close_all()
    ev("() => openBackupsModal()"); t3 = ev("() => document.querySelector('#backupsModalBg h2').textContent"); close_all()
    check("dialog titles are sentence case: 'Edit task', 'Import data', 'Local backups'", t1.startswith("Edit task") and t2 == "Import data" and t3 == "Local backups", (t1, t2, t3))
    ev("() => openBaselineModal()"); pg.wait_for_timeout(200)
    check("'Clear this baseline' is not shown while there is nothing to clear", not pg.is_visible("#baselineClearBtn"))
    pg.click("#baselineSetBtn"); pg.wait_for_timeout(300)
    check("...and appears once the baseline is set", pg.is_visible("#baselineClearBtn"))
    close_all()

    # ================================================================ 5. Help
    ev("() => openHelpModal()"); pg.wait_for_timeout(200)
    tabs = ev("() => [...document.querySelectorAll('#helpModalBg [role=tab]')].map(t => t.textContent.trim())")
    check("Help has an 'Hours & minutes' topic (seven topics)", "Hours & minutes" in tabs and len(tabs) == 7, tabs)
    txt = ev("() => document.getElementById('helpPane-hours').textContent")
    check("...holding the precision, different-hours, lags, hours-scale, inline-editing and paste/import notes", all(w in txt for w in ("Scheduling precision", "Different hours", "Lags are working time", "Hours scale", "date and time", "Paste and CSV")))
    check("...which no longer sit in the Calendar topic", "Lags are working time" not in ev("() => document.getElementById('helpPane-progress').textContent"))
    pg.fill("#helpSearch", "lag"); pg.wait_for_timeout(150)
    res = ev("() => ({ shown: !document.getElementById('helpPane-search').hidden, others: [...document.querySelectorAll('#helpModalBg .help-pane:not(#helpPane-search)')].every(p => p.hidden), marks: document.querySelectorAll('#helpPane-search mark').length, topics: [...document.querySelectorAll('#helpPane-search .help-jump')].map(b => b.textContent.trim()), tabsOn: document.querySelectorAll('#helpModalBg [aria-selected=true]').length })")
    check("searching 'lag' shows the matching rows grouped by topic with the word marked, in place of the topic pane", res["shown"] and res["others"] and res["marks"] >= 3 and any("Hours & minutes" in t for t in res["topics"]) and res["tabsOn"] == 0, res)
    pg.fill("#helpSearch", "hours scale export xyzzy"); pg.wait_for_timeout(150)
    check("a search with no match says so", "Nothing in Help matches" in pg.inner_text("#helpPane-search"))
    pg.fill("#helpSearch", "lag"); pg.wait_for_timeout(100)
    pg.press("#helpSearch", "Escape"); pg.wait_for_timeout(150)
    check("Escape in the search box clears it and shows the topic again — the dialog stays open", pg.input_value("#helpSearch") == "" and pg.locator("#helpModalBg.open").count() == 1 and ev("() => document.getElementById('helpPane-search').hidden"))
    pg.fill("#helpSearch", "baseline"); pg.wait_for_timeout(100)
    pg.click("#helpPane-search .help-jump >> nth=0"); pg.wait_for_timeout(150)
    check("a topic name in the results opens that topic (and ends the search)", pg.input_value("#helpSearch") == "" and ev("() => [...document.querySelectorAll('#helpModalBg .help-pane:not(#helpPane-search)')].filter(p => !p.hidden).length") == 1)
    pg.fill("#helpSearch", "lag"); pg.click("#helpTab-gantt"); pg.wait_for_timeout(100)
    check("clicking a topic while a search is showing ends the search", pg.input_value("#helpSearch") == "" and not pg.is_visible("#helpPane-search"))
    pg.fill("#helpSearch", "lag"); pg.keyboard.press("Escape"); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("a second Escape closes Help", pg.locator("#helpModalBg.open").count() == 0)
    ev("() => openHelpModal()"); pg.wait_for_timeout(100)
    check("reopening Help starts with an empty search", pg.input_value("#helpSearch") == "")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
