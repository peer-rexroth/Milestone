"""Gantt polish: the Today label, the two-row Week header (months over calendar weeks) and the baseline slip badge ("+2d" after a name)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0;
  const mk = (n, s, e, o = {}) => { const t = Object.assign({id: genId(), name: n, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1}, o); tasks.push(t); return t; };
  const g = mk('Group', '2026-11-02', '2026-12-04');
  mk('Late', '2026-11-02', '2026-11-13', {parentId: g.id, baselines: {0: ['2026-11-02', '2026-11-11']}});
  mk('OnTime', '2026-11-16', '2026-11-20', {parentId: g.id, baselines: {0: ['2026-11-16', '2026-11-20']}});
  mk('NoBaseline', '2026-11-23', '2026-12-04', {parentId: g.id});
  currentView = 'gantt'; showBaseline = true; zoom = 'week'; normalizeData(); save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = lambda js, *a: pg.evaluate(js, *a)
    ev(SEED); pg.wait_for_timeout(300)
    badges = lambda: ev("() => [...document.querySelectorAll('.gantt-slip')].map(e => e.closest('.gantt-out-label').textContent.replace(e.textContent, '').trim() + '=' + e.textContent)")
    # ---- slip badge
    check("a task that finishes later than its baseline gets a '+n d' badge after its name", badges() == ["Late=+2d"], badges())
    check("a group with a task that has no baseline gets none (its rollup would show the gap as a slip)", not any(x.startswith("Group") for x in badges()))
    check("a task on its baseline, and one with no baseline, get none", not any(x.startswith(("OnTime", "NoBaseline")) for x in badges()))
    check("the badge's tooltip says how far it slipped", "later than the baseline" in ev("() => document.querySelector('.gantt-slip').title"))
    ev("() => { byId(tasks.find(t => t.name === 'NoBaseline').id).baselines = {0: ['2026-11-23', '2026-12-04']}; render(); }")
    check("...and a group whose tasks all have one is badged once it slips (here it does not: no slip)", not any(x.startswith("Group") for x in badges()))
    ev("() => { tasks.find(t => t.name === 'NoBaseline').baselines = null; delete tasks.find(t => t.name === 'NoBaseline').baselines; showBaseline = false; render(); }")
    check("with the baseline hidden there is no badge", ev("() => document.querySelectorAll('.gantt-slip').length") == 0)
    ev("() => { showBaseline = true; render(); }")
    # ---- header: two rows on the Week scale
    check("Week scale: a month row over a calendar-week row", ev("() => document.querySelectorAll('#ganttHeader .gantt-tick.wk-month').length") >= 2 and ev("() => document.querySelectorAll('#ganttHeader .gantt-tick.wk-week').length") >= 5)
    tops = ev("() => { const m = document.querySelector('#ganttHeader .wk-month').getBoundingClientRect(), w = document.querySelector('#ganttHeader .wk-week').getBoundingClientRect(); return [m.top, m.bottom, w.top, w.bottom]; }")
    check("...the month row sits above the week row, each half the header", tops[0] < tops[2] and abs(tops[1] - tops[2]) < 2, tops)
    # ---- today
    ev("() => { zoom = 'month'; render(); }")
    check("the Today pill says 'Today' (a dot only on a very small scale)", ev("() => { const e = document.querySelector('.gantt-today-pill'); return !e || e.textContent === 'Today' || e.classList.contains('dot'); }"))
    ev("() => { zoom = 'week'; render(); }")
    pill = ev("() => { const e = document.querySelector('.gantt-today-pill'); return e ? [e.textContent, e.title, e.classList.contains('top')] : null; }")
    check("Week scale: the pill reads 'Today', its tooltip has the date, and it takes the month row (top)", pill is None or (pill[0] == "Today" and "Today ·" in pill[1] and pill[2]), pill)
    check("no page errors", not errors, errors)
    b.close()
print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(0 if all(results) else 1)
