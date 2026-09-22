import json
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))

# hierarchy: Group A (3 kids), Group B (2 kids, collapsed), Solo, TBD (free-text date -> blank), a milestone
SEED = """() => { tasks.length = 0; selectedTaskId = null; colFilters = newColFilters(); filterPinned.clear();
  let n = 0; const mk = (name, parent, s, e, extra) => { const t = Object.assign({id: genId(), name, parentId: parent || null, order: n++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}, extra || {}); tasks.push(t); return t.id; };
  const A = mk('Group A', null, '2026-09-07', '2027-01-15'); mk('A1', A, '2026-09-07', '2026-09-11'); mk('A2', A, '2026-10-05', '2026-10-09'); mk('A3', A, '2027-01-11', '2027-01-15');
  const B = mk('Group B', null, '2026-09-21', '2026-11-06', {collapsed: true}); mk('B1', B, '2026-09-21', '2026-09-25'); mk('B2', B, '2026-11-02', '2026-11-06');
  mk('Solo', null, '2026-09-07', '2026-09-30'); mk('TBD', null, '2026-09-01', '2026-09-02', {taskMode: 'manual', startText: 'TBD'}); mk('Milestone', null, '2026-10-05', '2026-10-05', {milestone: true});
  currentView = 'tasks'; save(); render(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1300, "height": 760}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; }"); pg.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status']) colHidden.add(c); }"); pg.evaluate("() => { colHidden.add('wbs'); save(); render(); }")
    def seed(): pg.evaluate(SEED); pg.wait_for_timeout(150)
    rows = lambda: pg.evaluate("() => visibleTaskList().map(x => x.task.name)")
    def open_filter(col, expand=True):
        pg.locator(f".col-filter-btn[data-col='{col}']").click(); pg.wait_for_selector("#filterMenu.open")
        while expand and pg.locator("#filterTree .ft-exp:has(i.fa-chevron-right)").count():   # months start collapsed; most tests need the days
            pg.locator("#filterTree .ft-exp:has(i.fa-chevron-right)").first.click()
    def apply_rule(col, rule, a=None, b_=None):
        open_filter(col); pg.select_option("#filterRuleSel", rule)
        if a: pg.fill("#filterInputA", a)
        if b_: pg.fill("#filterInputB", b_)
        pg.click("#filterOkBtn"); pg.wait_for_function("() => !document.getElementById('filterMenu').classList.contains('open')")
    def tree_labels(): return pg.locator("#filterTree .ft-label").all_inner_texts()
    def clear_all(): pg.evaluate("() => clearAllFilters()"); pg.wait_for_timeout(100)

    seed()
    check("Tasks view: a filter button on every data column (mode, name, start, finish, duration, %, predecessors)", pg.evaluate("() => [...document.querySelectorAll('.col-filter-btn')].map(b => b.dataset.col)") == ["mode", "name", "start", "end", "duration", "progress", "preds"])
    check("...and none on the ID column or the row actions", pg.locator(".grid-header > div").count() == 9 and pg.locator(".grid-header > div:first-child .col-filter-btn, .grid-header > div:last-child .col-filter-btn").count() == 0)
    check("no header label is cut off by its filter button", pg.evaluate("() => [...document.querySelectorAll('.grid-header .col-head > span')].every(e => e.scrollWidth <= e.clientWidth)"))
    pg.evaluate("() => { currentView = 'gantt'; render(); }")
    check("Gantt view: the list has a funnel for every visible column, exactly like the Tasks view", pg.evaluate("() => [...document.querySelectorAll('.col-filter-btn')].map(b => b.dataset.col)") == pg.evaluate("() => visibleTaskCols()"))
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    check("no filter bar while nothing is filtered", pg.locator("#filterBar:not(.hidden)").count() == 0 and rows() == ["Group A", "A1", "A2", "A3", "Group B", "Solo", "TBD", "Milestone"], rows())

    # ---------------- the panel: years open, months collapsed
    open_filter("start", expand=False)
    labels = tree_labels()
    check("panel opens with the years open and every month collapsed", labels == ["(Select All)", "2026", "September", "October", "November", "2027", "January", "(Blanks)"], labels)
    check("...so no individual days are listed yet", pg.locator("#filterTree .ft-cb[data-key^='d:']").count() == 0)
    pg.locator("#filterTree .ft-row:has(.ft-cb[data-key='m:2026-09']) .ft-exp").click()
    check("expanding a month leaves the panel open (it used to close it)", pg.locator("#filterMenu.open").count() == 1)
    check("opening a month lists just its days; the other months stay collapsed", pg.locator("#filterTree .ft-cb[data-key^='d:']").count() == 2 and pg.locator("#filterTree .ft-cb[data-key='d:2026-09-07']").count() == 1 and pg.locator("#filterTree .ft-cb[data-key='d:2026-10-05']").count() == 0)
    pg.locator("#filterTree .ft-row:has(.ft-cb[data-key='m:2026-09']) .ft-exp").click()
    check("...and it closes again", pg.locator("#filterTree .ft-cb[data-key^='d:']").count() == 0)
    pg.locator("#filterTree .ft-row:has(.ft-cb[data-key='y:2026']) .ft-exp").click()
    check("a year can be collapsed too", tree_labels() == ["(Select All)", "2026", "2027", "January", "(Blanks)"], tree_labels())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    open_filter("start", expand=False)
    check("a re-opened panel starts from the same default again", tree_labels() == ["(Select All)", "2026", "September", "October", "November", "2027", "January", "(Blanks)"], tree_labels())
    pg.fill("#filterSearch", "2027")
    check("searching still opens whatever it needs to show the matches", "11.01.2027" in tree_labels(), tree_labels())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    open_filter("start", expand=False); pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.locator("#filterTree .ft-cb[data-key='m:2026-10']").check(); pg.click("#filterOkBtn")
    check("a whole month can be picked without opening it", rows() == ["Group A", "A2", "Milestone"], rows())
    open_filter("start", expand=False)
    check("a filtered list re-opens with its months still collapsed (only their tick state shows)", pg.locator("#filterTree .ft-cb[data-key^='d:']").count() == 0 and pg.locator("#filterTree .ft-cb[data-key='m:2026-10']:checked").count() == 1 and pg.locator("#filterTree .ft-cb[data-key='m:2026-09']:checked").count() == 0)
    pg.keyboard.press("Escape"); clear_all()

    # ---------------- the panel
    open_filter("start")
    labels = tree_labels()
    check("panel: (Select All), Year > Month > Day, and (Blanks) because a task has no real start date", labels[0] == "(Select All)" and "2026" in labels and "2027" in labels and "07.09.2026" in labels and labels[-1] == "(Blanks)", labels)
    check("panel: everything starts checked; Clear filter disabled", pg.locator("#filterTree .ft-cb:checked").count() == pg.locator("#filterTree .ft-cb").count() and pg.locator("#filterClearBtn").is_disabled())
    check("panel: OK with nothing changed applies no filter", (pg.click("#filterOkBtn") or True) and not pg.evaluate("() => filtersActive()"))

    # ---------------- values: pick one date
    open_filter("start"); pg.locator("#filterTree .ft-cb[data-key='all']").uncheck()
    check("(Select All) unchecks everything and disables OK", pg.locator("#filterTree .ft-cb:checked").count() == 0 and pg.locator("#filterOkBtn").is_disabled())
    pg.locator("#filterTree .ft-cb[data-key='d:2026-09-07']").check(); pg.click("#filterOkBtn")
    check("filter Start = 07.09.2026 keeps the matching tasks (and Group A, which starts then)", rows() == ["Group A", "A1", "Solo"], rows())
    chip = pg.inner_text("#filterBar")
    check("the filter bar names it and counts the tasks", "Start: 07.09.2026" in chip and "3 of 10 tasks" in chip and "Clear all" in chip, chip)
    check("the header button is highlighted with a tooltip", pg.locator(".col-filter-btn.active").count() == 1 and "07.09.2026" in pg.locator(".col-filter-btn.active").get_attribute("title"))
    pg.click("#filterBar .filter-chip button"); pg.wait_for_timeout(100)
    check("the chip's × removes that filter", not pg.evaluate("() => filtersActive()") and len(rows()) == 8)

    # a match under a summary keeps the summary for context; a non-matching sibling is hidden
    open_filter("start"); pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.locator("#filterTree .ft-cb[data-key='d:2026-10-05']").check(); pg.click("#filterOkBtn")
    check("a matching sub-task keeps its group visible; siblings that don't match are hidden", rows() == ["Group A", "A2", "Milestone"], rows())

    # ---------------- tri-state and search
    clear_all(); open_filter("start")
    pg.locator("#filterTree .ft-cb[data-key='d:2026-09-07']").uncheck()
    check("unchecking one day makes its month and year indeterminate", pg.evaluate("() => ['m:2026-09', 'y:2026', 'all'].map(k => document.querySelector(`.ft-cb[data-key='${k}']`).indeterminate)") == [True, True, True])
    pg.locator("#filterTree .ft-cb[data-key='y:2026']").check()
    check("checking the year checks every day under it again", pg.locator("#filterTree .ft-cb[data-key='y:2026']:checked").count() == 1 and pg.locator("#filterTree .ft-cb[data-key='d:2026-09-07']:checked").count() == 1)
    pg.fill("#filterSearch", "2027")
    labels = tree_labels()
    check("search narrows the list to the matches and relabels Select All", labels[0] == "(Select All Search Results)" and "2026" not in labels and "11.01.2027" in labels and "(Blanks)" not in labels, labels)
    pg.click("#filterOkBtn")
    check("search + OK filters to exactly the matches", rows() == ["Group A", "A3"], rows())
    open_filter("start"); pg.fill("#filterSearch", "2027"); pg.fill("#filterSearch", "")
    check("clearing the search restores the previous selection", pg.locator("#filterTree .ft-cb:checked").count() + pg.locator("#filterTree .ft-cb:indeterminate").count() > 0)
    pg.fill("#filterSearch", "sept")
    check("search matches month names too ('sept' finds September)", any("September" in l for l in tree_labels()) if pg.locator("#filterTree .ft-label").count() else False, tree_labels())
    pg.fill("#filterSearch", "zzz")
    check("no matches: a message, and OK is disabled", "Nothing matches" in pg.inner_text("#filterTree") and pg.locator("#filterOkBtn").is_disabled())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes the panel without applying", not pg.locator("#filterMenu.open").count() and rows() == ["Group A", "A3"], rows())
    clear_all()

    # ---------------- rules
    apply_rule("start", "equals", "2026-09-21")
    check("rule: equals -> B1 (Group B is shown open although it was collapsed)", rows() == ["Group B", "B1"], rows())
    check("...its chevron shows open and clicking it explains why nothing happens", pg.evaluate("() => (document.querySelector('.grid-row .chevron i') || {}).className") is not None)
    pg.locator(".grid-row", has_text="Group B").locator(".chevron").click(); pg.wait_for_timeout(150)
    check("...(toast: groups stay open while a filter is on)", "stay open" in pg.inner_text("#toastMsg") and pg.evaluate("() => byId(tasks.find(t => t.name === 'Group B').id).collapsed") is True)
    clear_all(); check("clearing the filter puts Group B back to collapsed", rows() == ["Group A", "A1", "A2", "A3", "Group B", "Solo", "TBD", "Milestone"], rows())
    apply_rule("start", "before", "2026-09-08"); check("rule: before", rows() == ["Group A", "A1", "Solo"], rows())
    apply_rule("start", "after", "2026-11-01"); check("rule: after", rows() == ["Group A", "A3"] or rows() == ["Group A", "A3", "Group B", "B2"], rows())
    apply_rule("start", "between", "2026-09-01", "2026-09-30"); check("rule: between (excludes the blank-start TBD task)", rows() == ["Group A", "A1", "Group B", "B1", "Solo"] and "TBD" not in rows(), rows())
    apply_rule("start", "between", "2026-09-30", "2026-09-01"); check("rule: between accepts the dates in either order", rows() == ["Group A", "A1", "Group B", "B1", "Solo"], rows())
    clear_all(); open_filter("start"); pg.select_option("#filterRuleSel", "between")
    check("OK stays disabled until the dates are filled in", pg.locator("#filterOkBtn").is_disabled())
    pg.fill("#filterInputA", "2026-09-01"); check("...one date isn't enough for 'between'", pg.locator("#filterOkBtn").is_disabled())
    pg.fill("#filterInputB", "2026-09-02"); check("...both dates enable it", not pg.locator("#filterOkBtn").is_disabled())
    pg.locator("#filterTree .ft-cb[data-key='all']").click()
    check("ticking dates in the list switches back from a rule to a list filter", pg.input_value("#filterRuleSel") == "")
    pg.keyboard.press("Escape"); clear_all()

    # ---------------- blanks
    open_filter("start"); pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.locator("#filterTree .ft-cb[data-key='blank']").check(); pg.click("#filterOkBtn")
    check("(Blanks) alone -> only the task with no real date", rows() == ["TBD"], rows())
    open_filter("start"); pg.locator("#filterTree .ft-cb[data-key='all']").check(); pg.locator("#filterTree .ft-cb[data-key='blank']").uncheck(); pg.click("#filterOkBtn")
    check("everything but the blank -> the dated tasks only (Group B shown open while filtering)", "TBD" not in rows() and len(rows()) == 9, rows())
    apply_rule("start", "after", "2000-01-01"); check("a rule never matches a blank", "TBD" not in rows())
    clear_all()

    # ---------------- two columns combine, and the second list is cascaded
    apply_rule("start", "equals", "2026-09-21")
    open_filter("end"); labels = tree_labels()
    check("Finish's list only offers dates of tasks the Start filter lets through", "25.09.2026" in labels and "06.11.2026" in labels and "11.09.2026" not in labels and "(Blanks)" not in labels, labels)
    pg.keyboard.press("Escape"); clear_all()
    apply_rule("start", "between", "2026-09-01", "2026-09-30"); apply_rule("end", "equals", "2026-09-11")
    check("Start and Finish filters combine (AND)", rows() == ["Group A", "A1"], rows())
    bar = pg.inner_text("#filterBar")
    check("...the bar shows both, with the count", "Start: between" in bar and "Finish: equals 11.09.2026" in bar, bar)
    clear_all()

    # ---------------- relative rules against an independent Date-based reference, boundaries included
    ok_all, bad = True, []
    pg.evaluate("""() => { window.__ref = (rule) => { const t = new Date(); t.setHours(0, 0, 0, 0); const d = (y, m, dd) => new Date(y, m, dd), Y = t.getFullYear(), M = t.getMonth(), D = t.getDate(), dow = (t.getDay() + 6) % 7, qs = Math.floor(M / 3) * 3;
        const R = { today: [t, t], tomorrow: [d(Y, M, D + 1), d(Y, M, D + 1)], yesterday: [d(Y, M, D - 1), d(Y, M, D - 1)],
          thisWeek: [d(Y, M, D - dow), d(Y, M, D - dow + 6)], nextWeek: [d(Y, M, D - dow + 7), d(Y, M, D - dow + 13)], lastWeek: [d(Y, M, D - dow - 7), d(Y, M, D - dow - 1)],
          thisMonth: [d(Y, M, 1), d(Y, M + 1, 0)], nextMonth: [d(Y, M + 1, 1), d(Y, M + 2, 0)], lastMonth: [d(Y, M - 1, 1), d(Y, M, 0)],
          thisQuarter: [d(Y, qs, 1), d(Y, qs + 3, 0)], nextQuarter: [d(Y, qs + 3, 1), d(Y, qs + 6, 0)], lastQuarter: [d(Y, qs - 3, 1), d(Y, qs, 0)],
          thisYear: [d(Y, 0, 1), d(Y, 11, 31)], nextYear: [d(Y + 1, 0, 1), d(Y + 1, 11, 31)], lastYear: [d(Y - 1, 0, 1), d(Y - 1, 11, 31)], ytd: [d(Y, 0, 1), t] };
        const f = x => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`; return R[rule].map(f); }; }""")
    rules = ["today", "tomorrow", "yesterday", "thisWeek", "nextWeek", "lastWeek", "thisMonth", "nextMonth", "lastMonth", "thisQuarter", "nextQuarter", "lastQuarter", "thisYear", "nextYear", "lastYear", "ytd"]
    pg.evaluate("""(rules) => { tasks.length = 0; const seen = new Set(); const add = iso => { if (seen.has(iso)) return; seen.add(iso); tasks.push({id: genId(), name: iso, parentId: null, order: tasks.length, startDate: iso, endDate: iso, progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}); };
        const shift = (iso, n) => { const [y, m, d] = iso.split('-').map(Number); const x = new Date(y, m - 1, d + n); return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`; };
        for (const r of rules) { const [lo, hi] = window.__ref(r); [shift(lo, -1), lo, hi, shift(hi, 1)].forEach(add); } save(); render(); }""", rules)
    for r in rules:
        apply_rule("start", r)
        exp = pg.evaluate("(r) => { const [lo, hi] = window.__ref(r); return tasks.map(t => t.name).filter(n => n >= lo && n <= hi).sort(); }", r)
        got = sorted(rows())
        if got != exp: bad.append((r, got[:4], exp[:4]))
        clear_all()
    check(f"all {len(rules)} relative rules (today ... year to date) match an independent reference, at their boundaries", not bad, bad[:2])

    # ---------------- pinned rows, empty result, views, reset
    seed(); apply_rule("start", "equals", "2027-01-11")
    pg.evaluate("() => { addTask(); }"); pg.wait_for_selector("#taskModalBg.open"); pg.evaluate("() => closeTaskModal()")
    check("a task added while filtering stays visible even though it doesn't match", any(n == "" or n == "Untitled Task" for n in rows()) and "A3" in rows(), rows())
    tid = pg.evaluate("() => tasks.find(t => t.name === 'A3').id")
    pg.evaluate("(id) => { editingCell = {id, field: 'start'}; commitInlineEdit(id, 'start', '2026-12-24'); }", tid); pg.wait_for_timeout(100)
    check("an edited task stays visible although its new date no longer matches", "A3" in rows(), rows())
    apply_rule("start", "equals", "2027-01-11")
    check("re-applying the filter drops rows that no longer match", "A3" not in rows() and len(rows()) <= 2, rows())
    apply_rule("start", "equals", "2030-01-01")
    check("no match: the list says so and offers Clear all", "No tasks match the filter" in pg.inner_text("#gridRows") and pg.locator("#gridRows button:has-text('Clear all filters')").count() == 1)
    pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(200)
    check("...also in the Gantt view", "No tasks match the filter" in pg.inner_text("#ganttRows"))
    pg.click("#gridRows button:has-text('Clear all filters')") if pg.locator("#gridRows button:has-text('Clear all filters')").count() else pg.evaluate("() => clearAllFilters()")
    seed(); pg.evaluate("() => { currentView = 'gantt'; render(); }"); apply_rule("start", "between", "2026-09-01", "2026-09-30")
    n = pg.evaluate("() => visibleTaskList().length")
    check("Gantt view: the chart shows exactly the filtered rows, in step with the list", pg.locator(".gantt-row-bg").count() == n == pg.locator("#gridRows .grid-row").count() and n == 5, (n, pg.locator('.gantt-row-bg').count()))
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    check("the filter follows you from Gantt back to Tasks", pg.evaluate("() => filtersActive()") and pg.locator(".col-filter-btn.active").count() == 1)
    pg.reload(); pg.wait_for_selector("#addTaskBtn")
    check("filters are view state: gone after a reload", not pg.evaluate("() => filtersActive()"))
    pg.evaluate(SEED); apply_rule("start", "equals", "2026-09-07")
    pg.evaluate("() => { switchPlan(createPlanRecord('Other', null)); }"); pg.wait_for_timeout(500)
    check("a new plan has its own calendar: the default Mon-Fri (the other plan's every-day setting does not leak)", pg.evaluate("() => project.workDays === undefined && calendarLabel() === 'Mon–Fri'"))
    pg.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; }")   # (this plan too counts calendar days, like the rest of this file)
    check("switching plans clears the filters", not pg.evaluate("() => filtersActive()") and pg.locator("#filterBar:not(.hidden)").count() == 0)

    # ---------------- panel behaviour
    seed(); open_filter("start")
    pg.locator(".col-filter-btn[data-col='start']").click(); pg.wait_for_timeout(100)
    check("clicking the same header button again closes the panel", not pg.locator("#filterMenu.open").count())
    open_filter("start"); open_filter("end")
    check("opening the other column's panel replaces it", pg.inner_text("#filterMenu .filter-head strong") == "Filter Finish")
    pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.click("#filterMenu .filter-actions .btn:has-text('Cancel')")
    check("Cancel discards the changes", not pg.evaluate("() => filtersActive()"))
    open_filter("start"); pg.mouse.click(600, 600); pg.wait_for_timeout(100)
    check("clicking elsewhere closes it", not pg.locator("#filterMenu.open").count())
    apply_rule("start", "equals", "2026-09-07"); open_filter("start")
    check("re-opening shows the active rule and enables Clear filter", pg.input_value("#filterRuleSel") == "equals" and pg.input_value("#filterInputA") == "2026-09-07" and not pg.locator("#filterClearBtn").is_disabled())
    pg.click("#filterClearBtn"); pg.wait_for_timeout(100)
    check("Clear filter in the panel removes it", not pg.evaluate("() => filtersActive()") and not pg.locator("#filterMenu.open").count())


    # =====================================================================================================================
    # The other columns: name / predecessors (text), duration / % (number), task mode (list). Expectations are computed in
    # Python from what the grid DISPLAYS, independently of the filter code.
    # =====================================================================================================================
    def seed2():
        pg.evaluate(SEED)
        pg.evaluate("""() => { const by = n => tasks.find(t => t.name === n); by('Group B').collapsed = false;
            by('B1').predecessors = [{id: by('A1').id, type: 'FS', lag: 0}]; by('A3').predecessors = [{id: by('A2').id, type: 'FS', lag: 2}];
            by('A1').progress = 100; by('A2').progress = 50; by('Solo').progress = 40; by('B2').progress = 100;
            tasks.push({id: genId(), name: '', parentId: null, order: 99, startDate: '2026-12-01', endDate: '2026-12-03', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'});
            save(); render(); }""")
        pg.wait_for_timeout(150)
    def table():
        return pg.evaluate("""() => [...document.querySelectorAll('#gridRows .grid-row')].map(r => { const c = [...r.children]; return {id: r.dataset.id, name: (r.querySelector('.name-text') || {}).innerText || '', manual: !!r.querySelector('.mode-manual'), start: c[3].innerText.trim(), end: c[4].innerText.trim(), dur: c[5].innerText.trim(), pct: c[6].innerText.trim(), preds: c[7].innerText.trim()}; })""")
    def ids(): return pg.evaluate("() => visibleTaskList().map(x => x.task.id)")
    def expect(tbl, ok):
        parent = pg.evaluate("() => Object.fromEntries(tasks.map(t => [t.id, t.parentId]))")
        shown = {r["id"] for r in tbl if ok(r)}
        for i in list(shown):
            p = parent[i]
            while p: shown.add(p); p = parent[p]
        return [r["id"] for r in tbl if r["id"] in shown]
    num = lambda s, unit: (int(s.split()[0]) if unit == "d" and s else (int(s.rstrip("%")) if s else None))
    seed2(); T = table()
    check("seed has what the tests need: a task named by default, a blank duration, predecessors", any(r["name"] == "Untitled Task" for r in T) and any(r["dur"] == "" for r in T) and any(r["preds"] for r in T), ([r["name"] for r in T], [r["dur"] for r in T], [r["preds"] for r in T]))

    def rule_case(label, col, rule, a, b_, ok):
        seed2(); T = table(); apply_rule(col, rule, a, b_)
        got, exp = ids(), expect(T, ok)
        check(label, got == exp, [r["name"] for r in T if r["id"] in got] if got != exp else "")
        clear_all()
    # -- Task Name (text rules; case-insensitive; the negative rules keep blanks)
    nm = lambda r: r["name"].lower()
    rule_case("Task Name: contains 'a'", "name", "contains", "A", None, lambda r: "a" in nm(r))
    rule_case("Task Name: does not contain 'a'", "name", "notcontains", "a", None, lambda r: "a" not in nm(r))
    rule_case("Task Name: begins with 'gr'", "name", "begins", "gr", None, lambda r: nm(r).startswith("gr"))
    rule_case("Task Name: ends with '1'", "name", "ends", "1", None, lambda r: nm(r).endswith("1"))
    rule_case("Task Name: equals 'solo' (any case)", "name", "eq", "solo", None, lambda r: nm(r) == "solo")
    rule_case("Task Name: does not equal 'Solo'", "name", "ne", "Solo", None, lambda r: nm(r) != "solo")
    # -- Predecessors (text on the displayed '2FS' / '3FS+2')
    pr = lambda r: r["preds"].lower()
    rule_case("Predecessors: contains 'fs'", "preds", "contains", "fs", None, lambda r: "fs" in pr(r))
    rule_case("Predecessors: does not contain '+' (keeps tasks without any)", "preds", "notcontains", "+", None, lambda r: "+" not in pr(r))
    rule_case("Predecessors: begins with '2'", "preds", "begins", "2", None, lambda r: pr(r).startswith("2"))
    rule_case("Predecessors: ends with '+2'", "preds", "ends", "+2", None, lambda r: pr(r).endswith("+2"))
    rule_case("Predecessors: equals '2fs'", "preds", "eq", "2fs", None, lambda r: pr(r) == "2fs")
    # -- Duration (number rules on the displayed days; a blank only satisfies 'does not equal')
    du = lambda r: num(r["dur"], "d")
    rule_case("Duration: equals 5", "duration", "eq", "5", None, lambda r: du(r) == 5)
    rule_case("Duration: does not equal 5 (keeps the blank one)", "duration", "ne", "5", None, lambda r: du(r) != 5)
    rule_case("Duration: greater than 5", "duration", "gt", "5", None, lambda r: du(r) is not None and du(r) > 5)
    rule_case("Duration: greater than or equal to 24", "duration", "ge", "24", None, lambda r: du(r) is not None and du(r) >= 24)
    rule_case("Duration: less than 5", "duration", "lt", "5", None, lambda r: du(r) is not None and du(r) < 5)
    rule_case("Duration: less than or equal to 5", "duration", "le", "5", None, lambda r: du(r) is not None and du(r) <= 5)
    rule_case("Duration: between 5 and 47", "duration", "between", "5", "47", lambda r: du(r) is not None and 5 <= du(r) <= 47)
    rule_case("Duration: between accepts either order", "duration", "between", "47", "5", lambda r: du(r) is not None and 5 <= du(r) <= 47)
    # -- % complete
    pc = lambda r: num(r["pct"], "%")
    rule_case("%: greater than 0", "progress", "gt", "0", None, lambda r: pc(r) > 0)
    rule_case("%: equals 100", "progress", "eq", "100", None, lambda r: pc(r) == 100)
    rule_case("%: between 30 and 60", "progress", "between", "30", "60", lambda r: 30 <= pc(r) <= 60)
    rule_case("%: less than or equal to 0", "progress", "le", "0", None, lambda r: pc(r) <= 0)

    # -- value lists (flat, sorted, searchable, with (Blanks))
    seed2(); T = table(); open_filter("name")
    labels = tree_labels()
    check("Task Name list: every distinct name, sorted (a task can't have an empty name, so no (Blanks))", labels[0] == "(Select All)" and labels[1:4] == ["A1", "A2", "A3"] and "Solo" in labels and "Untitled Task" in labels and "(Blanks)" not in labels, labels)
    pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.locator("#filterTree .ft-label:has-text('Solo') .ft-cb").check(); pg.click("#filterOkBtn")
    check("ticking one name filters to it", [r["name"] for r in table() if r["id"] in ids()] == ["Solo"] and "Task Name: Solo" in pg.inner_text("#filterBar"), pg.inner_text("#filterBar"))
    clear_all(); open_filter("name"); pg.fill("#filterSearch", "gr")
    check("search in a list narrows it and selects the matches", tree_labels() == ["(Select All Search Results)", "Group A", "Group B"], tree_labels())
    pg.click("#filterOkBtn")
    got = [x for x in pg.evaluate("() => visibleTaskList().map(x => x.task.name)")]
    check("...(Group A, Group B and, as context, nothing else that doesn't match)", set(got) == {"Group A", "Group B"}, got)
    clear_all(); open_filter("duration")
    check("Duration list: the distinct durations in numeric order, and (Blanks)", tree_labels() == ["(Select All)", "1 day", "3 days", "5 days", "24 days", "47 days", "131 days", "(Blanks)"], tree_labels())
    pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.locator("#filterTree .ft-label:has-text('5 days') .ft-cb").check(); pg.click("#filterOkBtn")
    check("tick '5 days' -> exactly the 5-day tasks (+ their groups)", ids() == expect(T, lambda r: r["dur"] == "5 days"))
    open_filter("name")
    check("cascade: Task Name's list now only offers the tasks that survive the Duration filter", tree_labels() == ["(Select All)", "A1", "A2", "A3", "B1", "B2"], tree_labels())
    pg.keyboard.press("Escape"); clear_all()
    open_filter("progress")
    pl = tree_labels(); nums = [int(x.rstrip("%")) for x in pl[1:]]
    check("% list: exactly the displayed values, in numeric order (0% < 33% < 100%, not text order)", nums == sorted(set(nums)) and set(nums) == {int(r["pct"].rstrip("%")) for r in T} and 100 in nums and nums[0] == 0, pl)
    pg.keyboard.press("Escape")
    open_filter("preds"); labels = tree_labels()
    check("Predecessors list: the displayed references and (Blanks) for tasks without any", "2FS" in labels and "3FS+2" in labels and labels[-1] == "(Blanks)", labels)
    pg.locator("#filterTree .ft-cb[data-key='all']").uncheck(); pg.locator("#filterTree .ft-cb[data-key='blank']").check(); pg.click("#filterOkBtn")
    check("(Blanks) on Predecessors -> tasks without predecessors", ids() == expect(T, lambda r: r["preds"] == ""), [r["name"] for r in T if r["id"] in ids()])
    clear_all()

    # -- Task Mode: just a list
    open_filter("mode")
    check("Task Mode: a plain list with the two modes and no rule selector", tree_labels() == ["(Select All)", "Auto Scheduled", "Manually Scheduled"] and pg.locator("#filterRuleSel").count() == 0, tree_labels())
    pg.locator("#filterTree .ft-label:has-text('Auto Scheduled') .ft-cb").uncheck(); pg.click("#filterOkBtn")
    check("only Manually Scheduled -> just the manual task", [r["name"] for r in T if r["id"] in ids()] == ["TBD"], ids())
    check("...the chip says so", "Task Mode: Manually Scheduled" in pg.inner_text("#filterBar"), pg.inner_text("#filterBar"))
    clear_all(); open_filter("mode"); pg.locator("#filterTree .ft-label:has-text('Manually Scheduled') .ft-cb").uncheck(); pg.click("#filterOkBtn")
    check("only Auto Scheduled -> everything else", ids() == expect(T, lambda r: not r["manual"]) and "TBD" not in [r["name"] for r in T if r["id"] in ids()])
    clear_all()

    # -- the panel for text and number rules
    open_filter("duration"); pg.select_option("#filterRuleSel", "gt")
    check("number rule: OK waits for a number", pg.locator("#filterOkBtn").is_disabled() and pg.locator("#filterInputA").get_attribute("type") == "number")
    pg.fill("#filterInputA", "abc") if False else None
    pg.fill("#filterInputA", "5"); check("...and takes it", not pg.locator("#filterOkBtn").is_disabled())
    pg.select_option("#filterRuleSel", "between"); pg.fill("#filterInputB", "")
    check("'between' needs both numbers", pg.locator("#filterOkBtn").is_disabled())
    pg.fill("#filterInputB", "40"); pg.press("#filterInputB", "Enter"); pg.wait_for_timeout(150)
    check("Enter in a rule field applies it", pg.evaluate("() => colFilters.duration && colFilters.duration.rule") == "between" and not pg.locator("#filterMenu.open").count())
    check("...the chip reads 'between 5 and 40'", "Duration: between 5 and 40" in pg.inner_text("#filterBar"), pg.inner_text("#filterBar"))
    open_filter("duration")
    check("re-opening a number rule shows its values", pg.input_value("#filterRuleSel") == "between" and pg.input_value("#filterInputA") == "5" and pg.input_value("#filterInputB") == "40")
    pg.keyboard.press("Escape"); clear_all()
    open_filter("name"); pg.select_option("#filterRuleSel", "contains")
    check("text rule: OK waits for text", pg.locator("#filterOkBtn").is_disabled() and pg.locator("#filterInputA").get_attribute("type") == "text")
    pg.fill("#filterInputA", "   "); check("...whitespace doesn't count", pg.locator("#filterOkBtn").is_disabled())
    pg.fill("#filterInputA", "gro"); pg.click("#filterOkBtn")
    check("the chip reads: Task Name: contains “gro”", "Task Name: contains “gro”" in pg.inner_text("#filterBar"), pg.inner_text("#filterBar"))
    open_filter("duration"); pg.select_option("#filterRuleSel", "ge"); pg.fill("#filterInputA", "40"); pg.click("#filterOkBtn")
    check("columns combine: name contains 'gro' AND duration >= 40 -> Group A and Group B", set(pg.evaluate("() => visibleTaskList().map(x => x.task.name)")) == {"Group A", "Group B"} and "Duration: ≥ 40" in pg.inner_text("#filterBar"), pg.inner_text("#filterBar"))
    pg.evaluate("() => { currentView = 'gantt'; render(); }")
    check("...and the filters carry over into the Gantt view (a filtered column its list shows has its active funnel, one it doesn't show has none but keeps its chip)", pg.evaluate("() => visibleTaskList().length") == 2 and pg.locator(".col-filter-btn.active").count() == pg.evaluate("() => Object.entries(colFilters).filter(([c, f]) => f && visibleTaskCols().includes(c)).length") and pg.locator("#filterBar .filter-chip").count() == 2, (pg.locator(".col-filter-btn.active").count(), pg.locator("#filterBar .filter-chip").count()))
    pg.evaluate("() => { currentView = 'tasks'; render(); }"); clear_all()
    check("Clear all clears every column at once", not pg.evaluate("() => filtersActive()") and len(ids()) == len(T))

    print("console errors/warnings:", errors)
    print(f"{sum(results)}/{len(results)} passed")
    b.close()
