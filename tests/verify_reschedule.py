# -*- coding: utf-8 -*-
"""Reschedule remaining work from a status date (MS Project's "Update Project…") — an explicit user request, the one
gap "Known v1 limitations" had called out as the kind that matters for a plan used throughout a live project. A single
topological sweep both applies the rule and cascades it: complete tasks untouched, an overdue not-started task moves to
the status date (never before what its own predecessors allow), an in-progress task's Finish only ever moves later
(never compressed if it's ahead), knock-on delays propagate through ordinary dependency links, manual tasks and
milestones behave consistently with the rest of the scheduling engine."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    MK = "(n, i, s, e, x) => Object.assign({id: genId(), name: n, parentId: null, order: i, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}, x || {})"
    def seed(js):
        ev("() => { tasks.length = 0; selectedTaskId = null; delete project.workDays; }")
        ev(js)
        ev("() => { normalizeData(); save(); render(); }")
    dates = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.endDate]; }", n)
    touch = lambda iso: ev("iso => rescheduleFromStatusDate(iso)", iso)

    # ---------------------------------------------------------------- the core cases, via the pure function
    check("a complete task (100%) is never touched", (seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-07', '2026-09-08', {{progress: 100}})); }}"), touch("2026-09-21"))[1] == [])
    check("a complete-by-actual-finish task is never touched", (seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-07', '2026-09-08', {{actualStart: '2026-09-07', actualFinish: '2026-09-08', progress: 100}})); }}"), touch("2026-09-21"))[1] == [])
    check("a genuinely future, not-started task (no predecessor) is left alone", (seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-28', '2026-09-30')); }}"), touch("2026-09-21"))[1] == [])
    check("a manual task is never touched, even overdue", (seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-07', '2026-09-08', {{taskMode: 'manual'}})); }}"), touch("2026-09-21"))[1] == [])

    seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-07', '2026-09-08')); }}")
    t = touch("2026-09-21")
    check("an overdue, not-started task moves to the status date, keeping its duration", len(t) == 1 and dates("A") == ["2026-09-21", "2026-09-22"], dates("A"))

    seed(f"() => {{ const mk = {MK}; tasks.push(mk('M', 0, '2026-09-07', '2026-09-07', {{milestone: true}})); }}")
    t = touch("2026-09-21")
    check("an overdue, incomplete milestone moves to the status date (one date)", len(t) == 1 and dates("M") == ["2026-09-21", "2026-09-21"], dates("M"))

    seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-07', '2026-09-11', {{actualStart: '2026-09-07', progress: 20}})); }}")   # 5-day task, 20% done
    t = touch("2026-09-21")
    check("an in-progress task's remaining work (5d x 80% = 4d) is projected from the status date; Actual Start never moves", len(t) == 1 and dates("A") == ["2026-09-07", "2026-09-24"], dates("A"))

    seed(f"() => {{ const mk = {MK}; tasks.push(mk('A', 0, '2026-09-07', '2026-10-30', {{actualStart: '2026-09-07', progress: 90}})); }}")   # way ahead of schedule
    before = dates("A")
    t = touch("2026-09-08")
    check("an in-progress task ahead of schedule is never pulled earlier (left exactly where it is)", t == [] and dates("A") == before, dates("A"))

    # ---------------------------------------------------------------- cascading through dependencies, in one sweep
    seed(f"""() => {{
      const mk = {MK};
      tasks.push(mk('A', 0, '2026-09-07', '2026-09-11', {{actualStart: '2026-09-07', progress: 20}}));
      tasks.push(mk('B', 1, '2026-09-14', '2026-09-16'));
      tasks.push(mk('C', 2, '2026-09-17', '2026-09-18'));
      tasks[1].predecessors = [{{id: tasks[0].id, type: 'FS', lag: 0}}];
      tasks[2].predecessors = [{{id: tasks[1].id, type: 'FS', lag: 0}}];
    }}""")
    t = touch("2026-09-21")
    check("a delay cascades through FS links in the SAME sweep: A -> 09-24, B right after -> 09-25..29, C right after -> 09-30..10-01",
          len(t) == 3 and dates("A") == ["2026-09-07", "2026-09-24"] and dates("B") == ["2026-09-25", "2026-09-29"] and dates("C") == ["2026-09-30", "2026-10-01"],
          [dates("A"), dates("B"), dates("C")])
    seed(f"""() => {{
      const mk = {MK};
      tasks.push(mk('A', 0, '2026-09-07', '2026-09-18', {{progress: 100}}));   // complete: fixed, A finishes 09-18 regardless of anything
      tasks.push(mk('B', 1, '2026-09-10', '2026-09-11'));   // stored BEFORE A's finish (as if the link was added after B was placed) — genuinely overdue by 09-15
      tasks[1].predecessors = [{{id: tasks[0].id, type: 'FS', lag: 0}}];
    }}""")
    touch("2026-09-15")   # earlier than what A actually requires (day after A's finish = 09-21)
    check("a dependent task is never pulled to the status date alone — its real predecessor's requirement (day after A, 09-21) wins when it is later", dates("B") == ["2026-09-21", "2026-09-22"], dates("B"))

    # ---------------------------------------------------------------- the dialog: hint, button state, applying, toast + Undo
    seed(f"""() => {{
      const mk = {MK};
      tasks.push(mk('X', 0, '2026-09-07', '2026-09-08'));
      tasks.push(mk('Done', 1, '2026-09-07', '2026-09-08', {{progress: 100}}));
    }}""")
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    check("the schedule menu has 'Reschedule remaining work…'", pg.locator("#planRescheduleItem").count() == 1)
    pg.click("#planRescheduleItem"); pg.wait_for_selector("#rescheduleModalBg.open")
    check("the date field defaults to today", pg.input_value("#rescheduleDateInput") == ev("() => todayStr()"))
    check("the hint counts the incomplete tasks (1 of 2 — Done doesn't count)", "1 task" in pg.inner_text("#rescheduleHint"), pg.inner_text("#rescheduleHint"))
    pg.fill("#rescheduleDateInput", "2026-09-21")
    before_x = dates("X")
    pg.click("#rescheduleBtn")
    pg.wait_for_timeout(150)
    check("the dialog closes and X moved", pg.locator("#rescheduleModalBg.open").count() == 0 and dates("X") != before_x, dates("X"))
    check("the toast names the count and the date", "Rescheduled 1 task" in pg.inner_text("#toastMsg") and "21.09.2026" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(150)
    check("Undo restores the exact original dates", dates("X") == before_x, dates("X"))

    # ---------------------------------------------------------------- nothing to do
    seed(f"() => {{ const mk = {MK}; tasks.push(mk('Done', 0, '2026-09-07', '2026-09-08', {{progress: 100}})); }}")
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open"); pg.click("#planRescheduleItem"); pg.wait_for_selector("#rescheduleModalBg.open")
    check("with everything finished, the hint says so and the button is disabled", "already finished" in pg.inner_text("#rescheduleHint") and pg.is_disabled("#rescheduleBtn"), pg.inner_text("#rescheduleHint"))
    pg.keyboard.press("Escape")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
