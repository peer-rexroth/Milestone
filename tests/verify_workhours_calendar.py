# -*- coding: utf-8 -*-
"""Phase 1 of minute/hour-level scheduling precision (an explicit user request, "like in MS Project"): the working-HOURS
calendar layer that sits beside the existing whole-day working calendar, only consulted by a plan in project.timeUnit ===
'minute' mode. Tests the pure functions directly (minuteOfDay/hhmmOf/hhmmOk, workWindows/workMinutesPerDay, isWorkMinuteNum,
next/prevWorkMinuteNum, addWorkMinuteNum, countWorkMinuteNum, durationMinutes, finishMomentFor/startMomentFor) with no UI
dependency yet — the same technique verify_calendar.py uses for the day-level equivalents — plus normalizeData()'s cleaning
of project.timeUnit/workHours and the five new per-task time fields, and the MSPDI export's use of project.workHours in
place of its old hardcoded 08:00-12:00/13:00-17:00 literals. day-openness (weekends, holidays) stays entirely owned by the
existing isWorkNum()/holSet — this layer only adds a sub-day constraint on top of it, so a holiday needs no special-case
code of its own here, only a check that it is in fact inherited for free."""
import os, re
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

# 2026-09-07 is a Monday: 07 Mon 08 Tue 09 Wed 10 Thu 11 Fri 12 Sat 13 Sun 14 Mon
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    reset = lambda: ev("() => { delete project.workDays; delete project.holidays; delete project.workHours; delete project.timeUnit; }")
    mn = lambda iso, hm: ev(f"() => dayNumber('{iso}') * 1440 + minuteOfDay('{hm}')")
    hm_of = lambda moment_expr: ev(f"() => {{ const mn = {moment_expr}; return hhmmOf(mn - Math.floor(mn/1440)*1440); }}")
    day_of = lambda moment_expr, base_iso: ev(f"(base) => {{ const mn = {moment_expr}; return Math.floor(mn/1440) - dayNumber(base); }}", base_iso)

    # ---------------------------------------------------------------- minuteOfDay / hhmmOf / hhmmOk
    check("minuteOfDay/hhmmOf round-trip", ev("() => minuteOfDay('09:15')") == 555 and ev("() => hhmmOf(555)") == "09:15")
    check("hhmmOk accepts 00:00..23:59 and rejects garbage/out-of-range", ev("""() => hhmmOk('00:00') && hhmmOk('23:59') && !hhmmOk('24:00') && !hhmmOk('9:15') && !hhmmOk('09:60') && !hhmmOk('garbage') && !hhmmOk(null)"""))

    # ---------------------------------------------------------------- the default calendar (08:00-12:00, 13:00-17:00)
    reset()
    check("default working hours: two windows, 480 working minutes a day", ev("() => JSON.stringify(workWindows())") == "[[480,720],[780,1020]]" and ev("() => workMinutesPerDay()") == 480)
    check("10:00 on a working Monday is a working minute; 12:00 (break start) is not; 13:00 (break end) is", ev("m => isWorkMinuteNum(m)", mn("2026-09-07", "10:00")) is True and ev("m => isWorkMinuteNum(m)", mn("2026-09-07", "12:00")) is False and ev("m => isWorkMinuteNum(m)", mn("2026-09-07", "13:00")) is True)
    check("any time on a Saturday is never a working minute", ev("m => isWorkMinuteNum(m)", mn("2026-09-12", "10:00")) is False)

    # ---------------------------------------------------------------- next/prev across a break, a weekend, and a holiday
    check("nextWorkMinuteNum from inside a break snaps to the break's end", hm_of(f"nextWorkMinuteNum({mn('2026-09-07','12:30')})") == "13:00")
    check("nextWorkMinuteNum from exactly closing time (17:00, the exclusive end) rolls to next working day's opening", hm_of(f"nextWorkMinuteNum({mn('2026-09-11','17:00')})") == "08:00" and day_of(f"nextWorkMinuteNum({mn('2026-09-11','17:00')})", "2026-09-11") == 3)
    check("prevWorkMinuteNum from inside a break snaps to the break's start (the last working minute before it)", hm_of(f"prevWorkMinuteNum({mn('2026-09-07','12:30')})") == "11:59")
    check("prevWorkMinuteNum from before opening (07:00) rolls back to the previous working day's close", hm_of(f"prevWorkMinuteNum({mn('2026-09-07','07:00')})") == "16:59" and day_of(f"prevWorkMinuteNum({mn('2026-09-07','07:00')})", "2026-09-07") == -3)
    ev("() => { project.holidays = [{ date: '2026-09-08' }]; }")   # Tuesday off
    check("nextWorkMinuteNum skips a holiday entirely, landing on the day after it", hm_of(f"nextWorkMinuteNum({mn('2026-09-08','10:00')})") == "08:00" and day_of(f"nextWorkMinuteNum({mn('2026-09-08','10:00')})", "2026-09-08") == 1)
    check("...a holiday Monday is never a working minute at any time of day", ev("m => isWorkMinuteNum(m)", mn("2026-09-08", "10:00")) is False)
    reset()

    # ---------------------------------------------------------------- addWorkMinuteNum: same segment, across a break, across days/weekends, and a brute-force cross-check
    check("adding 60 working minutes within one segment: 09:00 -> 10:00", hm_of(f"addWorkMinuteNum({mn('2026-09-07','09:00')}, 60)") == "10:00")
    check("adding working minutes across the lunch break: 11:00 + 120 -> 14:00 (the break itself doesn't count)", hm_of(f"addWorkMinuteNum({mn('2026-09-07','11:00')}, 120)") == "14:00")
    check("adding working minutes across a weekend: Friday 16:00 + 120 -> Monday 09:00", hm_of(f"addWorkMinuteNum({mn('2026-09-11','16:00')}, 120)") == "09:00" and day_of(f"addWorkMinuteNum({mn('2026-09-11','16:00')}, 120)", "2026-09-11") == 3)
    check("subtracting (a lead) works the same way in reverse: Monday 09:00 - 120 -> Friday 16:00", hm_of(f"addWorkMinuteNum({mn('2026-09-14','09:00')}, -120)") == "16:00" and day_of(f"addWorkMinuteNum({mn('2026-09-14','09:00')}, -120)", "2026-09-14") == -3)
    # a brute-force, one-working-minute-at-a-time reference, to cross-check the O(1) bulk-day-shortcut implementation over a
    # range large enough to span several weeks (2,000 working minutes ≈ 4 working weeks at 480/day)
    brute = ev("""() => {
        let mn = dayNumber('2026-09-07') * 1440 + 540;   // Monday 09:00
        let left = 2000;
        while (left > 0) { mn++; if (isWorkMinuteNum(mn)) left--; }
        return mn;
    }""")
    fast = ev("() => addWorkMinuteNum(dayNumber('2026-09-07') * 1440 + 540, 2000)")
    check("addWorkMinuteNum's O(1) bulk-day shortcut agrees with a brute-force minute-by-minute walk over ~4 working weeks", fast == brute, (fast, brute))

    # ---------------------------------------------------------------- countWorkMinuteNum / durationMinutes
    check("countWorkMinuteNum same day, same segment: [09:00,11:00) = 120", ev(f"() => countWorkMinuteNum({mn('2026-09-07','09:00')}, {mn('2026-09-07','11:00')})") == 120)
    check("countWorkMinuteNum same day across the break: [11:00,14:00) = 120 (not 180)", ev(f"() => countWorkMinuteNum({mn('2026-09-07','11:00')}, {mn('2026-09-07','14:00')})") == 120)
    check("countWorkMinuteNum across a weekend: Friday 16:00 to Monday 09:00 = 120", ev(f"() => countWorkMinuteNum({mn('2026-09-11','16:00')}, {mn('2026-09-14','09:00')})") == 120)
    check("countWorkMinuteNum with b <= a is 0", ev(f"() => countWorkMinuteNum({mn('2026-09-07','11:00')}, {mn('2026-09-07','11:00')})") == 0)
    check("durationMinutes is never less than 1, even across two moments with no working time between them", ev(f"() => durationMinutes({mn('2026-09-12','10:00')}, {mn('2026-09-12','10:30')})") == 1, "a Saturday interval should floor to 1, not 0")

    # ---------------------------------------------------------------- finishMomentFor / startMomentFor (inverses of each other, moment-space mirror of finishFor/startFor)
    check("finishMomentFor(09:00, 120) = 11:00", hm_of(f"finishMomentFor({mn('2026-09-07','09:00')}, 120)") == "11:00")
    check("finishMomentFor across the break: (11:00, 120) = 14:00", hm_of(f"finishMomentFor({mn('2026-09-07','11:00')}, 120)") == "14:00")
    check("startMomentFor is finishMomentFor's inverse: startMomentFor(14:00, 120) = 11:00", hm_of(f"startMomentFor({mn('2026-09-07','14:00')}, 120)") == "11:00")
    check("shiftWorkMinute(mn, 0)-equivalent (finish immediately at the given moment's own next working minute) 12:30 + smallest step lands at 13:00 then holds", hm_of(f"shiftWorkMinute({mn('2026-09-07','12:30')}, 0)") == "13:00")

    # ---------------------------------------------------------------- lag/duration caps
    check("addWorkMinuteNum clamps an absurd k rather than looping unboundedly", (lambda v: v is not None and abs(v) < 10**15)(ev(f"() => addWorkMinuteNum({mn('2026-09-07','09:00')}, 999999999999)")))
    check("MAX_DURATION_MINUTES / MAX_LAG_MINUTES are day-caps scaled to minutes", ev("() => MAX_DURATION_MINUTES === MAX_DURATION_DAYS * 1440 && MAX_LAG_MINUTES === MAX_LAG_DAYS * 1440"))

    # ---------------------------------------------------------------- normalizeData(): project.timeUnit / project.workHours
    reset()
    r = ev("""() => {
        const out = {};
        project.timeUnit = 'minute'; project.workHours = { start: '09:00', end: '18:00', breaks: [{start:'12:30', end:'13:30'}] };
        normalizeData();
        out.custom = JSON.parse(JSON.stringify(project.workHours));
        project.workHours = { start: '08:00', end: '17:00', breaks: [{start:'12:00', end:'13:00'}] };   // exactly the default
        normalizeData();
        out.defaultDeleted = project.workHours === undefined;
        project.workHours = { start: 'garbage', end: '17:00', breaks: [] };
        normalizeData();
        out.badStartFallsBack = project.workHours.start === '08:00';
        project.workHours = { start: '09:00', end: '10:00', breaks: [{start: '09:30', end: '09:15'}, {start: '08:00', end: '23:00'}] };  // an inverted break and one entirely outside [start,end)
        normalizeData();
        out.badBreaksDropped = JSON.stringify(project.workHours.breaks) === '[]';
        project.timeUnit = 'nonsense';
        normalizeData();
        out.nonMinuteDeletesWorkHours = project.timeUnit === undefined && project.workHours === undefined;
        return out;
    }""")
    check("a custom workHours survives normalizeData() unchanged", r["custom"] == {"start": "09:00", "end": "18:00", "breaks": [{"start": "12:30", "end": "13:30"}]}, r["custom"])
    check("a workHours exactly equal to the default is not stored (absent = default, same convention as workDays)", r["defaultDeleted"])
    check("an invalid start time falls back to the default start", r["badStartFallsBack"])
    check("an inverted or out-of-range break is dropped", r["badBreaksDropped"])
    check("any timeUnit other than 'minute' deletes both timeUnit and workHours", r["nonMinuteDeletesWorkHours"])
    reset()

    # ---------------------------------------------------------------- normalizeData(): the five per-task time fields
    r2 = ev("""() => {
        const out = {};
        addTask();
        const t = tasks[tasks.length - 1];
        out.defaultNull = t.startTime === null && t.endTime === null && t.actualStartTime === null && t.actualFinishTime === null && t.constraintTime === null;
        project.timeUnit = 'minute';
        t.startTime = '09:15'; t.endTime = '17:45'; t.actualStart = t.startDate; t.actualStartTime = '09:20';
        normalizeData();
        out.survivesInMinuteMode = t.startTime === '09:15' && t.endTime === '17:45' && t.actualStartTime === '09:20';
        t.startTime = 'not a time';
        normalizeData();
        out.garbageRejected = t.startTime === null;
        t.milestone = true; t.startTime = '09:15'; t.endTime = '11:00';
        normalizeData();
        out.milestoneEndTimeFollowsStart = t.endTime === '09:15';
        t.actualStart = null; t.actualStartTime = '09:20';
        normalizeData();
        out.actualTimeNulledWithoutActualDate = t.actualStartTime === null;
        project.timeUnit = 'day';
        t.startTime = '09:15';
        normalizeData();
        out.dayModeNullsEverything = t.startTime === null;
        return out;
    }""")
    check("a freshly added task has every new time field null", r2["defaultNull"])
    check("valid HH:MM time fields survive normalizeData() in a minute-mode plan", r2["survivesInMinuteMode"])
    check("a garbage time field is nulled, not merely left alone", r2["garbageRejected"])
    check("a milestone's endTime always follows its startTime, same as its dates", r2["milestoneEndTimeFollowsStart"])
    check("actualStartTime is nulled whenever actualStart itself is cleared", r2["actualTimeNulledWithoutActualDate"])
    check("switching a plan back to day mode nulls every task's time fields on the next normalizeData()", r2["dayModeNullsEverything"])
    reset()

    # ---------------------------------------------------------------- MSPDI export reads project.workHours (Phase 1's one wired call site)
    r3 = ev("""() => {
        tasks.length = 0; addTask();
        project.timeUnit = 'minute'; project.workHours = { start: '09:00', end: '18:00', breaks: [{start:'12:30', end:'13:30'}] };
        normalizeData();
        return buildMspdi();
    }""")
    check("MSPDI export's DefaultStartTime/DefaultFinishTime/MinutesPerDay reflect a custom project.workHours", "<DefaultStartTime>09:00:00</DefaultStartTime>" in r3 and "<DefaultFinishTime>18:00:00</DefaultFinishTime>" in r3 and "<MinutesPerDay>480</MinutesPerDay>" in r3, r3[:400])
    check("...and the <WorkingTimes> block lists the real two windows around the break", "<FromTime>09:00:00</FromTime><ToTime>12:30:00</ToTime>" in r3 and "<FromTime>13:30:00</FromTime><ToTime>18:00:00</ToTime>" in r3)
    r4 = ev("""() => { tasks.length = 0; addTask(); delete project.timeUnit; delete project.workHours; normalizeData(); return buildMspdi(); }""")
    check("a day-mode plan's export keeps the original hardcoded 08:00/12:00/13:00/17:00 (byte-identical default)", "<DefaultStartTime>08:00:00</DefaultStartTime>" in r4 and "<FromTime>08:00:00</FromTime><ToTime>12:00:00</ToTime>" in r4 and "<FromTime>13:00:00</FromTime><ToTime>17:00:00</ToTime>" in r4)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
