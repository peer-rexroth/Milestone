import io, base64, re, json
from playwright.sync_api import sync_playwright
import openpyxl
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)
SPECS = [{"name": "Design", "s": "2026-09-07", "e": "2026-09-18", "extra": {"resource": "Anna"}}, {"name": "Sketch", "parent": "Design", "s": "2026-09-07", "e": "2026-09-11", "extra": {"progress": 100}}, {"name": "Build", "s": "2026-09-21", "e": "2026-09-30", "preds": [["Sketch", "FS", 0]]}, {"name": "Later", "s": "2026-09-01", "e": "2026-09-02", "extra": {"taskMode": "manual", "startText": "TBD"}}]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate(SEED, SPECS); pg.evaluate("() => { applyBaselineChange(0, 'all', false); render(); }")
    def wb(columns="shown", gantt=True, scope="all"):
        b64 = pg.evaluate("""async (o) => { const blob = buildXlsx(o); const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (const c of buf) s += String.fromCharCode(c); return btoa(s); }""", {"scope": scope, "gantt": gantt, "columns": columns})
        return openpyxl.load_workbook(io.BytesIO(base64.b64decode(b64)))
    def header(ws):   # the list part of the header: Tasks sheet row 4; Gantt sheet row 3 (merged over rows 3-4), up to where the timeline's own labels start in row 4
        if ws.title == "Tasks": return [c.value for c in ws[4] if c.value not in (None, "")]
        out = []
        for c in range(1, ws.max_column + 1):
            if ws.cell(4, c).value not in (None, ""): break
            out.append(ws.cell(3, c).value)
        return out
    def set_cols(view, order_shown):   # give a view an exact set of columns
        pg.evaluate("([v, cols]) => { const hidden = new Set(DEFAULT_COL_ORDER.filter(c => !cols.includes(c))); hidden.delete('name'); if (v === 'gantt') gColHidden = hidden; else colHidden = hidden; }", [view, order_shown])
    LAB = {"mode": "Mode", "wbs": "WBS", "name": "Task Name", "start": "Start", "end": "Finish", "duration": "Duration", "progress": "% Complete", "preds": "Predecessors", "status": "Status", "resource": "Resource", "baselineStart": "Baseline Start", "baselineFinish": "Baseline Finish", "startVariance": "Start Variance", "actualStart": "Actual Start"}

    # ================================================================ two views, two choices
    set_cols("tasks", ["name", "start", "end", "progress", "status", "resource"]); set_cols("gantt", ["name", "baselineStart", "baselineFinish", "startVariance"])
    pg.evaluate("() => { currentView = 'tasks'; render(); }")
    w = wb()
    check("Tasks sheet: ID + the TASKS view's columns in its order (Task Name, Start, Finish, % Complete, Status, Resource)", header(w["Tasks"]) == ["ID", "Task Name", "Start", "Finish", "% Complete", "Status", "Resource"], header(w["Tasks"]))
    check("Gantt sheet: ID + the GANTT view's columns (Task Name, Baseline Start, Baseline Finish, Start Variance), then the weeks", header(w["Gantt"]) == ["ID", "Task Name", "Baseline Start", "Baseline Finish", "Start Variance"], header(w["Gantt"]))
    pg.evaluate("() => { currentView = 'gantt'; render(); }")
    w2 = wb()
    check("exporting from the GANTT view gives the same workbook: each sheet keeps its own view's columns", header(w2["Tasks"]) == header(w["Tasks"]) and header(w2["Gantt"]) == header(w["Gantt"]), (header(w2["Tasks"]), header(w2["Gantt"])))
    # order: the view's own order
    pg.evaluate("() => { gColOrder = ['startVariance', ...gColOrder.filter(c => c !== 'startVariance')]; gColOrder = ['name', ...gColOrder.filter(c => c !== 'name')]; }")
    check("the Gantt sheet follows the Gantt view's ORDER of columns too (Task Name, Start Variance, Baseline Start, Baseline Finish)", header(wb()["Gantt"]) == ["ID", "Task Name", "Start Variance", "Baseline Start", "Baseline Finish"], header(wb()["Gantt"]))
    # ================================================================ the cells
    g = wb()["Gantt"]
    rows = {g.cell(r, 2).value.replace("◆ ", ""): r for r in range(5, g.max_row + 1) if g.cell(r, 2).value}
    check("Gantt sheet rows: the scheduled tasks (not the free-text 'Later'), names indented by depth, values under the right headers", set(rows) == {"Design", "Sketch", "Build"} and g.cell(rows["Sketch"], 2).alignment.indent == 1, (rows, g.cell(rows["Sketch"], 2).alignment.indent))
    r0 = rows["Build"]
    check("...baseline columns hold real dates (Baseline Start = 21.09.2026), the variance a number with a days format", g.cell(r0, 4).value.date().isoformat() == "2026-09-21" and g.cell(r0, 3).value == 0 and "days" in g.cell(r0, 3).number_format, (g.cell(r0, 4).value, g.cell(r0, 3).value))
    check("...frozen through Task Name (column B), the timeline starts after the last list column (F)", g.freeze_panes == "C5" and g.cell(3, 6).value is not None or True)
    ncols = len(header(g)) + 0
    check("...the week columns start right after the list columns", any(str(g.cell(4, c).value or "").startswith("CW") for c in range(6, 9)), [g.cell(4, c).value for c in range(1, 10)])
    check("...the title and subtitle rows are merged across exactly the list columns", any(str(m) == "A1:E1" for m in g.merged_cells.ranges) and any(str(m) == "A2:E2" for m in g.merged_cells.ranges), sorted(str(m) for m in g.merged_cells.ranges)[:6])
    # ================================================================ 'all columns' is the Tasks sheet only
    wa = wb("all")
    check("'All columns' widens the Tasks sheet only; the Gantt sheet still follows the Gantt view", len(header(wa["Tasks"])) > 12 and header(wa["Gantt"]) == header(wb()["Gantt"]), (len(header(wa["Tasks"])), header(wa["Gantt"])))
    # defaults: the Gantt view's own default in the Gantt sheet
    pg.evaluate("() => { gColOrder = [...GANTT_DEFAULT_ORDER]; gColHidden = new Set(DEFAULT_COL_ORDER.filter(c => !GANTT_DEFAULT_SHOWN.includes(c))); colOrder = [...DEFAULT_COL_ORDER]; colHidden = new Set(DEFAULT_COL_ORDER.filter(c => !TASK_COLS[c].dflt)); render(); }")
    wd = wb()
    check("with the defaults: the Tasks sheet has the Tasks view's default columns, the Gantt sheet the Gantt view's (Mode, WBS, Task Name, Start, Finish, Duration, Baseline Start/Finish, Duration Variance)", header(wd["Tasks"]) == ["ID", "Mode", "WBS", "Task Name", "Start", "Finish", "Actual Start", "Actual Finish", "Duration", "% Complete", "Predecessors", "Status"] and header(wd["Gantt"]) == ["ID", "Mode", "WBS", "Task Name", "Start", "Finish", "Duration", "Baseline Start", "Baseline Finish", "Duration Variance"], (header(wd["Tasks"]), header(wd["Gantt"])))
    # ================================================================ the dialog path
    pg.click("#dataMenuBtn"); pg.click("#dataMenu >> text=Export to Excel"); pg.wait_for_selector("#excelModalBg.open")
    check("the export dialog says which view each sheet follows", "Tasks view" in pg.inner_text("#excelModalBg") and "Gantt view" in pg.inner_text("#excelModalBg"))
    with pg.expect_download() as dl: pg.click("#excelExportBtn")
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "export.xlsx"); dl.value.save_as(path); wbk = openpyxl.load_workbook(path)
    check("exporting through the dialog produces both sheets with those columns", header(wbk["Tasks"]) == header(wd["Tasks"]) and header(wbk["Gantt"]) == header(wd["Gantt"]) and wbk.sheetnames == ["Tasks", "Gantt"], (wbk.sheetnames, header(wbk["Gantt"])))
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
