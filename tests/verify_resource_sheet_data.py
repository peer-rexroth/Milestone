# -*- coding: utf-8 -*-
"""Resource Sheet, Stage 1 — the data model. project.resources[] grows nine new MS-Project fields (type, materialLabel,
initials, group, stdRate, ovtRate, costPerUse, accrueAt, code), each the usual absence-is-default convention, cleaned
in normalizeData()'s existing resource-pool block right next to how maxUnits is already clamped. project.currencyCode
(absent = 'EUR') and fmtCurrency() round out the data model this stage builds on. See "Resource Sheet" in CLAUDE.md."""
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

    # ---------------------------------------------------------------- RESOURCE_TYPES / ACCRUE_TYPES / CURRENCIES
    check("RESOURCE_TYPES has exactly work/material/cost, in that order (matches the real MSPDI Type enum 1/0/2 mapping used at export time)",
          ev("() => RESOURCE_TYPES.map(t => t.id)") == ["work", "material", "cost"])
    check("ACCRUE_TYPES has exactly start/prorated/end, in that order (matches the real MSPDI AccrueAt enum 1/2/3)",
          ev("() => ACCRUE_TYPES.map(t => t.id)") == ["start", "prorated", "end"])
    check("accrueTypeInfo() with nothing recognized falls back to Prorated (MS Project's own default)", ev("() => accrueTypeInfo(undefined).id") == "prorated")
    check("resourceTypeInfo() with nothing recognized falls back to Work", ev("() => resourceTypeInfo(undefined).id") == "work")
    check("CURRENCIES includes the common majors", set(ev("() => CURRENCIES.map(c => c.code)")) >= {"USD", "EUR", "GBP", "JPY"})

    # ---------------------------------------------------------------- fmtCurrency() / currencyCode()
    check("currencyCode() defaults to EUR when unset", ev("() => { delete project.currencyCode; return currencyCode(); }") == "EUR")
    eur0 = ev("() => { delete project.currencyCode; return fmtCurrency(1234.5); }")
    check("fmtCurrency(1234.5) in EUR reads like real money (a euro sign, 1,234.50)", ("€" in eur0 or "EUR" in eur0) and "1,234.50" in eur0, eur0)
    check("fmtCurrency(0) and a non-finite input both read as zero, never NaN/undefined text", all(("0.00" in ev(f"() => fmtCurrency({v})")) for v in ["0", "NaN", "undefined"]))
    usd = ev("() => { project.currencyCode = 'USD'; return fmtCurrency(50); }")
    check("switching project.currencyCode changes the formatted output (a real dollar sign appears)", "$" in usd, usd)

    # ---------------------------------------------------------------- normalizeData(): the new resource fields are cleaned/defaulted
    SEED = "specs => { tasks.length = 0; deletedTaskIds.length = 0; selectedTaskId = null; delete project.resources; delete project.currencyCode; const ids = {}; for (const sp of specs) { const t = Object.assign({id: genId(), name: sp.name, parentId: sp.parent ? ids[sp.parent] : null, order: tasks.length, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: sp.r || '', actualStart: null, actualFinish: null}, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; } normalizeData(); save(); render(); }"
    seed = lambda specs: ev(SEED, specs)

    r = ev("""() => { project.resources = [{id: genId(), name: 'Anna', maxUnits: 100, type: 'material', materialLabel: '  tons  ', initials: '  AB  ', group: '  Eng  ', code: '  R-1  ', stdRate: 12.5, ovtRate: 18, costPerUse: 5, accrueAt: 'start'}];
      tasks.length = 0; normalizeData(); return project.resources[0]; }""")
    check("a full set of new fields survives cleaning: type/accrueAt kept (non-default), strings trimmed, rates kept",
          r["type"] == "material" and r["accrueAt"] == "start" and r["materialLabel"] == "tons" and r["initials"] == "AB" and r["group"] == "Eng" and r["code"] == "R-1" and r["stdRate"] == 12.5 and r["costPerUse"] == 5, r)
    check("...except the Ovt Rate, which a Material resource doesn't have (resourceFieldApplies) — dropped, never left hidden", "ovtRate" not in r, r)

    r2 = ev("""() => { project.resources = [{id: genId(), name: 'Ben', maxUnits: 100}];
      tasks.length = 0; normalizeData(); return project.resources[0]; }""")
    check("with nothing set, every new field is absent (the usual convention) — type reads as Work and accrueAt as Prorated only via the *Info() fallbacks, never stored",
          "type" not in r2 and "accrueAt" not in r2 and "materialLabel" not in r2 and "initials" not in r2 and "group" not in r2 and "code" not in r2 and "stdRate" not in r2 and "ovtRate" not in r2 and "costPerUse" not in r2, r2)

    r3 = ev("""() => { project.resources = [{id: genId(), name: 'Cost1', type: 'cost', accrueAt: 'end', stdRate: -5, ovtRate: 'abc', costPerUse: 1e20}];
      tasks.length = 0; normalizeData(); return project.resources[0]; }""")
    check("garbage/negative rates are dropped (absent) rather than stored as-is; an unreasonably huge costPerUse is still just a finite positive number (kept, not clamped here — display-side formatting handles scale)",
          r3["type"] == "cost" and r3["accrueAt"] == "end" and "stdRate" not in r3 and "ovtRate" not in r3 and r3["costPerUse"] == 1e20, r3)

    r4 = ev("""() => { project.resources = [{id: genId(), name: 'Weird', type: 'not-a-type', accrueAt: 'nonsense'}];
      tasks.length = 0; normalizeData(); return project.resources[0]; }""")
    check("an unrecognized type/accrueAt value is dropped (falls back to the default), not stored verbatim", "type" not in r4 and "accrueAt" not in r4, r4)

    r5 = ev("""() => { project.resources = [{id: genId(), name: 'Long', type: 'material', materialLabel: 'x'.repeat(99), group: 'y'.repeat(99), code: 'z'.repeat(99)}];
      tasks.length = 0; normalizeData(); return project.resources[0]; }""")
    check("free-text fields are length-capped (materialLabel/initials shorter, group/code longer)", len(r5["materialLabel"]) == 20 and len(r5["group"]) == 60 and len(r5["code"]) == 40, {"ml": len(r5["materialLabel"]), "g": len(r5["group"]), "c": len(r5["code"])})

    r6 = ev("() => { project.currencyCode = 'USD'; tasks.length = 0; normalizeData(); return project.currencyCode; }")
    check("a real, non-default currency code is kept", r6 == "USD")
    r7 = ev("() => { project.currencyCode = 'EUR'; tasks.length = 0; normalizeData(); return 'currencyCode' in project; }")
    check("EUR (the default) is never stored, same convention as everything else", r7 == False)
    r8 = ev("() => { project.currencyCode = 'not-a-code'; tasks.length = 0; normalizeData(); return 'currencyCode' in project; }")
    check("a garbage currency code is dropped, falling back to the EUR default", r8 == False)

    # ---------------------------------------------------------------- cost engine: assignmentHours / assignmentCost / taskCost
    ev("() => { project.workDays = [1,2,3,4,5]; }")   # a plain Mon-Fri calendar, so "2 days" below is exactly 2 working days
    seed([{"name": "G", "s": "2026-09-07", "e": "2026-09-08"}, {"name": "A", "s": "2026-09-07", "e": "2026-09-08", "parent": "G", "r": "Anna"},
          {"name": "B", "s": "2026-09-07", "e": "2026-09-08", "parent": "G", "r": "Anna, Ben"}])
    ev("() => { project.resources.find(r => r.name === 'Anna').stdRate = 50; project.resources.find(r => r.name === 'Ben').stdRate = 50; save(); render(); }")
    costA = ev("() => taskCost(tasks.find(t => t.name === 'A'))")
    check("a Work resource at $50/hr on a 2-working-day (16h) task, 100% assigned, costs $800 (16h x $50)", costA == 800, costA)
    costB = ev("() => taskCost(tasks.find(t => t.name === 'B'))")
    check("two Work resources at 100% each split the task's total 32h work by their own share (16h each) and both bill at $50/hr -> $1600 total", costB == 1600, costB)
    costG = ev("() => taskCost(tasks.find(t => t.name === 'G'))")
    check("a group's cost is the recursive rollup of its children's cost ($800 + $1600 = $2400)", costG == 2400, costG)

    seed([{"name": "M", "s": "2026-09-07", "e": "2026-09-08", "r": "Concrete:50%", "extra": {"milestone": True}}])
    ev("() => { project.resources.find(r => r.name === 'Concrete').type = 'material'; project.resources.find(r => r.name === 'Concrete').stdRate = 10; project.resources.find(r => r.name === 'Concrete').costPerUse = 20; save(); render(); }")
    costM = ev("() => taskCost(tasks.find(t => t.name === 'M'))")
    check("a Material resource at 50% assigned ($10/unit x 0.5 + $20 Cost/Use) costs $25 — its own assigned % stands in for quantity consumed, independent of the milestone's zero duration", costM == 25, costM)

    seed([{"name": "P", "s": "2026-09-07", "e": "2026-09-11", "r": "Permit:1%"}])
    ev("() => { project.resources.find(r => r.name === 'Permit').type = 'cost'; project.resources.find(r => r.name === 'Permit').costPerUse = 200; project.resources.find(r => r.name === 'Permit').stdRate = 999; save(); render(); }")
    costP = ev("() => taskCost(tasks.find(t => t.name === 'P'))")
    check("a Cost resource is a flat Cost/Use ($200) regardless of its own assigned % and ignores any Std Rate entirely", costP == 200, costP)

    seed([{"name": "U", "s": "2026-09-07", "e": "2026-09-08"}])
    costU = ev("() => taskCost(tasks.find(t => t.name === 'U'))")
    check("an unassigned task costs nothing", costU == 0)
    check("an empty line always costs 0", ev("() => taskCost({spacer: true})") == 0)
    check("taskCost(null/undefined) doesn't throw", ev("() => { try { return [taskCost(null), taskCost(undefined)]; } catch(e) { return 'threw: ' + e; } }") == [0, 0])

    # ---------------------------------------------------------------- memoization: _costCache is cleared by resetEffectiveCache() (which normalizeData()/save() already call)
    seed([{"name": "C1", "s": "2026-09-07", "e": "2026-09-08", "r": "Cara"}])
    ev("() => { project.resources.find(r => r.name === 'Cara').stdRate = 10; save(); render(); }")
    before = ev("() => taskCost(tasks.find(t => t.name === 'C1'))")
    ev("() => { project.resources.find(r => r.name === 'Cara').stdRate = 100; }")   # bypass save() on purpose — a raw, un-reset mutation
    stale = ev("() => taskCost(tasks.find(t => t.name === 'C1'))")
    check("a raw rate edit that skips save()/resetEffectiveCache() reads back the CACHED (stale) cost — proves it's really memoized, not recomputed every call", stale == before, (before, stale))
    ev("() => resetEffectiveCache()")
    fresh = ev("() => taskCost(tasks.find(t => t.name === 'C1'))")
    check("...and resetEffectiveCache() (already called by every real save()) clears it, so the next read reflects the new rate", fresh == before * 10, (before, fresh))

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
