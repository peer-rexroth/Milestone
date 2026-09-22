from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 900})
    page.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
    page.goto(URL); page.wait_for_selector("#addTaskBtn")
    page.evaluate("() => { localStorage.clear(); }"); page.reload(); page.wait_for_selector("#addTaskBtn"); page.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; }"); page.evaluate("() => { for (const c of ['actualStart', 'actualFinish', 'status']) colHidden.add(c); }"); page.evaluate("() => { colHidden.add('wbs'); save(); render(); }")

    def mk(name, start, end, mode, preds=None):
        return page.evaluate("""([name, start, end, mode, preds]) => {
            const t = {id: genId(), name, parentId: null, order: tasks.length, startDate: start, endDate: end,
                progress: 0, milestone: false, color: null, notes: '', predecessors: preds || [], collapsed: false,
                updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: mode};
            tasks.push(t); save(); render(); return t.id; }""", [name, start, end, mode, preds])
    T = lambda i: page.evaluate("(id) => tasks.find(t => t.id === id)", i)

    # Real control: with G SCHEDULED late, applying constraints must push H to 2027; with G
    # UNSCHEDULED (free-text start) the same call must leave H alone.
    g = mk("G", "2027-01-05", "2027-01-09", "manual")
    h = mk("H", "2026-10-12", "2026-10-13", "auto", [{"id": g, "type": "FS", "lag": 0}])
    page.evaluate("(id) => { applyConstraints(id); save(); render(); }", h)
    print("CONTROL scheduled manual pred pushes auto successor:", "PASS" if T(h)["startDate"] == "2027-01-10" else "FAIL " + T(h)["startDate"])
    page.evaluate("(id) => { const t = byId(id); t.startDate = '2026-10-12'; t.endDate = '2026-10-13'; save(); render(); }", h)
    page.evaluate("(id) => { const t = byId(id); t.startText = 'TBD'; save(); render(); }", g)
    page.evaluate("(id) => { applyConstraints(id); cascadeSchedule(id); save(); render(); }", h)
    print("TEST unscheduled (free-text) predecessor is ignored:", "PASS" if T(h)["startDate"] == "2026-10-12" else "FAIL " + T(h)["startDate"])

    # Real calendar button: click it, editor must stay open (not commit/destroy) and picker input focused
    page.click("text=Tasks") if page.locator("text=Tasks").count() else None
    k = mk("K", "2026-10-20", "2026-10-22", "manual")
    row = page.locator(f".grid-row[data-id='{k}']")
    row.locator(".grid-cell-dim").nth(2).click(); page.wait_for_selector(".inline-wrap")
    page.locator(".inline-wrap .inline-cal").click()
    page.wait_for_timeout(300)
    still = page.locator(".inline-wrap").count() == 1
    focused = page.evaluate("() => document.activeElement && document.activeElement.type")
    print("Calendar button click keeps editor open:", "PASS" if still else "FAIL", "| focused input type:", focused)
    page.screenshot(path=__import__("tempfile").gettempdir() + "/74_calendar_editor.png")
    # dismiss by Escape -> cancels without changing
    page.evaluate("() => { document.querySelector('.inline-wrap input[type=text]').value = '05.05.2030'; }")
    page.keyboard.press("Escape"); page.wait_for_timeout(200)
    after_first = page.locator(".inline-wrap").count()
    if after_first: page.keyboard.press("Escape"); page.wait_for_timeout(200)
    print("editor still open after 1st Escape (native popup swallowed it):", bool(after_first))
    print("Escape (focus in picker input) cancels the edit:", "PASS" if T(k)["startDate"] == "2026-10-20" and page.locator(".inline-wrap").count() == 0 else "FAIL " + T(k)["startDate"])

    # Typing over an existing date then clicking elsewhere commits it
    row.locator(".grid-cell-dim").nth(2).click(); page.wait_for_selector(".inline-wrap")
    page.fill(".inline-wrap input[type=text]", "21.10.2026")
    page.click("body", position={"x": 900, "y": 700}); page.wait_for_timeout(200)
    print("Blur commits typed date:", "PASS" if T(k)["startDate"] == "2026-10-21" else "FAIL " + T(k)["startDate"])
    # Invalid date-like text is kept as free text, not silently dropped
    row.locator(".grid-cell-dim").nth(2).click(); page.wait_for_selector(".inline-wrap")
    page.fill(".inline-wrap input[type=text]", "31.02.2026"); page.keyboard.press("Enter"); page.wait_for_timeout(150)
    print("Impossible date kept as text:", "PASS" if T(k)["startText"] == "31.02.2026" else "FAIL " + str(T(k)["startText"]))
    print("Console errors/warnings:", errors)
    browser.close()
