# -*- coding: utf-8 -*-
"""Minute-mode scheduling precision, PRINT / PDF. A minute-mode plan prints the time of day in its Start/Finish cells (a group's
rolled-up dates stay date-only, like the grid), its Duration in working time ("2.5 hrs", "0 min" for a milestone; a group's stays in
days) under a "Duration" heading, in wider columns; and the timeline can be an Hours scale — chosen in the dialog, or automatic when
the tasks span three days or fewer — where a day is the top tier over its hours, bars/milestones/baselines sit at their real
instants, each day's hours off (nights, the lunch break, a short Friday, days off) are shaded and today's line is at the time of day.
The Week/Month/Quarter scales stay whole-day. A day-mode plan prints exactly as before, and can't choose Hours."""
import os, re
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
    build = lambda opts=None: ev("""(o) => { const d = Object.assign(printDefaults(), { cols: ['id', 'name', 'start', 'end', 'duration'] }, o || {}); const b = buildPrintPages(d);
        return { svg: b.pages, unit: b.unit, range: b.range, chart: b.chart }; }""", opts)
    def plan(specs, minute=True, by=None):
        ev("m => { if (m) { project.timeUnit = 'minute'; normalizeData(); } else { delete project.timeUnit; delete project.workHours; delete project.lagUnit; } }", minute)
        ev("by => { if (by) project.workHoursByDay = by; else delete project.workHoursByDay; }", by)
        ev(SEED, specs)
        ev("() => { normalizeData(); save(); render(); }")
    day0 = ev("() => dayNumber('2026-09-07')")
    A = {"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "11:30"}}
    B = {"name": "B", "s": "2026-09-08", "e": "2026-09-08", "extra": {"startTime": "13:00", "endTime": "15:00"}}
    M = {"name": "Ms", "s": "2026-09-08", "e": "2026-09-08", "extra": {"milestone": True, "startTime": "10:00", "endTime": "10:00"}}
    bars = lambda svg: [(float(x), float(w)) for x, w in re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="[\d.]+" rx="1.5" fill="#[0-9a-f]{6}" stroke=', svg)]

    # ---------------------------------------------------------------- the list cells
    plan([A, B, M])
    r = build()
    svg = r["svg"][0]
    check("the list prints the time of day: '07.09.2026 09:00' and '07.09.2026 11:30'", "07.09.2026 09:00" in svg and "07.09.2026 11:30" in svg)
    check("...the duration in working time ('2.5 hrs', '2 hrs'; the milestone '0 min') under a 'Duration' heading, not 'Days'", "2.5 hrs" in svg and "2 hrs" in svg and "0 min" in svg and ">Duration<" in svg and ">Days<" not in svg)
    plan([{"name": "G", "s": "2026-09-07", "e": "2026-09-08"}, dict(A, parent="G"), dict(B, parent="G")])
    svg = build()["svg"][0]
    check("a group's rolled-up dates stay date-only and its duration is in days", re.search(r">07\.09\.2026<", svg) is not None and "2 days" in svg, "")
    ev("() => tasks.find(t => t.name === 'G').taskMode = 'manual'")
    plan([A])
    ev("() => { const t = tasks[0]; t.startTime = t.endTime = null; save(); }")
    svg = build()["svg"][0]
    check("a task with no time of its own prints its working day's open and close (08:00, 17:00)", "07.09.2026 08:00" in svg and "07.09.2026 17:00" in svg)

    # ---------------------------------------------------------------- the Hours scale
    plan([A, B, M])
    r = build()
    check("a plan spanning two days prints on the Hours scale automatically", r["unit"] == "hour", r["unit"])
    svg = r["svg"][0]; ch = r["chart"]
    check("the range is whole days — no week of padding (Mon 07.09 to Tue 08.09)", r["range"] == [day0, day0 + 1], r["range"])
    hrs = re.findall(r'font-size="8" fill="#1F2328">(\d\d)</text>', svg)
    check("the top tier is the day ('Mon 07.09.2026'), the bottom its hours — every second one here, so each label has room ('08', '14'; not '13')", "Mon 07.09.2026" in svg and "Tue 08.09.2026" in svg and "08" in hrs and "14" in hrs and "13" not in hrs, hrs[:12])
    a_bar = bars(svg)[0]
    exp_l = ch["cx0"] + (540 / 1440) * ch["pxd"]; exp_w = 150 / 1440 * ch["pxd"]
    check("A's bar starts at 09:00 and is 150 minutes long", abs(a_bar[0] - exp_l) < 0.05 and abs(a_bar[1] - exp_w) < 0.05, (a_bar, exp_l, exp_w))
    b_bar = bars(svg)[1]
    check("B's bar (Tuesday 13:00–15:00) sits on Tuesday at 13:00", abs(b_bar[0] - (ch["cx0"] + (1 + 780 / 1440) * ch["pxd"])) < 0.05 and abs(b_bar[1] - 120 / 1440 * ch["pxd"]) < 0.05, b_bar)
    ms = re.search(r'<polygon points="([\d.]+),', svg)
    check("the milestone (Tuesday 10:00) is at its own instant", ms and abs(float(ms.group(1)) - (ch["cx0"] + (1 + 600 / 1440) * ch["pxd"])) < 0.05, ms.group(1) if ms else None)
    shade = [(float(x), float(w)) for x, w in re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="[\d.]+" fill="#E6E9ED" opacity="0.55"/>', svg)]
    has = lambda day, a, bb: any(abs(x - (ch["cx0"] + (day + a / 24) * ch["pxd"])) < 0.05 and abs(w - (bb - a) / 24 * ch["pxd"]) < 0.05 for x, w in shade)
    check("the hours off are shaded: 00–08, the 12–13 lunch break and 17–24 on both days", all(has(d, a, bb) for d in (0, 1) for a, bb in ((0, 8), (12, 13), (17, 24))), shade[:6])
    check("with 'Shade days off' unticked nothing is shaded", 'opacity="0.55"' not in build({"shade": False})["svg"][0])
    check("with the scale set to Hours a longer plan gets it too, labelled every few hours", (lambda rr: rr["unit"] == "hour" and len(re.findall(r">(00|06|12|18)<", rr["svg"][0])) > 0)(build({"scale": "hour", "range": "custom", "from": "2026-09-07", "to": "2026-09-13"})))
    check("...and on the Week scale it prints whole days (its bar is a day cell wide, the times only in the list)", (lambda rr: rr["unit"] == "week" and "07.09.2026 09:00" in rr["svg"][0])(build({"scale": "week"})))
    now = ev("() => { const n = new Date(); return [dayNumber(todayStr()), (n.getHours() * 60 + n.getMinutes()) / 1440]; }")
    plan([dict(A, s="2026-09-25", e="2026-09-25")])
    ev("() => { const t = tasks[0]; t.startDate = t.endDate = todayStr(); save(); }")
    r = build(); ch = r["chart"]; svg = r["svg"][0]
    line = re.search(r'<line x1="([\d.]+)" y1="[\d.]+" x2="[\d.]+" y2="[\d.]+" stroke="#CF222E" stroke-width="0.8" stroke-dasharray="3 2"/>', svg)
    exp = ev("(c) => { const n = new Date(); return c.cx0 + (dayNumber(todayStr()) - c.d0 + (n.getHours() * 60 + n.getMinutes()) / 1440) * c.pxd; }", ch)
    check("today's line is at the current time of day on the Hours scale", line and abs(float(line.group(1)) - exp) < 0.6, (line.group(1) if line else None, exp))

    # ---------------------------------------------------------------- baseline bar
    plan([A])
    ev("() => { applyBaselineChange(0, 'all', false); const t = tasks[0]; t.startTime = '10:00'; t.endTime = '12:00'; save(); }")
    r = build({"baseline": True}); ch = r["chart"]
    bl = re.search(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="2.2" fill="#8C959F"/>', r["svg"][0])
    check("the baseline bar keeps the baseline's own 09:00–11:30, not the moved task's", bl and abs(float(bl.group(1)) - (ch["cx0"] + 540 / 1440 * ch["pxd"])) < 0.05 and abs(float(bl.group(2)) - 150 / 1440 * ch["pxd"]) < 0.05, bl.groups() if bl else None)

    # ---------------------------------------------------------------- a short Friday
    plan([{"name": "F", "s": "2026-09-11", "e": "2026-09-11", "extra": {"startTime": "09:00", "endTime": "12:00"}}], by={"5": {"start": "08:00", "end": "13:00", "breaks": []}})
    r = build({"scale": "hour", "range": "custom", "from": "2026-09-11", "to": "2026-09-11"}); ch = r["chart"]
    shade = [(float(x), float(w)) for x, w in re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="[\d.]+" fill="#E6E9ED" opacity="0.55"/>', r["svg"][0])]
    has = lambda a, bb: any(abs(x - (ch["cx0"] + a / 24 * ch["pxd"])) < 0.05 and abs(w - (bb - a) / 24 * ch["pxd"]) < 0.05 for x, w in shade)
    check("a short Friday's page is shaded 00–08 and 13–24, with no lunch band", has(0, 8) and has(13, 24) and not has(12, 13), shade)
    check("its finish prints 12:00 and a default-time task there would print Friday's own close", "11.09.2026 12:00" in r["svg"][0])

    # ---------------------------------------------------------------- day mode is unchanged
    plan([A, B], minute=False)
    r = build()
    check("a day-mode plan prints on the Week scale, dates only, a 'Days' heading and whole-day durations", r["unit"] == "week" and "07.09.2026 09:00" not in r["svg"][0] and ">Days<" in r["svg"][0] and ">Duration<" not in r["svg"][0])
    check("...and cannot choose Hours (asking for it falls back to the automatic scale)", build({"scale": "hour"})["unit"] == "week")

    # ---------------------------------------------------------------- the dialog
    plan([A, B, M])
    ev("() => openPrintModal()"); pg.wait_for_selector("#printModalBg.open"); pg.wait_for_timeout(300)
    check("the Timescale list offers Hours in a minute-mode plan", not ev("() => document.querySelector('#printScale option[value=hour]').hidden"))
    check("...the duration tick box is called 'Duration'", "Duration" in pg.inner_text("#printCol-duration >> xpath=..") and "Days" not in pg.inner_text("#printCol-duration >> xpath=.."))
    pg.select_option("#printScale", "hour"); pg.wait_for_timeout(300)
    check("choosing Hours redraws the preview on that scale", ev("() => printBuilt.unit") == "hour" and pg.locator("#printPreview svg, .print-preview svg, #printPageWrap svg").count() >= 1)
    check("an unticked Duration column drops out of the pages", (lambda: (pg.uncheck("#printCol-duration"), pg.wait_for_timeout(300), ">Duration<" not in ev("() => printBuilt.pages[0]"))[2])())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    plan([A, B], minute=False)
    ev("() => openPrintModal()"); pg.wait_for_selector("#printModalBg.open"); pg.wait_for_timeout(200)
    check("in a day-mode plan the option is hidden and the box says 'Days'", ev("() => document.querySelector('#printScale option[value=hour]').hidden") and "Days" in pg.inner_text("#printCol-duration >> xpath=.."))
    pg.keyboard.press("Escape")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
