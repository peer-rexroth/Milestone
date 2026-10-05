# -*- coding: utf-8 -*-
"""Export to CSV (Data menu): the dialog, the columns and rows, quoting, separators, the formula guard, the BOM, a filtered scope, and the round trip
through Milestone's own CSV import. See "Export to CSV" in CLAUDE.md."""
import os, re, tempfile
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """() => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.timeUnit; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now() }, x || {});
  tasks.push(mk('g', 'Phase 1', '2030-03-04', '2030-03-15'),
    mk('a', 'Design, "final"', '2030-03-04', '2030-03-08', { parentId: 'g', progress: 50, resource: 'Anna[50%], Ben' }),
    mk('b', 'Build', '2030-03-11', '2030-03-15', { parentId: 'g', predecessors: [{ id: 'a', type: 'FS', lag: 0 }], notes: 'line one\\nline two' }),
    mk('m', 'Launch', '2030-03-15', '2030-03-15', { milestone: true }),
    mk('f', '=SUM(A1)', '2030-03-18', '2030-03-19'));
  tasks.push(mk('sp', '', '2030-03-04', '2030-03-04', { spacer: true }));
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 800}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(250)
    def export(scope="all", cols="shown", sep=","):
        pg.click("#dataMenuBtn"); pg.click("#csvExportItem"); pg.wait_for_selector("#csvModalBg.open")
        if pg.locator("#csvScopeBlock").is_visible(): pg.check(f"input[name='csvScope'][value='{scope}']")
        pg.check(f"input[name='csvCols'][value='{cols}']"); pg.select_option("#csvSep", sep)
        with pg.expect_download() as d: pg.click("#csvExportBtn")
        path = os.path.join(tempfile.mkdtemp(), "x.csv"); d.value.save_as(path); return d.value.suggested_filename, open(path, "rb").read()
    check("the Data menu has 'Export to CSV…'", (pg.click("#dataMenuBtn") or True) and "Export to CSV" in pg.inner_text("#csvExportItem"))
    pg.keyboard.press("Escape")
    name, raw = export(sep=",")
    text = raw.decode("utf-8")
    check("the file is named after the plan and the date, .csv", re.fullmatch(r".+-\d{4}-\d{2}-\d{2}\.csv", name), name)
    check("UTF-8 with a BOM (Excel reads umlauts)", raw[:3] == b"\xef\xbb\xbf")
    lines = text.lstrip("﻿").split("\r\n")
    check("CRLF line ends and a final line end", text.endswith("\r\n") and "\n" not in text.replace("\r\n", ""))
    check("the header row: ID and the shown columns' labels", lines[0].startswith("ID,Task Name,Start,Finish,Duration,% Complete,Predecessors,Resource,Status"), lines[0])
    check("5 tasks and an empty line = 6 data rows plus the header", len([l for l in lines if l]) == 7, len(lines))
    check("a group's rollup dates and its sub-tasks are indented by two spaces per level", any(l.split(",")[1] == "Phase 1" for l in lines if l.startswith("1,")) and any(l.startswith('2,"  Design') for l in lines))
    check("a name with a comma and quotes is quoted and its quotes doubled", '"  Design, ""final"""' in text, text[:600])
    check("a milestone carries its ◆", "◆ Launch" in text)
    build = [l for l in lines if l.startswith("3,")][0]
    check("a predecessor reads the way the list shows it, and a resource list with a comma is quoted", ',2FS,' in build and '"Anna[50%], Ben"' in text, build)
    check("a text that Excel would take for a formula gets an apostrophe", "'=SUM(A1)" in text and ",=SUM" not in text)
    n2, raw2 = export(cols="all", sep=";")
    t2 = raw2.decode("utf-8").lstrip("﻿"); l2 = t2.split("\r\n")
    check("all columns: WBS, Actual Start and the rest are there, separated by semicolons", l2[0].startswith("ID;Task Mode;WBS;Task Name;Start;Finish;Deadline;Actual Start;") and "Notes" in l2[0], l2[0])
    check("...a name with a semicolon would be quoted; this one has none, but the comma is plain text now", 'Design, "final"' in t2 or '"  Design, ""final"""' in t2)
    check("...the note keeps one line: 'line one line two'", "line one line two" in t2)
    n3, raw3 = export(sep="\t")
    check("tab separated", raw3.decode("utf-8").lstrip("﻿").split("\r\n")[0].startswith("ID\tTask Name\tStart"))
    # filter scope
    ev("() => { colFilters.name = { type: 'values', values: new Set(['Build']), blanks: false }; render(); }"); pg.wait_for_timeout(200)
    pg.click("#dataMenuBtn"); pg.click("#csvExportItem"); pg.wait_for_selector("#csvModalBg.open")
    check("with a filter on, the dialog offers 'Only the N tasks matching the current filter'", pg.locator("#csvScopeBlock").is_visible() and "matching" in pg.inner_text("#csvScopeFiltered"))
    pg.check("input[name='csvScope'][value='filtered']")
    with pg.expect_download() as d: pg.click("#csvExportBtn")
    pth = os.path.join(tempfile.mkdtemp(), "f.csv"); d.value.save_as(pth); t4 = open(pth, encoding="utf-8-sig").read()
    check("the filtered export has only the matching tasks (and the group above them)", "Build" in t4 and "Launch" not in t4 and "=SUM" not in t4, t4[:400])
    ev("() => { for (const k of Object.keys(colFilters)) colFilters[k] = null; render(); }")
    # nothing to export
    # round trip
    ev("() => { historyCoalesceMs = 0; }")
    pg.click("#dataMenuBtn"); pg.click("#csvExportItem"); pg.wait_for_selector("#csvModalBg.open"); pg.select_option("#csvSep", ","); pg.check("input[name='csvCols'][value='shown']")
    with pg.expect_download() as d: pg.click("#csvExportBtn")
    pth = os.path.join(tempfile.mkdtemp(), "rt.csv"); d.value.save_as(pth); rt = open(pth, encoding="utf-8-sig").read()
    res = ev("""(txt) => { const rows = parseDelimited(txt); const r = tasksFromTable(rows, { dateFormat: 'dmy' }); return { n: r.tasks.length, names: r.tasks.map(t => t.name), parents: r.tasks.map(t => t.parentIdx != null ? t.parentIdx : (t.parent != null ? t.parent : null)), start: r.tasks.map(t => t.startDate), res: r.tasks.map(t => t.resource) }; }""", rt)
    check("Milestone's own CSV import reads the export back: the same names, in order", res["names"][:4] == ["Phase 1", 'Design, "final"', "Build", "Launch"], res)
    check("...with the same dates and the resource", res["start"][1] == "2030-03-04" and "Anna" in (res["res"][1] or ""), res)
    ev("() => document.getElementById('csvModalBg').classList.remove('open')")
    ev("() => { tasks.length = 0; save(); render(); }")
    pg.click("#dataMenuBtn"); pg.click("#csvExportItem"); pg.wait_for_timeout(200)
    check("an empty plan is refused with a message", not ev("() => document.getElementById('csvModalBg').classList.contains('open')") and "Nothing to export" in ev("() => document.getElementById('toastMsg').textContent"))
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
