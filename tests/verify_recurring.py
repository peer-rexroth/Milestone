# -*- coding: utf-8 -*-
"""Recurring tasks: the dialog, the patterns (daily / working days / weekly / monthly / yearly, count or end date), days off,
the summary with its occurrences, changing the pattern (started occurrences kept), undo, data cleaning. See "Recurring tasks"
in CLAUDE.md."""
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
    ev("""() => { historyCoalesceMs = 0; project.workDays = [1,2,3,4,5]; tasks.length = 0;
      tasks.push({ id: 'k', name: 'Kickoff', parentId: null, order: 0, startDate: '2026-10-05', endDate: '2026-10-06', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
      normalizeData(); save(); setSelection(['k']); render(); resetHistory(); }""")
    dates = lambda r: ev("r => recurrenceDates(cleanRecurrence(r)).dates", r)

    # ---------------------------------------------------------------- the patterns
    check("weekly on Monday, 4 times", dates({"freq": "weekly", "every": 1, "days": [1], "start": "2026-10-05", "count": 4}) == ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"])
    check("every 2 weeks on Tue and Thu, until a date", dates({"freq": "weekly", "every": 2, "days": [2, 4], "start": "2026-10-05", "until": "2026-10-31"}) == ["2026-10-06", "2026-10-08", "2026-10-20", "2026-10-22"])
    check("daily, every day: a weekend day moves to Monday and counts once", dates({"freq": "daily", "every": 1, "start": "2026-10-09", "count": 4}) == ["2026-10-09", "2026-10-12"])
    check("daily on working days only", dates({"freq": "daily", "every": 1, "workdays": True, "start": "2026-10-09", "count": 3}) == ["2026-10-09", "2026-10-12", "2026-10-13"])
    check("monthly on day 31: the last day of a shorter month, a weekend moved to Monday (31.01 Sat → 02.02, 28.02 Sat → 02.03, 31.03)", dates({"freq": "monthly", "every": 1, "monthDay": 31, "start": "2026-01-01", "count": 3}) == ["2026-02-02", "2026-03-02", "2026-03-31"], dates({"freq": "monthly", "every": 1, "monthDay": 31, "start": "2026-01-01", "count": 3}))
    check("yearly on the start date (29 Feb → 28 Feb, then the next working day)", dates({"freq": "yearly", "every": 1, "start": "2028-02-29", "count": 2})[0] == "2028-02-29" and dates({"freq": "yearly", "every": 1, "start": "2028-02-29", "count": 2})[1] == "2029-02-28")
    check("a count is capped at 500", len(dates({"freq": "daily", "every": 1, "start": "2026-01-01", "count": 9999})) <= 500)
    check("the summary text reads naturally", ev("() => recurrenceSummary(cleanRecurrence({ freq: 'weekly', every: 1, days: [1, 3], start: '2026-10-05', count: 12 }))") == "Weekly on Mon, Wed, 12 times")

    # ---------------------------------------------------------------- the dialog
    pg.click("#addMenuBtn"); pg.click("#addRecurBtn"); pg.wait_for_timeout(150)
    check("Add menu → Recurring task… opens the dialog", pg.locator("#recurModalBg.open").count() == 1 and pg.inner_text("#recurOkBtn") == "Create")
    pg.fill("#recurName", "Weekly status meeting")
    ev("() => { const s = document.getElementById('recurStart'); s.value = '2026-10-05'; s.dispatchEvent(new Event('change', { bubbles: true })); }")
    ev("() => { for (const i of document.querySelectorAll('#recurDays input')) i.checked = i.value === '1'; }")
    pg.fill("#recurCount", "12"); pg.locator("#recurCount").dispatch_event("input"); pg.wait_for_timeout(80)
    check("the preview names the occurrences and their span", pg.inner_text("#recurPreview").startswith("12 occurrences: 05.10.2026 – 21.12.2026"), pg.inner_text("#recurPreview"))
    ev("() => { for (const i of document.querySelectorAll('#recurDays input')) i.checked = false; document.getElementById('recurDays').dispatchEvent(new Event('change', { bubbles: true })); }")
    check("no weekday ticked: says so, Create is off", "weekday" in pg.inner_text("#recurPreview") and pg.is_disabled("#recurOkBtn"))
    ev("() => { document.querySelector('#recurDays input[value=\"1\"]').checked = true; document.getElementById('recurDays').dispatchEvent(new Event('change', { bubbles: true })); }")
    pg.click("#recurOkBtn"); pg.wait_for_timeout(200)
    s = ev("() => { const s = tasks.find(t => t.recurrence); const k = childrenOf(s.id); return { name: s.name, parent: s.parentId, order: s.order, n: k.length, first: [k[0].name, k[0].startDate, k[0].endDate, k[0].constraintType, k[0].constraintDate, k[0].taskMode], last: [k[11].name, k[11].startDate] }; }")
    check("Create makes a summary with 12 occurrences, below the selected task", s["n"] == 12 and s["name"] == "Weekly status meeting" and s["parent"] is None and s["order"] == 1, s)
    check("...each an Auto task pinned to its date (Start No Earlier Than), 1 day, numbered", s["first"] == ["Weekly status meeting 1", "2026-10-05", "2026-10-05", "SNET", "2026-10-05", "auto"] and s["last"] == ["Weekly status meeting 12", "2026-12-21"], s)
    check("the summary shows a ↻ icon with the pattern as its tooltip", "Weekly on Mon, 12 times" in ev("() => document.querySelector('#gridRows .recur-ind').title"))
    check("one Undo takes it all back", (ev("() => historyUndo()"), ev("() => tasks.length"))[1] == 1)
    ev("() => historyRedo()")
    sid = ev("() => tasks.find(t => t.recurrence).id")

    # ---------------------------------------------------------------- changing it
    ev("(id) => { const k = childrenOf(id); k[0].actualStart = k[0].startDate; k[0].progress = 50; save(); render(); }", sid)
    pg.click(f"#gridRows .grid-row[data-id='{sid}'] .recur-ind"); pg.wait_for_timeout(150)
    check("the ↻ icon reopens it, filled in, as 'Change recurring task'", pg.inner_text("#recurTitle") == "Change recurring task" and pg.input_value("#recurName") == "Weekly status meeting" and not pg.is_hidden("#recurKeepNote"))
    ev("() => { document.querySelector('input[name=recurFreq][value=daily]').checked = true; document.getElementById('recurWorkdays').checked = true; document.getElementById('recurEndCount').checked = true; }")
    pg.fill("#recurCount", "5"); pg.locator("#recurCount").dispatch_event("input"); pg.wait_for_timeout(60)
    pg.fill("#recurName", "Daily stand-up"); pg.click("#recurOkBtn"); pg.wait_for_timeout(200)
    k = ev("(id) => childrenOf(id).map(t => [t.name, t.startDate, t.progress])", sid)
    check("a new pattern makes the occurrences again — the started one is kept, not duplicated", len(k) == 5 and k[0] == ["Daily stand-up 1", "2026-10-05", 50] and [x[1] for x in k] == ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"], k)
    check("...renamed throughout, the pattern stored on the summary", ev("(id) => byId(id).name", sid) == "Daily stand-up" and ev("(id) => byId(id).recurrence.freq", sid) == "daily")
    pg.click(f"#gridRows .grid-row[data-id='{sid}']", button="right", position={"x": 300, "y": 16}); pg.wait_for_timeout(80)
    check("the right-click menu offers Change recurrence…", pg.locator("#rowMenu.open .dropdown-item:has-text('Change recurrence')").count() == 1)
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- milestones, minute mode, data
    ev("() => { setSelection([]); openRecurModal(); }"); pg.fill("#recurName", "Report due"); pg.fill("#recurDur", "0")
    ev("() => { document.querySelector('input[name=recurFreq][value=monthly]').checked = true; const s = document.getElementById('recurStart'); s.value = '2026-10-01'; document.getElementById('recurMonthDay').value = 15; }")
    pg.fill("#recurCount", "3"); pg.locator("#recurCount").dispatch_event("input"); pg.click("#recurOkBtn"); pg.wait_for_timeout(150)
    m = ev("() => { const s = tasks.find(t => t.recurrence && t.name === 'Report due'); return childrenOf(s.id).map(t => [t.milestone, t.startDate]); }")
    check("duration 0 makes milestones (monthly on the 15th)", m == [[True, "2026-10-15"], [True, "2026-11-16"], [True, "2026-12-15"]], m)
    check("a recurrence on a task without sub-tasks is dropped by the cleaner", ev("() => { const t = tasks.find(x => x.id === 'k'); t.recurrence = { freq: 'weekly', start: '2026-10-05', count: 3 }; normalizeData(); return !('recurrence' in t); }"))
    check("garbage in a stored pattern is cleaned (every clamped, a count default)", ev("() => { const r = cleanRecurrence({ freq: 'weekly', every: 500, days: [9, 1, 'x'], start: '2026-10-05' }); return r.every === 99 && JSON.stringify(r.days) === '[1]' && r.count === 1; }"))
    ev("() => { project.timeUnit = 'minute'; save(); render(); setSelection([]); openRecurModal(); }")
    pg.fill("#recurName", "Sync"); pg.fill("#recurDur", "30m")
    ev("() => { const s = document.getElementById('recurStart'); s.value = '2026-10-05'; document.getElementById('recurTime').value = '14:00'; }")
    pg.fill("#recurCount", "2"); pg.locator("#recurCount").dispatch_event("input"); pg.click("#recurOkBtn"); pg.wait_for_timeout(150)
    mt = ev("() => { const s = tasks.find(t => t.name === 'Sync'); return childrenOf(s.id).map(t => [t.startDate, t.startTime, t.endTime]); }")
    check("in an Hours & minutes plan: a time of day and a minute duration", mt[0] == ["2026-10-05", "14:00", "14:30"], mt)
    check("no console errors", not errors, errors[:5])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
