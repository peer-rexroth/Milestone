"""The Gantt's Apple-style look: pale pill bars with a solid finished part, groups as thin brackets, names beside the bars, the selected task's ring,
the today pill in the header, thin links with an accent highlight, and the hover card (the title is put back afterwards)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 820}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    ev("""() => { tasks.length = 0; const today = todayStr(), mk = (name, s, e, extra = {}) => { const t = Object.assign({id: genId(), name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: []}, extra); tasks.push(t); return t; };
      const g = mk('Group', '2026-11-02', '2026-11-13'); const a = mk('Alpha', '2026-11-02', '2026-11-06', {parentId: g.id, progress: 50}); const c = mk('Beta', '2026-11-09', '2026-11-13', {parentId: g.id, predecessors: [{id: a.id, type: 'FS', lag: 0}]}); mk('Done it', '2026-11-16', '2026-11-20'); tasks[tasks.length - 1].progress = 100; mk('Go', '2026-11-23', '2026-11-23', {milestone: true});
      currentView = 'gantt'; normalizeData(); save(); render(); setSelection([a.id]); render(); }"""); pg.wait_for_timeout(300)
    bar = lambda n: f".gantt-bar[data-id='{ev('(n) => tasks.find(t => t.name === n).id', n)}']"
    cs = lambda sel, prop: ev("([s, p]) => getComputedStyle(document.querySelector(s))[p]", [sel, prop])
    check("a bar is a rounded pill with a pale tint behind a solid fill", cs(bar("Alpha"), "borderRadius") == "7px" and ev("(s) => getComputedStyle(document.querySelector(s + ' .fill')).backgroundColor !== getComputedStyle(document.querySelector(s)).backgroundColor", bar("Alpha")))
    check("a group is a thin bracket (8px) with end caps, not a bar", cs(bar("Group"), "height") == "8px" and ev("(s) => getComputedStyle(document.querySelector(s), '::before').borderTopWidth", bar("Group")) == "6px")
    check("every name is beside its bar, none inside", ev("() => document.querySelectorAll('.bar-label').length") == 0 and ev("() => [...document.querySelectorAll('.gantt-out-label')].map(e => e.textContent).sort().join()") == "Alpha,Beta,Done it,Go,Group")
    check("the selected task has a ring", "rgb" in cs(bar("Alpha"), "boxShadow") and "sel" in ev("(s) => document.querySelector(s).className", bar("Alpha")))
    check("the today line is a hairline", cs(".gantt-today-line", "width") == "1px")
    check("the header carries a today marker", ev("() => document.querySelectorAll('#ganttHeader .gantt-today-pill').length") <= 1)
    ev("() => { setSelection([tasks.find(t => t.name === 'Done it').id]); render(); }"); pg.wait_for_timeout(150)
    check("links are 1px with an open chevron head", ev("() => getComputedStyle(document.querySelector('#ganttDeps path[data-from]')).strokeWidth") == "1px")
    ev("() => { setSelection([tasks.find(t => t.name === 'Alpha').id]); render(); }"); pg.wait_for_timeout(150)
    check("the selected task's links are accent-coloured", ev("() => { const p = document.querySelector('#ganttDeps path.hl'); return !!p && getComputedStyle(p).strokeWidth === '1.5px'; }"))
    pg.hover(bar("Beta")); pg.wait_for_timeout(900)
    check("resting on a bar shows the card with its dates and progress", ev("() => { const c = document.querySelector('.gantt-card.show'); return !!c && /Beta/.test(c.textContent) && /Start/.test(c.textContent) && /Complete/.test(c.textContent); }"))
    check("...and the browser's own tooltip is out of the way meanwhile", ev("(s) => !document.querySelector(s).hasAttribute('title')", bar("Beta")))
    pg.mouse.move(700, 600); pg.wait_for_timeout(300)
    check("leaving the bar closes the card and puts the title back", ev("() => !document.querySelector('.gantt-card.show')") and ev("(s) => (document.querySelector(s).getAttribute('title') || '').startsWith('Beta')", bar("Beta")))
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
