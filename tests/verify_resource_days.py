# -*- coding: utf-8 -*-
"""The Days off dialog — one resource's own days off, opened from a Resource Sheet row's "Days off" link. It replaced
the old Resource pool dialog (add/rename/Max Units/remove for every resource), whose CRUD moved to the Resource Sheet;
the Resource Sheet is a view tab. Rename/remove cascades are
covered by verify_resource_sheet_view.py. See "Resource levelling" and "Resource Sheet" in CLAUDE.md."""
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
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); resetHistory(); }"
    seed = lambda specs: ev(SEED, specs)
    days = lambda n: ev("n => (project.resources.find(r => r.name === n) || {}).daysOff", n)
    is_open = lambda: pg.locator("#resourceDaysModalBg.open").count() == 1

    # ---------------------------------------------------------------- the old Resource pool dialog is gone
    check("the old Resource pool dialog and its CRUD functions no longer exist",
          ev("() => !document.getElementById('resourcePoolModalBg') && typeof openResourcePoolModal === 'undefined' && typeof applyResourcePoolDraft === 'undefined'"))
    check("the shared rename/remove cascades the Resource Sheet uses are still there",
          ev("() => typeof renameResourceEverywhere === 'function' && typeof removeResourceEverywhere === 'function'"))

    # ---------------------------------------------------------------- the Resource Sheet is a view tab (the Schedule menu holds only actions now)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna:50%, Ben"}, {"name": "G", "s": "2026-09-07", "e": "2026-09-08", "r": "GroupOnly"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-08", "parent": "G", "r": "Ben"}])
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    check("the Schedule menu no longer has a Resource Sheet entry (it's a view tab)", pg.locator("#planResourcesItem").count() == 0)
    pg.keyboard.press("Escape")
    pg.click("#mainViewTabs .view-tab:has-text('Resources')"); pg.wait_for_timeout(120)
    check("its view tab switches to the Resource Sheet, where the pool shows (a group's own text never enters it)", ev("() => currentView") == "resourceSheet" and pg.locator(".rst-row").count() == 2)

    # ---------------------------------------------------------------- opening from a Resource Sheet row
    ben_row = lambda: pg.locator(".rst-row").filter(has=pg.locator('input[aria-label="Resource name"][value="Ben"]'))
    ben_row().locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    check("a row's Days off link opens the Days off dialog, titled with that resource's name", is_open() and "Ben" in pg.inner_text("#resourceDaysModalBg h2"), pg.inner_text("#resourceDaysModalBg h2"))
    check("...showing an empty state with nothing to list, and the first date box focused",
          "No days off" in pg.inner_text("#resDayList") and ev("() => document.activeElement && document.activeElement.id") == "resDayFrom")
    check("the boxes are labelled First day / Last day (optional) / Name (optional), and Add says just 'Add' while empty",
          [t.strip() for t in pg.locator("#resourceDaysModalBg .hol-field > label").all_inner_texts()] == ["First day", "Last day (optional)", "Name (optional)"] and pg.inner_text("#resDayAddBtn").strip() == "Add",
          pg.locator("#resourceDaysModalBg .hol-field > label").all_inner_texts())
    check("...with none of the old pool CRUD in it (no name/Max Units fields, no Add resource)",
          pg.locator("#resourceDaysModalBg .res-name, #resourceDaysModalBg .res-units").count() == 0 and pg.locator("#resourceDaysModalBg button:has-text('Add resource')").count() == 0)

    # ---------------------------------------------------------------- adding: validation, a single day, a range
    pg.click("#resourceDaysModalBg .res-days-add button.btn")
    check("Add with no date is refused with a message", "Pick the day off first" in pg.inner_text("#toastMsg") and ev("() => resourceDaysDraft.length") == 0)
    pg.fill("#resDayFrom", "10.01.2027"); pg.fill("#resDayTo", "05.01.2027")
    pg.click("#resourceDaysModalBg .res-days-add button.btn")
    check("a range that ends before it starts is refused", "before the first day" in pg.inner_text("#toastMsg") and ev("() => resourceDaysDraft.length") == 0)
    pg.fill("#resDayFrom", "24.12.2026"); pg.fill("#resDayTo", ""); pg.fill("#resDayName", "Christmas Eve")
    check("with only a first day, the button says 'Add 1 day'", pg.inner_text("#resDayAddBtn").strip() == "Add 1 day", pg.inner_text("#resDayAddBtn"))
    pg.fill("#resDayTo", "24.12.2026")
    check("...and the same date in both boxes is still one day", pg.inner_text("#resDayAddBtn").strip() == "Add 1 day", pg.inner_text("#resDayAddBtn"))
    pg.click("#resourceDaysModalBg .res-days-add button.btn")
    check("a single day is added to the list, with its name, and the boxes clear for the next one",
          "24.12.2026" in pg.inner_text("#resDayList") and "Christmas Eve" in pg.inner_text("#resDayList") and ev("() => document.getElementById('resDayFrom').value") == "", pg.inner_text("#resDayList"))
    check("...added as a single day (no 'to'), and the button is back to 'Add'", ev("() => resourceDaysDraft.some(h => h.date === '2026-12-24' && !h.to)") and pg.inner_text("#resDayAddBtn").strip() == "Add")
    pg.fill("#resDayFrom", "03.08.2026"); pg.fill("#resDayTo", "14.08.2026")
    check("a range: the button counts every day in it ('Add 12 days')", pg.inner_text("#resDayAddBtn").strip() == "Add 12 days", pg.inner_text("#resDayAddBtn"))
    pg.click("#resourceDaysModalBg .res-days-add button.btn")
    check("a range is added too, and the list stays in date order", ev("() => resourceDaysDraft.map(h => h.date)") == ["2026-08-03", "2026-12-24"], ev("() => resourceDaysDraft"))
    check("the footer counts real days, not entries (a 12-day range + 1 day = 13)", "13 days off" in pg.inner_text("#resourceDaysCount"), pg.inner_text("#resourceDaysCount"))
    check("nothing is written to the plan before Save", days("Ben") is None)

    # ---------------------------------------------------------------- Save, the row's link, Undo
    pg.click("#resourceDaysModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("Save writes them onto the resource (cleaned the same way project.holidays is)",
          days("Ben") == [{"date": "2026-08-03", "to": "2026-08-14"}, {"date": "2026-12-24", "name": "Christmas Eve"}] and not is_open(), days("Ben"))
    check("the Resource Sheet row's link counts real days too ('13 days off')", "13 days off" in ben_row().locator(".rst-days-link").inner_text())
    check("the day off is zero capacity for levelling (Ben over-allocated on a day off he's assigned)",
          ev("() => { tasks.find(t => t.name === 'K').startDate = '2026-12-24'; tasks.find(t => t.name === 'K').endDate = '2026-12-24'; resetEffectiveCache(); return overallocatedResources().some(o => o.name === 'Ben'); }"))
    ev("() => { tasks.find(t => t.name === 'K').startDate = '2026-09-07'; tasks.find(t => t.name === 'K').endDate = '2026-09-08'; resetEffectiveCache(); }")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    check("Ctrl+Z (the generic history) takes the save back", days("Ben") is None, days("Ben"))
    pg.keyboard.press("Control+Shift+z"); pg.wait_for_timeout(150)

    # ---------------------------------------------------------------- removing, discard confirmation, Escape
    ben_row().locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    check("reopening lists what was saved", pg.locator("#resDayList .hol-row").count() == 2)
    pg.click("#resDayList .hol-row:first-child button")
    check("removing one takes it off the list", pg.locator("#resDayList .hol-row").count() == 1)
    pg.click("#resourceDaysModalBg .modal-header button")
    check("closing with unsaved changes asks first", pg.locator("#confirmModalBg.open").count() == 1)
    pg.keyboard.press("Escape")
    check("Escape on that question keeps editing", is_open() and pg.locator("#confirmModalBg.open").count() == 0)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    pg.click("#confirmModalBg button:has-text('Discard changes')"); pg.wait_for_timeout(120)
    check("discarding closes without saving", not is_open() and len(days("Ben")) == 2, days("Ben"))

    ben_row().locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    check("an untouched dialog closes on Escape without asking", not is_open() and pg.locator("#confirmModalBg.open").count() == 0)

    ben_row().locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    for _ in range(2): pg.click("#resDayList .hol-row:first-child button")
    pg.click("#resourceDaysModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("removing every day off and saving clears daysOff entirely (absent, not an empty array)",
          "daysOff" not in ev("() => project.resources.find(r => r.name === 'Ben')"), ev("() => project.resources"))
    ben_row().locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    pg.fill("#resDayFrom", "01.10.2026"); pg.click("#resourceDaysModalBg .res-days-add button.btn")
    pg.fill("#resDayFrom", "02.10.2026")
    pg.click("#resourceDaysModalBg .modal-footer button:has-text('Cancel')"); pg.wait_for_timeout(100)
    ben_row().locator(".rst-days-link").click(); pg.wait_for_timeout(120)
    check("reopening starts with empty boxes (nothing typed last time carries over) and a plain 'Add'",
          ev("() => document.getElementById('resDayFrom').value") == "" and pg.inner_text("#resDayAddBtn").strip() == "Add")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    check("Cancel discards without asking, even with changes", not is_open() and pg.locator("#confirmModalBg.open").count() == 0 and "daysOff" not in ev("() => project.resources.find(r => r.name === 'Ben')"))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
