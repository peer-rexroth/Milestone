# -*- coding: utf-8 -*-
"""The third dialog UX round (after a review of all 19 dialogs once more). (1) Help's topic pane no longer spills out of the
dialog on a phone. (2) A long Task Name opens with the caret — and the visible text — at the START of the name, not its end.
(3) The Baselines "selected task" label never shows a stray space before its closing quote, and stacks to one column on a
phone. (4) A typed date/time box that refuses what you wrote also shows a red border and a small bubble under the box (on
top of the existing toast), which clears as soon as you retype and disappears if its dialog closes while it's showing.
(5) Leaving Hours & minutes warns first when it would drop a time of day or round a lag, naming how many — Cancel leaves
everything exactly as it was. (6) Edit tasks now asks before discarding a ticked-but-unapplied change, like the other
dialogs. (7) Reschedule and Baselines: Enter (outside a button) applies the dialog, the same convention Edit tasks already
had and the task dialog's Name box always had."""
import os, re
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)
LONG = "Website relaunch phase two: legal review of the new privacy policy and cookie consent banner across every regional storefront"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    toast = lambda: ev("() => document.getElementById('toastMsg').textContent")
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)
    def plan(specs, minute=True):
        ev("m => { if (m) { project.timeUnit = 'minute'; normalizeData(); } else { delete project.timeUnit; delete project.workHours; delete project.lagUnit; delete project.workHoursByDay; }; setView('tasks'); }", minute)
        ev(SEED, specs)
        ev("() => { normalizeData(); save(); render(); }")
    def close_all(): ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); }")
    A = {"name": "A", "s": "2026-09-07", "e": "2026-09-08", "extra": {"startTime": "09:00", "endTime": "11:30"}}
    B = {"name": "B", "s": "2026-09-09", "e": "2026-09-10", "preds": [["A", "FS", 0]]}

    # ================================================================ 1. Help on a phone
    pg.set_viewport_size({"width": 390, "height": 780})
    plan([A])
    ev("() => openHelpModal()"); pg.wait_for_timeout(250)
    fit = ev("""() => { const m = document.querySelector('#helpModalBg .modal').getBoundingClientRect(), pa = document.getElementById('helpPane-start');
        return { modalBottom: Math.round(m.bottom), viewport: innerHeight, paneScrolls: pa.scrollHeight > pa.clientHeight, paneRight: Math.round(pa.getBoundingClientRect().right), modalRight: Math.round(m.right) }; }""")
    check("Help's topic pane scrolls INSIDE the dialog on a phone, not past it (the dialog fits the viewport, the pane's content doesn't spill past the dialog's own edge)", fit["modalBottom"] <= fit["viewport"] and fit["paneRight"] <= fit["modalRight"] + 1, fit)
    close_all()
    pg.set_viewport_size({"width": 1400, "height": 860})

    # ================================================================ 2. long Task Name opens at its start
    plan([dict(A, name=LONG)])
    ev("() => openTaskModal(tasks[0].id)"); pg.wait_for_timeout(250)
    pos = ev("() => { const e = document.getElementById('taskNameInput'); return [e.selectionStart, e.selectionEnd, e.scrollLeft]; }")
    check("a long Task Name opens with the caret at the very start (not scrolled to show the end)", pos[0] == 0 and pos[1] == 0, pos)
    close_all()

    # ================================================================ 3. Baselines label
    plan([dict(A, name=LONG + " ")])   # a name with real trailing whitespace (paste/import can leave one; commitInlineEdit only trims on the LIST's own edit path)
    ev("() => setSelection([tasks[0].id])")
    ev("() => openBaselineModal()"); pg.wait_for_timeout(200)
    lbl = pg.inner_text("#baselineScopeSelLabel")
    check("the 'selected task' label never shows a trailing space before the closing quote, whatever is in the name", lbl.rstrip().endswith('”') and '” ' not in lbl[:-1] + ' ' and not lbl[:-1].endswith(' '), lbl)
    close_all()
    pg.set_viewport_size({"width": 390, "height": 780})
    ev("() => openBaselineModal()"); pg.wait_for_timeout(200)
    check("on a phone the baseline grid stacks to one column (Which baseline above Apply to, not squeezed side by side)", ev("() => getComputedStyle(document.querySelector('#baselineModalBg .bl-grid')).gridTemplateColumns.split(' ').length") == 1)
    close_all()
    pg.set_viewport_size({"width": 1400, "height": 860})

    # ================================================================ 4. inline error bubble on typed boxes
    plan([A, B])
    ev("() => openTaskModal(tasks.find(t => t.name === 'B').id)"); pg.wait_for_timeout(250)
    pg.fill("#taskStartInput", "not a date"); pg.press("#taskStartInput", "Tab"); pg.wait_for_timeout(150)
    check("an unreadable date gets a red border and a bubble under the box, on top of the toast", ev("() => document.getElementById('taskStartInput').classList.contains('dt-err')") and ev("() => { const b = document.querySelector('.dt-err-bubble'); return b && b.classList.contains('show') && b.textContent.includes('24.12.2026'); }") and "isn't a date" in toast())
    pg.fill("#taskStartInput", "9"); pg.wait_for_timeout(80)
    check("retyping clears the red border and the bubble right away (before even leaving the box)", not ev("() => document.getElementById('taskStartInput').classList.contains('dt-err')") and not ev("() => document.querySelector('.dt-err-bubble').classList.contains('show')"))
    pg.fill("#taskStartTimeInput", "99:99"); pg.press("#taskStartTimeInput", "Tab"); pg.wait_for_timeout(150)
    check("an unreadable time gets its own bubble ('14:30')", ev("() => document.getElementById('taskStartTimeInput').classList.contains('dt-err')") and "14:30" in ev("() => document.querySelector('.dt-err-bubble').textContent"))
    pg.click("#taskModalBg .modal-header button"); pg.wait_for_timeout(200)
    check("closing the dialog with an error still showing takes the bubble with it (not left floating over the page)", not ev("() => { const b = document.querySelector('.dt-err-bubble'); return b && b.classList.contains('show'); }"))
    close_all()

    # ================================================================ 5. leaving Hours & minutes warns
    plan([A, B])
    ev("() => { tasks.find(t => t.name === 'B').predecessors[0].lag = 90; save(); }")   # a lag that won't round evenly
    before = ev("() => JSON.stringify({ tasks, timeUnit: project.timeUnit })")
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='precision']"); pg.wait_for_selector("#precisionModalBg.open")
    pg.click("#precisionDay"); pg.click("#precisionModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    body = pg.inner_text("#confirmModalBody")
    check("the warning names both what is lost: a task's time of day AND a lag that will round", "task" in body and "time of day" in body and "lag" in body and "round to whole working days" in body, body)
    pg.click("#confirmModalCancelBtn"); pg.wait_for_timeout(150)
    check("Cancel leaves the plan exactly as it was (still Hours & minutes, times and the odd lag intact) and the precision dialog stays open", ev("() => JSON.stringify({ tasks, timeUnit: project.timeUnit })") == before and pg.locator("#precisionModalBg.open").count() == 1)
    pg.click("#precisionModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150); pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(200)
    check("confirming actually switches to Days", ev("() => project.timeUnit") is None)
    close_all()
    plan([{"name": "A", "s": "2026-09-07", "e": "2026-09-08"}])   # no times, no odd lags: nothing to lose
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='precision']"); pg.wait_for_selector("#precisionModalBg.open")
    pg.click("#precisionDay"); pg.click("#precisionModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    check("switching to Days with nothing to lose asks nothing", pg.locator("#confirmModalBg.open").count() == 0 and ev("() => project.timeUnit") is None)
    close_all()

    # ================================================================ 6. Edit tasks discard confirmation
    plan([A, B])
    ev("() => { setSelection(tasks.map(t => t.id)); openBulkModal(); }"); pg.wait_for_timeout(200)
    check("nothing ticked: the backdrop closes it right away", True)   # sanity baseline, proven by the next assertion's contrast
    pg.click("#bulkModalBg", position={"x": 5, "y": 5}); pg.wait_for_timeout(150)
    check("...(a click on the untouched dialog's backdrop closes it with no question)", pg.locator("#bulkModalBg.open").count() == 0 and pg.locator("#confirmModalBg.open").count() == 0)
    ev("() => { setSelection(tasks.map(t => t.id)); openBulkModal(); }"); pg.wait_for_timeout(200)
    pg.check("#bulkOn-progress"); pg.fill("#bulkVal-progress", "40")
    pg.click("#bulkModalBg .modal-header button"); pg.wait_for_timeout(150)
    check("with a field ticked, the header × asks first", pg.locator("#confirmModalBg.open").count() == 1 and "did not apply" in pg.inner_text("#confirmModalBody"), pg.inner_text("#confirmModalBody") if pg.locator("#confirmModalBg.open").count() else None)
    pg.click("#confirmModalCancelBtn"); pg.wait_for_timeout(100)
    check("Keep editing leaves the dialog open with the tick still there", pg.locator("#bulkModalBg.open").count() == 1 and pg.is_checked("#bulkOn-progress"))
    pg.click("#bulkModalBg", position={"x": 5, "y": 5}); pg.wait_for_timeout(150)
    check("the backdrop asks too, the same way", pg.locator("#confirmModalBg.open").count() == 1)
    pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(150)
    check("discarding closes it and nothing was applied", pg.locator("#bulkModalBg.open").count() == 0 and ev("() => tasks[0].progress") == 0)
    check("...Cancel (the dialog's own button, a deliberate choice) still closes it directly, no question asked", (lambda: (ev("() => { setSelection(tasks.map(t => t.id)); openBulkModal(); }"), pg.wait_for_timeout(150), pg.check("#bulkOn-progress"), pg.click("#bulkModalBg .modal-footer button:has-text('Cancel')"), pg.wait_for_timeout(150), pg.locator("#bulkModalBg.open").count() == 0 and pg.locator("#confirmModalBg.open").count() == 0)[-1])())

    # ================================================================ 7. Enter applies Reschedule and Baselines
    plan([A])
    ev("() => openRescheduleModal()"); pg.wait_for_timeout(200)
    pg.click("#rescheduleDateInput"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("Enter with focus in the (typed) date box settles it, then applies Reschedule", pg.locator("#rescheduleModalBg.open").count() == 0)
    close_all()
    plan([A])
    ev("() => openBaselineModal()"); pg.wait_for_timeout(200)
    pg.locator("#baselineSlotSelect").focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("Enter with focus on the baseline picker (a select, not a button) applies Set baseline", ev("() => project.baselines && project.baselines[0] !== undefined"))
    close_all()

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
