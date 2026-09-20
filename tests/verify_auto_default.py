import json
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:250]}]" if not cond and detail else ""))
TASK = lambda name, mode: {"id": "t" + name.lower(), "name": name, "parentId": None, "order": 0, "startDate": "2026-09-21", "endDate": "2026-09-25", "progress": 0, "milestone": False, "color": None, "predecessors": [], "collapsed": False, "updatedAt": 1, "constraintType": "ASAP", "constraintDate": None, "taskMode": mode}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); ctx = b.new_context(viewport={"width": 1400, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    boot = lambda: (pg.goto(URL), pg.wait_for_selector("#addTaskBtn"), pg.wait_for_timeout(150))
    reload = lambda: (pg.reload(), pg.wait_for_selector("#addTaskBtn"), pg.wait_for_timeout(150))
    mode = lambda: pg.evaluate("() => project.newTaskMode")
    boot(); pg.evaluate("() => localStorage.clear()"); reload()

    # ---- a fresh install
    check("fresh install: the 'New tasks' button reads Auto Scheduled", "Auto Scheduled" in pg.inner_text("#newTaskModeBtn"), pg.inner_text("#newTaskModeBtn"))
    pg.click("#addTaskBtn"); pg.wait_for_selector("#taskModalBg.open")
    check("...a new task is Auto Scheduled, and the dialog shows it", pg.evaluate("() => tasks[0].taskMode") == "auto" and pg.eval_on_selector("#taskModeInput", "e => e.value") == "auto")
    pg.fill("#taskNameInput", "First"); pg.click("#taskModalBg .btn-primary"); pg.wait_for_timeout(120)
    check("...and its row uses the Auto icon (chart), not the pushpin", pg.locator(".task-mode-cell i.mode-auto").count() == 1 and pg.locator(".task-mode-cell i.mode-manual").count() == 0)
    # ---- choosing Manual is remembered
    pg.locator("#newTaskModeBtn").click(); pg.wait_for_selector("#taskModeMenu.open"); pg.click("#taskModeMenu .dropdown-item:has-text('Manually Scheduled')"); pg.wait_for_timeout(100)
    check("choosing Manually Scheduled for new tasks works", mode() == "manual" and "Manually Scheduled" in pg.inner_text("#newTaskModeBtn"))
    pg.click("#addTaskBtn"); pg.wait_for_selector("#taskModalBg.open"); pg.evaluate("() => closeTaskModal()")
    check("...new tasks are then Manual", pg.evaluate("() => tasks[tasks.length - 1].taskMode") == "manual")
    reload()
    check("...and that choice survives a reload (the one-time switch never overrides it)", mode() == "manual", mode())
    check("the project carries the revision marker", pg.evaluate("() => project.modeRev") == 1)
    pg.locator("#newTaskModeBtn").click(); pg.wait_for_selector("#taskModeMenu.open"); pg.click("#taskModeMenu .dropdown-item:has-text('Auto Scheduled')"); pg.wait_for_timeout(100)
    reload(); check("switching back to Auto is remembered too", mode() == "auto")

    # ---- a project saved while Manual was the default (no marker, 'manual' stored)
    pid = pg.evaluate("() => currentPlanId")
    pg.evaluate("""([pid, t1, t2]) => { localStorage.setItem('milestone-plan-' + pid, JSON.stringify({version: 1, project: {name: 'Old plan', updatedAt: 5, newTaskMode: 'manual'}, tasks: [t1, t2], deletedTaskIds: []})); }""", [pid, TASK("Kept", "manual"), TASK("Auto1", "auto")])
    reload()
    check("a project saved under the old default ('manual', no marker) is switched to Auto once", mode() == "auto" and pg.evaluate("() => project.modeRev") == 1, (mode(), pg.evaluate("() => project.modeRev")))
    check("...its existing tasks keep their own modes (only the default for NEW tasks changed)", pg.evaluate("() => tasks.map(t => t.name + ':' + t.taskMode).join()") == "Kept:manual,Auto1:auto")
    check("...and it keeps its name and stamp (nothing else about the project was touched)", pg.evaluate("() => [project.name, project.updatedAt]") == ["Old plan", 5])
    # a project saved AFTER the change with an explicit manual choice stays manual
    pg.evaluate("""(pid) => { localStorage.setItem('milestone-plan-' + pid, JSON.stringify({version: 1, project: {name: 'Chosen', updatedAt: 9, newTaskMode: 'manual', modeRev: 1}, tasks: [], deletedTaskIds: []})); }""", pid)
    reload(); check("a project that chose Manual after the change (marker present) stays Manual", mode() == "manual" and pg.evaluate("() => project.name") == "Chosen", mode())
    # legacy single-project storage
    pg.evaluate("""() => { localStorage.clear(); localStorage.setItem('milestone-v1', JSON.stringify({project: {name: 'Legacy', updatedAt: 3, newTaskMode: 'manual'}, tasks: [], deletedTaskIds: []})); }""")
    reload(); check("the very old single-project storage migrates to Auto too", mode() == "auto" and pg.evaluate("() => project.name") == "Legacy", mode())
    # a project from a file/import with no mode at all
    pg.evaluate("() => { project = {name: 'Bare', updatedAt: 0}; normalizeData(); }")
    check("a project object with no mode at all gets Auto", mode() == "auto")
    # plans
    pg.evaluate("() => { switchPlan(createPlanRecord('Second', null)); }"); pg.wait_for_timeout(500)
    check("a newly created plan starts on Auto", mode() == "auto" and pg.evaluate("() => project.name") == "Second", mode())
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
