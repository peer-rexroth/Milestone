from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev("() => { historyCoalesceMs = 0; }")
    def mk(name, parent=None, order=0, extra=None):
        extra = dict(extra or {})
        return {"name": name, "parent": parent, "order": order, "s": extra.pop("s", None), "e": extra.pop("e", None), "extra": extra}
    SEED = """(specs) => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); colFilters = newColFilters(); filterPinned.clear(); const ids = {};
      for (const sp of specs) { const t = Object.assign({ id: genId() + Math.random().toString(36).slice(2, 5), name: sp.name, parentId: null, order: sp.order, startDate: sp.s || '2026-09-07', endDate: sp.e || sp.s || '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; }
      for (const sp of specs) if (sp.parent) tasks.find(x => x.name === sp.name).parentId = ids[sp.parent];
      currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
    seed = lambda specs: ev(SEED, specs)
    base = [mk("Website relaunch", None, 0), mk("Design", "Website relaunch", 0), mk("Design review", "Design", 0, {"resource": "Anna Meier"}), mk("Wireframes", "Design", 1, {"resource": "Ben"}),
            mk("Build", "Website relaunch", 1), mk("Backend design", "Build", 0, {"resource": "Anna, Chris"}), mk("Launch", None, 1), mk("Release notes", "Launch", 0, {"custom": {"text1": "Cost centre 7"}})]
    seed(base)
    def search(q):
        pg.fill("#searchInput", q); pg.wait_for_timeout(60)
        return ev("() => searchHits.map(h => h.t.name)")
    is_open = lambda: ev("() => document.getElementById('searchModalBg').classList.contains('open')")

    # ------------------------------------------------------------ opening and closing
    ev("() => document.activeElement && document.activeElement.blur()")
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(120)
    check("Ctrl+K opens the palette with the cursor in the search box", is_open() and ev("() => document.activeElement.id") == "searchInput")
    check("...an empty search explains the syntax and counts the tasks", "8 tasks" in pg.inner_text("#searchResults") and "#12" in pg.inner_text("#searchResults"), pg.inner_text("#searchResults"))
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(120)
    check("Ctrl+K again closes it", not is_open())
    pg.keyboard.press("Meta+k"); pg.wait_for_timeout(120)
    check("Cmd+K opens it too", is_open())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("Escape closes it", not is_open())
    ev("() => document.activeElement && document.activeElement.blur()"); pg.keyboard.press("/"); pg.wait_for_timeout(120)
    check("'/' opens it when you are not typing (and does not type a slash into the box)", is_open() and pg.input_value("#searchInput") == "", pg.input_value("#searchInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.click("#searchBtn"); pg.wait_for_timeout(120)
    check("the Find button in the toolbar opens it", is_open())
    pg.mouse.click(5, 5); pg.wait_for_timeout(200)
    check("a click outside closes it", not is_open())
    ev("() => startInlineEdit(tasks[0].id, 'name')"); pg.wait_for_timeout(150); pg.keyboard.type("/")
    check("typing a slash in a cell being edited does not open the palette", not is_open())
    pg.keyboard.press("Escape"); ev("() => document.activeElement && document.activeElement.blur()")
    ev("() => openTaskModal(tasks[0].id)"); pg.wait_for_timeout(250); pg.keyboard.press("Control+k"); pg.wait_for_timeout(120)
    check("with the task dialog open Ctrl+K does nothing", not is_open())
    ev("() => closeTaskModal()"); pg.wait_for_timeout(250)

    # ------------------------------------------------------------ matching
    pg.click("#searchBtn"); pg.wait_for_timeout(100)
    check("a name search is case-insensitive and finds by part of a word: 'DESIGN' -> Design, Design review, Backend design (a name that starts with it first)", search("DESIGN") == ["Design", "Design review", "Backend design"], search("DESIGN"))
    check("every word has to match: 'design review'", search("design review") == ["Design review"])
    check("words can be in any order: 'review design'", search("review design") == ["Design review"])
    check("a word inside a name ranks above a mere substring: 'notes' finds Release notes", search("notes") == ["Release notes"])
    check("the resource is searched too: 'anna' -> Design review, Backend design", sorted(search("anna")) == ["Backend design", "Design review"], search("anna"))
    check("'@anna' searches resources only (Anna Meier's Design review, Anna and Chris' Backend design; no task NAMED anna)", sorted(search("@anna")) == ["Backend design", "Design review"] and search("@ben") == ["Wireframes"], search("@anna"))
    check("custom text fields are searched: 'centre' -> Release notes", search("centre") == ["Release notes"], search("centre"))
    n = ev("() => taskDisplayId(tasks.find(t => t.name === 'Build').id)")
    check(f"'#{n}' finds the task with that ID (Build)", search(f"#{n}") == ["Build"], search(f"#{n}"))
    check("'#999' finds nothing", search("#999") == [])
    check("a WBS code: '1.1' finds Design and everything below it (Design, Design review, Wireframes)", search("1.1") == ["Design", "Design review", "Wireframes"], search("1.1"))
    check("'1.2.1' finds exactly Backend design", search("1.2.1") == ["Backend design"], search("1.2.1"))
    check("no match says so and lists nothing", search("zzz") == [] and "No task matches" in pg.inner_text("#searchResults"), pg.inner_text("#searchResults"))
    search("wire")
    html = ev("() => document.querySelector('#searchResults .sr-name').innerHTML")
    check("the matching part of the name is highlighted", "<mark>Wire</mark>frames" in html, html)
    row = pg.inner_text("#searchResults .sr")
    check("a result shows the ID, the WBS code, the name, its groups (Website relaunch › Design) and its dates", "Wireframes" in row and "1.1.2" in row and "Website relaunch › Design" in row and "07.09.2026" in row, row)
    check("the first result is the active one", ev("() => document.querySelector('#searchResults .sr').classList.contains('active')"))
    ids = {n: ev("n => tasks.find(t => t.name === n).id", n) for n in ("Design", "Wireframes", "Design review", "Release notes")}
    pg.keyboard.press("Escape")

    # ------------------------------------------------------------ jumping
    ev("() => { tasks.filter(t => t.name === 'Design' || t.name === 'Website relaunch').forEach(t => t.collapsed = true); render(); }")
    check("(setup) the groups above Wireframes are folded, its row is not in the list", pg.locator(f".grid-row[data-id='{ids['Wireframes']}']").count() == 0)
    pg.click("#searchBtn"); pg.fill("#searchInput", "wireframes"); pg.wait_for_timeout(60); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    check("Enter jumps to the task: the folded groups above it open and it is the (only) selection", pg.locator(f".grid-row[data-id='{ids['Wireframes']}']").count() == 1 and ev("() => selectedIds().map(id => byId(id).name)") == ["Wireframes"] and not is_open())
    check("...the row flashes so the eye finds it", ev("(id) => document.querySelector(`.grid-row[data-id='${id}']`).classList.contains('jump-flash')", ids["Wireframes"]))
    check("...jumping changes nothing in the plan (no undo step)", ev("() => undoStack.length") == 0, ev("() => undoStack.length"))
    pg.wait_for_timeout(1700)
    check("...and the flash goes away again", not ev("(id) => document.querySelector(`.grid-row[data-id='${id}']`).classList.contains('jump-flash')", ids["Wireframes"]))
    # a filter that hides it
    ev("() => { colFilters.name = { type: 'values', values: new Set(['Launch']), blanks: false }; filterPinned.clear(); render(); }")
    check("(setup) a filter shows only Launch", pg.locator(".grid-row").count() <= 2)
    pg.click("#searchBtn"); pg.fill("#searchInput", "backend"); pg.wait_for_timeout(60); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    check("a task the filter hides is shown anyway when you jump to it (it is pinned)", ev("() => document.querySelectorAll('.grid-row[data-id=\"' + tasks.find(t => t.name === 'Backend design').id + '\"]').length") == 1 and ev("() => selectedIds().map(id => byId(id).name)") == ["Backend design"])
    ev("() => { colFilters = newColFilters(); filterPinned.clear(); render(); }")

    # long list: the row scrolls into view
    many = [mk("Group", None, 0)] + [mk(f"Task {i:03d}", "Group", i) for i in range(120)]
    seed(many)
    pg.click("#searchBtn"); pg.fill("#searchInput", "task 095"); pg.wait_for_timeout(60); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    vis = ev("() => { const r = document.querySelector('#gridRows'), e = r.querySelector('.grid-row.selected'), a = r.getBoundingClientRect(), b = e.getBoundingClientRect(); return { inside: b.top >= a.top - 1 && b.bottom <= a.bottom + 1, scrolled: r.scrollTop > 0 }; }")
    check("in a long list the row is scrolled into view (task 095 of 120, in the middle of the list)", vis["inside"] and vis["scrolled"], vis)
    # gantt
    seed([mk("Early", None, 0, {"s": "2026-09-07", "e": "2026-09-11"}), mk("Far away", None, 1, {"s": "2028-03-06", "e": "2028-03-24"}), mk("Also early", None, 2, {"s": "2026-09-14", "e": "2026-09-15"})])
    ev("() => { setView('gantt'); setZoom('month'); }"); pg.wait_for_timeout(300)
    pg.click("#searchBtn"); pg.fill("#searchInput", "far away"); pg.wait_for_timeout(60); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    g = ev("() => { const o = document.getElementById('ganttPaneOuter').getBoundingClientRect(), bar = document.querySelector('.gantt-bar[data-id=\"' + tasks.find(t => t.name === 'Far away').id + '\"]'); if (!bar) return null; const r = bar.getBoundingClientRect(); return { inView: r.left >= o.left && r.right <= o.right + 2, scrollLeft: document.getElementById('ganttPaneOuter').scrollLeft }; }")
    check("in the Gantt view the chart scrolls sideways to the bar (a task in 2028)", g and g["inView"] and g["scrollLeft"] > 0, g)
    ev("() => setView('tasks')"); pg.wait_for_timeout(200)

    # ------------------------------------------------------------ navigating the list, showing only the matches
    seed(base)
    pg.click("#searchBtn"); pg.fill("#searchInput", "design"); pg.wait_for_timeout(60)
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowDown")
    check("ArrowDown moves the highlight (third result)", ev("() => searchIdx") == 2 and ev("() => document.querySelectorAll('#searchResults .sr')[2].classList.contains('active')"))
    pg.keyboard.press("ArrowDown"); check("...and wraps around after the last result", ev("() => searchIdx") == 0)
    pg.keyboard.press("ArrowUp"); check("ArrowUp wraps to the last", ev("() => searchIdx") == 2)
    pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    check("Enter goes to the highlighted one (Backend design)", ev("() => selectedIds().map(id => byId(id).name)") == ["Backend design"])
    pg.click("#searchBtn"); pg.fill("#searchInput", "design"); pg.wait_for_timeout(60)
    pg.locator("#searchResults .sr").nth(1).click(); pg.wait_for_timeout(250)
    check("a click on a result goes there (Design review)", ev("() => selectedIds().map(id => byId(id).name)") == ["Design review"])
    pg.click("#searchBtn"); pg.fill("#searchInput", "design"); pg.wait_for_timeout(60); pg.keyboard.press("Shift+Enter"); pg.wait_for_timeout(300)
    shown = ev("() => visibleTaskList().map(v => v.task.name)")
    check("Shift+Enter turns the matches into a Task Name filter (Design, Design review, Backend design shown, with their groups)", "Design" in shown and "Design review" in shown and "Backend design" in shown and "Wireframes" not in shown and "Launch" not in shown, shown)
    check("...the filter bar shows it and the toast explains how to clear it", not ev("() => document.getElementById('filterBar').classList.contains('hidden')") and "Showing the 3 tasks" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    ev("() => { colFilters = newColFilters(); filterPinned.clear(); render(); }")
    pg.click("#searchBtn"); pg.fill("#searchInput", "wireframes"); pg.wait_for_timeout(60)
    check("with a single match there is no 'show only' hint", ev("() => getComputedStyle(document.querySelector('#searchFoot span:last-child')).visibility") == "hidden")
    pg.keyboard.press("Escape")
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
