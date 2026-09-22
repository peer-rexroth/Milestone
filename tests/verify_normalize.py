# -*- coding: utf-8 -*-
"""normalizeData on thousands of random plans (nested groups, manual and auto, TBD dates, days off, actual dates, milestones):
idempotent, independent of the order the tasks are stored in (two devices must write the same bytes), and a merge with itself changes nothing."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:700]}]" if not cond and detail else ""))

FUZZ = """([seed, N]) => {
  let a = seed >>> 0; const rnd = () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const ri = n => Math.floor(rnd() * n), pick = arr => arr[ri(arr.length)], date = () => addDays('2026-10-26', ri(30)), out = { idem: [], order: [], merge: [] };
  const diffOf = (x, y) => { const A = JSON.parse(x), B = JSON.parse(y), am = new Map(A.tasks.map(t => [t.id, t])), d = []; for (const t of B.tasks) { const o = am.get(t.id); if (!o) { d.push('new ' + t.name); continue; } for (const k of new Set([...Object.keys(t), ...Object.keys(o)])) if (JSON.stringify(t[k]) !== JSON.stringify(o[k])) d.push(t.name + '.' + k + ': ' + JSON.stringify(o[k]) + ' -> ' + JSON.stringify(t[k])); } return d.slice(0, 4); };
  for (let it = 0; it < N; it++) {
    delete project.workDays; delete project.holidays;
    if (rnd() < .3) project.workDays = pick([[1, 2, 3, 4, 5, 6], [0, 1, 2, 3, 4, 5, 6], [2, 3, 4]]);
    if (rnd() < .3) project.holidays = [{ date: date() }, { date: date(), to: date() }];
    const n = 3 + ri(10), list = [];
    for (let i = 0; i < n; i++) {
      const s = date(), e = addDays(s, ri(8)), manual = rnd() < .3;
      const t = { id: 't' + i, name: 'T' + i, parentId: i && rnd() < .6 ? 't' + ri(i) : null, order: ri(4), startDate: s, endDate: e, progress: ri(101), milestone: rnd() < .15, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: manual ? 'manual' : 'auto', resource: '', actualStart: rnd() < .2 ? date() : null, actualFinish: rnd() < .15 ? date() : null };
      if (manual && rnd() < .5) { t.startText = 'TBD'; if (rnd() < .5) t.endText = 'TBD'; } if (manual && rnd() < .2) t.durText = '5?';
      if (i && rnd() < .3) t.predecessors = [{ id: 't' + ri(i), type: pick(['FS', 'SS', 'FF', 'SF']), lag: ri(4) - 1 }];
      list.push(t);
    }
    const shuffled = () => { const l = JSON.parse(JSON.stringify(list)); for (let i = l.length - 1; i > 0; i--) { const j = ri(i + 1); [l[i], l[j]] = [l[j], l[i]]; } return l; };
    const run = l => { tasks.length = 0; deletedTaskIds.length = 0; tasks.push(...l); normalizeData(); const a1 = canonicalText(); normalizeData(); return [a1, canonicalText()]; };
    const [a1, a2] = run(shuffled());
    if (a1 !== a2 && out.idem.length < 3) out.idem.push({ it, d: diffOf(a1, a2) });
    const [b1] = run(shuffled());
    if (a1 !== b1 && out.order.length < 3) out.order.push({ it, d: diffOf(a1, b1) });
    tasks.length = 0; tasks.push(...JSON.parse(a1).tasks); const before = canonicalText(); const base = JSON.parse(before);
    mergeData(JSON.parse(before), { respectTombstones: true, base, conflicts: [], changedIds: new Map() });
    if (canonicalText() !== before && out.merge.length < 3) out.merge.push({ it, d: diffOf(before, canonicalText()) });
  }
  return out;
}"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    for seed in (12345, 777, 2026):
        r = pg.evaluate(FUZZ, [seed, 3000])
        check(f"seed {seed}: 3,000 random plans — normalising twice changes nothing", not r["idem"], r["idem"])
        check(f"seed {seed}: ...the result does not depend on the order the tasks are stored in (two devices write the same bytes)", not r["order"], r["order"])
        check(f"seed {seed}: ...and merging a plan with itself changes nothing", not r["merge"], r["merge"])
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
