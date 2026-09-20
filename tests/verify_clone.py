from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))

# spec: name, parent (name), start, end, extra, preds=[[name,type,lag]]
SEED = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear(); deletedTaskIds.length = 0;
  const ids = {}; const ord = {}; 
  for (const sp of specs) { const k = sp.parent || ''; ord[k] = ord[k] || 0;
    const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: ord[k]++, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, sp.extra || {});
    tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.parent) t.parentId = ids[sp.parent];
    if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({id: ids[n], type, lag})); }
  currentView = 'tasks'; save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seed = lambda specs: (pg.evaluate(SEED, specs), pg.wait_for_timeout(100))
    tid = lambda n: pg.evaluate("n => (tasks.find(t => t.name === n) || {}).id", n)
    names = lambda: pg.evaluate("() => visibleTaskList().map(v => v.task ? v.task.name : v.name)") 
    order_of = lambda parent: pg.evaluate("p => childrenOf(p).map(t => t.name)", parent)
    clone_btn = lambda n: pg.locator(f".grid-row[data-id='{tid(n)}'] .grid-actions button[title^='Clone']")
    def click_clone(n):
        pg.locator(f".grid-row[data-id='{tid(n)}']").hover(); clone_btn(n).click(); pg.wait_for_timeout(150)

    # ---------------------------------------------------------- a single task
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-11", "extra": {"progress": 40, "resource": "Ann", "color": "blue", "actualStart": "2026-09-08", "constraintType": "SNET", "constraintDate": "2026-09-07", "custom": {"text1": "hello", "num1": 5}}},
          {"name": "B", "s": "2026-09-12", "e": "2026-09-14"}])
    check("the row has a Clone button next to Edit and Delete", pg.locator(f".grid-row[data-id='{tid('A')}'] .grid-actions button").count() == 3)
    check("...and the actions column is wide enough for all three (nothing clipped)", pg.evaluate("() => { const r = document.querySelector('.grid-row .grid-actions'); const row = r.parentElement.getBoundingClientRect(); return r.getBoundingClientRect().right <= row.right + 0.5 && r.scrollWidth <= r.clientWidth + 1; }"))
    click_clone("A")
    check("cloning A adds exactly one task, placed directly below A (before B)", pg.evaluate("() => tasks.length") == 3 and order_of(None) == ["A", "A (copy)", "B"], order_of(None))
    c = pg.evaluate("() => { const t = tasks.find(x => x.name === 'A (copy)'), a = tasks.find(x => x.name === 'A'); return {same: ['startDate','endDate','progress','resource','color','actualStart','actualFinish','constraintType','constraintDate','taskMode','milestone'].every(k => t[k] === a[k]), custom: JSON.stringify(t.custom) === JSON.stringify(a.custom), newId: t.id !== a.id, sel: selectedTaskId === t.id}; }")
    check("the copy is exact (dates, %, resource, colour, actual dates, constraint, mode)", c["same"], c)
    check("...custom fields are copied", c["custom"])
    check("...it has its own id and becomes the selected task", c["newId"] and c["sel"])
    pg.evaluate("() => { tasks.find(x => x.name === 'A (copy)').custom.text1 = 'changed'; }")
    check("custom values are deep-copied (editing the copy leaves the original alone)", pg.evaluate("() => tasks.find(x => x.name === 'A').custom.text1") == "hello")
    check("a toast confirms it, with Undo", "Cloned" in pg.inner_text("#toastMsg") and pg.locator("#toastUndoBtn").is_visible())
    check("the moved sibling B got a fresh updatedAt (so a sync sees the reorder); the original A did not", pg.evaluate("() => tasks.find(x => x.name === 'B').updatedAt") > 1 and pg.evaluate("() => tasks.find(x => x.name === 'A').updatedAt") == 1)
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(150)
    check("Undo removes the copy and restores the order", order_of(None) == ["A", "B"] and pg.evaluate("() => tasks.length") == 2 and pg.evaluate("() => tasks.find(x => x.name === 'B').order") == 1, order_of(None))
    check("...and selects what was selected before", pg.evaluate("() => selectedTaskId") is None)

    # ---------------------------------------------------------- a group, three levels deep
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-20"},
          {"name": "G1", "parent": "G", "s": "2026-09-07", "e": "2026-09-10"},
          {"name": "G2", "parent": "G", "s": "2026-09-11", "e": "2026-09-20"},
          {"name": "G2a", "parent": "G2", "s": "2026-09-11", "e": "2026-09-14", "extra": {"progress": 100}, "preds": [["G1", "FS", 0]]},
          {"name": "G2b", "parent": "G2", "s": "2026-09-15", "e": "2026-09-20", "preds": [["G2a", "FS", 1], ["X", "FS", 0]]},
          {"name": "G2c", "parent": "G2", "s": "2026-09-18", "e": "2026-09-20"},
          {"name": "G2c1", "parent": "G2c", "s": "2026-09-18", "e": "2026-09-19"},
          {"name": "X", "s": "2026-09-01", "e": "2026-09-03"},
          {"name": "Z", "s": "2026-09-25", "e": "2026-09-26", "preds": [["G1", "FS", 0]]}])
    # give X a real position before G's tasks: X was created last; fine — it is a root task
    n_before = pg.evaluate("() => tasks.length")
    click_clone("G")
    check("cloning the group copies it and every level below: 7 new tasks (G + 6 descendants over three levels)", pg.evaluate("() => tasks.length") - n_before == 7, pg.evaluate("() => tasks.length"))
    check("the copy sits right below the ORIGINAL group (after G, before X)", order_of(None) == ["G", "G (copy)", "X", "Z"], order_of(None))
    struct = pg.evaluate("""() => { const copy = tasks.find(t => t.name === 'G (copy)');
      const walk = (id) => childrenOf(id).map(c => [c.name, walk(c.id)]);
      const orig = tasks.find(t => t.name === 'G');
      return {copy: walk(copy.id), orig: walk(orig.id)}; }""")
    check("the copy has the same tree (names, nesting and order) as the original", struct["copy"] == struct["orig"] and len(struct["copy"]) == 2, struct)
    check("...and the original tree is untouched", struct["orig"] == [["G1", []], ["G2", [["G2a", []], ["G2b", []], ["G2c", [["G2c1", []]]]]]], struct["orig"])
    check("only the top task is renamed; sub-tasks keep their names", pg.evaluate("() => tasks.filter(t => t.name.includes('(copy)')).length") == 1)
    ids_ok = pg.evaluate("""() => { const all = tasks.map(t => t.id); if (new Set(all).size !== all.length) return 'duplicate ids';
      const copy = tasks.find(t => t.name === 'G (copy)'); const copyIds = new Set([copy.id, ...descendantIds(copy.id)]);
      const origG = tasks.find(t => t.name === 'G'); const origIds = new Set([origG.id, ...descendantIds(origG.id)]);
      for (const id of copyIds) if (origIds.has(id)) return 'shared id';
      for (const id of copyIds) { const t = byId(id); if (id !== copy.id && !copyIds.has(t.parentId)) return 'child ' + t.name + ' points outside the copy'; }
      return 'ok'; }""")
    check("every clone has a new id and hangs under a clone (never under an original)", ids_ok == "ok", ids_ok)
    links = pg.evaluate("""() => { const copy = tasks.find(t => t.name === 'G (copy)'); const inCopy = new Set(descendantIds(copy.id));
      const g2 = childrenOf(copy.id)[1], g1 = childrenOf(copy.id)[0], g2b = childrenOf(g2.id)[1], g2a = childrenOf(g2.id)[0];
      const X = tasks.find(t => t.name === 'X');
      return {g2: g2a.predecessors.map(p => [p.id === g1.id, p.type, p.lag]), g2b: g2b.predecessors.map(p => [p.id === g2a.id ? 'clone G2a' : p.id === X.id ? 'X' : 'other', p.type, p.lag])}; }""")
    check("a link between two cloned tasks points at the clones (G2a (copy) <- G1 (copy), across two levels)", links["g2"] == [[True, "FS", 0]], links)
    check("...with type and lag kept; a link to a task OUTSIDE the clone (X) is kept as it was", links["g2b"] == [["clone G2a", "FS", 1], ["X", "FS", 0]], links)
    check("nothing else starts depending on the clone: Z still depends only on the original G1", pg.evaluate("() => { const z = tasks.find(t => t.name === 'Z'); return z.predecessors.length === 1 && z.predecessors[0].id === tasks.find(t => t.name === 'G1').id; }"))
    check("the copy's rollup matches the original's (same dates and progress)", pg.evaluate("() => { const a = effectiveDates(tasks.find(t => t.name === 'G').id), b = effectiveDates(tasks.find(t => t.name === 'G (copy)').id); return a.start === b.start && a.end === b.end && a.progress === b.progress; }"))
    check("the copy is selected and its WBS code is 2 (G is 1, X moves to 3)", pg.evaluate("() => wbsCode(selectedTaskId)") == "2" and pg.evaluate("() => wbsCode(tasks.find(t => t.name === 'X').id)") == "3")
    check("toast says how many sub-tasks came along", "6 sub-tasks" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    check("the schedule didn't move anything (clones sit on the same dates; no auto task shifted)", pg.evaluate("() => tasks.filter(t => t.name === 'G2b').every(t => t.startDate === '2026-09-15') && tasks.find(t => t.name === 'Z').startDate === '2026-09-25'"))
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(150)
    check("Undo removes the whole clone (all 7) and restores the order", pg.evaluate("() => tasks.length") == n_before and order_of(None) == ["G", "X", "Z"] and pg.evaluate("() => tasks.find(t => t.name === 'X').order") == 1, order_of(None))
    check("...removed clones are tombstoned so a sync can't resurrect them", pg.evaluate("() => deletedTaskIds.length") == 7, pg.evaluate("() => deletedTaskIds.length"))

    # ---------------------------------------------------------- a sub-task, a collapsed group, milestone, filters, persistence
    click_clone("G2")
    check("cloning a NESTED task keeps it in the same parent, right after it, with its sub-tasks", pg.evaluate("() => { const g = tasks.find(t => t.name === 'G'); return childrenOf(g.id).map(t => t.name); }") == ["G1", "G2", "G2 (copy)"] and pg.evaluate("() => { const c = tasks.find(t => t.name === 'G2 (copy)'); return descendantIds(c.id).length; }") == 4)
    check("...and the copy's WBS is 1.3 (a fresh outline number in the same group)", pg.evaluate("() => wbsCode(selectedTaskId)") == "1.3", pg.evaluate("() => wbsCode(selectedTaskId)"))
    seed([{"name": "C", "s": "2026-09-07", "e": "2026-09-10", "extra": {"collapsed": True}}, {"name": "C1", "parent": "C", "s": "2026-09-07", "e": "2026-09-10"},
          {"name": "M", "s": "2026-09-11", "e": "2026-09-11", "extra": {"milestone": True, "actualStart": "2026-09-11", "actualFinish": "2026-09-11", "progress": 100}}])
    click_clone("C")
    check("a collapsed group is cloned collapsed, with its hidden sub-task", pg.evaluate("() => tasks.find(t => t.name === 'C (copy)').collapsed") is True and pg.evaluate("() => descendantIds(tasks.find(t => t.name === 'C (copy)').id).length") == 1)
    click_clone("M")
    check("a milestone is cloned as a milestone (one date, actual date kept)", pg.evaluate("() => { const m = tasks.find(t => t.name === 'M (copy)'); return m.milestone && m.startDate === m.endDate && m.actualFinish === '2026-09-11'; }"))
    # filter active: the clone is pinned visible
    pg.evaluate("() => { colFilters.name = {text: 'C1'}; }") if False else None
    pg.evaluate("() => { filterPinned.clear(); }")
    n = pg.evaluate("() => tasks.length")
    click_clone("M")
    check("the clone is pinned so an active filter can't hide it", pg.evaluate("() => filterPinned.has(selectedTaskId)"))
    # persistence
    pg.wait_for_timeout(200)
    total = pg.evaluate("() => tasks.length")
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(300)
    check("the clones survive a reload (saved)", pg.evaluate("() => tasks.length") == total and pg.evaluate("() => tasks.some(t => t.name === 'C (copy)')"), pg.evaluate("() => tasks.length"))

    # ---------------------------------------------------------- toolbar button
    pg.evaluate("() => { selectedTaskId = null; render(); }")
    check("toolbar Duplicate is not shown with nothing selected", not pg.is_visible("#cloneTaskBtn"))
    seed([{"name": "T", "s": "2026-09-07", "e": "2026-09-10"}, {"name": "T1", "parent": "T", "s": "2026-09-07", "e": "2026-09-08"}])
    pg.click(f".grid-row[data-id='{tid('T')}'] >> nth=0", position={"x": 30, "y": 10}); pg.wait_for_timeout(100)
    check("...and enabled once a task is selected", not pg.is_disabled("#cloneTaskBtn"))
    pg.click("#cloneTaskBtn"); pg.wait_for_timeout(150)
    check("the toolbar button clones the selected task with its sub-task", order_of(None) == ["T", "T (copy)"] and pg.evaluate("() => descendantIds(tasks.find(t => t.name === 'T (copy)').id).length") == 1, order_of(None))
    check("the row button's tooltip says sub-tasks come along for a group, not for a leaf", "sub-tasks" in pg.get_attribute(f".grid-row[data-id='{tid('T')}'] .grid-actions button[title^='Clone']", "title") and "sub-tasks" not in pg.get_attribute(f".grid-row[data-id='{tid('T1')}'] .grid-actions button[title^='Clone']", "title"))
    # clicking the button must not open the dialog or start an edit
    check("clicking Clone doesn't open the task dialog", not pg.evaluate("() => document.getElementById('taskModalBg').classList.contains('open')"))
    # dark theme visible / light? gantt view: no crash
    pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(100)
    check("the Gantt view still renders with clones", pg.locator(".gantt-bar").count() > 0)
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
