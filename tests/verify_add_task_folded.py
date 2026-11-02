"""Add Task next to a folded group: the group is one row, so the new task goes below it as a sibling (not hidden inside it as its first sub-task). An open group still
takes it as its first sub-task; a plain task puts it right below itself."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
SEED = """() => { const mk = (id, name, parent, order, extra) => Object.assign({ id, name, parentId: parent, order, startDate: '2027-01-04', endDate: '2027-01-15', progress: 0, predecessors: [], taskMode: 'auto', updatedAt: 1 }, extra || {});
  tasks = [mk('a','First',null,0), mk('g','Group',null,1,{collapsed:true}), mk('g1','Child 1','g',0), mk('g2','Child 2','g',1), mk('z','Last',null,2)]; colFilters = newColFilters(); normalizeData(); save(); render(); }"""
SHOW = "() => displayRows().map(r => (r.task.parentId ? '  ' : '') + (r.task.name || 'Untitled Task') + (r.task.collapsed ? ' [folded]' : ''))"
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 900}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(400)
    pg.evaluate("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))"); ev = pg.evaluate
    def add(sel):
        ev(SEED); ev(f"() => {{ setSelection(['{sel}']); render(); addTask(); }}"); pg.wait_for_timeout(100); pg.keyboard.press("Escape"); return ev(SHOW)
    r = add('a'); check("a plain task: the new task is right below it, above the folded group", r[:3] == ['First', 'Untitled Task', 'Group [folded]'], r)
    r = add('g'); check("a folded group: the new task is below the group (still folded), not inside it", r == ['First', 'Group [folded]', 'Untitled Task', 'Last'], r)
    check("...and the group stayed folded", ev("() => byId('g').collapsed") is True)
    ev(SEED); ev("() => { byId('g').collapsed = false; setSelection(['g']); render(); addTask(); }"); pg.wait_for_timeout(100); pg.keyboard.press("Escape"); r = ev(SHOW)
    check("an open group: the new task is its first sub-task", r[:4] == ['First', 'Group', '  Untitled Task', '  Child 1'], r)
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
