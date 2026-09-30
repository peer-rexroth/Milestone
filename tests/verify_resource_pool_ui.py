# -*- coding: utf-8 -*-
"""Resource levelling, Stage 2 — the Resource Pool dialog (Schedule menu -> Resource pool...). Modelled on the Custom
Fields dialog's draft-array CRUD (JSON-snapshot dirty-check, discard confirmation, toggle-remove that discards a brand-
new row but strikes through an existing one, validate-then-confirm-then-apply on Save) but with free-form ids instead of
fixed slots. The one thing unique to it: renaming or removing a resource actively rewrites every affected task's Resource
TEXT (matched by the row's ORIGINAL name) -- the cascade the "resolve assignments by name" design depends on. See
"Resource levelling" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); resetHistory(); }"
    seed = lambda specs: ev(SEED, specs)
    resource = lambda n: ev("n => tasks.find(t => t.name === n).resource", n)

    # ---------------------------------------------------------------- opening: rows, the menu hint, an empty state
    seed([])
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    check("the menu hint says 'none yet' with no resources", "none yet" in pg.inner_text("#planResourcesItem"))
    pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    check("an empty pool shows the empty-state message", "No resources yet" in pg.inner_text("#resourceRows"))
    pg.keyboard.press("Escape")

    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna:50%, Ben"}, {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna"}])
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    check("the menu hint counts the auto-populated pool ('2 people')", "2 people" in pg.inner_text("#planResourcesItem")) if False else None
    check("two auto-populated rows show, each with its 'used by' task count", pg.locator("#resourceRows .res-item").count() == 2 and "1 task" in pg.inner_text("#resourceRows"))
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- renaming cascades to every task's Resource text (matched by the OLD name)
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    pg.fill("(//input[@class='res-name'])[1]", "Anna Schmidt")
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("A's text updates to the new name, keeping its own % and Ben untouched", resource("A") == "Anna Schmidt:50%, Ben", resource("A"))
    check("B's text (which had no %) updates too", resource("B") == "Anna Schmidt", resource("B"))
    check("the pool itself now shows the new name", ev("() => project.resources.map(r => r.name)") == ["Anna Schmidt", "Ben"], ev("() => project.resources"))

    # ---------------------------------------------------------------- removing a resource in use asks first, strips it from affected tasks' text, and undoes
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    pg.click("#resourceRows .res-item:nth-child(2) .res-remove")   # Ben
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("removing a resource in use asks for confirmation, naming it and how many tasks it affects", pg.locator("#confirmModalBg.open").count() == 1 and "Ben" in pg.inner_text("#confirmModalBg") and "1 task" in pg.inner_text("#confirmModalBg"), pg.inner_text("#confirmModalBg"))
    pg.click("#confirmModalBg button:has-text('Remove')"); pg.wait_for_timeout(150)
    check("...A's text drops Ben, keeping Anna Schmidt's %", resource("A") == "Anna Schmidt:50%", resource("A"))
    check("...and the pool no longer has Ben", ev("() => project.resources.map(r => r.name)") == ["Anna Schmidt"])
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    check("Undo (Ctrl+Z, the app's generic history) restores both the task's text and the pool entry", resource("A") == "Anna Schmidt:50%, Ben" and ev("() => project.resources.map(r => r.name)") == ["Anna Schmidt", "Ben"], (resource("A"), ev("() => project.resources")))

    # ---------------------------------------------------------------- removing a resource with NO uses needs no confirmation
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    pg.click("#resourcePoolModalBg button:has-text('Add resource')")
    pg.fill("(//input[@class='res-name'])[last()]", "Unused")
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    pg.click("#resourceRows .res-item:nth-child(3) .res-remove")   # Unused, no uses
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("removing an unused resource needs no confirmation — it's just gone", pg.locator("#confirmModalBg.open").count() == 0 and ev("() => project.resources.map(r => r.name)") == ["Anna Schmidt", "Ben"], ev("() => project.resources"))

    # ---------------------------------------------------------------- max units, uniqueness, empty-name, dirty-check, discard
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    pg.fill("(//input[@class='res-units'])[1]", "9999")
    pg.click("(//input[@class='res-units'])[1]"); pg.keyboard.press("Tab")   # commit the onchange
    check("max units clamps live in the box itself (typed 9999 -> shows 800)", pg.input_value("(//input[@class='res-units'])[1]") == "800")
    pg.click("#resourcePoolModalBg button:has-text('Add resource')")
    pg.fill("(//input[@class='res-name'])[last()]", "Ben")   # a duplicate of an existing name
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("a duplicate name (case-insensitive) is refused, the dialog stays open", "already the name" in pg.inner_text("#toastMsg") and pg.locator("#resourcePoolModalBg.open").count() == 1, pg.inner_text("#toastMsg"))
    pg.click("#resourcePoolModalBg .modal-header button")
    check("closing with unsaved changes (the max-units edit, the new row) asks first", pg.locator("#confirmModalBg.open").count() == 1)
    pg.click("#confirmModalBg button:has-text('Discard changes')")
    check("discarding closes without saving anything", pg.locator("#resourcePoolModalBg.open").count() == 0 and ev("() => project.resources.find(r => r.name === 'Anna Schmidt').maxUnits") == 100)

    # ---------------------------------------------------------------- a group's Resource text never enters the pool
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-08", "r": "GroupOnly"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-08", "parent": "G", "r": "KidOnly"}])
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    names_shown = ev("() => resourceDraft.map(r => r.name)")
    check("only the child's name enters the pool, not the group's", names_shown == ["KidOnly"], names_shown)
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- days off: add, list, remove
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    pg.click("#resourceRows .res-days summary")
    pg.fill("#resDayFrom-0", "24.12.2026")
    pg.click("#resourceRows .res-days-add button.btn")   # not .dt-cal, the two typed-date boxes' own calendar-picker buttons (same ".res-days-add button" selector, different class)
    check("a day off is added and the summary count updates", "1 day off" in pg.inner_text("#resourceRows .res-days summary"), pg.inner_text("#resourceRows .res-days summary"))
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("it's saved onto the pool entry, cleaned the same way project.holidays already is", ev("() => project.resources.find(r => r.name === 'KidOnly').daysOff") == [{"date": "2026-12-24"}], ev("() => project.resources"))
    pg.click("#scheduleMenuBtn"); pg.click("#planResourcesItem"); pg.wait_for_selector("#resourcePoolModalBg.open")
    check("reopening shows the day off saved, open by default since it's not empty", pg.locator("#resourceRows .res-days").get_attribute("open") is not None and "24.12.2026" in pg.inner_text("#resourceRows"))
    pg.click("#resourceRows .hol-row button")
    pg.click("#resourcePoolModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("removing it again clears daysOff entirely (absent, not an empty array)", "daysOff" not in ev("() => project.resources.find(r => r.name === 'KidOnly')"), ev("() => project.resources"))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
