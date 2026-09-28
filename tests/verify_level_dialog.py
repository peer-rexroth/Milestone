# -*- coding: utf-8 -*-
"""Resource levelling, Stage 6 — the "Level resources" dialog (`#levelModalBg`, Schedule menu, next to Reschedule).
Wraps `levelResources()`/`levelDryRun()` exactly the way the Reschedule dialog wraps its own engine function: a live
dry-run preview (hint line + a "Which tasks" list sorted by display id), the "Keep within existing slack" checkbox
(default on) and a "Only from a date on" scope, Apply + a toast Undo. Reached from the Schedule menu, whose own item
shows a live over-allocated count (there is no separate top-bar badge for it — removed at the user's request). See
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
    SEED = ("specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.workDays; delete project.holidays; "
            "const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: null, order: tasks.length, startDate: sp.s, endDate: sp.e, "
            "progress: 0, milestone: false, color: null, predecessors: (sp.preds||[]).map(p => ({id: ids[p[0]], type: p[1]||'FS', lag: p[2]||0})), collapsed: false, updatedAt: 1, "
            "constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } "
            "normalizeData(); save(); render(); }")
    seed = lambda specs: ev(SEED, specs)
    dates = lambda: ev("() => Object.fromEntries(tasks.map(t => [t.name, [t.startDate, t.endDate]]))")

    # ---------------------------------------------------------------- no pool at all: informative hint, disabled button
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08"}])
    pg.click("#scheduleMenuBtn")
    check("the Schedule menu item is there", pg.locator("#planLevelItem").count() == 1)
    check("with no resources, the item shows no hint", pg.locator("#planLevelItem .item-hint").count() == 0)
    pg.click("#planLevelItem"); pg.wait_for_selector("#levelModalBg.open")
    check("no pool -> an informative hint, not a crash", "No resources yet" in pg.inner_text("#levelHint"))
    check("the button is disabled", pg.get_attribute("#levelBtn", "disabled") is not None)
    pg.keyboard.press("Escape")
    check("Escape closes it", pg.locator("#levelModalBg.open").count() == 0)

    # ---------------------------------------------------------------- a resolvable conflict: preview, apply, undo
    seed([
        {"name": "LongBranch", "s": "2026-09-07", "e": "2026-09-16"},
        {"name": "C", "s": "2026-09-08", "e": "2026-09-09", "r": "Anna"},
        {"name": "D", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"},
        {"name": "J", "s": "2026-09-17", "e": "2026-09-18", "preds": [["LongBranch", "FS"], ["C", "FS"]]},
    ])
    pg.click("#scheduleMenuBtn")
    check("the Schedule menu item now shows the over-allocated count", "1 over-allocated" in pg.inner_text("#planLevelItem"))
    pg.click("#planLevelItem"); pg.wait_for_selector("#levelModalBg.open")
    check("the dry-run hint says one task would move", "1 task would move" in pg.inner_text("#levelHint"), pg.inner_text("#levelHint"))
    check("the button is enabled", pg.get_attribute("#levelBtn", "disabled") is None)
    check("Which tasks lists exactly one row (C, not D — whichever has the slack)", pg.locator("#levelList .rs-row").count() == 1)
    row_name = pg.eval_on_selector_all("#levelList .rs-name", "els => els.map(e => e.textContent)")[0]
    check("no unresolved note shown", "hidden" in pg.get_attribute("#levelUnresolvedNote", "class"))
    before = dates()
    pg.click("#levelBtn")
    pg.wait_for_timeout(150)
    check("the dialog closes on Apply", pg.locator("#levelModalBg.open").count() == 0)
    check("the moved task's date actually changed", dates()[row_name] != before[row_name], (row_name, dates(), before))
    check("the over-allocation is gone", ev("() => overallocatedResources()") == [])
    check("a toast with Undo appears", pg.locator("#toastUndoBtn:visible").count() == 1)
    pg.click("#toastUndoBtn")
    pg.wait_for_timeout(150)
    check("Undo restores the exact original dates", dates() == before, (dates(), before))
    check("the conflict is back too, so the Schedule menu's hint shows it again", (pg.click("#scheduleMenuBtn"), "1 over-allocated" in pg.inner_text("#planLevelItem"))[1])
    check("there is no separate top-bar badge for it", pg.locator("#resourceOverallocBtn").count() == 0)
    pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- genuinely zero slack: unresolved note, toggling the checkbox off resolves it
    seed([
        {"name": "E", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna"},
        {"name": "F", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna"},
        {"name": "G", "s": "2026-09-09", "e": "2026-09-09", "preds": [["E", "FS"], ["F", "FS"]]},
    ])
    pg.click("#scheduleMenuBtn"); pg.click("#planLevelItem"); pg.wait_for_selector("#levelModalBg.open")
    check("nothing resolvable within slack -> the button stays disabled", pg.get_attribute("#levelBtn", "disabled") is not None)
    check("the hint mentions the unresolved conflicts", "could not be resolved" in pg.inner_text("#levelHint"), pg.inner_text("#levelHint"))
    check("the unresolved note names the tasks", not ("hidden" in pg.get_attribute("#levelUnresolvedNote", "class")) and "E" in pg.inner_text("#levelUnresolvedNote") and "F" in pg.inner_text("#levelUnresolvedNote"))
    pg.click("#levelWithinSlack")
    pg.wait_for_timeout(150)
    check("turning the cap off makes it resolvable", pg.get_attribute("#levelBtn", "disabled") is None)
    ebefore = dates()
    pg.click("#levelBtn")
    pg.wait_for_timeout(150)
    check("it actually resolves the conflict this time", ev("() => overallocatedResources()") == [])
    check("G (the shared successor) is unaffected in position relative to its own predecessors — no dependency violation", ev("() => tasks.find(t => t.name === 'G').startDate") >= max(dates()['E'][1], dates()['F'][1]))

    # ---------------------------------------------------------------- scope: "Only from a date on" filters what's eligible
    seed([
        {"name": "LongBranch", "s": "2026-09-07", "e": "2026-09-16"},
        {"name": "C", "s": "2026-09-08", "e": "2026-09-09", "r": "Anna"},
        {"name": "D", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"},
        {"name": "J", "s": "2026-09-17", "e": "2026-09-18", "preds": [["LongBranch", "FS"], ["C", "FS"]]},
    ])
    pg.click("#scheduleMenuBtn"); pg.click("#planLevelItem"); pg.wait_for_selector("#levelModalBg.open")
    check("the date field starts hidden", "hidden" in pg.get_attribute("#levelFromInput", "class"))
    pg.click("#levelFromOn")
    check("checking the scope reveals the date field", "hidden" not in pg.get_attribute("#levelFromInput", "class"))
    pg.fill("#levelFromInput", "20.09.2026"); pg.locator("#levelFromInput").dispatch_event("change")
    pg.wait_for_timeout(150)
    check("scoping past both conflicting tasks' own floor leaves nothing to level", "Nothing to level" in pg.inner_text("#levelHint"), pg.inner_text("#levelHint"))
    check("the button is disabled again", pg.get_attribute("#levelBtn", "disabled") is not None)
    pg.fill("#levelFromInput", "01.09.2026"); pg.locator("#levelFromInput").dispatch_event("change")
    pg.wait_for_timeout(150)
    check("scoping to include the conflict finds it again", "1 task would move" in pg.inner_text("#levelHint"), pg.inner_text("#levelHint"))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
