# -*- coding: utf-8 -*-
"""The Gantt's progress line and the plan's status date: the toolbar toggle (per device, Gantt only), the point of every kind of task
(in progress, behind, ahead, due and not started, future, complete, milestones, groups giving none), the status date (Plan settings →
Scheduling rules; empty = today), its own line and label, outside the chart, data cleaning, large plans. See "Progress line and status
date" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """() => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.statusDate; tasks.length = 0; let o = 0;
  const d = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, x || {});
  tasks.push(mk('g', 'Phase', d(-20), d(20)),
    mk('a', 'Behind', d(-20), d(-1), { parentId: 'g', progress: 40 }), mk('b', 'On track', d(-5), d(4), { parentId: 'g', progress: 50 }), mk('c', 'Ahead', d(-5), d(4), { parentId: 'g', progress: 80 }),
    mk('d', 'Should have started', d(-3), d(6), { parentId: 'g' }), mk('e', 'Future', d(5), d(12), { parentId: 'g' }), mk('f', 'Done', d(-15), d(-10), { parentId: 'g', progress: 100 }),
    mk('f2', 'Done early', d(8), d(12), { parentId: 'g', progress: 100 }),
    mk('m1', 'Due milestone', d(-4), d(-4), { parentId: 'g', milestone: true }), mk('m2', 'Later milestone', d(9), d(9), { parentId: 'g', milestone: true }), mk('m3', 'Done milestone', d(-6), d(-6), { parentId: 'g', milestone: true, progress: 100, actualStart: d(-6), actualFinish: d(-6) }));
  tasks.push(mk('sp', '', d(0), d(0), { spacer: true }));
  normalizeData(); save(); showProgressLine = false; setSelection([]); currentView = 'gantt'; render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(250)
    line = lambda: ev("() => { const l = document.querySelector('#ganttDeps polyline.progress-line'); return l ? l.getAttribute('points').split(' ').map(s => s.split(',').map(Number)) : null; }")

    # ---- the toggle
    check("a Progress line toggle in the Gantt toolbar, off by default, no line drawn", pg.is_visible("#progressLineBtn") and pg.get_attribute("#progressLineBtn", "aria-pressed") == "false" and line() is None)
    pg.click("#progressLineBtn"); pg.wait_for_timeout(200)
    check("clicking it draws the line and presses the button", pg.get_attribute("#progressLineBtn", "aria-pressed") == "true" and line() is not None)
    check("its tooltip names the status date (today) and where to change it", "today" in pg.get_attribute("#progressLineBtn", "title") and "Scheduling rules" in pg.get_attribute("#progressLineBtn", "title"))

    # ---- the points
    r = ev("""() => { const list = visibleTaskList(), pts = document.querySelector('#ganttDeps polyline.progress-line').getAttribute('points').split(' ').map(s => s.split(',').map(Number));
      const byY = new Map(pts.slice(1, -1).map(p => [p[1], p[0]])), out = {};
      list.forEach(({ task: t }, i) => { out[t.id] = byY.has(i * ROW_H + ROW_H / 2) ? byY.get(i * ROW_H + ROW_H / 2) : null; });
      const g = id => barGeom[id];
      return { sx: pts[0][0], ex: pts[pts.length - 1][0], n: pts.length, out, geo: { a: [g('a').left, g('a').width], d: g('d').left, c: [g('c').left, g('c').width], f2: g('f2').right, m1: g('m1').left + g('m1').width / 2, m3: g('m3').left } }; }""")
    sx, o = r["sx"], r["out"]
    check("the line starts and ends on the status line (today)", r["ex"] == sx and abs(sx - ev("() => document.querySelector('.gantt-today-line').offsetLeft")) <= 1, (sx, r["ex"]))
    check("a task in progress: the end of its progress fill (Behind: left of the line)", abs(o["a"] - (r["geo"]["a"][0] + r["geo"]["a"][1] * 0.4)) < 1.5 and o["a"] < sx - 20, o)
    check("...on track: on the line; ahead: right of it", abs(o["b"] - sx) < 6 and o["c"] > sx + 10 and abs(o["c"] - (r["geo"]["c"][0] + r["geo"]["c"][1] * 0.8)) < 1.5, (sx, o["b"], o["c"]))
    check("not started but due (its start is before the status date): at its start — behind", abs(o["d"] - r["geo"]["d"]) < 1.5 and o["d"] < sx)
    check("not started and not yet due: on the line", o["e"] == sx)
    check("complete: on the line; finished before its time (it lies ahead): at its end, right of the line", o["f"] == sx and abs(o["f2"] - r["geo"]["f2"]) < 1.5 and o["f2"] > sx)
    check("a milestone that is due and not done: at its date (behind); a later one and a done one: on the line", abs(o["m1"] - r["geo"]["m1"]) < 1.5 and o["m1"] < sx and o["m2"] == sx and o["m3"] == sx, (o["m1"], o["m2"], o["m3"]))
    check("a group and an empty line give no point (the line runs on between their neighbours)", o["g"] is None and o["sp"] is None and r["n"] == 2 + 10)

    # ---- the status date
    ev("() => { project.statusDate = new Date(Date.now() - 10 * 864e5).toISOString().slice(0, 10); save(); render(); }"); pg.wait_for_timeout(200)
    r2 = ev("() => ({ pts: document.querySelector('#ganttDeps polyline.progress-line').getAttribute('points').split(' ')[0].split(',').map(Number), label: (document.querySelector('#ganttDeps text.status-label') || {}).textContent, line: !!document.querySelector('#ganttDeps line.status-line'), today: document.querySelector('.gantt-today-line').offsetLeft })")
    check("a status date other than today: the line moves there, with its own dashed line and a 'Status dd.mm.yyyy' label", r2["pts"][0] < r2["today"] - 100 and r2["line"] and (r2["label"] or "").startswith("Status "), r2)
    check("...today's red line stays where it is", abs(r2["today"] - sx) <= 1)
    ev("() => { project.statusDate = '2999-01-01'; save(); render(); }"); pg.wait_for_timeout(150)
    check("a status date outside the chart: no line (nothing to measure against)", line() is None and not ev("() => !!document.querySelector('#ganttDeps text.status-label')"))
    ev("() => { delete project.statusDate; save(); render(); }")

    # ---- Plan settings → Scheduling rules
    ev("() => openSettingsTab('rules')"); pg.wait_for_timeout(200)
    check("Scheduling rules has a Status date box, empty ('Today') while none is set", pg.is_visible("#rulesStatusDateInput") and ev("() => document.getElementById('rulesStatusDateInput').value") == "" and pg.get_attribute("#rulesStatusDateInput", "placeholder") == "Today")
    pg.fill("#rulesStatusDateInput", "01.09.2026"); pg.press("#rulesStatusDateInput", "Tab")
    pg.click("#rulesModalBg .modal-footer .btn-primary"); pg.wait_for_timeout(200)
    check("typing a date and saving stores it on the plan (ISO), as one Undo step", ev("() => project.statusDate") == "2026-09-01" and ev("() => undoStack.length") >= 1)
    check("...and the toggle's tooltip names it", "01.09.2026" in pg.get_attribute("#progressLineBtn", "title"))
    ev("() => openSettingsTab('rules')"); pg.wait_for_timeout(150)
    check("reopening shows it; leaving the box empty and saving goes back to today (the key is removed)", ev("() => document.getElementById('rulesStatusDateInput').value") == "2026-09-01")
    pg.fill("#rulesStatusDateInput", ""); pg.press("#rulesStatusDateInput", "Tab"); pg.click("#rulesModalBg .modal-footer .btn-primary"); pg.wait_for_timeout(200)
    check("...cleared", ev("() => 'statusDate' in project") is False)
    ev("() => openSettingsTab('rules')"); pg.wait_for_timeout(100); pg.fill("#rulesStatusDateInput", "02.09.2026"); pg.press("#rulesStatusDateInput", "Tab")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(120)
    check("closing with an unsaved status date asks first (it counts as a change)", "Discard your changes" in pg.inner_text("#confirmModalBg")); pg.click("#confirmModalBg .modal-footer .btn:has-text('Discard')"); pg.wait_for_timeout(120)
    check("...and discarding leaves the plan as it was", ev("() => 'statusDate' in project") is False)

    # ---- data
    check("data cleaning: an unreadable or impossible status date is dropped, a real one kept", ev("() => { const r = []; for (const v of ['abc', '2026-13-45', '2026-02-30', 5, null, '2026-09-01']) { project.statusDate = v; normalizeData(); r.push(project.statusDate || null); } delete project.statusDate; return JSON.stringify(r); }") == '[null,null,null,null,null,"2026-09-01"]')
    check("the status date merges and is described in a conflict", ev("() => CONFLICT_LABELS.statusDate") == "Status date")

    # ---- per device, other views, reload
    ev("() => { setView('tasks'); }"); pg.wait_for_timeout(100)
    check("the toggle belongs to the Gantt view only", not pg.is_visible("#progressLineBtn"))
    pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(200)
    check("the choice is remembered on this device (a preference, not part of the plan)", ev("() => showProgressLine") is True and ev("() => JSON.parse(localStorage.getItem('milestone-prefs')).showProgressLine") is True and 'showProgressLine' not in ev("() => JSON.parse(canonicalText()).project"))

    # ---- a large plan (rows outside the built window still give points)
    ev(SEED); ev("""() => { const d = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
      for (let i = 0; i < 400; i++) tasks.push({ id: 'x' + i, name: 'Bulk ' + i, parentId: null, order: 100 + i, startDate: d(-10), endDate: d(10), progress: i % 100, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
      normalizeData(); save(); showProgressLine = true; render(); }"""); pg.wait_for_timeout(500)
    n = ev("() => document.querySelector('#ganttDeps polyline.progress-line').getAttribute('points').split(' ').length")
    check("a plan of 400+ tasks (rows windowed): a point for every task, not just the built rows", n >= 400 and ev("() => document.querySelectorAll('#ganttRows .gantt-bar').length") < 200, n)
    check("no console errors", not errors, errors[:5])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
