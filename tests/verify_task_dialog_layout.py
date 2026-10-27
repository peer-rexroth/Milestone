# -*- coding: utf-8 -*-
"""The task dialog's General tab as a grouped inspector (ClearDesk's panel): tinted groups of rows, label left and value right, no boxed fields, switches
for the on / off choices, read-only values as plain text; the body scrolls inside a dialog that always fits the window. See "Task dialog" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """(minute) => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.timeUnit; if (minute) project.timeUnit = 'minute'; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 40, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }, x || {});
  tasks.push(mk('a', 'Discovery', '2030-03-04', '2030-03-08', { resource: 'Anna' }), mk('b', 'Build', '2030-03-11', '2030-03-15', { predecessors: [{ id: 'a', type: 'FS', lag: 0 }] }), mk('g', 'Phase', '2030-03-04', '2030-03-15'), mk('c', 'Child', '2030-03-04', '2030-03-08', { parentId: 'g' }), mk('m', 'Launch', '2030-03-18', '2030-03-18', { milestone: true }));
  normalizeData(); save(); setSelection([]); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED, False)
    def open_task(i):
        ev("(i) => openTaskModal(i)", i); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(350)
    Y = lambda sel: ev("(s) => document.querySelector(s).getBoundingClientRect().top", sel)
    open_task("b")
    top = lambda sel: ev("(s) => document.querySelector(s).getBoundingClientRect().top", sel)
    groups = ev("() => [...document.querySelectorAll('#taskTabGeneral > .tgrp')].map(g => ({ top: g.getBoundingClientRect().top, rows: g.querySelectorAll('.trow').length, bg: getComputedStyle(g).backgroundColor }))")
    check("the General tab is five tinted groups (task | schedule | type | rules and look | predecessors) in that order", len(groups) == 5 and all(groups[i]["top"] < groups[i + 1]["top"] for i in range(4)) and all(g["bg"] != "rgba(0, 0, 0, 0)" for g in groups), groups)
    check("the fields run Name, Mode, Resource, Milestone down one column, then Start … Status", top("#taskNameInput") < top("#taskModeInput") < top("#taskResourceInput") < top("#taskMilestoneInput") < top("#taskStartInput") < top("#taskEndInput") < top("#taskDurationInput") < top("#taskProgressInput") < top("#taskRemainingInfo") < top("#taskStatusInfo"))
    check("...then Type, Effort-Driven, Work, then Constraint, Deadline, Actual Start, Actual Finish, Color, then the predecessors", top("#taskTypeInput") < top("#effortDrivenInput") < top("#taskWorkInput") < top("#taskConstraintTypeInput") < top("#taskDeadlineInput") < top("#taskActualStartInput") < top("#taskActualFinishInput") < top("#taskColorSwatches") < top("#predecessorRows"))
    boxed = ev("() => [...document.querySelectorAll('#taskTabGeneral .trow :is(input:not(.tsw):not(.dt-native), select)')].filter(e => e.offsetParent && (parseFloat(getComputedStyle(e).borderTopWidth) > 0)).map(e => e.id || e.className)")
    check("no field is a box: every input and select in a row has no border", boxed == [], boxed)
    check("the read-only values (Remaining, Status) are plain text: no dashed frame", ev("() => ['taskRemainingInfo','taskStatusInfo'].every(i => getComputedStyle(document.getElementById(i)).borderTopStyle === 'none')"))
    sw = ev("() => ['taskMilestoneInput','effortDrivenInput'].map(i => { const c = getComputedStyle(document.getElementById(i)); return [c.appearance, Math.round(parseFloat(c.width)), c.borderRadius]; })")
    check("Milestone and Effort-Driven are switches (38 x 22, round), not checkboxes", all(s[0] == "none" and s[1] == 38 for s in sw), sw)
    pg.check("#taskMilestoneInput"); pg.wait_for_timeout(100)
    check("a switch turns on with the accent colour", ev("() => getComputedStyle(document.getElementById('taskMilestoneInput')).backgroundColor") != ev("() => getComputedStyle(document.getElementById('effortDrivenInput')).backgroundColor"))
    pg.uncheck("#taskMilestoneInput"); pg.wait_for_timeout(100)
    right = ev("() => ['taskResourceInput','taskWorkInput'].map(i => Math.round(document.getElementById(i).getBoundingClientRect().right))")
    check("values sit at the right end of their rows (Resource and Work share one right edge)", max(right) - min(right) <= 4, right)
    check("the tabs are one capsule with the current tab raised", ev("() => { const t = document.querySelector('#taskModalInner .modal-tabs'), a = document.querySelector('#taskModalInner .modal-tab.active'); return parseFloat(getComputedStyle(t).borderRadius) > 20 && getComputedStyle(a).backgroundColor !== 'rgba(0, 0, 0, 0)'; }"))
    check("the duration unit follows the number ('1 day', '2 days')", ev("() => document.getElementById('taskDurationUnit').textContent") in ("day", "days") and "Duration" == pg.inner_text("#taskDurationLabel"))
    pg.fill("#taskDurationInput", "1"); pg.dispatch_event("#taskDurationInput", "input")
    u1 = pg.inner_text("#taskDurationUnit"); pg.fill("#taskDurationInput", "3"); pg.dispatch_event("#taskDurationInput", "input")
    check("...it reads 'day' for 1 and 'days' for 3", u1 == "day" and pg.inner_text("#taskDurationUnit") == "days", (u1, pg.inner_text("#taskDurationUnit")))
    # the note about actuals
    tip = pg.get_attribute("#taskActualsNote", "title")
    check("the note about actual dates is a tooltip on the 'Actual Start' label (no icon)", "Recording an Actual" in tip and pg.is_visible("#taskActualsNote"))
    check("...and there is no ⓘ beside it", pg.evaluate("() => !document.querySelector('#taskActualStartField .info-i')"))
    check("...and no 'Recording…' sentence is left in the dialog's text", "Recording an Actual Start" not in pg.inner_text("#taskModalBg .modal-body"))
    # always fits the window: the body scrolls, the footer stays
    pg.set_viewport_size({"width": 1400, "height": 830}); pg.wait_for_timeout(250)
    box = ev("() => { const m = document.querySelector('#taskModalBg .modal').getBoundingClientRect(), b = document.querySelector('#taskModalBg .modal-body'), s = document.querySelector('#taskModalBg .modal-footer .btn-primary').getBoundingClientRect(); return { top: m.top, bottom: m.bottom, save: s.bottom, scrolls: b.scrollHeight > b.clientHeight }; }")
    check("in an 830px-high window the dialog is inside the window, Save in view, and the body scrolls (a sheet, as Apple's)", box["top"] >= 0 and box["bottom"] <= 830 and box["save"] <= 830 and box["scrolls"], box)
    ev("() => { const b = document.querySelector('#taskModalBg .modal-body'); b.scrollTop = b.scrollHeight; }"); pg.wait_for_timeout(100)
    check("...scrolled to the end, the predecessors' Add button is reachable", ev("() => { const a = document.querySelector('#taskModalBg .tadd').getBoundingClientRect(); return a.bottom <= document.querySelector('#taskModalBg .modal-footer').getBoundingClientRect().top + 1; }"))
    pg.set_viewport_size({"width": 1400, "height": 1000})
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # group and milestone
    open_task("g")
    check("a group: the same groups, with the Type group gone", ev("() => document.querySelectorAll('#taskTabGeneral > .tgrp').length") >= 4 and not pg.is_visible("#taskTypeInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    open_task("m")
    check("a milestone: Finish, Duration and Actual Finish are hidden, one date remains", not pg.is_visible("#taskEndInput") and not pg.is_visible("#taskDurationInput") and not pg.is_visible("#taskActualFinishInput") and pg.is_visible("#taskStartInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # minute mode
    ev(SEED, True); open_task("b")
    check("Hours & minutes: the Start row holds a date and a time on one line, and Duration shows no unit", pg.is_visible("#taskStartTimeInput") and abs(top("#taskStartInput") - top("#taskStartTimeInput")) <= 4 and pg.inner_text("#taskDurationUnit") == "")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # narrow
    ev(SEED, False); pg.set_viewport_size({"width": 520, "height": 900}); open_task("b")
    check("on a phone-width window the dialog fits the width and no row overflows", ev("() => { const m = document.querySelector('#taskModalBg .modal'); return m.getBoundingClientRect().right <= innerWidth + 1 && [...document.querySelectorAll('#taskTabGeneral .trow')].every(r => r.scrollWidth <= r.clientWidth + 1); }"))
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
