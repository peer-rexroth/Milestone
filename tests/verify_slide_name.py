"""Slide Name: an optional short label on a task (or group, or milestone) that the Chart for Slides draws instead of the name. A column (hidden until shown, a click opens
the task dialog on it), a row of the task dialog, saved with the plan, in the CSV / Excel exports, read back by the import; the chart says how many labels it had to
shorten and offers to select them for typing a Slide Name."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
LONG = "Run the complete vendor selection process for the new customer relationship platform including reference calls"
SEED = """(LONG) => {
  const mk = (id, name, parent, order, s, e, extra) => Object.assign({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'manual', updatedAt: 1 }, extra || {});
  tasks = [ mk('a','Discovery',null,0,'2027-01-04','2027-02-26'), mk('a1', LONG,'a',0,'2027-01-04','2027-01-29'), mk('a2','Short one','a',1,'2027-02-01','2027-02-26') ];
  normalizeData(); save(); render();
}"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 1200}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED, LONG); pg.wait_for_timeout(300)
    names = lambda: ev("() => tasks.filter(t => t.slideName).map(t => t.name + '=' + t.slideName)")
    check("the column 'Slide Name' exists and is hidden until shown", ev("() => !!TASK_COLS.slideName && TASK_COLS.slideName.label === 'Slide Name' && colHidden.has('slideName')"))
    ev("() => { colHidden.delete('slideName'); save(); render(); }"); pg.wait_for_timeout(200)
    check("shown, it has a header", pg.locator(".col-head:has-text('Slide Name')").count() == 1)
    pg.locator(".grid-row:has-text('Short one') .grid-cell-dim.editable[onclick*='openTaskSlideName']").click(); pg.wait_for_timeout(300)
    check("a click on its cell opens the task dialog with the cursor in Slide Name", pg.evaluate("() => document.activeElement && document.activeElement.id") == "taskSlideNameInput")
    pg.fill("#taskSlideNameInput", "  Short  "); ev("() => saveTaskFromModal()"); pg.wait_for_timeout(250)
    check("saving keeps it, trimmed", names() == ["Short one=Short"], names())
    ev("() => openTaskModal('a2')"); pg.wait_for_timeout(200)
    check("the dialog shows it next time, in the group with Color and On Slide (how the task shows)", pg.input_value("#taskSlideNameInput") == "Short" and abs(ev("() => document.getElementById('taskSlideNameInput').getBoundingClientRect().top - document.getElementById('taskOnSlideInput').getBoundingClientRect().top")) < 130)
    pg.fill("#taskSlideNameInput", ""); ev("() => saveTaskFromModal()"); pg.wait_for_timeout(200)
    check("emptying it removes the key (nothing empty is stored)", ev("() => tasks.every(t => !('slideName' in t))"))
    ev("() => { byId('a2').slideName = 'Short'; save(); render(); }")
    pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(200)
    check("it is saved with the plan", names() == ["Short one=Short"], names())
    ev("() => { setSelection(['a2']); cloneSelected(); }"); pg.wait_for_timeout(250)
    check("Duplicate copies it", sorted(names()) == ["Short one (copy)=Short", "Short one=Short"], names())
    ev("() => { tasks = tasks.filter(t => !/copy/.test(t.name)); normalizeData(); save(); render(); }")
    csv = ev("() => buildCsv({ scope: 'all', columns: ['name', 'slideName'], sep: ',' })")
    check("the CSV export carries the column", "Slide Name" in csv and "Short one,Short," in csv, csv[:200])

    # the chart
    ev("() => { openSlideChart(); }"); pg.wait_for_timeout(300)
    svg = ev("() => scBuilt.charts[0]")
    check("the chart draws the Slide Name instead of the name", ">Short<" in svg and "Short one" not in svg)
    check("a label too long for its column is cut, and the chart reports it", ev("() => scBuilt.cut.includes('a1')") and not ev("() => scBuilt.cut.includes('a2')"), ev("() => scBuilt.cut"))
    check("the dialog says so, with 'Add Slide Names…'", pg.is_visible("#scCutNote") and "1 label is shortened" in pg.inner_text("#scCutText") and pg.locator("#scCutNote button").count() == 1, pg.inner_text("#scCutNote"))
    pg.click("#scCutNote button"); pg.wait_for_timeout(400)
    check("it closes the chart, shows the column and selects the shortened task", pg.locator("#slideChartModalBg.open").count() == 0 and ev("() => [...selectedTaskIds]") == ["a1"] and not ev("() => colHidden.has('slideName')"), ev("() => [...selectedTaskIds]"))
    ev("() => { byId('a1').slideName = 'Vendor selection'; save(); render(); openSlideChart(); }"); pg.wait_for_timeout(300)
    check("with a Slide Name on it nothing is shortened: the note is gone", ev("() => scBuilt.cut.length") == 0 and not pg.is_visible("#scCutNote"), ev("() => scBuilt.cut"))
    ev("() => closeSlideChart()")
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
