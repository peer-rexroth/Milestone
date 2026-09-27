# -*- coding: utf-8 -*-
"""project.honorConstraintDates — MS Project's "Tasks will always honor their constraint dates": on (the standard, absent = true)
a task's own constraint always overrides what its links compute, same as before this existed; off, a link wins when the two
disagree and the constraint only shows as unmet (constraintViolated()) rather than forcing the date. The dialog (Working
calendar), the engine (constraintStartMoment's floor/cap), and that an isolated (no-predecessor) task is unaffected either way."""
import re, os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    seed = lambda specs: ev(SEED, specs)
    tid = lambda n: ev("n => tasks.find(t => t.name === n).id", n)
    dates = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    violated = lambda n: ev("n => constraintViolated(tasks.find(t => t.name === n))", n)
    apply = lambda n: ev("n => { applyConstraints(tasks.find(t => t.name === n).id); save(); render(); }", n)

    # ---------------------------------------------------------------- the dialog: default, toggling, save, dirty-check
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open"); pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    check("defaults checked (the standard: constraints always win)", pg.is_checked("#honorConstraintDatesInput"))
    pg.uncheck("#honorConstraintDatesInput")
    pg.click("#calendarModalBg .modal-header button")
    check("unchecking it and closing without saving asks first", pg.locator("#confirmModalBg.open").count() == 1)
    pg.click("#confirmModalBg button:has-text('Keep editing')")
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("saved: project.honorConstraintDates is false", ev("() => project.honorConstraintDates") == False)
    pg.click("#scheduleMenuBtn"); pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    check("reopening shows it unchecked", not pg.is_checked("#honorConstraintDatesInput"))
    pg.check("#honorConstraintDatesInput")
    pg.click("#calendarModalBg .modal-footer button.btn-primary"); pg.wait_for_timeout(150)
    check("checking it again saves absent (the standard), not a stored true", "honorConstraintDates" not in ev("() => Object.keys(project)"))

    # ---------------------------------------------------------------- engine: an upper bound (SNLT) caps a predecessor push only when honored
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-14"},
          {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "preds": [["A", "FS", 0]], "extra": {"constraintType": "SNLT", "constraintDate": "2026-09-10"}}])
    apply("B")
    check("honored (the default): SNLT caps the predecessor push exactly at its own date", dates("B") == ["2026-09-10", "2026-09-11"], dates("B"))
    check("...and is not flagged violated (the cap already satisfies it)", violated("B") == False)
    ev("() => { project.honorConstraintDates = false; }")
    apply("B")
    check("not honored: the link wins instead — B follows A's push straight past the SNLT date", dates("B") == ["2026-09-15", "2026-09-16"], dates("B"))
    check("...but it's still flagged violated (shown, just not enforced)", violated("B") == True)

    # ---------------------------------------------------------------- engine: a lower bound (SNET) no longer extends past a predecessor push
    seed([{"name": "C", "s": "2026-09-07", "e": "2026-09-16"},
          {"name": "D", "s": "2026-09-07", "e": "2026-09-08", "preds": [["C", "FS", 0]], "extra": {"constraintType": "SNET", "constraintDate": "2026-09-08"}}])
    ev("() => { delete project.honorConstraintDates; }")
    apply("D")
    check("honored: SNET is a floor that can still push later than the predecessor alone would (here the predecessor already wins, later than the constraint)", dates("D")[0] == "2026-09-17", dates("D"))
    seed([{"name": "E", "s": "2026-09-07", "e": "2026-09-09"},
          {"name": "F", "s": "2026-09-07", "e": "2026-09-08", "preds": [["E", "FS", 0]], "extra": {"constraintType": "SNET", "constraintDate": "2026-09-20"}}])
    apply("F")
    check("honored: SNET later than the predecessor push wins (a real floor; 09-20 is a Sunday, snapped to the next working day)", dates("F")[0] == "2026-09-21", dates("F"))
    ev("() => { project.honorConstraintDates = false; }")
    apply("F")
    check("not honored: SNET no longer extends past what the predecessor alone requires", dates("F")[0] == "2026-09-10", dates("F"))
    check("...and constraintViolated() stays false either way for a lower bound — by design it only ever flags an exact or upper bound (see its own comment); a lower bound sitting earlier than it asks for is not a 'violation' to report", violated("F") == False)

    # ---------------------------------------------------------------- an isolated task (no predecessor) honors its constraint regardless of the toggle
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-08", "extra": {"constraintType": "SNET", "constraintDate": "2026-09-14"}}])
    ev("() => { delete project.honorConstraintDates; }")
    apply("G")
    honored_iso = dates("G")
    ev("() => { project.honorConstraintDates = false; }")
    apply("G")
    check("an isolated constrained task is unaffected by the toggle either way (nothing to conflict with)", dates("G") == honored_iso, (honored_iso, dates("G")))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
