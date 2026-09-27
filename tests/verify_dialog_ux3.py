# -*- coding: utf-8 -*-
"""The fourth dialog UX round (a third review of the same 19 dialogs, after round 3 shipped) — three small fixes found by it.
(1) Pronoun agreement: the leave-Hours-&-minutes warning said "1 task will lose THEIR time of day", and the pre-existing
Edit-tasks skip note said "1 group kept THEIR worked-out progress" — both now say "its" for exactly one, "their" for more
than one, matching the house style already used for "1 task has" / "2 tasks have" elsewhere. (2) A typed date/time box in
its refused state now also carries aria-invalid="true" (cleared the moment it's fixed), so a screen-reader user who reaches
the field directly — without having heard the toast — still knows it's wrong. (3) The error bubble now also repositions on
a window resize, not just on scroll, so it stays under its box instead of drifting out of place."""
import os, re
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)
    def plan(specs, minute=True):
        ev("m => { if (m) { project.timeUnit = 'minute'; normalizeData(); } else { delete project.timeUnit; delete project.workHours; delete project.lagUnit; delete project.workHoursByDay; }; setView('tasks'); }", minute)
        ev(SEED, specs)
        ev("() => { normalizeData(); save(); render(); }")
    def close_all(): ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); }")
    A = {"name": "A", "s": "2026-09-07", "e": "2026-09-08", "extra": {"startTime": "09:00", "endTime": "11:30"}}
    B = {"name": "B", "s": "2026-09-09", "e": "2026-09-10"}

    # ================================================================ 1. pronoun agreement
    plan([A])
    pg.click("#scheduleMenuBtn"); pg.click("#planPrecisionItem"); pg.wait_for_selector("#precisionModalBg.open")
    pg.click("#precisionDay"); pg.click("#precisionModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    body1 = pg.inner_text("#confirmModalBody")
    check("exactly one task: 'will lose ITS time of day', not 'their'", "will lose its time of day" in body1 and "their" not in body1, body1)
    pg.click("#confirmModalActionBtn"); pg.wait_for_timeout(150)
    close_all()
    plan([A, dict(B, extra={"startTime": "09:00", "endTime": "10:00"})])
    pg.click("#scheduleMenuBtn"); pg.click("#planPrecisionItem"); pg.wait_for_selector("#precisionModalBg.open")
    pg.click("#precisionDay"); pg.click("#precisionModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(200)
    body2 = pg.inner_text("#confirmModalBody")
    check("two tasks: 'will lose THEIR time of day' (plural is correct here)", "will lose their time of day" in body2, body2)
    pg.click("#confirmModalCancelBtn"); pg.wait_for_timeout(100)
    close_all()
    plan([{"name": "G1", "s": "2026-09-07", "e": "2026-09-08"}])
    ev("() => { const g = tasks[0]; setSelection([g.id]); }")
    ev("""() => { const g = tasks[0]; const c = { id: genId(), name: 'c', parentId: g.id, order: 0, startDate: '2026-09-07', endDate: '2026-09-08', progress: 30, milestone: false, color: null,
        predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null };
        tasks.push(c); normalizeData(); save(); render(); }""")
    ev("() => { setSelection(tasks.map(t => t.id)); openBulkModal(); }"); pg.wait_for_timeout(200)
    pg.check("#bulkOn-progress"); pg.fill("#bulkVal-progress", "60"); pg.click("#bulkModalBg .modal-footer .btn-primary"); pg.wait_for_timeout(200)
    check("one group skipped in Edit tasks: 'kept ITS worked-out progress', not 'their'", "kept its worked-out progress" in ev("() => document.getElementById('toastMsg').textContent"), ev("() => document.getElementById('toastMsg').textContent"))

    # ================================================================ 2. aria-invalid
    plan([A])
    ev("() => openTaskModal(tasks[0].id)"); pg.wait_for_timeout(250)
    check("a valid box starts with no aria-invalid", ev("() => document.getElementById('taskStartInput').getAttribute('aria-invalid')") is None)
    pg.fill("#taskStartInput", "garbage"); pg.press("#taskStartInput", "Tab"); pg.wait_for_timeout(150)
    check("a refused date is marked aria-invalid=true", ev("() => document.getElementById('taskStartInput').getAttribute('aria-invalid')") == "true")
    pg.fill("#taskStartInput", "9"); pg.wait_for_timeout(80)
    check("...cleared the moment it's fixed (even before leaving the box)", ev("() => document.getElementById('taskStartInput').getAttribute('aria-invalid')") is None)
    pg.fill("#taskStartTimeInput", "99:99"); pg.press("#taskStartTimeInput", "Tab"); pg.wait_for_timeout(150)
    check("a refused time is marked aria-invalid too", ev("() => document.getElementById('taskStartTimeInput').getAttribute('aria-invalid')") == "true")
    close_all()

    # ================================================================ 3. bubble follows a window resize
    plan([A])
    ev("() => openTaskModal(tasks[0].id)"); pg.wait_for_timeout(250)
    pg.fill("#taskStartInput", "garbage"); pg.press("#taskStartInput", "Tab"); pg.wait_for_timeout(150)
    before = ev("() => { const b = document.querySelector('.dt-err-bubble').getBoundingClientRect(), f = document.getElementById('taskStartInput').getBoundingClientRect(); return [Math.round(b.left - f.left), Math.round(b.top - f.bottom)]; }")
    pg.set_viewport_size({"width": 1100, "height": 860}); pg.wait_for_timeout(150)
    after = ev("() => { const b = document.querySelector('.dt-err-bubble').getBoundingClientRect(), f = document.getElementById('taskStartInput').getBoundingClientRect(); return [Math.round(b.left - f.left), Math.round(b.top - f.bottom), b.width > 0]; }")
    check("resizing the window keeps the bubble aligned under its box (same offset from the field, not left behind)", after[2] and abs(after[0] - before[0]) <= 1 and abs(after[1] - before[1]) <= 1, (before, after))
    pg.set_viewport_size({"width": 1400, "height": 860})
    close_all()

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
