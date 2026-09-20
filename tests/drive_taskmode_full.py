import json
from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
import tempfile
SHOT = tempfile.gettempdir()
errors = []
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if detail and not cond else ""))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 900})
    page.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
    page.goto(URL)
    page.wait_for_selector("#addTaskBtn")
    page.evaluate("() => { localStorage.clear(); }")
    page.reload(); page.wait_for_selector("#addTaskBtn"); page.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; }"); page.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status']) colHidden.add(c); }"); page.evaluate("() => { colHidden.add('wbs'); save(); render(); }")   # these checks index cells by position, so keep the pre-WBS column layout
    page.wait_for_selector("#addTaskBtn")

    def mk(name, start, end, mode="auto", parent=None, preds=None, milestone=False):
        return page.evaluate("""([name, start, end, mode, parent, preds, milestone]) => {
            const t = {id: genId(), name, parentId: parent, order: tasks.length, startDate: start, endDate: end,
                progress: 0, milestone, color: null, notes: '', predecessors: preds || [], collapsed: false,
                updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: mode};
            tasks.push(t); save(); render(); return t.id; }""", [name, start, end, mode, parent, preds, milestone])
    def T(id):
        return page.evaluate("(id) => tasks.find(t => t.id === id)", id)
    def row(id):
        return page.locator(f".grid-row[data-id='{id}']")

    # ---- Gap 1: default is Auto Scheduled (new tasks + project setting) — was Manual until the user asked for Auto
    page.click("#addTaskBtn"); page.wait_for_selector("#taskModalBg.open")
    check("1  new task defaults to auto", page.evaluate("() => tasks[0].taskMode") == "auto")
    check("1  modal Task Mode field shows auto", page.eval_on_selector("#taskModeInput", "e => e.value") == "auto")
    page.fill("#taskNameInput", "First"); page.click("#taskModalBg button:has-text('Save')")
    page.wait_for_selector("#taskModalBg:not(.open)")
    check("1  'New tasks' button reads Auto Scheduled", "Auto Scheduled" in page.inner_text("#newTaskModeBtn"))

    # ---- Gap 2: icons (pushpin = manual, chart = auto); constraint icon no longer a thumbtack
    first = page.evaluate("() => tasks[0].id")
    mm = mk("M", "2026-09-21", "2026-09-25", "manual")
    check("2  manual row uses pushpin icon", row(mm).locator(".task-mode-cell i.fa-thumbtack.mode-manual").count() == 1)
    a = mk("A", "2026-09-21", "2026-09-25", "auto")
    check("2  auto row uses chart icon", row(a).locator(".task-mode-cell i.fa-chart-gantt.mode-auto").count() == 1)

    # ---- Gap 3: picker with the two named options (not a blind toggle)
    row(a).locator(".task-mode-cell").click()
    page.wait_for_selector("#taskModeMenu.open")
    items = page.eval_on_selector_all("#taskModeMenu .dropdown-item", "els => els.map(e => e.innerText.trim())")
    check("3  picker lists both named modes", items == ["Manually Scheduled", "Auto Scheduled"], items)
    check("3  current mode is checked", page.locator("#taskModeMenu .dropdown-item.active .mode-check").count() == 1 and "Auto" in page.inner_text("#taskModeMenu .dropdown-item.active"))
    page.screenshot(path=f"{SHOT}/70_mode_picker.png")
    page.click("#taskModeMenu .dropdown-item:has-text('Manually Scheduled')")
    check("3  picking Manual applies + closes menu", T(a)["taskMode"] == "manual" and not page.eval_on_selector("#taskModeMenu", "e => e.classList.contains('open')"))
    page.locator("#newTaskModeBtn").click()
    page.wait_for_selector("#taskModeMenu.open")
    page.click("#taskModeMenu .dropdown-item:has-text('Auto Scheduled')")
    check("3  'New tasks' picker sets project default", page.evaluate("() => project.newTaskMode") == "auto" and "Auto Scheduled" in page.inner_text("#newTaskModeBtn"))
    page.click("#addTaskBtn"); page.wait_for_selector("#taskModalBg.open")
    check("3  next new task follows the new default (auto)", page.eval_on_selector("#taskModeInput", "e => e.value") == "auto")
    page.click("#taskModalBg button:has-text('Cancel')")
    page.locator("#newTaskModeBtn").click(); page.click("#taskModeMenu .dropdown-item:has-text('Manually Scheduled')")

    # ---- Gap 4: field in the task dialog
    page.evaluate("() => { tasks.length = 0; selectedTaskId = null; save(); render(); }")
    a = mk("A", "2026-09-21", "2026-09-25", "auto")
    b = mk("B", "2026-09-22", "2026-09-24", "manual", preds=[{"id": a, "type": "FS", "lag": 0}])
    row(b).locator(".icon-btn").first.click(); page.wait_for_selector("#taskModalBg.open")
    check("4  dialog preselects task's mode", page.eval_on_selector("#taskModeInput", "e => e.value") == "manual")
    page.select_option("#taskModeInput", "auto")
    page.click("#taskModalBg button:has-text('Save')"); page.wait_for_selector("#taskModalBg:not(.open)")
    check("4  dialog can switch mode", T(b)["taskMode"] == "auto")

    # ---- Gap 8: switching to Auto goes to the earliest valid date, earlier OR later
    #   B was manual at 22-24 Sep (before A finishes 25th) -> auto must push LATER to 26th
    check("8  manual->auto moves LATER when links require", (T(b)["startDate"], T(b)["endDate"]) == ("2026-09-26", "2026-09-28"), T(b))
    c = mk("C", "2026-10-15", "2026-10-17", "manual", preds=[{"id": a, "type": "FS", "lag": 0}])
    setmode = lambda i, m: page.evaluate("([i, m]) => setTaskMode(i, m)", [i, m])
    setmode(c, "auto")
    check("8  manual->auto moves EARLIER when links allow", (T(c)["startDate"], T(c)["endDate"]) == ("2026-09-26", "2026-09-28"), T(c))
    d = mk("D", "2026-11-02", "2026-11-04", "manual")
    setmode(d, "auto")
    check("8  manual->auto with no links keeps dates", (T(d)["startDate"], T(d)["endDate"]) == ("2026-11-02", "2026-11-04"))

    # ---- Gap 6: schedule-mismatch warning (manual task starting before its links allow)
    e = mk("E", "2026-09-22", "2026-09-23", "manual", preds=[{"id": a, "type": "FS", "lag": 0}])
    check("6  warning icon on inconsistent manual task", row(e).locator(".mismatch-warn").count() == 1)
    check("6  warning tooltip names the auto date", "26.09.2026" in (row(e).locator(".mismatch-warn").get_attribute("title") or ""))
    f = mk("F", "2026-09-30", "2026-10-01", "manual", preds=[{"id": a, "type": "FS", "lag": 0}])
    check("6  no warning when manual task starts after links", row(f).locator(".mismatch-warn").count() == 0)
    check("6  no warning on consistent auto task", row(b).locator(".mismatch-warn").count() == 0)
    check("6  manual task was NOT moved by its predecessor", T(e)["startDate"] == "2026-09-22")

    # ---- Gap 5: Gantt look
    page.click("text=Gantt"); page.wait_for_timeout(200)
    check("5  manual bar is styled differently", page.locator(f".gantt-bar.manual[data-id='{e}']").count() == 1)
    check("5  auto bar has no manual style", page.locator(f".gantt-bar[data-id='{b}']:not(.manual)").count() == 1)
    check("5  mismatch bar flagged", page.locator(f".gantt-bar.mismatch[data-id='{e}']").count() == 1)
    bs = page.evaluate("(id) => getComputedStyle(document.querySelector(`.gantt-bar[data-id='${id}']`)).borderStyle", e)
    check("5  manual bar border is dashed", bs == "dashed", bs)
    m1 = mk("M", "2026-10-05", "2026-10-05", "manual", milestone=True)
    page.wait_for_timeout(100)
    check("5  manual milestone is hollow/dashed", page.locator(".gantt-milestone.manual").count() == 1)
    page.screenshot(path=f"{SHOT}/71_gantt_manual_styles.png")
    page.click("text=Tasks"); page.wait_for_timeout(150)

    # ---- Gap 10: free-text / blank dates
    g = mk("G", "2026-10-06", "2026-10-09", "manual")
    h = mk("H", "2026-10-12", "2026-10-13", "auto", preds=[{"id": g, "type": "FS", "lag": 0}])
    cell = lambda i, n: row(i).locator(".grid-cell-dim").nth(n)   # 0 id,1 mode,2 start,3 finish,4 dur,5 %,6 preds
    cell(g, 2).click(); page.wait_for_selector(".inline-wrap")
    check("10 manual date editor is a text box + calendar button", page.locator(".inline-wrap input[type=text]").count() == 1 and page.locator(".inline-wrap .inline-cal").count() == 1)
    page.fill(".inline-wrap input[type=text]", "TBD"); page.keyboard.press("Enter"); page.wait_for_timeout(120)
    check("10 free-text Start is stored", T(g)["startText"] == "TBD")
    check("10 grid shows the text", cell(g, 2).inner_text().strip() == "TBD")
    page.click("text=Gantt"); page.wait_for_timeout(150)
    check("10 only-Start-unknown task shows a bracket at Finish (no bar)", page.locator(f".gantt-bar[data-id='{g}']").count() == 0 and page.locator(".gantt-bracket.br-end").count() == 1)
    page.click("text=Tasks"); page.wait_for_timeout(150)
    cell(g, 3).click(); page.wait_for_selector(".inline-wrap")
    page.fill(".inline-wrap input[type=text]", ""); page.keyboard.press("Enter"); page.wait_for_timeout(120)
    check("10 blank Finish is stored as blank", T(g)["endText"] == "")
    page.click("text=Gantt"); page.wait_for_timeout(150)
    check("10 both dates unknown -> no bar and no bracket", page.locator(f".gantt-bar[data-id='{g}']").count() == 0 and page.locator(".gantt-bracket").count() == 0)
    page.click("text=Tasks"); page.wait_for_timeout(150)
    before = T(h)["startDate"]
    page.evaluate("(id) => { cascadeSchedule(id); save(); render(); }", g)
    check("10 unscheduled predecessor is ignored by successors", T(h)["startDate"] == before)
    cell(g, 4).click(); page.wait_for_selector(".inline-edit")
    page.fill(".inline-edit", "a few days"); page.keyboard.press("Enter"); page.wait_for_timeout(120)
    check("10 free-text Duration", T(g)["durText"] == "a few days" and "a few days" in cell(g, 4).inner_text())
    # type real dates back in
    cell(g, 2).click(); page.wait_for_selector(".inline-wrap")
    page.fill(".inline-wrap input[type=text]", "07.10.2026"); page.keyboard.press("Enter"); page.wait_for_timeout(120)
    cell(g, 3).click(); page.wait_for_selector(".inline-wrap")
    page.fill(".inline-wrap input[type=text]", "10.10.2026"); page.keyboard.press("Enter"); page.wait_for_timeout(120)
    check("10 typing DD.MM.YYYY restores real dates", (T(g)["startDate"], T(g)["endDate"], T(g)["startText"], T(g)["endText"]) == ("2026-10-07", "2026-10-10", None, None), T(g))
    check("10 real dates clear stale duration text", T(g)["durText"] is None)
    # calendar button path: picking a date in the hidden native input commits it
    cell(g, 2).click(); page.wait_for_selector(".inline-wrap")
    page.evaluate("""() => { const d = document.querySelector('.inline-date-hidden'); d.value = '2026-10-08'; d.dispatchEvent(new Event('change', {bubbles: true})); }""")
    page.wait_for_timeout(150)
    check("10 calendar-picker selection commits the date", T(g)["startDate"] == "2026-10-08", T(g)["startDate"])
    page.click("text=Gantt"); page.wait_for_timeout(150)
    check("10 bar returns once both dates are real", page.locator(f".gantt-bar[data-id='{g}']").count() == 1)
    page.click("text=Tasks"); page.wait_for_timeout(150)
    # switching to Auto drops free text
    page.evaluate("(id) => { const t = byId(id); t.startText = 'soon'; save(); render(); }", g)
    setmode(g, "auto")
    check("10 switching to Auto clears free text", (T(g)["startText"], T(g)["endText"], T(g)["durText"]) == (None, None, None))
    # dialog keeps free text unless the date field is changed
    k = mk("K", "2026-10-20", "2026-10-22", "manual")
    page.evaluate("(id) => { const t = byId(id); t.endText = 'TBD'; save(); render(); }", k)
    row(k).locator(".icon-btn").first.click(); page.wait_for_selector("#taskModalBg.open")
    check("10 dialog explains free-text dates", not page.eval_on_selector("#taskTextDatesNote", "e => e.classList.contains('hidden')"))
    page.click("#taskModalBg button:has-text('Save')"); page.wait_for_selector("#taskModalBg:not(.open)")
    check("10 saving dialog untouched keeps the free text", T(k)["endText"] == "TBD")

    # ---- Gap 7: summary tasks can be manually scheduled
    par = mk("Parent", "2026-11-01", "2026-11-03", "manual")
    ch1 = mk("Kid1", "2026-11-10", "2026-11-12", "auto", parent=par)
    ch2 = mk("Kid2", "2026-11-13", "2026-11-20", "auto", parent=par)
    eff = page.evaluate("(id) => { resetEffectiveCache(); return effectiveDates(id); }", par)
    check("7  manual summary keeps its OWN dates", (eff["start"], eff["end"]) == ("2026-11-01", "2026-11-03"), eff)
    check("7  and still reports the children's rollup", (eff["rollStart"], eff["rollEnd"]) == ("2026-11-10", "2026-11-20"), eff)
    check("7  manual summary can be edited inline", cell(par, 2).get_attribute("onclick") is not None)
    check("7  summary has a working mode picker", row(par).locator(".task-mode-cell").get_attribute("onclick") is not None)
    page.click("text=Gantt"); page.wait_for_timeout(150)
    check("7  Gantt draws rollup bar under manual summary", page.locator(".gantt-rollup").count() == 1)
    page.screenshot(path=f"{SHOT}/72_manual_summary.png")
    page.click("text=Tasks"); page.wait_for_timeout(150)
    setmode(par, "auto")
    eff2 = page.evaluate("(id) => { resetEffectiveCache(); return effectiveDates(id); }", par)
    check("7  auto summary rolls up again", (eff2["start"], eff2["end"]) == ("2026-11-10", "2026-11-20"), eff2)

    # ---- Gap 9: critical path excludes manual tasks
    page.evaluate("() => { tasks.length = 0; save(); render(); }")
    x = mk("X", "2026-09-21", "2026-09-25", "auto")
    y = mk("Y", "2026-09-26", "2026-09-30", "auto", preds=[{"id": x, "type": "FS", "lag": 0}])
    z = mk("Z", "2026-09-26", "2026-10-30", "manual", preds=[{"id": x, "type": "FS", "lag": 0}])
    crit = page.evaluate("() => [...computeCriticalPath()]")
    check("9  manual task never on critical path", z not in crit and x in crit and y in crit, crit)

    # ---- legacy data and integrity
    page.evaluate("""() => { localStorage.setItem('milestone-v1', JSON.stringify({version:1, project:{name:'Old',updatedAt:1}, tasks:[
        {id:'legacy1', name:'Old task', parentId:null, order:0, startDate:'2026-09-01', endDate:'2026-09-03', progress:0, milestone:false, color:null, notes:'', predecessors:[], collapsed:false, updatedAt:1}], deletedTaskIds:[]})); }""")
    page.reload(); page.wait_for_selector("#addTaskBtn")
    check("legacy tasks without a mode stay Auto Scheduled", page.evaluate("() => tasks[0].taskMode") == "auto")
    check("legacy project gets the Manual new-task default", page.evaluate("() => project.newTaskMode") == "manual")

    # ---- regression: modal predecessor linking + indent/outdent still work
    page.evaluate("() => { tasks.length = 0; save(); render(); }")
    p1 = mk("P1", "2026-09-21", "2026-09-23", "auto"); p2 = mk("P2", "2026-09-21", "2026-09-23", "auto")
    row(p2).locator(".icon-btn").first.click(); page.wait_for_selector("#taskModalBg.open")
    page.click("text=Add predecessor"); page.fill(".pred-row input.pred-id-input", "1"); page.press(".pred-row input.pred-id-input", "Tab")
    page.click("#taskModalBg button:has-text('Save')"); page.wait_for_selector("#taskModalBg:not(.open)")
    check("regression: modal predecessor link + auto cascade", T(p2)["predecessors"] and T(p2)["startDate"] == "2026-09-24", T(p2))
    page.evaluate("(id) => { selectedTaskId = id; render(); }", p2)
    page.click("#indentBtn"); check("regression: indent", T(p2)["parentId"] == p1)
    page.click("#outdentBtn"); check("regression: outdent", T(p2)["parentId"] is None)

    page.screenshot(path=f"{SHOT}/73_final_tasks_view.png")
    print("\nConsole errors/warnings:", errors)
    fails = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(fails)}/{len(results)} checks passed" + (f"; FAILED: {fails}" if fails else ""))
    browser.close()
