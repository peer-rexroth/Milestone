# -*- coding: utf-8 -*-
"""The Edit task dialog's General tab in four sections (Task | Schedule | Rules and look | Predecessors) separated by thin dividers; the note about
actual dates is a hint on its label's ⓘ; the dialog still fits its height budgets. See "Edit task sections" in CLAUDE.md."""
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
    seps = ev("() => [...document.querySelectorAll('#taskTabGeneral > .task-sep')].map(e => { const r = e.getBoundingClientRect(), b = document.querySelector('#taskModalBg .modal-body').getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), bodyW: Math.round(b.width), top: r.top }; })")
    check("three thin dividers (1px) cross the General tab, as wide as the page", len(seps) == 3 and all(x["h"] == 1 and x["w"] >= x["bodyW"] - 40 for x in seps), seps)
    order = [Y("#taskNameInput"), seps[0]["top"], Y("#taskStartInput"), seps[1]["top"], Y("#taskConstraintTypeInput"), seps[2]["top"], Y("#predecessorRows")]
    check("they divide the four sections in order: Task (name, mode, resource, type, work) | Schedule (dates, actuals) | Rules and look (constraint, deadline, row colour) | Predecessors", order == sorted(order), order)
    check("Task Type / Work are in the first section (above the first divider); Row colour in the third (below the second, above the last)", Y("#taskTypeInput") < seps[0]["top"] and seps[1]["top"] < Y("#taskColorSwatches") < seps[2]["top"])
    check("the Actual Start / Finish row and Remaining / Status are in the Schedule section (between the first two dividers)", seps[0]["top"] < Y("#taskActualStartInput") < seps[1]["top"] and seps[0]["top"] < ev("() => document.getElementById('taskStatusInfo').getBoundingClientRect().top") < seps[1]["top"])
    check("Constraint and Deadline share the third section's row", abs(Y("#taskConstraintTypeInput") - Y("#taskDeadlineInput")) < 4)
    check("the divider colour is the theme's border (visible in light and dark)", ev("() => getComputedStyle(document.querySelector('#taskTabGeneral > .task-sep')).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent"))
    ev("() => document.documentElement.setAttribute('data-theme', 'dark')"); pg.wait_for_timeout(100)
    check("...also in the dark theme (it follows --border)", ev("() => getComputedStyle(document.querySelector('#taskTabGeneral > .task-sep')).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent"))
    ev("() => document.documentElement.removeAttribute('data-theme')")
    # the note about actuals
    tip = pg.get_attribute("#taskActualsNote", "title")
    check("the note about actual dates is no longer a line between the sections: it is a hint on an ⓘ beside 'Actual Start'", "Recording an Actual" in tip and pg.is_visible("#taskActualsNote") and ev("() => document.getElementById('taskActualsNote').closest('label').textContent.trim().startsWith('Actual Start')") and ev("() => document.querySelectorAll('.pred-empty#taskActualsNote').length") == 0)
    check("...it is keyboard-focusable and has an accessible name", pg.get_attribute("#taskActualsNote", "tabindex") == "0" and "Recording an Actual" in pg.get_attribute("#taskActualsNote", "aria-label"))
    check("...and the ⓘ is on the Actual Start label only (no 'Recording…' sentence left in the dialog's text)", "Recording an Actual Start" not in pg.inner_text("#taskModalBg .modal-body"))
    # rhythm
    gaps = ev("() => { const r = id => document.getElementById(id).getBoundingClientRect(); return [r('taskActualStartInput').top - r('taskStartInput').bottom, r('taskDurationInput').top - r('taskConstraintTypeInput').bottom]; }")
    check("the Actual row keeps the dialog's 12px rhythm under the Start row (label included: input to next input within 12–40px)", 12 <= gaps[0] + 0 <= 40, gaps)
    # height budgets
    h = ev("() => document.querySelector('#taskModalBg .modal').getBoundingClientRect().height")
    fits = ev("() => { const m = document.querySelector('#taskModalBg .modal-body'); return m.scrollHeight <= m.clientHeight + 1; }")
    pg.set_viewport_size({"width": 1400, "height": 830}); pg.wait_for_timeout(250)
    fits830 = ev("() => { const m = document.querySelector('#taskModalBg .modal-body'); return m.scrollHeight <= m.clientHeight + 1; }")
    check("the dialog (a day-mode task with a predecessor) fits an 830px-high window without scrolling — and is shorter than before the dividers (the grey note went)", fits830 and h < 780, (h, fits830))
    pg.set_viewport_size({"width": 1400, "height": 1000})
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # group and milestone
    open_task("g")
    check("a group: the same sections (dividers present), actual dates read-only with the group wording in the hint", ev("() => document.querySelectorAll('#taskTabGeneral > .task-sep').length") == 3 and "earliest actual start" in pg.get_attribute("#taskActualsNote", "title") and pg.is_disabled("#taskActualStartInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    open_task("m")
    check("a milestone: the sections still read in order with its shorter Schedule block", ev("() => document.querySelectorAll('#taskTabGeneral > .task-sep').length") == 3 and Y("#taskStartInput") > Y("#taskNameInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # minute mode
    ev(SEED, True); pg.set_viewport_size({"width": 1400, "height": 910}); open_task("b")
    check("Hours & minutes: three dividers too, and it fits a 910px-high window", ev("() => document.querySelectorAll('#taskTabGeneral > .task-sep').length") == 3 and ev("() => { const m = document.querySelector('#taskModalBg .modal-body'); return m.scrollHeight <= m.clientHeight + 1; }"))
    seps = ev("() => [...document.querySelectorAll('#taskTabGeneral > .task-sep')].map(e => e.getBoundingClientRect().top)")
    check("...and the order is the same (Task | dates and actuals | constraint | predecessors)", Y("#taskNameInput") < seps[0] < Y("#taskStartInput") < seps[1] < Y("#taskConstraintTypeInput") < seps[2] < Y("#predecessorRows"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # narrow
    ev(SEED, False); pg.set_viewport_size({"width": 520, "height": 900}); open_task("b")
    check("on a phone-width window the dividers stay full width and the sections stack in order", ev("() => document.querySelectorAll('#taskTabGeneral > .task-sep').length") == 3 and ev("() => { const s = [...document.querySelectorAll('#taskTabGeneral > .task-sep')].map(e => e.getBoundingClientRect()); const b = document.querySelector('#taskModalBg .modal-body').getBoundingClientRect(); return s.every(r => r.width >= b.width - 40); }"))
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
