# -*- coding: utf-8 -*-
"""Phase 3 of minute/hour-level scheduling precision: the UI to actually use the engine and data model Phases 1-2 built —
the "Scheduling precision" toggle and working-hours/breaks editor (folded into the existing Working Calendar dialog), the
task dialog's paired time inputs and hour/minute-aware Duration field, the inline grid's date+time display, and the
column-width adaptation ("size of date fields and column width should be adapted when switched to hour/minutes planning",
the user's own words). Everything here is additive and gated on project.timeUnit === 'minute': a day-mode plan's dialog,
grid and column widths are unaffected — that's covered by every OTHER suite in this run, which never sets timeUnit."""
import re, os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    seed = lambda specs: ev(SEED, specs)
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)

    # ---------------------------------------------------------------- Working calendar dialog: the precision toggle
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open"); pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    check("opens on Days, the standard", pg.is_checked("#precisionDay") and not pg.is_checked("#precisionMinute"))
    check("the working-hours editor starts hidden", "hidden" in (pg.get_attribute("#workHoursEditor", "class") or ""))
    pg.check("#precisionMinute")
    check("checking Hours & minutes reveals the working-hours editor", "hidden" not in (pg.get_attribute("#workHoursEditor", "class") or ""))
    check("it defaults to 08:00-17:00 with the usual lunch break", pg.input_value("#whStart") == "08:00" and pg.input_value("#whEnd") == "17:00" and "12:00" in pg.inner_text("#whBreakList") and "13:00" in pg.inner_text("#whBreakList"))
    pg.click("#precisionDay")
    check("switching back to Days hides the editor again", "hidden" in (pg.get_attribute("#workHoursEditor", "class") or ""))
    pg.keyboard.press("Escape")   # no dirty change yet (still on the default), closes without asking
    check("Escape with nothing changed just closes", pg.locator("#calendarModalBg.open").count() == 0)

    # ---------------------------------------------------------------- saving a custom precision + working hours
    pg.click("#scheduleMenuBtn"); pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    pg.check("#precisionMinute")
    pg.fill("#whStart", "09:00"); pg.fill("#whEnd", "18:00")
    pg.click("#whBreakList .hol-row button")   # remove the default 12:00-13:00 break first — an overlapping add would be deduped, not replace it
    pg.fill("#whBreakFrom", "12:30"); pg.fill("#whBreakTo", "13:15"); pg.click("#calendarModalBg .wh-break-add button")
    check("the added break appears in its list", "12:30" in pg.inner_text("#whBreakList") and "13:15" in pg.inner_text("#whBreakList"))
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    wh = ev("() => ({ timeUnit: project.timeUnit, workHours: project.workHours })")
    check("saved: timeUnit is 'minute' and workHours holds the custom start/end/break", wh["timeUnit"] == "minute" and wh["workHours"] == {"start": "09:00", "end": "18:00", "breaks": [{"start": "12:30", "end": "13:15"}]}, wh)
    check("the Schedule menu's Working calendar hint mentions the hours", "09:00" in ev("() => calendarSummary()"))

    # ---------------------------------------------------------------- reopening shows the saved state; discard-confirmation catches a precision change
    pg.click("#scheduleMenuBtn"); pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    check("reopening shows Hours & minutes checked with the saved values", pg.is_checked("#precisionMinute") and pg.input_value("#whStart") == "09:00" and pg.input_value("#whEnd") == "18:00")
    pg.click("#precisionDay")
    pg.click("#calendarModalBg .modal-header button")   # the × close button
    check("switching precision without saving triggers the discard-changes confirmation", pg.locator("#confirmModalBg.open").count() == 1)
    pg.click("#confirmModalBg button:has-text('Keep editing')")
    pg.check("#precisionMinute"); pg.keyboard.press("Escape")   # back to the saved state -> no longer dirty
    check("returning to the saved state before closing asks nothing", pg.locator("#calendarModalBg.open").count() == 0 and pg.locator("#confirmModalBg.open").count() == 0)

    # ---------------------------------------------------------------- an invalid break is refused with a message, not silently dropped
    pg.click("#scheduleMenuBtn"); pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    pg.fill("#whBreakFrom", "14:00"); pg.fill("#whBreakTo", "13:00"); pg.click("#calendarModalBg .wh-break-add button")
    check("a break ending before it starts is refused with a toast, not added", "end after it starts" in pg.inner_text("#toastMsg"))
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- task dialog: time inputs, duration parsing, save round-trip
    ev("() => { delete project.workHours; normalizeData(); save(); }")   # back to the 08:00-17:00/12:00-13:00 default (an earlier section customized it)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}])
    pg.click(f".grid-row[data-id='{tid('A')}'] .icon-btn[title=Edit]"); pg.wait_for_selector("#taskModalBg.open")
    check("in a minute-mode plan the task dialog shows Start/Finish time inputs", pg.is_visible("#taskStartTimeInput") and pg.is_visible("#taskEndTimeInput"))
    check("the Duration label drops '(days)' and its tooltip explains hour/minute entry", pg.inner_text("#taskDurationLabel") == "Duration" and "bare number is hours" in (pg.get_attribute("#taskDurationLabel", "title") or ""))
    check("the modal widens so the date input isn't squeezed down to icon-only width", pg.eval_on_selector("#taskModalInner", "e => e.classList.contains('minute-mode')") and pg.locator("#taskModalInner").bounding_box()["width"] > 620)
    date_box = pg.locator("#taskStartInput").bounding_box(); time_box = pg.locator("#taskStartTimeInput").bounding_box()
    check("...wide enough that the Start date shows its text (not just the calendar icon), same row as its time", date_box["width"] >= 100 and abs(date_box["y"] - time_box["y"]) < 2, (date_box, time_box))
    pg.fill("#taskStartTimeInput", "09:00"); pg.dispatch_event("#taskStartTimeInput", "change")
    pg.fill("#taskDurationInput", "90m"); pg.dispatch_event("#taskDurationInput", "change")
    check("'90m' duration from 09:00 computes Finish 10:30", pg.input_value("#taskEndTimeInput") == "10:30", pg.input_value("#taskEndTimeInput"))
    pg.fill("#taskDurationInput", "4h"); pg.dispatch_event("#taskDurationInput", "change")
    check("'4h' duration from 09:00 (crossing the lunch break) computes Finish 14:00", pg.input_value("#taskEndTimeInput") == "14:00", pg.input_value("#taskEndTimeInput"))
    pg.click("#taskModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    a = ev("() => { const t = tasks.find(x => x.name === 'A'); return [t.startDate, t.startTime, t.endDate, t.endTime]; }")
    check("saved with the exact start/finish time computed in the dialog", a == ["2026-09-07", "09:00", "2026-09-07", "14:00"], a)

    # ---------------------------------------------------------------- actual start/finish time round-trip
    pg.click(f".grid-row[data-id='{tid('A')}'] .icon-btn[title=Edit]"); pg.wait_for_selector("#taskModalBg.open")
    pg.fill("#taskActualStartInput", "2026-09-07"); pg.dispatch_event("#taskActualStartInput", "change")
    pg.fill("#taskActualStartTimeInput", "09:30"); pg.dispatch_event("#taskActualStartTimeInput", "change")
    check("recording an Actual Start time updates the Start time to match (the actual dates ARE the schedule)", pg.input_value("#taskStartTimeInput") == "09:30", pg.input_value("#taskStartTimeInput"))
    pg.click("#taskModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    a2 = ev("() => { const t = tasks.find(x => x.name === 'A'); return [t.actualStart, t.actualStartTime, t.startTime]; }")
    check("the actual start time is saved and reflected in Start", a2 == ["2026-09-07", "09:30", "09:30"], a2)

    # ---------------------------------------------------------------- grid: date+time display and adapted column widths
    idx = ev("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col).indexOf('start')")
    cell = pg.locator(f".grid-row[data-id='{tid('A')}']").locator(":scope > div").nth(idx + 1).inner_text()
    check("the grid's Start cell shows the date AND the time", "09:30" in cell and "07.09.2026" in cell, cell)
    cols_css = ev("() => getComputedStyle(document.getElementById('main')).getPropertyValue('--task-cols')")
    tracks = cols_css.strip().split()
    check("Start/Finish/Actual Start/Actual Finish widen to 150px in minute mode (the standard day-mode 104px column)", tracks[4:8] == ["150px"] * 4, tracks)

    # ---------------------------------------------------------------- switching back to day mode: grid and dialog revert, times dropped
    ev("() => { project.timeUnit = 'day'; delete project.workHours; normalizeData(); save(); render(); }")
    pg.wait_for_timeout(150)
    cols_css2 = ev("() => getComputedStyle(document.getElementById('main')).getPropertyValue('--task-cols')")
    check("column widths revert to the standard 104px once back in day mode", cols_css2.strip().split()[4:8] == ["104px"] * 4)
    cell2 = pg.locator(f".grid-row[data-id='{tid('A')}']").locator(":scope > div").nth(idx + 1).inner_text()
    check("the grid's Start cell shows only the date again, no time", cell2 == "07.09.2026", cell2)
    pg.click(f".grid-row[data-id='{tid('A')}'] .icon-btn[title=Edit]"); pg.wait_for_selector("#taskModalBg.open")
    check("the task dialog hides the time inputs again in day mode", not pg.is_visible("#taskStartTimeInput"))
    check("the Duration label is back to '(days)'", pg.inner_text("#taskDurationLabel") == "Duration (days)")
    check("...and the modal narrows back to its standard width", not pg.eval_on_selector("#taskModalInner", "e => e.classList.contains('minute-mode')") and pg.locator("#taskModalInner").bounding_box()["width"] == 620)
    pg.keyboard.press("Escape")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
