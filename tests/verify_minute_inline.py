# -*- coding: utf-8 -*-
"""Minute-mode scheduling precision, the LIST: the inline cell editors take a time of day. In a minute-mode plan Start, Finish,
Actual Start and Actual Finish are edited in one typed box, "dd.mm.yyyy hh:mm" (the box a Manually Scheduled task always had,
with its calendar button): a date alone keeps the task's time, a time alone keeps its date, the calendar button keeps the typed
time, and a time in the lunch break is moved onto working time like a date on a day off. A finish at a window's close
(17:00, or 12:00 as the break starts) is a valid finish and stays as typed (snapToWorkDays used to turn it into 16:59 / 11:59).
Duration is edited in working minutes ("4h", "90m", "2d", "1w"; a bare number is hours) and shown the same way. A day-mode plan
keeps its native date input and whole-day duration exactly as before."""
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
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)
    f = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.startTime, t.endDate, t.endTime]; }", n)
    def minute_plan(specs):
        ev("() => { project.timeUnit = 'minute'; }")   # (before the seed: saving a day-mode plan drops every time of day)
        ev(SEED, specs)
        ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); render(); }")
    def cell(name, col):
        idx = ev("c => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col).indexOf(c)", col)
        return pg.locator(f".grid-row[data-id='{tid(name)}']").locator(":scope > div").nth(idx + 1)
    def edit(name, col, text):
        cell(name, col).click(); pg.wait_for_selector(".inline-edit"); pg.fill(".inline-edit", text); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    for c in ("actualStart", "actualFinish"): ev("c => { colHidden.delete(c); render(); }", c)

    A = {"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "11:30"}}

    # ---------------------------------------------------------------- the editor
    minute_plan([A]);
    cell("A", "start").click(); pg.wait_for_selector(".inline-edit")
    check("the Start editor of an Auto task in a minute-mode plan is the typed box, holding date AND time", pg.input_value(".inline-edit") == "07.09.2026 09:00" and pg.get_attribute(".inline-edit", "type") == "text", pg.input_value(".inline-edit"))
    check("...with a calendar button and a placeholder saying what to type", pg.locator(".inline-wrap .inline-cal").count() == 1 and pg.get_attribute(".inline-edit", "placeholder") == "dd.mm.yyyy hh:mm")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape cancels: nothing changed", f("A") == ["2026-09-07", "09:00", "2026-09-07", "11:30"], f("A"))
    minute_plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}])
    cell("A", "end").click(); pg.wait_for_selector(".inline-edit")
    check("a task with no time of its own shows the working day's own: Finish 17:00", pg.input_value(".inline-edit") == "07.09.2026 17:00", pg.input_value(".inline-edit"))
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- typing date and time
    minute_plan([A])
    edit("A", "start", "07.09.2026 10:15")
    check("'07.09.2026 10:15' sets the start time (the finish stays)", f("A") == ["2026-09-07", "10:15", "2026-09-07", "11:30"], f("A"))
    check("the cell shows it", "10:15" in cell("A", "start").inner_text(), cell("A", "start").inner_text())
    edit("A", "start", "10:45")
    check("a time alone ('10:45') keeps the date", f("A") == ["2026-09-07", "10:45", "2026-09-07", "11:30"], f("A"))
    edit("A", "end", "2026-09-07T15:00")
    check("the ISO form with a T is read too", f("A")[2:] == ["2026-09-07", "15:00"], f("A"))
    edit("A", "end", "08.09.2026")
    check("a date alone keeps the finish time (15:00) — the task now runs into Tuesday", f("A") == ["2026-09-07", "10:45", "2026-09-08", "15:00"], f("A"))
    edit("A", "start", "1.9.2026 9:05")
    check("single-digit day, month and hour are fine ('1.9.2026 9:05' = Tuesday 01.09.2026 09:05)", f("A")[:2] == ["2026-09-01", "09:05"], f("A"))

    # ---------------------------------------------------------------- times that are not working time
    minute_plan([A])
    edit("A", "start", "07.09.2026 12:30")
    check("a start in the lunch break moves to the next working minute (13:00) — and says so", f("A")[1] == "13:00" and "working" in ev("() => document.getElementById('toastMsg').textContent").lower(), (f("A"), ev("() => document.getElementById('toastMsg').textContent")))
    minute_plan([A])
    edit("A", "end", "07.09.2026 17:00")
    check("a finish at the day's close (17:00) is valid and stays exactly 17:00 (it used to become 16:59)", f("A")[3] == "17:00", f("A"))
    edit("A", "end", "07.09.2026 12:00")
    check("a finish as the lunch break starts (12:00) stays 12:00 (it used to become 11:59)", f("A")[3] == "12:00", f("A"))
    edit("A", "end", "07.09.2026 12:30")
    check("a finish inside the break settles on its start (12:00)", f("A")[3] == "12:00", f("A"))
    edit("A", "end", "07.09.2026 20:00")
    check("a finish after closing settles on the close (17:00)", f("A")[3] == "17:00", f("A"))
    minute_plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-07"}])
    ev("() => { const t = tasks.find(x => x.name === 'A'); snapToWorkDays(t); }")
    check("snapping a task at the default working hours no longer writes 16:59 into it", f("A")[3] is None and f("A")[1] is None, f("A"))

    # ---------------------------------------------------------------- refusals
    minute_plan([A])
    edit("A", "start", "25:99")
    check("something that isn't a date or a time leaves an Auto task alone", f("A") == ["2026-09-07", "09:00", "2026-09-07", "11:30"], f("A"))
    edit("A", "start", "07.09.2026 09:60")
    check("...an impossible time too", f("A") == ["2026-09-07", "09:00", "2026-09-07", "11:30"], f("A"))

    # ---------------------------------------------------------------- the calendar button keeps the typed time
    minute_plan([A])
    cell("A", "start").click(); pg.wait_for_selector(".inline-edit"); pg.fill(".inline-edit", "07.09.2026 10:20")
    pg.evaluate("() => { const d = document.querySelector('.inline-date-hidden'); d.value = '2026-09-08'; d.dispatchEvent(new Event('change', { bubbles: true })); }"); pg.wait_for_timeout(150)
    check("picking a date with the calendar button keeps the time typed beside it", f("A")[:2] == ["2026-09-08", "10:20"], f("A"))

    # ---------------------------------------------------------------- a Manual task: date-time or free text
    minute_plan([{"name": "Mn", "s": "2026-09-07", "e": "2026-09-07", "extra": {"taskMode": "manual", "startTime": "09:00", "endTime": "10:00"}}])
    edit("Mn", "start", "07.09.2026 12:15")
    check("a Manual task keeps exactly the moment typed (12:15 is in the lunch break and stays)", f("Mn")[:2] == ["2026-09-07", "12:15"], f("Mn"))
    edit("Mn", "end", "TBD")
    check("...and still takes free text such as TBD", ev("() => tasks.find(t => t.name === 'Mn').endText") == "TBD")

    # ---------------------------------------------------------------- milestone: one instant
    minute_plan([{"name": "Ms", "s": "2026-09-07", "e": "2026-09-07", "extra": {"milestone": True, "startTime": "10:00", "endTime": "10:00"}}])
    edit("Ms", "start", "08.09.2026 14:30")
    check("a milestone's Start carries its Finish along (date and time)", f("Ms") == ["2026-09-08", "14:30", "2026-09-08", "14:30"], f("Ms"))
    check("its Duration reads 0 min, not the 1 min the engine's minimum would give", cell("Ms", "duration").inner_text() == "0 min", cell("Ms", "duration").inner_text())

    # ---------------------------------------------------------------- a started task: actual dates carry a time and ARE the schedule
    minute_plan([{"name": "S", "s": "2026-09-07", "e": "2026-09-08", "extra": {"startTime": "09:00", "endTime": "12:00"}}])
    edit("S", "actualStart", "07.09.2026 09:30")
    check("typing an Actual Start with a time records it and the Start follows (the actual dates ARE the schedule)", ev("() => { const t = tasks.find(x => x.name === 'S'); return [t.actualStart, t.actualStartTime, t.startTime]; }") == ["2026-09-07", "09:30", "09:30"], ev("() => { const t = tasks.find(x => x.name === 'S'); return [t.actualStart, t.actualStartTime, t.startTime]; }"))
    edit("S", "start", "07.09.2026 10:00")
    check("editing the Start of a started task moves its Actual Start with it, time included", ev("() => { const t = tasks.find(x => x.name === 'S'); return [t.actualStartTime, t.startTime]; }") == ["10:00", "10:00"])
    edit("S", "actualFinish", "07.09.2026 09:00")
    check("an Actual Finish before the Actual Start is refused, on the time as well as the date", ev("() => tasks.find(x => x.name === 'S').actualFinish") is None and "before" in ev("() => document.getElementById('toastMsg').textContent"))
    edit("S", "actualFinish", "08.09.2026 11:00")
    af = ev("() => { const t = tasks.find(x => x.name === 'S'); return [t.actualFinish, t.actualFinishTime, t.endDate, t.endTime, t.progress]; }")
    check("a later Actual Finish is recorded with its time, the Finish follows, the task is 100% complete", af == ["2026-09-08", "11:00", "2026-09-08", "11:00", 100], af)
    edit("S", "actualStart", "")
    check("clearing an actual date clears its time too", ev("() => { const t = tasks.find(x => x.name === 'S'); return [t.actualStart, t.actualStartTime]; }") == [None, None])

    # ---------------------------------------------------------------- Duration: working minutes
    minute_plan([A])
    check("the Duration cell of a minute-mode task reads in working time: 09:00–11:30 = '2.5 hrs'", cell("A", "duration").inner_text() == "2.5 hrs", cell("A", "duration").inner_text())
    cell("A", "duration").click(); pg.wait_for_selector(".inline-edit")
    check("its editor is a text box holding that value, with a hint on the units", pg.get_attribute(".inline-edit", "type") == "text" and pg.input_value(".inline-edit") == "2.5 hrs" and "bare number is hours" in (pg.get_attribute(".inline-edit", "title") or ""))
    pg.fill(".inline-edit", "90m"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    check("'90m' from 09:00 finishes at 10:30", f("A")[3] == "10:30", f("A"))
    edit("A", "duration", "4h")
    check("'4h' from 09:00 crosses the lunch break: finish 14:00", f("A")[3] == "14:00", f("A"))
    edit("A", "duration", "3")
    check("a bare number is hours: '3' from 09:00 finishes at 12:00 as the lunch break starts", f("A")[3] == "12:00" and f("A")[2] == "2026-09-07", f("A"))
    edit("A", "duration", "1d")
    check("'1d' is a working day of 8 working hours: from 09:00 that is 7h to the 17:00 close, the 8th hour ends Tuesday 09:00", f("A")[2:] == ["2026-09-08", "09:00"], f("A"))
    edit("A", "duration", "1w")
    check("'1w' is five working days", f("A")[2] == "2026-09-14" and f("A")[3] == "09:00", f("A"))
    before = f("A")
    edit("A", "duration", "soon")
    check("nonsense is refused with a message and changes nothing", f("A") == before and "Can't read" in ev("() => document.getElementById('toastMsg').textContent"))
    minute_plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "extra": {"startTime": "09:00", "endTime": "12:00"}}, {"name": "B", "s": "2026-09-08", "e": "2026-09-08", "preds": [["A", "FS", 0]], "extra": {"startTime": "12:00", "endTime": "13:00"}}])
    edit("A", "duration", "1h")
    check("changing a duration cascades to its successors at minute precision (B follows A's new finish)", f("A")[3] == "10:00" and f("B")[1] == "10:00", (f("A"), f("B")))
    minute_plan([{"name": "Mn", "s": "2026-09-07", "e": "2026-09-07", "extra": {"taskMode": "manual", "startTime": "09:00", "endTime": "10:00"}}])
    edit("Mn", "duration", "2h")
    check("a Manual task's duration is in minutes too (09:00 + 2h = 11:00)", f("Mn")[3] == "11:00", f("Mn"))
    edit("Mn", "duration", "to be decided")
    check("...and still takes free text", ev("() => tasks.find(t => t.name === 'Mn').durText") == "to be decided")
    minute_plan([{"name": "G", "s": "2026-09-07", "e": "2026-09-09"}, {"name": "C", "s": "2026-09-07", "e": "2026-09-09", "parent": "G"}])
    check("a group's rolled-up duration stays in days", "day" in cell("G", "duration").inner_text(), cell("G", "duration").inner_text())

    # ---------------------------------------------------------------- day mode: exactly as before
    ev(SEED, [{"name": "A", "s": "2026-09-07", "e": "2026-09-09"}])
    ev("() => { delete project.timeUnit; delete project.workHours; normalizeData(); save(); render(); }")
    cell("A", "start").click(); pg.wait_for_selector(".inline-edit")
    check("a day-mode plan's Start editor is still the native date input", pg.get_attribute(".inline-edit", "type") == "date")
    pg.keyboard.press("Escape")
    cell("A", "duration").click(); pg.wait_for_selector(".inline-edit")
    check("...and its Duration a whole-day number box", pg.get_attribute(".inline-edit", "type") == "number" and pg.input_value(".inline-edit") == "3")
    pg.keyboard.press("Escape")
    check("a day-mode Duration cell still reads '3 days'", cell("A", "duration").inner_text() == "3 days")
    check("a day-mode task carries no time of day at all", ev("() => { const t = tasks.find(x => x.name === 'A'); return 'startTime' in t ? t.startTime : null; }") is None)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
