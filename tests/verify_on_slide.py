"""On Slide: a Yes / No mark on a task (or a group, which takes everything below it) that the Chart for Slides can take as "the tasks marked On Slide". It is a column
(hidden until ticked, a click toggles it), a filter, a switch in the task dialog, a field of Edit Tasks, an item of the right-click menu, saved with the plan, and in the
CSV and Excel exports; the chart offers the scope only when something is marked."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
SEED = """() => {
  const mk = (id, name, parent, order, s, e, extra) => Object.assign({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'manual', updatedAt: 1 }, extra || {});
  tasks = [ mk('a','Alpha',null,0,'2027-01-04','2027-02-26'), mk('a1','A one','a',0,'2027-01-04','2027-01-29'), mk('a2','A two','a',1,'2027-02-01','2027-02-26'),
            mk('b','Beta',null,1,'2027-03-01','2027-04-30'), mk('b1','B one','b',0,'2027-03-01','2027-03-31'), mk('b2','B two','b',1,'2027-04-01','2027-04-30'), mk('c','Solo',null,2,'2027-05-03','2027-05-14') ];
  normalizeData(); save(); render();
}"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 900}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(300)
    marked = lambda: ev("() => tasks.filter(t => t.onSlide).map(t => t.name)")
    check("the column 'On Slide' exists and is hidden until ticked", ev("() => !!TASK_COLS.onSlide && TASK_COLS.onSlide.label === 'On Slide' && colHidden.has('onSlide')"))
    ev("() => { colHidden.delete('onSlide'); save(); render(); }"); pg.wait_for_timeout(200)
    check("shown, it has a header and a cell for each task", pg.locator(".col-head:has-text('On Slide')").count() == 1 and pg.locator(".grid-row .custom-flag[onclick*='toggleOnSlide']").count() == 7)
    pg.locator(".grid-row:has-text('A one') .custom-flag[onclick*='toggleOnSlide']").click(); pg.wait_for_timeout(200)
    check("a click marks a task: a tick appears and the task carries onSlide", marked() == ["A one"] and pg.locator(".grid-row:has-text('A one') .custom-flag i.fa-check").count() == 1, marked())
    pg.locator(".grid-row:has-text('A one') .custom-flag[onclick*='toggleOnSlide']").click(); pg.wait_for_timeout(200)
    check("a second click takes it off, and the key is gone (nothing empty is stored)", marked() == [] and ev("() => tasks.every(t => !('onSlide' in t))"))
    pg.locator(".grid-row:has-text('Beta') .custom-flag[onclick*='toggleOnSlide']").first.click(); pg.wait_for_timeout(200)
    check("a group can be marked too", marked() == ["Beta"], marked())

    # undo / reload / clone
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(200)
    check("Undo takes the mark back", marked() == [])
    ev("() => { toggleOnSlide('a2'); }"); pg.wait_for_timeout(100); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(200)
    check("the mark is saved with the plan: still there after a reload", marked() == ["A two"], marked())
    ev("() => { setSelection(['a2']); cloneSelected(); }"); pg.wait_for_timeout(250)
    check("Duplicate copies the mark", sorted(marked()) == ["A two", "A two (copy)"], marked())
    ev("() => { selectedTaskIds.clear(); }")

    # the task dialog
    ev("() => openTaskModal('b1')"); pg.wait_for_timeout(200)
    check("the task dialog has an 'On Slide' switch, off for an unmarked task", pg.is_visible("#taskOnSlideInput") and not pg.is_checked("#taskOnSlideInput"))
    pos = ev("() => { const r = id => document.getElementById(id).getBoundingClientRect().top; return [r('taskColorSwatches'), r('taskOnSlideInput'), r('taskMilestoneInput')]; }")
    check("...it sits right under Color (with how the task shows), not beside Milestone (what kind of task it is)", 0 < pos[1] - pos[0] < 60 and pos[1] > pos[2], pos)
    pg.check("#taskOnSlideInput", force=True); ev("() => saveTaskFromModal()"); pg.wait_for_timeout(250)
    check("saving the dialog with it on marks the task", "B one" in marked(), marked())
    ev("() => openTaskModal('b1')"); pg.wait_for_timeout(150)
    check("...and the dialog shows it on next time", pg.is_checked("#taskOnSlideInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    if pg.locator("#confirmModalBg.open").count(): pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(150)

    # Edit Tasks (several selected)
    ev("() => { tasks.forEach(t => delete t.onSlide); save(); render(); }")
    ev("() => { setSelection(['b1', 'b2', 'c']); openBulkModal(); }"); pg.wait_for_timeout(250)
    check("Edit Tasks has an 'On Slide' field", pg.is_visible("#bulkOn-onSlide") and pg.is_visible("#bulkVal-onSlide"))
    pg.check("#bulkOn-onSlide", force=True); pg.select_option("#bulkVal-onSlide", "yes"); pg.click("#bulkApplyBtn"); pg.wait_for_timeout(300)
    check("applying 'Yes' marks all selected tasks", sorted(marked()) == ["B one", "B two", "Solo"], marked())
    ev("() => { setSelection(['b1', 'b2']); openBulkModal(); }"); pg.wait_for_timeout(250)
    pg.check("#bulkOn-onSlide", force=True); pg.select_option("#bulkVal-onSlide", "no"); pg.click("#bulkApplyBtn"); pg.wait_for_timeout(300)
    check("applying 'No' takes them off again", marked() == ["Solo"], marked())

    # right-click menu: On Slide is not there (too much for a menu that is already long)
    ev("() => { selectedTaskIds.clear(); setSelection(['a1']); }")
    pg.locator(".grid-row:has-text('A one')").first.click(button="right"); pg.wait_for_selector("#rowMenu.open")
    check("the right-click menu has no On Slide item", "Slide" not in pg.inner_text("#rowMenu"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    ev("() => { toggleOnSlide('a1'); toggleOnSlide('c'); }"); pg.wait_for_timeout(100)

    # the filter
    ev("() => { colFilters = newColFilters(); }")
    check("the filter lists Yes first, then No", ev("() => { const v = ['No', 'Yes'].sort(filterCompare('list', 'onSlide')); return v.join(); }") == "Yes,No")
    check("the filter value is Yes / No", ev("() => [filterColValue(byId('a1'), 'onSlide'), filterColValue(byId('a2'), 'onSlide')]") == ["Yes", "No"])

    # CSV and Excel use the column
    csv = ev("() => { const o = { scope: 'all', columns: ['name', 'onSlide'], sep: ',' }; return buildCsv(o); }")
    check("the CSV export carries the column: 'Yes' for a marked task, empty otherwise", "On Slide" in csv and __import__("re").search(r"A one,.*,Yes\s", csv) is not None and __import__("re").search(r"A two,.*,\s", csv) is not None, csv[:200])

    # the chart: the scope appears only when something is marked
    ev("() => { tasks.forEach(t => delete t.onSlide); save(); render(); openSlideChart(); }"); pg.wait_for_timeout(300)
    check("the chart dialog does not offer 'marked' while nothing is marked", pg.locator("#scScopeMarked.hidden").count() == 1)
    ev("() => closeSlideChart()")
    ev("() => { toggleOnSlide('a1'); toggleOnSlide('b'); toggleOnSlide('c'); openSlideChart(); }"); pg.wait_for_timeout(300)
    check("with marks it offers 'The tasks marked On Slide' with their count", pg.locator("#scScopeMarked:not(.hidden)").count() == 1 and "3 tasks" in pg.inner_text("#scScopeMarkedN"), pg.inner_text("#scScopeMarkedN"))
    pg.locator("input[name=scScope][value=marked]").check(force=True); pg.wait_for_timeout(300)
    check("choosing it draws A one, the whole of Beta (a marked group takes everything below it) and Solo: 4 rows", ev("() => scBuilt.rows") == 4, ev("() => scBuilt.rows"))
    svg = ev("() => scBuilt.charts[0]")
    check("...and not the unmarked tasks (A two)", "A two" not in svg and "A one" in svg and "Solo" in svg)
    ev("() => { closeSlideChart(); toggleOnSlide('b'); openSlideChart(); }"); pg.wait_for_timeout(250)
    check("the choice is remembered ('marked' stays chosen when there are still marks)", pg.is_checked("input[name=scScope][value=marked]"))
    ev("() => { closeSlideChart(); tasks.forEach(t => delete t.onSlide); save(); render(); openSlideChart(); }"); pg.wait_for_timeout(250)
    check("when the last mark goes the scope falls back to the whole plan", pg.is_checked("input[name=scScope][value=all]"))
    ev("() => closeSlideChart()")
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
