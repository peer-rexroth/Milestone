# -*- coding: utf-8 -*-
"""Task Type / Work, Stage 2 — wiring `recalcTaskType()` into the interactive edit paths (import/paste/merge are
deliberately untouched, same as every other computed-on-edit behavior in this app). The inline grid's Duration cell
(now also a new Work cell) and Resource cell, the task dialog's save (comparing against a `modalOrigDates`-style
before/after snapshot — a net Duration change takes priority over a Resource-text change when both happened in the
same dialog session), and the bulk edit Resource field all call `recalcTaskType()` and, when it rescaled the resource
text, toast the change. See "Task Type / Work" in CLAUDE.md."""
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
            "progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', effortDriven: true, resource: sp.r || '', "
            "actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }")
    seed = lambda specs: ev(SEED, specs)
    days = lambda i=0: ev(f"() => durationDays(tasks[{i}].startDate, tasks[{i}].endDate)")
    toastText = lambda: ev("() => document.getElementById('toastMsg').textContent")

    # ---------------------------------------------------------------- inline grid: Resource cell (Fixed Units default)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])   # 4 days
    ev("() => { editingCell = { id: tasks[0].id, field: 'resource' }; commitInlineEdit(tasks[0].id, 'resource', 'Anna, Ben'); }")
    check("inline Resource edit: Fixed Units shrinks Duration ('two people finish faster')", days() == 2, days())

    # ---------------------------------------------------------------- inline grid: the new Work cell
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    half = ev("() => tasks[0].work / 2")
    ev(f"() => {{ editingCell = {{ id: tasks[0].id, field: 'work' }}; commitInlineEdit(tasks[0].id, 'work', '{half}m'); }}")
    check("inline Work edit recalculates Duration (Fixed Units)", days() == 2, days())
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    ev("() => { editingCell = { id: tasks[0].id, field: 'work' }; commitInlineEdit(tasks[0].id, 'work', 'not a duration'); }")
    check("an unreadable Work value is refused with a toast, nothing changes", "Can't read" in toastText() and days() == 4, toastText())

    # ---------------------------------------------------------------- inline grid: Resource edit on Fixed Duration recalculates Work silently (no text to rescale, so no toast)
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedDuration"}}])
    d0 = days(); w0f = ev("() => tasks[0].work")
    ev("() => { editingCell = { id: tasks[0].id, field: 'resource' }; commitInlineEdit(tasks[0].id, 'resource', 'Anna, Ben'); }")
    check("Fixed Duration: dates unaffected by a resource edit", days() == d0)
    check("...Work increases silently instead (nothing to toast — Units is text, Work isn't)", ev("() => tasks[0].work") > w0f)

    # ---------------------------------------------------------------- inline grid: milestones/groups are never touched
    seed([{"name": "M", "s": "2026-09-07", "e": "2026-09-07", "r": "Anna", "extra": {"milestone": True}}])
    ev("() => { editingCell = { id: tasks[0].id, field: 'resource' }; commitInlineEdit(tasks[0].id, 'resource', 'Anna, Ben'); }")
    check("a milestone's resource edit never touches its (single) date", ev("() => tasks[0].startDate") == "2026-09-07")

    # ---------------------------------------------------------------- task dialog: Resource field, saved
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    ev("() => openTaskModal(tasks[0].id, false)")
    pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(50)   # past openTaskModal()'s own 30ms deferred autofocus, a documented test gotcha (see CLAUDE.md)
    pg.fill("#taskResourceInput", "Anna, Ben")
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")
    check("task dialog: saving a Resource change shrinks Duration too", days() == 2, days())

    # ---------------------------------------------------------------- task dialog: Duration field on a Fixed Work task rescales the resource text
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna:100%, Ben:100%", "extra": {"taskType": "fixedWork"}}])
    ev("() => openTaskModal(tasks[0].id, false)")
    pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(50)   # past openTaskModal()'s own 30ms deferred autofocus, a documented test gotcha (see CLAUDE.md)
    pg.fill("#taskDurationInput", "2")
    pg.locator("#taskDurationInput").dispatch_event("change")
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")
    check("task dialog: shrinking Duration on Fixed Work rescales the resource text", ev("() => taskUnitsPercent(tasks[0])") == 400, ev("() => tasks[0].resource"))
    check("...and toasts what changed", "keep Work the same" in toastText(), toastText())

    # ---------------------------------------------------------------- task dialog: a Duration edit takes priority over a Resource edit in the same session
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])   # Fixed Units, 4 days
    ev("() => openTaskModal(tasks[0].id, false)")
    pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(50)   # past openTaskModal()'s own 30ms deferred autofocus, a documented test gotcha (see CLAUDE.md)
    pg.fill("#taskResourceInput", "Anna, Ben")   # would shrink to 2 days on its own
    pg.fill("#taskDurationInput", "6"); pg.locator("#taskDurationInput").dispatch_event("change")   # but Duration was also typed explicitly
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")
    check("an explicit Duration edit wins over an incidental Resource edit in the same save", days() == 6, days())

    # ---------------------------------------------------------------- task dialog: nothing changed -> no spurious recalculation
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}])
    w0 = ev("() => tasks[0].work")
    ev("() => openTaskModal(tasks[0].id, false)")
    pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(50)   # past openTaskModal()'s own 30ms deferred autofocus, a documented test gotcha (see CLAUDE.md)
    pg.click("#taskModalBg .btn-primary")
    pg.wait_for_selector("#taskModalBg.open", state="hidden")
    check("saving with nothing touched leaves Work exactly as it was", ev("() => tasks[0].work") == w0)

    # ---------------------------------------------------------------- bulk edit: Resource field
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"}, {"name": "B", "s": "2026-09-07", "e": "2026-09-11", "r": "Ben"}])
    ev("() => setSelection(tasks.map(t => t.id))")
    ev("() => openBulkModal()")
    pg.check("#bulkOn-resource")
    pg.fill("#bulkVal-resource", "Anna, Ben")
    ev("() => applyBulkEdit()")
    check("bulk Resource edit recalculates each task's own Duration independently", ev("() => tasks.map(t => durationDays(t.startDate, t.endDate))") == [2, 3], ev("() => tasks.map(t => durationDays(t.startDate, t.endDate))"))
    check("...the toast says how many tasks changed", "Updated 2 tasks" in toastText(), toastText())

    # ---------------------------------------------------------------- bulk edit: a Fixed-Duration task in the mix keeps its dates, gains Work instead
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna", "extra": {"taskType": "fixedDuration"}}])
    d1 = days(); w1 = ev("() => tasks[0].work")
    ev("() => setSelection(tasks.map(t => t.id))")
    ev("() => openBulkModal()")
    pg.check("#bulkOn-resource")
    pg.fill("#bulkVal-resource", "Anna, Ben")
    ev("() => applyBulkEdit()")
    check("bulk Resource edit on a Fixed-Duration task leaves its dates alone", days() == d1)
    check("...and increases its Work instead", ev("() => tasks[0].work") > w1)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
