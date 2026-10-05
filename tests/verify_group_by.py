# -*- coding: utf-8 -*-
"""Group by (Tasks view): the toolbar button and menu, a header per value with count and roll-ups, the values' order, folding, the status-bar chip,
columns (Status, Resource, months, % bands, custom fields), selection and keyboard on the displayed order, moving blocked, filters and sort inside,
the Gantt view keeping the outline, the column-header menu, large plans. See "Group by" in CLAUDE.md."""
import os, time
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """(extra) => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.timeUnit; delete project.fieldNames; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now() }, x || {});
  tasks.push(mk('g', 'Design phase', '2030-03-04', '2030-04-12'),
    mk('a', 'Discovery workshop', '2030-03-04', '2030-03-08', { parentId: 'g', progress: 100, resource: 'Anna', custom: { text1: 'Web', flag1: true } }),
    mk('b', 'Information architecture', '2030-03-11', '2030-03-22', { parentId: 'g', progress: 40, resource: 'Ben', custom: { text1: 'Web' } }),
    mk('c', 'Visual design', '2030-03-25', '2030-04-12', { parentId: 'g', resource: 'Anna', custom: { text1: 'App' } }),
    mk('d', 'Build', '2030-04-15', '2030-05-03', { resource: 'Ben' }),
    mk('m', 'Launch', '2030-05-06', '2030-05-06', { milestone: true }));
  tasks.push(mk('sp', '', '2030-03-04', '2030-03-04', { spacer: true }));
  for (let i = 0; i < (extra || 0); i++) tasks.push(mk('x' + i, 'Extra ' + i, '2030-06-0' + (1 + i % 9), '2030-06-1' + (i % 9), { resource: 'R' + (i % 7), progress: (i * 13) % 101 }));
  project.fieldNames = { text1: 'Squad' };
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; groupSpec = null; groupCollapsed.clear(); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED, 0); pg.wait_for_timeout(250)
    heads = lambda: [h.split("\n")[0].strip() for h in pg.locator("#gridRows .group-head .group-head-name").all_inner_texts()]
    names = lambda: pg.locator("#gridRows .grid-row:not(.group-head) .name-text").all_inner_texts()
    rows = lambda: pg.evaluate("() => [...document.querySelectorAll('#gridRows .grid-row')].map(r => r.classList.contains('group-head') ? 'H:' + r.querySelector('.name-text').textContent : r.querySelector('.name-text').textContent.trim())")
    def group(label):
        pg.click("#groupBtn"); pg.wait_for_selector("#groupMenu.open"); pg.click(f"#groupMenu button:has-text('{label}')"); pg.wait_for_timeout(250)
    check("the Tasks view's toolbar has a Group button; nothing is grouped at first", pg.is_visible("#groupBtn") and pg.get_attribute("#groupBtn", "aria-pressed") == "false" and not heads())
    pg.click("#groupBtn"); pg.wait_for_selector("#groupMenu.open")
    items = pg.locator("#groupMenu .dropdown-item").all_inner_texts()
    check("its menu: None plus Status, Resource, Task Mode, Task Type, Start, Finish, Deadline, % Complete and the custom field in use (by its plan name)", [i.strip() for i in items][:9] == ["None — the outline", "Status", "Resource", "Task Mode", "Task Type", "Start", "Finish", "Deadline", "% Complete"] and "Squad" in [i.strip() for i in items], items)
    check("None is ticked while nothing is grouped", pg.locator("#groupMenu [aria-checked=true]").count() == 1 and "None" in pg.locator("#groupMenu [aria-checked=true]").inner_text())
    pg.click("#groupMenu button:has-text('Resource')"); pg.wait_for_timeout(250)
    check("Group by Resource: a header per value — Anna, Ben, then (none) last", heads() == ["Anna", "Ben", "(none)"], heads())
    r = rows()
    check("...the tasks sit under their header: Discovery + Visual design under Anna, Information architecture + Build under Ben, Launch under (none)", r == ["H:Anna", "Discovery workshop", "Visual design", "H:Ben", "Information architecture", "Build", "H:(none)", "Launch"], r)
    check("...the summary task ('Design phase') and the empty line are not listed", "Design phase" not in " ".join(r) and not any(x == "" for x in r))
    hh = pg.locator("#gridRows .group-head").first.inner_text()
    check("a header shows its task count", "2 tasks" in hh, hh)
    check("...and the span, % of its tasks: Anna 04.03.2030 – 12.04.2030, 21% (weighted by duration: 5 days at 100%, 19 at 0%)", "04.03.2030" in hh and "12.04.2030" in hh and "21%" in hh, hh)
    check("task IDs are still their outline numbers (2 for Discovery, 4 for Visual design)", ev("() => [...document.querySelectorAll('#gridRows .grid-row:not(.group-head)')].slice(0, 2).map(r => r.firstElementChild.textContent.trim())") == ["2", "4"])
    chip = pg.inner_text("#filterBar")
    check("the status bar says 'Grouped by Resource' with a × to clear it", "Grouped by Resource" in chip and pg.is_visible("#filterBar") and pg.get_attribute("#groupBtn", "aria-pressed") == "true", chip)
    check("the Group button is lit and says what it is grouped by", "Resource" in pg.get_attribute("#groupBtn", "title"))
    check("moving is off: rows aren't draggable, and the collapse-all arrow is disabled", ev("() => [...document.querySelectorAll('#gridRows .grid-row:not(.group-head)')].every(r => r.draggable === false)") and pg.is_disabled("#collapseToggleBtn"))
    ev("() => { setSelection(['b']); render(); }"); pg.click("#indentBtn"); pg.wait_for_timeout(150)
    check("indent is refused with a message while grouped", "grouped" in ev("() => document.getElementById('toastMsg').textContent") and ev("() => tasks.find(t => t.id === 'b').parentId") == "g")
    # fold
    pg.locator("#gridRows .group-head").first.click(); pg.wait_for_timeout(200)
    check("clicking a header folds its group (the tasks go, the count stays)", heads()[0] == "Anna" and "Discovery workshop" not in names() and pg.locator("#gridRows .group-head").first.get_attribute("aria-expanded") == "false" and "2 tasks" in pg.locator("#gridRows .group-head").first.inner_text())
    pg.locator("#gridRows .group-head").first.focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("Enter on a focused header opens it again", "Discovery workshop" in names() and pg.locator("#gridRows .group-head").first.get_attribute("aria-expanded") == "true")
    pg.click("#groupBtn"); pg.click("#groupMenu button:has-text('Collapse all groups')"); pg.wait_for_timeout(200)
    check("the menu's Collapse all groups folds every group", not names() and len(heads()) == 3)
    pg.click("#groupBtn"); pg.click("#groupMenu button:has-text('Expand all groups')"); pg.wait_for_timeout(200)
    check("...and Expand all opens them", len(names()) == 5)
    # selection on displayed order
    pg.locator("#gridRows .grid-row:not(.group-head)").nth(0).locator(":scope > div").first.click(); pg.locator("#gridRows .grid-row:not(.group-head)").nth(2).locator(":scope > div").first.click(modifiers=["Shift"]); pg.wait_for_timeout(150)
    check("Shift+click selects the rows between, in the displayed order, headers skipped (Discovery → Information architecture = Discovery, Visual design, Information architecture)", sorted(ev("() => selectedIds()")) == sorted(["a", "c", "b"]), ev("() => selectedIds()"))
    pg.keyboard.press("Control+a"); pg.wait_for_timeout(100)
    check("Ctrl+A selects the five listed tasks (not the summary task, not headers)", sorted(ev("() => selectedIds()")) == sorted(["a", "b", "c", "d", "m"]), ev("() => selectedIds()"))
    ev("() => { setSelection([]); render(); }")
    # add task keeps its group open
    pg.locator("#gridRows .group-head").nth(1).click(); pg.wait_for_timeout(150)
    ev("() => { tasks.find(t => t.id === 'd').name = 'Build!'; save(); }")
    ev("() => { jumpToTask('d'); }"); pg.wait_for_timeout(500)
    check("jumping to a task in a folded group (Find) opens the group", "Build!" in names())
    # status
    group("Status"); h = heads()
    check("Group by Status: in the status order — On Schedule, Future Task, Complete", h == ["On Schedule", "Future Task", "Complete"], h)
    check("...Complete holds Discovery workshop; Future Task holds three (Visual design, Build, Launch)", rows()[-2:] == ["H:Complete", "Discovery workshop"] and rows()[2:6] == ["H:Future Task", "Visual design", "Build!", "Launch"], rows())
    # start month
    group("Start"); h = heads()
    check("Group by Start: one header per month, oldest first (March 2030, April 2030, May 2030)", h == ["March 2030", "April 2030", "May 2030"], h)
    # % complete
    group("% Complete"); h = heads()
    check("Group by % Complete: bands in order (Not started, Started, Complete)", h == ["Not started (0%)", "Started (1–49%)", "Complete (100%)"], h)
    # task mode & type
    group("Task Mode"); check("Group by Task Mode: one group, Auto Scheduled, holding all five", heads() == ["Auto Scheduled"] and len(names()) == 5, heads())
    group("Task Type"); check("Group by Task Type: Fixed Units for the four ordinary tasks, a milestone has none (shown under (none))", heads() == ["Fixed Units", "(none)"] and names()[-1].strip().endswith("Launch"), (heads(), names()))
    # custom
    group("Squad"); h = heads()
    check("Group by a custom text field (the plan's name 'Squad'): App, Web, then (none)", h == ["App", "Web", "(none)"], h)
    check("the chip names the field by its plan name", "Grouped by Squad" in pg.inner_text("#filterBar"))
    # sort inside
    ev("() => { setSort('name', -1); }"); pg.wait_for_timeout(200)
    r = rows()
    check("a sort works inside the groups (Web: Information architecture before Discovery workshop when sorted Z → A)", r.index("Information architecture") < r.index("Discovery workshop"), r)
    ev("() => setSort(null, 0)")
    # filter inside
    ev("() => { filterPinned.clear(); colFilters.resource = { type: 'values', values: new Set(['Anna']), blanks: false }; render(); }"); pg.wait_for_timeout(200)
    check("a filter applies first: only the matching tasks, empty groups vanish (Web has just Discovery, App just Visual design)", [x for x in rows() if not x.startswith("H:")] == ["Visual design", "Discovery workshop"] and heads() == ["App", "Web"], rows())
    ev("() => { for (const k of Object.keys(colFilters)) colFilters[k] = null; filterPinned.clear(); render(); }")
    # gantt keeps the outline
    pg.click(".view-tab:has-text('Gantt')"); pg.wait_for_timeout(400)
    check("the Gantt view keeps the outline: no headers, the summary task is listed, and the Group button is hidden", not heads() and "Design phase" in names() and not pg.is_visible("#groupBtn") and "Grouped" not in pg.inner_text("#filterBar"))
    pg.click(".view-tab:has-text('Tasks')"); pg.wait_for_timeout(300)
    check("back in the Tasks view the grouping is still on", len(heads()) == 3)
    # header context menu
    pg.locator("#gridHeader .col-head").nth(0).click(button="right"); pg.wait_for_timeout(150)
    # right-click the Resource column header
    ev("() => { const h = [...document.querySelectorAll('#gridHeader .col-head')].find(x => x.textContent.trim().toUpperCase().startsWith('RESOURCE')); h.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 600, clientY: 120 })); }"); pg.wait_for_timeout(150)
    check("a column header's right-click menu offers 'Group by Resource' and 'Clear grouping'", "Group by Resource" in pg.inner_text("#colWidthMenu") and "Clear grouping" in pg.inner_text("#colWidthMenu"), pg.inner_text("#colWidthMenu"))
    pg.click("#colWidthMenu button:has-text('Clear grouping')"); pg.wait_for_timeout(250)
    check("Clear grouping brings the outline back (summary task and sub-tasks)", not heads() and "Design phase" in names() and not pg.is_visible("#filterBar"))
    # right-click menus: a group's own "Add sub-task", and a group header's menu
    rowmenu = lambda: [x.strip().split("\n")[0] for x in pg.locator("#rowMenu .dropdown-item").all_inner_texts()]
    pg.locator("#gridRows .grid-row[data-id='g']").click(button="right", position={"x": 300, "y": 10}); pg.wait_for_timeout(150)
    check("right-click on a group (a task with sub-tasks) says 'Add sub-task', since that is where the new task goes", "Add sub-task" in rowmenu() and "Add task below" not in rowmenu(), rowmenu())
    pg.keyboard.press("Escape")
    pg.locator("#gridRows .grid-row[data-id='d']").click(button="right", position={"x": 300, "y": 10}); pg.wait_for_timeout(150)
    check("...a task without sub-tasks keeps 'Add task below'", "Add task below" in rowmenu() and "Add sub-task" not in rowmenu(), rowmenu())
    pg.keyboard.press("Escape")
    ev("() => { setGroup('resource'); }"); pg.wait_for_timeout(250)
    pg.locator("#gridRows .group-head").first.click(button="right"); pg.wait_for_timeout(150)
    check("right-click on a group header: Collapse this group, Collapse all, Expand all, Clear grouping (no task items)", rowmenu() == ["Collapse this group", "Collapse all groups", "Expand all groups", "Clear grouping"], rowmenu())
    pg.click("#rowMenu >> text=Collapse this group"); pg.wait_for_timeout(200)
    check("...Collapse this group folds it, and the menu then offers 'Expand this group'", "Discovery workshop" not in names() and pg.locator("#gridRows .group-head").first.get_attribute("aria-expanded") == "false")
    pg.locator("#gridRows .group-head").first.click(button="right"); pg.wait_for_timeout(150)
    check("...and the menu then offers 'Expand this group'", rowmenu()[0] == "Expand this group", rowmenu())
    pg.click("#rowMenu >> text=Clear grouping"); pg.wait_for_timeout(200)
    check("...and Clear grouping from it brings the outline back", not heads() and "Design phase" in names())
    ev("() => { setGroup('resource'); }")
    ev("() => { resetTransientUI(); render(); }"); pg.wait_for_timeout(200)
    check("switching plans (resetTransientUI) clears a grouping", not heads())
    # a very big plan
    ev(SEED, 600); pg.wait_for_timeout(500)
    t0 = time.time(); ev("() => { setGroup('resource'); }"); pg.wait_for_timeout(300); dt = time.time() - t0
    n = ev("() => displayRows().length")
    check("a large plan: 600+ tasks grouped by Resource still builds only the window (virtualised), with headers counted as rows", ev("() => renderedWin.virtual") and ev("() => document.querySelectorAll('#gridRows .grid-row').length") < 120 and n > 600, (n, dt))
    ev("() => { document.getElementById('gridRows').scrollTop = 200 * 32; }"); pg.wait_for_timeout(300)
    check("scrolling far shows rows from the middle (headers and tasks) with no blank gap", pg.locator("#gridRows .grid-row").count() > 20 and ev("() => { const r = document.querySelector('#gridRows .grid-row'); return r.getBoundingClientRect().top < 400; }"))
    ev("() => { jumpToTask('x599'); }"); pg.wait_for_timeout(600)
    check("jump to a far task scrolls to it in the grouped list", pg.locator("#gridRows .grid-row[data-id='x599']").count() == 1)
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
