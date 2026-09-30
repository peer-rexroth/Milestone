# -*- coding: utf-8 -*-
"""Resource levelling, Stage 1 — the data model. task.resource stays exactly the free-text field it always was (unchanged
shape, unchanged consumers); its syntax grows an optional "Name[NN%]" allocation (MS Project's form; the older "Name:NN%" is still read), mirroring exactly how elapsed lags added
an 'e' suffix to Predecessors. project.resources (the pool) is populated automatically from whatever names appear in that
text, inside normalizeData() — the same way MS Project auto-adds a typed name to its resource list. No new task field:
assignments are resolved on demand (taskAssignments()) by matching a task's text against the pool, not a stored id.
See "Resource levelling" in CLAUDE.md."""
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

    # ---------------------------------------------------------------- parseResourceAssignments / formatResourceString
    check("'Anna[50%], Ben' (MS Project's form) -> [{Anna,50},{Ben,100}] (a bare name is 100%)", ev("() => parseResourceAssignments('Anna[50%], Ben')") == [{"name": "Anna", "units": 50}, {"name": "Ben", "units": 100}])
    check("the older 'Anna:50%' form and a loosely typed 'Anna [ 50 ]' read the same", ev("() => [parseResourceAssignments('Anna:50%, Ben'), parseResourceAssignments('Anna [ 50 ], Ben')]") == [[{"name": "Anna", "units": 50}, {"name": "Ben", "units": 100}]] * 2)
    check("canonicalResourceText() rewrites only the % notation into Name[NN%] (100% bare), keeping separators and anything unparseable",
          ev("() => [canonicalResourceText('Anna:50%; Ben[100%], Carl [ 25 ]'), canonicalResourceText('Anna[abc], Ben')]") == ["Anna[50%]; Ben, Carl[25%]", "Anna[abc], Ben"])
    check("a semicolon separates too, and extra spaces are trimmed", ev("() => parseResourceAssignments(' Anna ; Ben:75 % ')") == [{"name": "Anna", "units": 100}, {"name": "Ben", "units": 75}])
    check("a percentage outside 1-800 falls back to 100, not refused (never a strict field)", ev("() => parseResourceAssignments('Anna:0%, Ben:9000%')") == [{"name": "Anna", "units": 100}, {"name": "Ben", "units": 100}])
    check("a duplicate name (case-insensitive) in one string counts once", ev("() => parseResourceAssignments('Anna, anna:50%')") == [{"name": "Anna", "units": 100}])
    check("empty / blank text has no assignments", ev("() => parseResourceAssignments('')") == [] and ev("() => parseResourceAssignments('   ')") == [])
    check("formatResourceString is the inverse (100% is written bare)", ev("() => formatResourceString([{name:'Anna',units:50},{name:'Ben',units:100}])") == "Anna[50%], Ben")

    # ---------------------------------------------------------------- normalizeData(): the pool auto-populates from task text
    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }"
    seed = lambda specs: ev(SEED, specs)

    seed([{"name": "A", "s": "2026-09-07", "e": "2026-09-08", "r": "Anna:50%, Ben"}, {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "r": "anna, Carl:200%"}])
    pool = ev("() => project.resources")
    names = sorted(r["name"] for r in pool)
    check("three distinct people across two tasks -> three pool entries, deduplicated case-insensitively ('anna' == 'Anna')", names == ["Anna", "Ben", "Carl"], pool)
    check("...each with the default 100% max units (nothing here overrides it)", all(r["maxUnits"] == 100 for r in pool), pool)
    aid = next(r["id"] for r in pool if r["name"] == "Anna")
    ta_a = ev("() => taskAssignments(tasks.find(t => t.name === 'A'))")
    ta_b = ev("() => taskAssignments(tasks.find(t => t.name === 'B'))")
    check("taskAssignments(A) resolves to the pool entries with their own units", [(a["resource"]["name"], a["units"]) for a in ta_a] == [("Anna", 50), ("Ben", 100)], ta_a)
    check("taskAssignments(B)'s 'anna' resolves to the SAME pool entry id as A's 'Anna' — not a second one", ta_b[0]["resource"]["id"] == aid and ta_b[1]["units"] == 200, (ta_b, aid))

    # ---------------------------------------------------------------- a group's (and a spacer's) resource text never enters the pool
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-08", "r": "GroupPerson"}, {"name": "K", "s": "2026-09-07", "e": "2026-09-08", "parent": "G", "r": "Kid"}])
    check("a group's own Resource text is free-form notes (matches MSPDI export's own precedent), not an assignment — only the child's name enters the pool", [r["name"] for r in ev("() => project.resources")] == ["Kid"], ev("() => project.resources"))
    seed([{"name": "S", "s": "2026-09-07", "e": "2026-09-08", "r": "SpacerName", "extra": {"spacer": True}}])
    check("a spacer's resource is force-cleared before the pool ever sees it", ev("() => 'resources' in project") == False)

    # ---------------------------------------------------------------- normalizeData() sanitizes an existing pool
    r = ev("""() => { project.resources = [{id: genId(), name: '  Weird  ', maxUnits: 9999, daysOff: [{date:'2026-12-24'}, {date:'not-a-date'}]}];
      tasks.length = 0; normalizeData(); return project.resources; }""")
    check("a name is trimmed, max units clamped to 800, and daysOff cleaned the same way project.holidays already is (the bad entry dropped, the real one kept)",
          r == [{"id": r[0]["id"], "name": "Weird", "maxUnits": 800, "daysOff": [{"date": "2026-12-24"}]}], r)
    r2 = ev("() => { project.resources = [{id: genId(), name: 'X', maxUnits: 0}]; tasks.length = 0; normalizeData(); return project.resources[0].maxUnits; }")
    check("max units is also clamped up from below 1", r2 == 1, r2)
    r3 = ev("() => { delete project.resources; tasks.length = 0; normalizeData(); return 'resources' in project; }")
    check("an empty pool stays absent (the usual convention), not an empty array", r3 == False)
    r4 = ev("""() => { project.resources = [{id: genId(), name: 'Dup'}, {id: genId(), name: 'dup'}]; tasks.length = 0; normalizeData(); return project.resources.length; }""")
    check("a case-insensitive name collision in a corrupted/hand-edited pool is de-duplicated defensively (the dialog itself is the real uniqueness gate)", r4 == 1, r4)
    r5 = ev("() => { project.resources = [{id: 'not a safe id!', name: 'X'}]; tasks.length = 0; normalizeData(); return 'resources' in project; }")
    check("an entry with a malformed id is dropped outright, not kept with a bad id", r5 == False, r5)

    conv = ev("""() => { tasks.length = 0; const mk = (id, name, parentId, resource) => ({ id, name, parentId, order: tasks.length, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource, actualStart: null, actualFinish: null });
      tasks.push(mk('g', 'G', null, 'Notes: 2 people'), mk('k', 'K', 'g', 'Anna:50%, Ben:100%')); normalizeData(); return [tasks[0].resource, tasks[1].resource]; }""")
    check("an older plan's 'Anna:50%, Ben:100%' becomes 'Anna[50%], Ben' on load; a group's own notes text is left exactly as typed", conv == ["Notes: 2 people", "Anna[50%], Ben"], conv)
    check("normalizeData() is idempotent on it", ev("() => { const before = tasks[1].resource; normalizeData(); return tasks[1].resource === before; }"))
    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
