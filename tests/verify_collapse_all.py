from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:260]}]" if not cond and detail else ""))
MK = """(specs) => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear();
  let n = 0; const ids = {};
  for (const sp of specs) { const t = {id: genId(), name: sp[0], parentId: sp[1] ? ids[sp[1]] : null, order: n++, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}; tasks.push(t); ids[sp[0]] = t.id; }
  save(); render(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); ctx = b.new_context(viewport={"width": 1400, "height": 760}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    names = lambda: pg.evaluate("() => visibleTaskList().map(x => x.task.name)")
    st = lambda: pg.evaluate("() => { const b = document.getElementById('collapseToggleBtn'); return {disabled: b.disabled, icon: b.firstElementChild.className.replace('fa-solid fa-angles-', ''), title: b.title}; }")
    click = lambda: (pg.click("#collapseToggleBtn"), pg.wait_for_timeout(90))
    def make(specs): pg.evaluate(MK, specs); pg.wait_for_timeout(80)

    # ---- three levels of groups: A(A1, A2(A2a(A2a1), A2b)), B(B1), C leaf, D(D1(D1a))
    make([["A"], ["A1", "A"], ["A2", "A"], ["A2a", "A2"], ["A2a1", "A2a"], ["A2b", "A2"], ["B"], ["B1", "B"], ["C"], ["D"], ["D1", "D"], ["D1a", "D1"]])
    FULL = ["A", "A1", "A2", "A2a", "A2a1", "A2b", "B", "B1", "C", "D", "D1", "D1a"]
    L0 = ["A", "B", "C", "D"]
    L1 = ["A", "A1", "A2", "B", "B1", "C", "D", "D1"]
    L2 = ["A", "A1", "A2", "A2a", "A2b", "B", "B1", "C", "D", "D1", "D1a"]
    geo = pg.evaluate("() => { const btn = document.getElementById('collapseToggleBtn').getBoundingClientRect(), id = document.querySelector('#gridRows .grid-row > div').getBoundingClientRect(), row = document.querySelector('#gridRows .grid-row').getBoundingClientRect(); return {dx: Math.abs(btn.left - id.left), above: btn.bottom <= row.top + 1, gap: row.top - btn.bottom}; }")
    check("the toggle is left-aligned in the ID column (its left edge is the column's left edge), directly over the first task", geo["dx"] < 2 and geo["above"] and geo["gap"] < 12, geo)
    pg.evaluate("() => { currentView = 'gantt'; render(); }")
    geo2 = pg.evaluate("() => { const btn = document.getElementById('collapseToggleBtn').getBoundingClientRect(), id = document.querySelector('#gridRows .grid-row > div').getBoundingClientRect(); return Math.abs(btn.left - id.left); }")
    check("...and the same in the Gantt view's side list", geo2 < 2, geo2)
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    check("everything open: the next click collapses (up arrows, 'Collapse all groups')", names() == FULL and st()["icon"] == "up" and st()["title"] == "Collapse all groups" and not st()["disabled"], st())
    click()
    check("step 1 — collapse all: only the top-level tasks are left", names() == L0, names())
    check("...the button now offers the first level (down arrows, 'Expand to level 1')", st()["icon"] == "down" and st()["title"] == "Expand to level 1", st())
    click()
    check("step 2 — first level opened: the top-level groups show their children, deeper groups stay closed", names() == L1, names())
    check("...next: 'Expand to level 2'", st()["title"] == "Expand to level 2", st())
    click()
    check("step 3 — second level opened", names() == L2, names())
    check("...next is the last level: 'Expand all groups'", st()["title"] == "Expand all groups" and st()["icon"] == "down", st())
    click()
    check("step 4 — everything open again", names() == FULL, names())
    check("...and the cycle starts over: the button offers to collapse again", st()["icon"] == "up" and st()["title"] == "Collapse all groups", st())
    click(); check("a second lap begins the same way (collapse all)", names() == L0)
    click(); click(); click()
    check("...and comes back to everything open after the same number of clicks", names() == FULL, names())
    # ---- it doesn't touch leaves, and isn't an edit
    check("only groups are ever changed (leaves keep their flag) and no task is stamped as edited", pg.evaluate("() => tasks.filter(t => !tasks.some(x => x.parentId === t.id)).every(t => t.collapsed === false) && tasks.every(t => t.updatedAt === 1)"))
    # ---- a state the cycle doesn't produce
    click(); click()      # now at level 1: A, B, D open; A2, A2a, D1 closed
    check("(back at level 1)", names() == L1, names())
    pg.evaluate("() => { tasks.find(t => t.name === 'A2').collapsed = false; render(); }")
    check("open a nested group by hand -> that isn't one of the cycle's states", names() != L1 and names() != L2 and names() != FULL, names())
    check("...so the next click restarts from 'Collapse all'", st()["title"] == "Collapse all groups", st())
    click(); check("...and does collapse everything", names() == L0, names())
    # ---- state comes from the stored flags: survives a reload mid-cycle
    click(); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
    check("reload at level 1 keeps the outline as it was and the button knows the next step is level 2", names() == L1 and st()["title"] == "Expand to level 2", (names(), st()))
    # ---- Gantt view
    pg.evaluate("() => { currentView = 'gantt'; render(); }")
    check("the same button sits in the Gantt view's side list", pg.locator("#gridHeader > div:first-child #collapseToggleBtn").count() == 1 and pg.locator(".gantt-row-bg").count() == len(L1))
    click()
    check("...and steps there too (level 2 shows 11 rows; the chart rows follow)", pg.locator(".gantt-row-bg").count() == len(L2) and pg.locator("#gridRows .grid-row").count() == len(L2))
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    # ---- two levels only / one level only
    make([["A"], ["A1", "A"], ["B"], ["B1", "B"], ["C"]])
    check("one level of groups: the cycle is just collapse / expand", (click(), names())[1] == ["A", "B", "C"] and st()["title"] == "Expand all groups" and (click(), names())[1] == ["A", "A1", "B", "B1", "C"] and st()["title"] == "Collapse all groups")
    make([["A"], ["A1", "A"], ["A2", "A1"], ["B"]])
    seq = []
    for _ in range(5): click(); seq.append(names())
    check("two levels: collapse -> level 1 -> all, then around (5 clicks)", seq == [["A", "B"], ["A", "A1", "B"], ["A", "A1", "A2", "B"], ["A", "B"], ["A", "A1", "B"]], seq)
    # ---- the button survives re-renders
    pg.evaluate("() => { render(); render(); }")
    check("the button survives re-renders (the header is rebuilt each time) with its state intact", pg.locator("#collapseToggleBtn").count() == 1 and st()["title"] == "Expand all groups", st())
    # ---- filters
    pg.evaluate("() => { colFilters.name = {type: 'rule', rule: 'contains', a: 'a1'}; render(); }")
    check("while a filter is on the toggle is disabled and says why", st()["disabled"] and "filter" in st()["title"], st())
    before = pg.evaluate("() => tasks.map(t => t.collapsed)"); pg.evaluate("() => toggleAllCollapsed()")
    check("...calling it anyway changes nothing, with a toast", pg.evaluate("() => tasks.map(t => t.collapsed)") == before and "filter" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    pg.evaluate("() => { colFilters = newColFilters(); render(); }")
    check("clearing the filter enables it again", not st()["disabled"])
    make([["x"], ["y"]])
    check("with no groups at all it is disabled", st()["disabled"], st())
    pg.evaluate("() => { tasks.length = 0; render(); }")
    check("...and with no tasks", st()["disabled"])
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
