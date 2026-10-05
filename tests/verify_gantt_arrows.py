# -*- coding: utf-8 -*-
"""The Gantt's dependency arrows: a small FILLED head (it used to inherit the line's fill:none and show as an open V), rounded elbows, the head
stopping 2px short of what it points at (4px more at a diamond's tip), critical arrows in their own colour, and a task's own links standing
out (hover / selection) while the others step back. See "Dependency arrows" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """() => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; tasks.length = 0; let o = 0;
  const d = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, x || {});
  tasks.push(mk('a', 'WS1', d(0), d(8)), mk('b', 'WS7', d(9), d(16), { predecessors: [{ id: 'a', type: 'FS', lag: 0 }] }), mk('c', 'Narrow', d(11), d(11), { predecessors: [{ id: 'a', type: 'FS', lag: 0 }] }),
    mk('m', 'Milestone', d(17), d(17), { milestone: true, predecessors: [{ id: 'b', type: 'FS', lag: 0 }] }), mk('z', 'Loose', d(3), d(5)));
  normalizeData(); save(); showCriticalPath = false; setSelection([]); currentView = 'gantt'; render(); resetHistory(); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 700}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(250)

    head = ev("""() => { const m = document.querySelector('#ganttDeps marker#arrowhead'), p = m.querySelector('path'), cs = getComputedStyle(p);
      return { fill: cs.fill, stroke: cs.stroke, w: m.getAttribute('markerWidth'), h: m.getAttribute('markerHeight'), units: m.getAttribute('markerUnits') }; }""")
    check("the arrowhead is a FILLED triangle with no outline (not an open V)", head["fill"] != "none" and head["stroke"] == "none", head)
    check("...small: 7 × 6 px, whatever the line's width", head["w"] == "7" and head["h"] == "6" and head["units"] == "userSpaceOnUse", head)
    check("the line is a thin 1.25px stroke", ev("() => getComputedStyle(document.querySelector('#ganttDeps path[data-from]')).strokeWidth") == "1.25px")
    check("every arrow knows its two ends (data-from / data-to)", ev("() => [...document.querySelectorAll('#ganttDeps path[data-from]')].map(p => p.dataset.from + '>' + p.dataset.to).sort().join()") == "a>b,a>c,b>m")
    check("elbows are rounded (a curve at each corner)", ev("() => [...document.querySelectorAll('#ganttDeps path[data-from]')].filter(p => /Q/.test(p.getAttribute('d'))).length") >= 2)

    ends = ev("""() => { const end = id => { const p = document.querySelector('#ganttDeps path[data-to="' + id + '"]'), m = p.getAttribute('d').match(/L([\\d.\\-]+),([\\d.\\-]+)$/); return +m[1]; };
      return { b: [end('b'), barGeom.b.left], c: [end('c'), barGeom.c.left], m: [end('m'), barGeom.m.left] }; }""")
    check("the head stops 2px short of a bar, narrow ones included", abs(ends["b"][0] - (ends["b"][1] - 2)) < 0.6 and abs(ends["c"][0] - (ends["c"][1] - 2)) < 0.6, ends)
    check("...and 6px short of a diamond's box (its tip reaches 4px past it)", abs(ends["m"][0] - (ends["m"][1] - 6)) < 0.6, ends)
    check("a milestone has a data-id like a bar", ev("() => !!document.querySelector('.gantt-milestone[data-id=\"m\"]')"))

    # ---- critical arrows
    ev("() => { showCriticalPath = true; render(); }"); pg.wait_for_timeout(150)
    crit = ev("() => { const p = document.querySelector('#ganttDeps path.critical'); return p ? p.getAttribute('marker-end') : null; }")
    check("a critical arrow uses the critical head (red)", crit == "url(#arrowhead-crit)" and ev("() => getComputedStyle(document.querySelector('#ganttDeps marker.crit path')).fill") != ev("() => getComputedStyle(document.querySelector('#ganttDeps marker#arrowhead path')).fill"), crit)
    ev("() => { showCriticalPath = false; render(); }"); pg.wait_for_timeout(100)

    # ---- own links stand out
    state = lambda: ev("() => ({ svg: document.getElementById('ganttDeps').classList.contains('has-hl'), hl: [...document.querySelectorAll('#ganttDeps path.hl')].map(p => p.dataset.from + '>' + p.dataset.to).sort().join(), head: document.querySelector('#ganttDeps path[data-to=\"b\"]').getAttribute('marker-end') })")
    check("at rest nothing is emphasised", state()["svg"] is False and state()["hl"] == "")
    pg.hover(".gantt-bar[data-id='b']"); pg.wait_for_timeout(100); s = state()
    check("hovering a bar emphasises its own links (in and out) and uses the dark head for them", s["svg"] is True and s["hl"] == "a>b,b>m" and s["head"] == "url(#arrowhead-hl)", s)
    check("...the other arrows step back", ev("() => +getComputedStyle(document.querySelector('#ganttDeps path[data-to=\"c\"]')).opacity") < 0.5)
    pg.mouse.move(5, 650); pg.wait_for_timeout(100)
    check("moving away clears it", state()["svg"] is False and state()["hl"] == "")
    pg.hover(".gantt-milestone[data-id='m']"); pg.wait_for_timeout(100)
    check("a milestone does the same", state()["hl"] == "b>m")
    pg.mouse.move(5, 650); pg.wait_for_timeout(80)
    ev("() => { setSelection(['a']); render(); }"); pg.wait_for_timeout(100)
    check("the selected task's links stay emphasised", state()["hl"] == "a>b,a>c")
    pg.hover(".gantt-bar[data-id='b']"); pg.wait_for_timeout(80); pg.mouse.move(5, 650); pg.wait_for_timeout(80)
    check("...also after hovering something else and leaving (back to the selection)", state()["hl"] == "a>b,a>c")
    ev("() => { setSelection(['z']); render(); }"); pg.wait_for_timeout(100)
    check("a selected task without links: nothing emphasised, nothing faded", state()["svg"] is False)
    check("no console errors", not errors, errors[:5])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
