# -*- coding: utf-8 -*-
"""Version skew: two builds of the app on one plan (a stale cached copy on one device, a linked file synced between an updated and
a not-yet-updated device). Every save stamps the plan with APP_VERSION. (1) A plan a NEWER build wrote says so (it may hold what
this build would drop). (2) A minute-mode plan last written by a build OLDER than the first minute-mode one (MINUTE_MODE_VERSION)
was scheduled by a day-only engine that moves startDate/endDate without knowing the time-of-day siblings: on load, and on a merge
from the file, the tasks it can have left inconsistent (a finish before the start, an Auto task off its links) are realigned and
the plan says so. A plan written by a build that knows minute mode, and every day-mode plan, is left completely alone."""
import os, re
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
SEED = re.search(r'SEED = """(.*?)"""', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_clone.py')).read(), re.S).group(1)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    toast = lambda: ev("() => { const e = document.getElementById('toastMsg'); return e ? e.textContent : ''; }")
    f = lambda n: ev("n => { const t = tasks.find(x => x.name === n); return [t.startDate, t.startTime, t.endDate, t.endTime]; }", n)
    app_version = ev("() => APP_VERSION")

    check("this build is version 3 and every save carries it", app_version == 3 and ev("() => syncPayload().version") == 3 and '"version": 3' in ev("() => canonicalText()"))
    check("a minute-mode plan first came with version 2 (MINUTE_MODE_VERSION)", ev("() => MINUTE_MODE_VERSION") == 2)

    def plant(version, minute=True):
        """A plan as an OLDER build would have left it after a day-only cascade: B (Auto, FS after A) sits before A's finish moment, and C's finish is before its start."""
        ev("m => { project.timeUnit = m ? 'minute' : undefined; if (!m) delete project.timeUnit; }", minute)
        ev(SEED, [{"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "11:30"}},
                  {"name": "B", "s": "2026-09-07", "e": "2026-09-07", "preds": [["A", "FS", 0]], "extra": {"startTime": "09:00", "endTime": "10:00"}},
                  {"name": "C", "s": "2026-09-08", "e": "2026-09-08", "extra": {"startTime": "14:00", "endTime": "10:00"}}])
        ev("() => { normalizeData(); save(); }")
        ev("""(v) => { const k = planDataKey(currentPlanId), raw = JSON.parse(localStorage.getItem(k));
            const B = raw.tasks.find(t => t.name === 'B'), C = raw.tasks.find(t => t.name === 'C');
            B.startTime = '09:00'; B.endTime = '10:00'; C.startTime = '14:00'; C.endTime = '10:00';
            if (v === null) delete raw.version; else raw.version = v;
            localStorage.setItem(k, JSON.stringify(raw)); }""", version)
        pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(700)
    stored = lambda: ev("() => JSON.parse(localStorage.getItem(planDataKey(currentPlanId))).version")

    # ---------------------------------------------------------------- an older build wrote a minute-mode plan
    plant(1)
    check("(setup) the plant is what an older build could leave: B before A's finish, C finishing before it starts — and the app has repaired both",
          f("B")[1] == "11:30", f("B"))
    check("B, an Auto task, was put back where its FS link says — A's finish, 11:30 — keeping its 1h of working time (30 min before lunch, 30 after: 13:30)", f("B") == ["2026-09-07", "11:30", "2026-09-07", "13:30"], f("B"))
    c = f("C")
    check("C's finish is no longer before its start", c[2] > c[0] or (c[2] == c[0] and c[3] >= c[1]), c)
    check("the plan says so: a toast naming the older build and the count", "older Milestone" in toast() and "realigned" in toast(), toast())
    check("the repaired plan is stored (now under this build's version), so it is repaired once, not on every open", stored() == app_version, stored())
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(700)
    check("...and opening it again says nothing and moves nothing", f("B")[1] == "11:30" and "older Milestone" not in toast(), (f("B"), toast()))

    # a file with no version at all is an older build's, too
    plant(None)
    check("a plan with no version stamp at all counts as older: repaired too", f("B")[1] == "11:30", f("B"))

    # ---------------------------------------------------------------- left alone
    plant(2)
    check("a plan written by a build that knows minute mode (version 2) is left exactly as it is", f("B") == ["2026-09-07", "09:00", "2026-09-07", "10:00"] and "older Milestone" not in toast(), (f("B"), toast()))
    plant(1, minute=False)
    check("a day-mode plan is never touched, whatever the version (a day-only build schedules it correctly)", "older Milestone" not in toast() and ev("() => tasks.find(t => t.name === 'B').startTime") is None, toast())

    # ---------------------------------------------------------------- a NEWER build wrote it
    plant(99)
    check("a plan a newer build wrote (version 99) says so and names both versions", "newer Milestone" in toast() and "99" in toast() and str(app_version) in toast(), toast())
    check("...and is not changed (the inconsistent B stays where the file had it)", f("B")[1] == "09:00", f("B"))

    # ---------------------------------------------------------------- the file merge path
    ev("() => { project.timeUnit = 'minute'; }")
    ev(SEED, [{"name": "A", "s": "2026-09-07", "e": "2026-09-07", "extra": {"startTime": "09:00", "endTime": "11:30"}}])
    ev("() => { normalizeData(); save(); }")
    old_remote = """(v) => { const d = JSON.parse(JSON.stringify(syncPayload())); d.version = v;
        d.tasks.push({ id: 'remoteC', name: 'RemoteC', parentId: null, order: 5, startDate: '2026-09-08', endDate: '2026-09-08', startTime: '14:00', endTime: '10:00',
          progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now() + 5000, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
        return d; }"""
    res = ev("v => { const d = (" + old_remote + ")(v); return mergeFromFile(d, 'poll'); }", 1)
    rc = f("RemoteC")
    check("a merge of a minute-mode file an older build wrote realigns what it brought in (RemoteC no longer finishes before it starts)", res["changed"] and (rc[2] > rc[0] or (rc[2] == rc[0] and rc[3] >= rc[1])), (res, rc))
    ev("() => { const t = tasks.find(x => x.name === 'RemoteC'); if (t) { t.startTime = '14:00'; t.endTime = '10:00'; } }")
    ev("v => { const d = (" + old_remote.replace("remoteC", "remoteD").replace("RemoteC", "RemoteD") + ")(v); mergeFromFile(d, 'poll'); }", app_version)
    rd = f("RemoteD")
    check("the same file stamped by a current build is merged as it is (RemoteD keeps its odd 14:00–10:00: not this guard's business)", rd[1] == "14:00" and rd[3] == "10:00", rd)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
