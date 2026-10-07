# -*- coding: utf-8 -*-
"""Per-weekday working hours (minute-mode plans): project.workHoursByDay = { weekday 0-6: { start, end, breaks } } holds the hours of
the weekdays that differ from the plan's standard day (project.workHours) — a short Friday. The whole working-hours layer takes the
day into account (windows, the next/previous working minute, adding and counting working minutes, finish/start moments, the
default time of a task with none of its own), cross-checked against a minute-by-minute walk on random cases with holidays and a
working Saturday; a plan whose days are all alike keeps its O(1) shortcuts (uniform). The Scheduling precision dialog edits the
different days (a row per working weekday), normalizeData() cleans them, the Gantt's Hours scale and the hourly Excel Gantt sheet
follow each day's hours, MS Project XML carries each weekday's own WorkingTimes (and an ordinary file with a short Friday still
imports as a day-mode plan)."""
import os, re, tempfile
from playwright.sync_api import sync_playwright
import openpyxl
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)
TMP = tempfile.mkdtemp()
FRI = {"start": "08:00", "end": "13:00", "breaks": []}

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    f = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.startTime, t.endDate, t.endTime]; }", n)
    toast = lambda: ev("() => document.getElementById('toastMsg').textContent")
    mn = lambda iso, hm: ev("([i, h]) => dayNumber(i) * 1440 + minuteOfDay(h)", [iso, hm])
    hm = lambda m: ev("m => { const d = Math.floor(m / 1440); return dayNumberToIso(d) + ' ' + hhmmOf(m - d * 1440); }", m)
    def plan(specs=None, by=None, days=None, extra=""):
        ev("""([by, days]) => { project.timeUnit = 'minute'; delete project.workHours; if (by) project.workHoursByDay = by; else delete project.workHoursByDay;
            if (days) project.workDays = days; else delete project.workDays; delete project.holidays; normalizeData(); }""", [by, days])
        if specs is not None: ev(SEED, specs)
        ev("() => { normalizeData(); save(); render(); }")

    # ---------------------------------------------------------------- the calendar itself
    plan([], {"5": FRI})
    info = ev("() => ({ uniform: hoursInfo().uniform, fri: winOfDay(dayNumber('2026-09-11')), mon: winOfDay(dayNumber('2026-09-07')), week: weekMinutes(), std: workMinutesPerDay() })")
    check("a plan with a short Friday is not uniform; Friday 08:00–13:00 is one window, Monday keeps its lunch break", info["uniform"] is False and info["fri"] == [[480, 780]] and info["mon"] == [[480, 720], [780, 1020]], info)
    check("the week is 4 x 480 + 300 = 2220 working minutes; a 'day' (for 1d in a duration or lag) stays the standard 480", info["week"] == 2220 and info["std"] == 480, info)
    check("a task with no time of its own starts and finishes at ITS day's hours: Friday 08:00–13:00, Monday 08:00–17:00", ev("() => [wStart('2026-09-11'), wEnd('2026-09-11'), wStart('2026-09-07'), wEnd('2026-09-07')]") == ["08:00", "13:00", "08:00", "17:00"])
    check("Friday has no lunch break (12:30 works), and nothing after 13:00", ev("() => [isWorkMinuteNum(dayNumber('2026-09-11') * 1440 + 750), isWorkMinuteNum(dayNumber('2026-09-11') * 1440 + 800), isWorkMinuteNum(dayNumber('2026-09-07') * 1440 + 750)]") == [True, False, False])
    check("after Friday's close the next working minute is Monday 08:00; before Monday's open, still Monday 08:00", hm(ev("m => nextWorkMinuteNum(m)", mn("2026-09-11", "14:00"))) == "2026-09-14 08:00")
    check("the last working minute before the weekend is Friday 12:59, and the latest valid FINISH on or before Friday 15:00 is 13:00 (a window's close)", hm(ev("m => prevWorkMinuteNum(m)", mn("2026-09-12", "10:00"))) == "2026-09-11 12:59" and hm(ev("m => prevFinishMinuteNum(m)", mn("2026-09-11", "15:00"))) == "2026-09-11 13:00")
    check("+120 working minutes from Friday 12:00: 60 left on Friday, 60 on Monday (09:00)", hm(ev("m => addWorkMinuteNum(m, 120)", mn("2026-09-11", "12:00"))) == "2026-09-14 09:00")
    check("-60 from Monday 08:30: back over the weekend into Friday's last half hour... (Friday 12:30)", hm(ev("m => addWorkMinuteNum(m, -60)", mn("2026-09-14", "08:30"))) == "2026-09-11 12:30")
    check("a 6h task from Friday 09:00 finishes Monday 10:00 (4h on Friday, 2h on Monday)", hm(ev("m => finishMomentFor(m, 360)", mn("2026-09-11", "09:00"))) == "2026-09-14 10:00")
    check("...and its inverse: a 6h task finishing Monday 10:00 starts Friday 09:00", hm(ev("m => startMomentFor(m, 360)", mn("2026-09-14", "10:00"))) == "2026-09-11 09:00")
    check("working minutes Friday 09:00 to Monday 10:00 = 240 + 120", ev("([a, b]) => countWorkMinuteNum(a, b)", [mn("2026-09-11", "09:00"), mn("2026-09-14", "10:00")]) == 360)

    # ---------------------------------------------------------------- cross-checked against a minute-by-minute walk (holidays, a working Saturday with its own hours)
    plan([], {"5": FRI, "6": {"start": "09:00", "end": "11:30", "breaks": []}, "2": {"start": "10:00", "end": "18:00", "breaks": [{"start": "14:00", "end": "14:30"}]}}, days=[1, 2, 3, 4, 5, 6])
    ev("() => { project.holidays = [{ date: '2026-09-16', name: 'x' }, { date: '2026-09-22', to: '2026-09-23' }]; normalizeData(); }")
    res = ev("""() => {
      let seed = 12345; const rnd = n => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
      const d0 = dayNumber('2026-09-07'), bad = [];
      const isW = x => isWorkMinuteNum(x);
      for (let i = 0; i < 300; i++) {
        let s = (d0 + rnd(40)) * 1440 + rnd(1440); s = nextWorkMinuteNum(s);
        const k = rnd(7000) - 2500;
        // forward/back by k working minutes
        let x = s, c = 0;
        if (k > 0) { while (c < k) { if (isW(x)) c++; x++; } x = nextWorkMinuteNum(x); }
        else if (k < 0) { while (c < -k) { x--; if (isW(x)) c++; } }
        if (addWorkMinuteNum(s, k) !== x) bad.push(['add', s, k, addWorkMinuteNum(s, k), x]);
        // counting
        const e = s + rnd(9000); let n = 0; for (let y = s; y < e; y++) if (isW(y)) n++;
        if (countWorkMinuteNum(s, e) !== n) bad.push(['count', s, e, countWorkMinuteNum(s, e), n]);
        // finish / start inverse
        const d = 1 + rnd(3000), f = finishMomentFor(s, d);
        if (countWorkMinuteNum(s, f) !== d) bad.push(['finish', s, d, f, countWorkMinuteNum(s, f)]);
        if (nextWorkMinuteNum(startMomentFor(f, d)) !== s) bad.push(['start', s, d, f, startMomentFor(f, d)]);   // (a start exactly at a break's edge is the same working position either side of it)
      }
      return bad.slice(0, 5);
    }""")
    check("300 random cases (holidays, a working Saturday, a Tuesday with its own break): add, count, finish and start all agree with a minute-by-minute walk", res == [], res)
    t0 = ev("() => { const t = performance.now(); let a = nextWorkMinuteNum(dayNumber('2026-09-07') * 1440); for (let i = 0; i < 40; i++) addWorkMinuteNum(a, 14000000); return performance.now() - t; }")
    check("an absurd lag (the 14-million-minute cap) with holidays in the plan is walked, capped, in well under a second", t0 < 1500, t0)
    plan([], {"5": FRI})
    t1 = ev("() => { const t = performance.now(); let a = nextWorkMinuteNum(dayNumber('2026-09-07') * 1440); for (let i = 0; i < 400; i++) addWorkMinuteNum(a, 14000000); return performance.now() - t; }")
    check("...and without holidays whole weeks shift in bulk (400 of them in a few ms)", t1 < 300, t1)

    # ---------------------------------------------------------------- scheduling
    plan([{"name": "A", "s": "2026-09-11", "e": "2026-09-11", "extra": {"startTime": "09:00", "endTime": "13:00"}},
          {"name": "B", "s": "2026-09-11", "e": "2026-09-11", "preds": [["A", "FS", 0]]},
          {"name": "C", "s": "2026-09-14", "e": "2026-09-14"}], {"5": FRI})
    ev("() => { const b = tasks.find(t => t.name === 'B'); applyConstraints(b.id); save(); render(); }")
    check("B (FS after A, which closes Friday at 13:00) starts Monday at 08:00", f("B")[:2] == ["2026-09-14", "08:00"], f("B"))
    ev("() => { const t = tasks.find(x => x.name === 'A'); t.startTime = '09:00'; t.endTime = '10:00'; save(); }")
    check("a task with no times is drawn/described by its own day: Friday's finish shows 13:00, Monday's 17:00", ev("() => [gridDateTimeText('2026-09-11', null, true, true), gridDateTimeText('2026-09-14', null, true, true)]") == ["11.09.2026 13:00", "14.09.2026 17:00"])
    ev("() => { const t = tasks.find(x => x.name === 'C'); t.startDate = '2026-09-11'; t.endDate = '2026-09-11'; t.startTime = t.endTime = null; snapToWorkDays(t); save(); render(); }")
    check("snapping a default-time Friday task leaves its times alone (08:00–13:00 is its own day: no 12:59)", f("C")[1] is None and f("C")[3] is None, f("C"))
    ev("() => { const t = tasks.find(x => x.name === 'C'); t.endTime = '17:00'; snapToWorkDays(t); }")
    check("a Friday finish typed as 17:00 is brought back to Friday's close, 13:00", f("C")[3] == "13:00", f("C"))
    dur = ev("() => durationMinutes(taskMoment(tasks.find(t => t.name === 'C'), 'start'), taskMoment(tasks.find(t => t.name === 'C'), 'end'))")
    check("that Friday task is 5 hours long (300 min)", dur == 300, dur)

    # ---------------------------------------------------------------- normalize
    plan([], {"5": FRI})
    ev("() => { project.workHoursByDay = { 5: { start: '08:00', end: '17:00', breaks: [{ start: '12:00', end: '13:00' }] }, 4: { start: '09:00', end: '15:00', breaks: [{ start: '08:00', end: '09:00' }, { start: '12:00', end: '12:30' }] }, 9: { start: '09:00', end: '10:00' }, x: 1, 3: 'no' }; normalizeData(); }")
    by = ev("() => project.workHoursByDay")
    check("normalizeData keeps the days that differ (Thursday, its break outside the day dropped), drops one equal to the standard day (Friday), a non-weekday and junk", by == {"4": {"start": "09:00", "end": "15:00", "breaks": [{"start": "12:00", "end": "12:30"}]}}, by)
    ev("() => { project.workHoursByDay = [1, 2]; normalizeData(); }")
    check("a non-object is dropped", ev("() => 'workHoursByDay' in project") is False)
    ev("() => { project.workHoursByDay = { 5: { start: '08:00', end: '13:00', breaks: [] } }; project.timeUnit = 'day'; normalizeData(); }")
    check("in a day-mode plan it is dropped, like workHours", ev("() => ['workHoursByDay', 'workHours', 'timeUnit'].some(k => k in project)") is False)

    # ---------------------------------------------------------------- the dialog
    plan([], None)
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open")
    check("with no different days the section is folded away and empty, with an 'Add a different day' control offering all 5 working weekdays", not ev("() => document.getElementById('whDayDetails').open") and pg.locator("#whDayRows .whd-row").count() == 0 and pg.locator("#whDayAddSelect option").count() == 5)
    ev("() => { document.getElementById('whDayDetails').open = true; }")
    pg.select_option("#whDayAddSelect", "5"); pg.click("#whDayAddRow button")
    fri = pg.locator("#whDayRows .whd-row[data-wd='5']")
    check("adding Friday gives it its own row, copied from the standard day (08:00 to 17:00, breaks '12:00-13:00')", fri.count() == 1 and fri.locator(".whd-start").input_value() == "08:00" and fri.locator(".whd-end").input_value() == "17:00" and fri.locator(".whd-breaks").input_value() == "12:00-13:00")
    check("...and Friday no longer offers itself in 'Add a different day' (4 left)", pg.locator("#whDayAddSelect option").count() == 4)
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("saving an added day that is still the standard day stores nothing (it IS the standard day)", ev("() => 'workHoursByDay' in project") is False)
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open")
    check("...and reopening shows no different days again (nothing was saved)", pg.locator("#whDayRows .whd-row").count() == 0)
    ev("() => { document.getElementById('whDayDetails').open = true; }")
    pg.select_option("#whDayAddSelect", "5"); pg.click("#whDayAddRow button")
    fri = pg.locator("#whDayRows .whd-row[data-wd='5']")
    fri.locator(".whd-end").fill("13:00"); fri.locator(".whd-breaks").fill("")
    pg.keyboard.press("Escape")
    check("changing a day and pressing Escape asks before discarding", pg.locator("#confirmModalBg.open").count() == 1)
    pg.click("#confirmModalBg button:has-text('Keep editing')")
    fri.locator(".whd-breaks").fill("12:00-x")
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("an unreadable break is refused with a message and the dialog stays open", "breaks are written like" in toast() and pg.locator("#calendarModalBg.open").count() == 1, toast())
    fri.locator(".whd-breaks").fill("")
    fri.locator(".whd-end").fill("07:00")
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("a day that ends before it starts is refused", "must end after it starts" in toast() and pg.locator("#calendarModalBg.open").count() == 1, toast())
    fri.locator(".whd-end").fill("13:00")
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("saved: Friday 08:00–13:00 with no break, stored under weekday 5", ev("() => project.workHoursByDay") == {"5": FRI}, ev("() => project.workHoursByDay"))
    check("the Schedule menu's hint says one day differs", "1 day differs" in ev("() => precisionSummary()"), ev("() => precisionSummary()"))
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open")
    fri = pg.locator("#whDayRows .whd-row[data-wd='5']")
    check("reopened, the section opens by itself with Friday's own hours; no other day has a row", ev("() => document.getElementById('whDayDetails').open") and fri.locator(".whd-end").input_value() == "13:00" and pg.locator("#whDayRows .whd-row").count() == 1)
    fri.locator(".whd-remove").click()
    check("removing it clears the row", pg.locator("#whDayRows .whd-row").count() == 0)
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("saving with it removed puts Friday back on the standard day", ev("() => 'workHoursByDay' in project") is False)
    ev("() => { project.workHoursByDay = { 5: { start: '08:00', end: '13:00', breaks: [] } }; project.workDays = [1, 2, 3, 4]; normalizeData(); save(); }")
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open"); ev("() => { document.getElementById('whDayDetails').open = true; }")
    check("a stale override for a weekday that is no longer a working day (Friday, now that this plan works Mon–Thu) shows no row, and 'Add a different day' offers only the 4 real working weekdays", pg.locator("#whDayRows .whd-row").count() == 0 and pg.locator("#whDayAddSelect option").count() == 4)
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- Gantt Hours scale and Excel
    plan([{"name": "A", "s": "2026-09-11", "e": "2026-09-11", "extra": {"startTime": "09:00", "endTime": "11:00"}},
          {"name": "B", "s": "2026-09-14", "e": "2026-09-14", "extra": {"startTime": "13:00", "endTime": "15:00"}}], {"5": FRI})
    ev("() => { setView('gantt'); setZoom('hour'); }"); pg.wait_for_timeout(250)
    nonwork = ev("() => [...document.querySelectorAll('#ganttRows .gantt-nonwork')].map(e => [parseFloat(e.style.left), parseFloat(e.style.width)])")
    d0 = ev("() => dateRange.start"); fri_i = ev("() => dayNumber('2026-09-11')") - d0; mon_i = ev("() => dayNumber('2026-09-14')") - d0
    has = lambda day, a, bb: any(abs(l - (day + a / 24) * 480) < 0.01 and abs(w - (bb - a) / 24 * 480) < 0.01 for l, w in nonwork)
    check("Friday's chart is shaded 00–08 and 13–24, with NO lunch band (12–13 is working time)", has(fri_i, 0, 8) and has(fri_i, 13, 24) and not has(fri_i, 12, 13), nonwork[:10])
    check("Monday still has its 12–13 lunch band and closes at 17", has(mon_i, 12, 13) and has(mon_i, 17, 24))
    def export_gantt(name):
        pg.click("#dataMenuBtn"); pg.click("#excelExportItem"); pg.wait_for_selector("#excelModalBg.open")
        with pg.expect_download() as d: pg.click("#excelExportBtn")
        path = os.path.join(TMP, name); d.value.save_as(path)
        return openpyxl.load_workbook(path)["Gantt"]
    ws = export_gantt("wd.xlsx")
    hdr = {c.column: c.value for c in ws[4] if c.value is not None}
    first = min(c for c, v in hdr.items() if isinstance(v, str) and re.fullmatch(r"\d\d", v))
    hours = [hdr[c] for c in sorted(hdr) if c >= first]
    check("the hourly Gantt sheet has Friday's five working hours (08–12), then Monday's eight (08–11, 13–16)", hours == ["08", "09", "10", "11", "12", "08", "09", "10", "11", "13", "14", "15", "16"], hours)

    # ---------------------------------------------------------------- MS Project XML
    plan([{"name": "A", "s": "2026-09-11", "e": "2026-09-11", "extra": {"startTime": "09:30", "endTime": "13:00"}},
          {"name": "B", "s": "2026-09-14", "e": "2026-09-14"}], {"5": FRI})
    xml = ev("() => buildMspdi()")
    fri_x = re.search(r"<WeekDay><DayType>6</DayType><DayWorking>1</DayWorking><WorkingTimes>(.*?)</WorkingTimes>", xml).group(1)
    mon_x = re.search(r"<WeekDay><DayType>2</DayType><DayWorking>1</DayWorking><WorkingTimes>(.*?)</WorkingTimes>", xml).group(1)
    check("the calendar writes each weekday's own working times: Friday one segment 08:00–13:00, Monday two", fri_x.count("<WorkingTime>") == 1 and "<ToTime>13:00:00</ToTime>" in fri_x and mon_x.count("<WorkingTime>") == 2, (fri_x, mon_x))
    check("MinutesPerWeek is the real week (2220), not 5 x the standard day", "<MinutesPerWeek>2220</MinutesPerWeek>" in xml)
    check("a task with no time on the short Friday exports its own 13:00 close; on Monday 17:00", "<Start>2026-09-14T08:00:00</Start><Finish>2026-09-14T17:00:00</Finish>" in xml)
    res = ev("x => { const r = parseMspdi(x); return { tu: r.project.timeUnit, wh: r.project.workHours, by: r.project.workHoursByDay }; }", xml)
    check("importing it back: minute mode (a task starts at 09:30), the standard day is Monday–Thursday's (with lunch), Friday differs", res["tu"] == "minute" and res["wh"] is None and res["by"] == {"5": FRI}, res)
    plan([{"name": "A", "s": "2026-09-11", "e": "2026-09-11"}, {"name": "B", "s": "2026-09-14", "e": "2026-09-14"}], {"5": FRI})
    xml2 = ev("() => buildMspdi()")
    res2 = ev("x => { const r = parseMspdi(x); return { tu: r.project.timeUnit, by: r.project.workHoursByDay, tasks: r.tasks.map(t => [t.startTime, t.endTime]) }; }", xml2)
    check("an ordinary file with a short Friday (every task on its own day's open/close) is NOT switched to minute mode", res2["tu"] is None and res2["by"] is None and all(t == [None, None] for t in res2["tasks"]), res2)

    # ---------------------------------------------------------------- a uniform plan keeps the shortcut and is untouched
    plan([], None)
    check("a plan with no different days is uniform (the O(1) day-bulk path)", ev("() => hoursInfo().uniform") is True)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
