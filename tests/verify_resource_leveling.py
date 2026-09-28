# -*- coding: utf-8 -*-
"""Resource levelling, Stage 5 — the algorithm itself. `levelResources(opts)` walks the same eligible network
`criticalPathAnalysis()`/`rescheduleFromStatusDate()` already build (leaves, non-cyclic, non-manual, non-started,
non-complete) in topological order, delaying a resource-conflicted task to the next working-day span where every one of
its assigned resources has capacity — never earlier than its own dependencies allow, and (withinSlackOnly, the default)
never past its own existing slack, so the project's own finish never moves in that mode. It reuses `cascadeSchedule()`
to ripple each move, exactly as `rescheduleFromStatusDate()` reuses `topoOrder()` instead of a new mechanism. An
assignment that genuinely can't fit within its cap is left exactly where it is and reported (`unresolved`), never
silently dropped. `levelDryRun(opts)` is the same snapshot-run-restore idiom `rescheduleDryRun()` already uses. See
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
            "const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, "
            "startDate: sp.s, endDate: sp.e, progress: 0, milestone: !!sp.ms, color: null, "
            "predecessors: (sp.preds||[]).map(p => ({id: ids[p[0]], type: p[1]||'FS', lag: p[2]||0})), collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, "
            "taskMode: sp.mode || 'auto', resource: sp.r || '', actualStart: sp.as || null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } "
            "normalizeData(); save(); render(); }")
    seed = lambda specs: ev(SEED, specs)
    dates = lambda: ev("() => Object.fromEntries(tasks.map(t => [t.name, [t.startDate, t.endDate]]))")

    # ---------------------------------------------------------------- basic conflict resolved, without cap
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09", "r": "Anna"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"}])
    check("starts over-allocated", len(ev("() => overallocatedResources()")) == 1)
    res = ev("() => levelResources({withinSlackOnly: false})")
    ev("() => { normalizeData(); save(); render(); }")
    check("one task moved, none left unresolved", len(res["touched"]) == 1 and res["unresolved"] == [], res)
    check("the over-allocation is gone", ev("() => overallocatedResources()") == [])
    check("durations preserved (3 working days each)", all(ev(f"n => durationDays(tasks.find(t=>t.name===n).startDate, tasks.find(t=>t.name===n).endDate)", n) == 3 for n in ("A", "B")))

    # ---------------------------------------------------------------- within-slack: a task with slack moves, a critical one doesn't, the finish is unchanged
    seed([
        {"name": "LongBranch", "s": "2026-09-07", "e": "2026-09-16"},
        {"name": "C", "s": "2026-09-08", "e": "2026-09-09", "r": "Anna"},   # no successor -> plenty of slack
        {"name": "D", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"},
        {"name": "J", "s": "2026-09-17", "e": "2026-09-18", "preds": [["LongBranch", "FS"], ["C", "FS"]]},   # C feeds the project's own finish tightly
    ])
    j_before, c_before, d_before = dates()["J"], dates()["C"], dates()["D"]
    dry = ev("() => levelDryRun({withinSlackOnly: true})")
    check("dry run resolves the conflict by moving exactly one of the two slack-bearing tasks", len(dry["rows"]) == 1 and dry["rows"][0]["name"] in ("C", "D") and dry["unresolved"] == [], dry)
    check("dry run changes nothing on the live plan", dates()["D"] == d_before and dates()["C"] == c_before)
    res2 = ev("() => levelResources({withinSlackOnly: true})")
    ev("() => { normalizeData(); save(); render(); }")
    check("the real run matches the dry run's own row", res2["touched"] == [dry["rows"][0]["id"]], (res2, dry))
    check("the over-allocation is gone", ev("() => overallocatedResources()") == [])
    check("the project's own finish (J) never moved — the point of withinSlackOnly", dates()["J"] == j_before, (dates()["J"], j_before))

    # ---------------------------------------------------------------- fromIso scope: only tasks currently floored on/after that date are eligible
    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-09", "r": "Anna"}, {"name": "B", "s": "2026-09-08", "e": "2026-09-10", "r": "Anna"}])
    scoped_out = ev("() => levelResources({withinSlackOnly: false, fromIso: '2026-09-20'})")
    check("a scope that excludes both tasks' own floor leaves everything untouched, not even reported unresolved", scoped_out["touched"] == [] and scoped_out["unresolved"] == [], scoped_out)
    check("nothing moved", ev("() => overallocatedResources()").__len__() == 1)
    scoped_in = ev("() => levelResources({withinSlackOnly: false, fromIso: '2026-09-01'})")
    check("a scope that includes them resolves the conflict as usual", len(scoped_in["touched"]) == 1, scoped_in)

    # ---------------------------------------------------------------- genuinely no slack anywhere: reported, not silently dropped, nothing moved
    seed([
        {"name": "E", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna"},
        {"name": "F", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna"},
        {"name": "G", "s": "2026-09-09", "e": "2026-09-09", "preds": [["E", "FS"], ["F", "FS"]]},   # both feed G with zero float
    ])
    fl = dict(ev("() => [...criticalPathAnalysis().float.entries()].map(([id,f]) => [byId(id).name, f])"))
    check("both E and F genuinely have zero slack", fl.get("E") == 0 and fl.get("F") == 0, fl)
    e_f_before = dates()
    dry2 = ev("() => levelDryRun({withinSlackOnly: true})")
    check("both are reported unresolved, not dropped silently", {r["name"] for r in dry2["unresolved"]} == {"E", "F"} and dry2["rows"] == [], dry2)
    res3 = ev("() => levelResources({withinSlackOnly: true})")
    ev("() => { normalizeData(); save(); render(); }")
    check("nothing actually moved on the real run either", res3["touched"] == [] and dates()["E"] == e_f_before["E"] and dates()["F"] == e_f_before["F"])
    check("the same conflict resolves once the cap is lifted", (ev("() => levelResources({withinSlackOnly: false})"), ev("() => { normalizeData(); save(); render(); overallocatedResources(); }"), ev("() => overallocatedResources()"))[2] == [])

    # ---------------------------------------------------------------- a permanently infeasible assignment terminates (bounded search), reported unresolved
    seed([{"name": "H", "s": "2026-09-07", "e": "2026-09-08", "r": "Solo:150%"}])
    ev("() => { project.resources[0].maxUnits = 100; save(); }")   # 150% assigned, 100% max units — can never fit, alone or anywhere
    import time
    t0 = time.time()
    res4 = ev("() => levelResources({withinSlackOnly: false})")
    elapsed = time.time() - t0
    check("an impossible assignment is reported unresolved rather than looping forever", res4["unresolved"] == [ev("() => byId(tasks[0].id) && tasks[0].id")] or len(res4["unresolved"]) == 1, res4)
    check("it terminates quickly (bounded search, not a hang)", elapsed < 15, elapsed)
    check("nothing was moved for it", res4["touched"] == [])

    # ---------------------------------------------------------------- scope exclusions: milestones, manual/started/complete tasks, groups are left alone by the mover
    seed([
        {"name": "M1", "s": "2026-09-07", "e": "2026-09-07", "ms": True, "r": "Anna"},
        {"name": "Man", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna", "mode": "manual"},
        {"name": "Started", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna", "as": "2026-09-07"},
        {"name": "Grp", "s": "2026-09-07", "e": "2026-09-10", "r": "Anna"},
        {"name": "Kid", "s": "2026-09-07", "e": "2026-09-08", "parent": "Grp", "r": "Ben"},
    ])
    before5 = dates()
    res5 = ev("() => levelResources({withinSlackOnly: false})")
    ev("() => { normalizeData(); save(); render(); }")
    after5 = dates()
    check("a milestone is never itself moved by the mover", after5["M1"] == before5["M1"])
    check("a manual task is never moved", after5["Man"] == before5["Man"])
    check("a started task is never moved (its Start is a fact)", after5["Started"] == before5["Started"])
    grp_id = ev("() => tasks.find(t => t.name === 'Grp').id")
    check("a group is never itself levelled (it's a rollup, its own Resource text isn't an assignment)", grp_id not in res5["touched"] and grp_id not in res5["unresolved"])

    # ---------------------------------------------------------------- minute mode: a moved task keeps its own time of day, only the day changes
    ev("() => { project.timeUnit = 'minute'; project.workHours = { start: '08:00', end: '17:00', breaks: [{start:'12:00',end:'13:00'}] }; save(); }")
    seed([
        {"name": "MA", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna", "extra": {"startTime": "09:00", "endTime": "11:00"}},
        {"name": "MB", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna", "extra": {"startTime": "09:00", "endTime": "11:00"}},
    ])
    ev("() => { project.timeUnit = 'minute'; project.workHours = { start: '08:00', end: '17:00', breaks: [{start:'12:00',end:'13:00'}] }; normalizeData(); save(); render(); }")
    times_before = ev("() => Object.fromEntries(tasks.map(t => [t.name, [t.startTime, t.endTime]]))")
    ev("() => levelResources({withinSlackOnly: false})")
    ev("() => { normalizeData(); save(); render(); }")
    times_after = ev("() => Object.fromEntries(tasks.map(t => [t.name, [t.startTime, t.endTime]]))")
    check("time-of-day is preserved by levelling — only the day moves (resource load is whole-day granularity)", times_before == times_after, (times_before, times_after))
    ev("() => { project.timeUnit = 'day'; delete project.workHours; save(); }")

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
