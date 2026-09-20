import re, json, base64, io
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open('verify_clone.py').read(), re.S).group(1)
SPECS = [{"name": "Design", "s": "2026-09-07", "e": "2026-09-18"}, {"name": "Sketch", "parent": "Design", "s": "2026-09-07", "e": "2026-09-11"}, {"name": "Build", "s": "2026-09-21", "e": "2026-09-30"}]
TASKS_DEFAULT = ["mode", "wbs", "name", "start", "end", "actualStart", "actualFinish", "duration", "progress", "preds", "status"]   # (the user's own choice from the Columns menu)
GANTT_DEFAULT = ["mode", "wbs", "name", "start", "end", "duration", "baselineStart", "baselineFinish", "durationVariance"]   # (the user's choice: also the order below — Duration in front of the actual dates)
GANTT_ORDER_HEAD = ["mode", "wbs", "name", "start", "end", "duration", "actualStart", "actualFinish", "progress", "preds", "remaining", "status", "baselineStart", "baselineFinish", "baselineDuration", "startVariance", "finishVariance", "durationVariance", "resource"]
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    def new_page(prefs=None, w=1500):
        ctx = b.new_context(viewport={"width": w, "height": 700}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
        pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()")
        if prefs is not None: pg.evaluate("p => localStorage.setItem('milestone-prefs', JSON.stringify(p))", prefs)
        pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate(SEED, SPECS); pg.wait_for_timeout(200); return pg
    pg = new_page()
    shown = lambda v: pg.evaluate("v => visibleTaskCols(v)", v)
    hdr = lambda: pg.evaluate("() => [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(b => b.dataset.col)")
    def tab(name): pg.click(f".view-tab:has-text('{name}')"); pg.wait_for_timeout(200)
    def open_menu():
        pg.click("#columnsBtn"); pg.wait_for_selector("#columnsMenu.open"); pg.wait_for_timeout(100)
    def tick(col, on):
        cb = pg.locator(f"#columnsMenu input[data-col='{col}']"); cb.set_checked(on); pg.wait_for_timeout(150)

    # ================================================================ defaults
    check("the Tasks view's default columns: Mode, WBS, Name, Start, Finish, Actual Start, Actual Finish, Duration, %, Predecessors, Status", shown("tasks") == TASKS_DEFAULT, shown("tasks"))
    check("the Gantt view has its own default: Mode, WBS, Name, Start, Finish, Duration, Baseline Start, Baseline Finish, Duration Variance", shown("gantt") == GANTT_DEFAULT, shown("gantt"))
    check("...and its own default ORDER of all columns (Duration in front of the actual dates; the custom fields at the end)", pg.evaluate("() => gColOrder.slice(0, 19)") == GANTT_ORDER_HEAD and pg.evaluate("() => gColOrder.length") == pg.evaluate("() => DEFAULT_COL_ORDER.length") and pg.evaluate("() => colOrder.indexOf('actualStart') < colOrder.indexOf('duration')"))
    tab("Gantt")
    check("switching to the Gantt view shows ITS columns in the list header", hdr() == GANTT_DEFAULT, hdr())
    tab("Tasks")
    check("...and back: the Tasks view's own", hdr() == TASKS_DEFAULT, hdr())
    # ================================================================ the menu belongs to a view
    open_menu(); head = pg.inner_text("#columnsMenu .cols-head"); hint = pg.inner_text("#columnsMenu .cols-hint")
    check("the Columns menu says which view it edits (Tasks view) and that the other view keeps its own choice", "Tasks view" in head and "Gantt view keeps its own choice" in hint, (head, hint))
    tab("Gantt")
    check("switching views closes the menu (it would otherwise show the other view's ticks)", pg.locator("#columnsMenu.open").count() == 0)
    open_menu(); head = pg.inner_text("#columnsMenu .cols-head")
    ticked = pg.evaluate("() => [...document.querySelectorAll('#columnsMenu input[type=checkbox]')].filter(c => c.checked).map(c => c.dataset.col)")
    check("in the Gantt view the menu is titled 'Gantt view' and ticks the Gantt view's columns", "Gantt view" in head and ticked == GANTT_DEFAULT, (head, ticked))
    # ================================================================ independence
    tick("progress", True); tick("resource", True)
    check("ticking % Complete and Resource in the Gantt view adds them to the Gantt list only (in its order)", shown("gantt") == GANTT_DEFAULT[:6] + ["progress"] + GANTT_DEFAULT[6:] + ["resource"] and hdr() == shown("gantt") and shown("tasks") == TASKS_DEFAULT, (shown("gantt"), shown("tasks")))
    pg.keyboard.press("Escape"); tab("Tasks"); open_menu()
    tick("start", False); tick("baselineStart", True)
    check("in the Tasks view: hiding Start and showing Baseline Start changes the Tasks list only (the Gantt list keeps Start, and its own Baseline columns)", "start" not in shown("tasks") and "baselineStart" in shown("tasks") and "baselineFinish" not in shown("tasks") and "start" in shown("gantt") and "baselineFinish" in shown("gantt"), (shown("tasks"), shown("gantt")))
    pg.keyboard.press("Escape")
    # ================================================================ order
    tab("Gantt"); open_menu()
    before_t = pg.evaluate("() => [...colOrder]")
    pg.click("#columnsMenu button[aria-label='Move Start up']"); pg.wait_for_timeout(150)
    order_g = pg.evaluate("() => gColOrder"); pg.keyboard.press("Escape")
    check("moving a column in the Gantt view reorders the Gantt list (Start now before Task Name) and leaves the Tasks view's order alone", order_g.index("start") < order_g.index("name") and pg.evaluate("() => colOrder") == before_t and hdr().index("start") < hdr().index("name"), (hdr(), order_g[:6]))
    # ================================================================ reset
    open_menu(); pg.click("#columnsMenu .btn-link"); pg.wait_for_timeout(200); pg.keyboard.press("Escape")
    check("'Reset to default' in the Gantt view restores the Gantt default (columns and order) and does not touch the Tasks view", shown("gantt") == GANTT_DEFAULT and pg.evaluate("() => gColOrder.slice(0, 19)") == GANTT_ORDER_HEAD and "baselineStart" in shown("tasks") and "start" not in shown("tasks"), (shown("gantt"), shown("tasks")))
    tab("Tasks"); open_menu(); pg.click("#columnsMenu .btn-link"); pg.wait_for_timeout(200); pg.keyboard.press("Escape")
    tab("Gantt"); open_menu(); tick("status", True); pg.keyboard.press("Escape")
    check("...and 'Reset to default' in the Tasks view restores the Tasks defaults, not the Gantt view's (which keeps Status)", shown("tasks") == TASKS_DEFAULT and "status" in shown("gantt"), (shown("tasks"), shown("gantt")))
    # ================================================================ persistence
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(300)
    prefs = pg.evaluate("() => JSON.parse(localStorage.getItem('milestone-prefs'))")
    check("both sets are saved on this device (cols for the Tasks view, gcols for the Gantt view) and come back after a reload", prefs["cols"]["hidden"] is not None and prefs["gcols"]["order"] and "status" not in prefs["gcols"]["hidden"] and shown("gantt") == GANTT_DEFAULT[:6] + ["status"] + GANTT_DEFAULT[6:] and shown("tasks") == TASKS_DEFAULT, (shown("gantt"), shown("tasks")))
    # ================================================================ upgrades and garbage
    pg2 = new_page({"theme": "light", "zoom": "week", "zoomRev": 2, "view": "gantt", "cols": {"order": ["mode", "wbs", "name", "start", "end", "actualStart", "actualFinish", "duration", "progress", "preds", "remaining", "status", "resource"], "hidden": ["actualStart", "actualFinish", "remaining", "status", "resource"], "rev": 1}})
    g2 = pg2.evaluate("() => visibleTaskCols('gantt')"); t2 = pg2.evaluate("() => visibleTaskCols('tasks')")
    check("preferences saved before this version (a Tasks set only): the Tasks view keeps ITS saved choice (not the new default), the Gantt view starts with its default", g2 == GANTT_DEFAULT and t2 == ["mode", "wbs", "name", "start", "end", "duration", "progress", "preds"], (g2, t2))
    pg3 = new_page({"theme": "light", "zoom": "week", "zoomRev": 2, "view": "gantt", "gcols": {"order": ["resource", "bogus", "start", "name", "mode"], "hidden": ["name", "bogus", "mode", "end"]}})
    g3 = pg3.evaluate("() => visibleTaskCols('gantt')"); o3 = pg3.evaluate("() => gColOrder")
    check("garbage in the Gantt set is ignored: unknown columns dropped, Task Name can never be hidden, columns this version knows but the save doesn't are appended and follow the Gantt default (the default ones shown)", "name" in g3 and "bogus" not in o3 and g3 == ["resource", "start", "name", "wbs", "duration", "baselineStart", "baselineFinish", "durationVariance"] and o3[:3] == ["resource", "start", "name"] and set(o3) == set(pg3.evaluate("() => DEFAULT_COL_ORDER")), (g3, o3[:6]))
    # ================================================================ what follows the set
    pg.evaluate("() => { currentView = 'gantt'; gColHidden.add('wbs'); render(); }"); pg.wait_for_timeout(200)
    fg = pg.evaluate("() => ({frz: [...document.querySelector('#gridRows .grid-row').children].filter(c => c.classList.contains('frz')).length, min: frozenMinWidth})")
    pg.evaluate("() => { currentView = 'tasks'; render(); }"); pg.wait_for_timeout(200)
    ft = pg.evaluate("() => ({frz: [...document.querySelector('#gridRows .grid-row').children].filter(c => c.classList.contains('frz')).length, min: frozenMinWidth})")
    check("the frozen columns follow the view's set: with WBS hidden the Gantt list freezes ID+Mode+Name (3, narrower minimum) vs the Tasks list ID+Mode+WBS+Name (4)", fg["frz"] == 3 and ft["frz"] == 4 and fg["min"] < ft["min"], (fg, ft))
    pg.evaluate("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(200)
    b64 = pg.evaluate("""async () => { const blob = buildXlsx({ scope: 'all', gantt: false, columns: 'shown' }); const buf = new Uint8Array(await blob.arrayBuffer()); let s = ''; for (const c of buf) s += String.fromCharCode(c); return btoa(s); }""")
    try:
        import openpyxl
        H = [c.value for c in openpyxl.load_workbook(io.BytesIO(base64.b64decode(b64)))["Tasks"][4]]
        check("Excel: the Tasks sheet follows the TASKS view's columns even when exporting from the Gantt view (the Gantt sheet follows the Gantt view's — see verify_excel_views.py)", H == ["ID", "Mode", "WBS", "Task Name", "Start", "Finish", "Actual Start", "Actual Finish", "Duration", "% Complete", "Predecessors", "Status"], H)
    except ImportError:
        pass
    pg.click(".col-filter-btn[data-col='start']"); pg.wait_for_selector("#filterMenu.open"); pg.keyboard.press("Escape")
    check("the funnels in the Gantt list are exactly its columns", hdr() == shown("gantt"), (hdr(), shown("gantt")))
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
