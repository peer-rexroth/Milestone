import io, base64, json, sys
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:1500]}]" if not cond and detail else ""))
STRESS_JS = r"""
async ([seed, steps, allowCalendar]) => {
  let calChanged = false; const everStarted = new Set(), knownIds = new Set();   // a task whose actual dates were cleared is a normal Auto task again but stays where it was (documented: it is pushed the next time a predecessor changes)
  let a = seed >>> 0;
  const rnd = () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const ri = (n) => Math.floor(rnd() * n), pick = (arr) => arr[ri(arr.length)];
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  const randDate = () => addDays('2026-09-01', ri(120));
  const leaf = () => tasks.filter(t => !hasChildren(t.id));
  const anyTask = () => tasks.length ? pick(tasks) : null;
  const many = () => { const out = []; for (let i = 1 + ri(3); i > 0 && tasks.length; i--) { const x = pick(tasks).id; if (!out.includes(x)) out.push(x); } return out; };
  const inv = () => {
    const bad = [], ids = new Set();
    for (const t of tasks) {
      if (ids.has(t.id)) bad.push('duplicate id ' + t.id); ids.add(t.id);
      if (!ISO.test(t.startDate) || !ISO.test(t.endDate)) { bad.push('bad date on ' + t.name + ' ' + t.startDate + ' ' + t.endDate); continue; }
      if (dayNumber(t.endDate) < dayNumber(t.startDate)) bad.push('end before start: ' + t.name);
      if (t.milestone && t.startDate !== t.endDate) bad.push('milestone with two dates: ' + t.name);
      if (!Number.isInteger(t.progress) || t.progress < 0 || t.progress > 100) bad.push('progress ' + t.progress + ' on ' + t.name);
      if (t.parentId && !tasks.some(x => x.id === t.parentId)) bad.push('dangling parent on ' + t.name);
      if (t.actualStart && t.actualFinish && dayNumber(t.actualFinish) < dayNumber(t.actualStart)) bad.push('actual finish before start: ' + t.name);
      if (t.baselines) { if (hasChildren(t.id)) bad.push('baseline on a group ' + t.name); for (const [slot, b] of Object.entries(t.baselines)) if (!(slot >= 0 && slot < BASELINE_SLOTS) || !ISO.test(b[0]) || !ISO.test(b[1]) || b[1] < b[0]) bad.push('bad baseline ' + slot + ' on ' + t.name); }
    }
    for (const t of tasks) {   // parent chains end (no cycles)
      let n = 0, cur = t; while (cur && cur.parentId && n++ < 500) cur = tasks.find(x => x.id === cur.parentId);
      if (n >= 500) bad.push('parent cycle at ' + t.name);
    }
    for (const t of tasks) for (const p of t.predecessors) {
      const q = tasks.find(x => x.id === p.id);
      if (!q) bad.push('dangling predecessor on ' + t.name); else if (q.id === t.id) bad.push('self dependency on ' + t.name); else if (hasChildren(q.id)) bad.push('a group is a predecessor of ' + t.name);
    }
    for (const t of tasks) if (hasChildren(t.id) && t.predecessors.length) bad.push('a group has predecessors: ' + t.name);
    const cyc = taskCycleSet();
    for (const t of tasks) if (isStarted(t)) everStarted.add(t.id);
    if (!calChanged) for (const t of tasks) {   // an Auto task that has not started sits where its links allow (the cascade's promise) — until the calendar is changed (that never moves dates, by design)
      if (t.taskMode === 'manual' || hasChildren(t.id) || cyc.has(t.id) || isStarted(t) || isUnscheduled(t)) continue;
      const cs = constraintStart(t);
      if (cs && !everStarted.has(t.id) && dayNumber(cs) !== dayNumber(t.startDate)) bad.push('Auto task is not where its links put it: ' + t.name + ' ' + t.startDate + ' < ' + cs);
      if (!isWorkDay(t.startDate) || (!t.milestone && !isWorkDay(t.endDate))) bad.push('Auto task on a day off: ' + t.name + ' ' + t.startDate + '..' + t.endDate);
    }
    const dispIds = tasks.map(t => taskDisplayId(t.id)); if (new Set(dispIds).size !== dispIds.length) bad.push('display ids not unique');
    return bad;
  };
  const cycle = (t) => { editingCell = { id: t.id, field: 'x' }; };
  const edit = (t, field, value) => { editingCell = { id: t.id, field }; commitInlineEdit(t.id, field, value); };
  const OPS = [
    ['add', 10, () => { const s = anyTask(); selectedTaskId = s ? s.id : null; addTask(); closeTaskModal(); const n = tasks.find(x => x.id === selectedTaskId); if (n) { n.name = 'T' + ri(1e6); if (rnd() < .5) { const d = randDate(); n.startDate = isWorkDay(d) ? d : nextWorkDay(d); n.endDate = shiftWork(n.startDate, ri(6)); } save(); render(); } }],
    ['delete', 5, () => { const t = anyTask(); if (!t || tasks.length < 3) return; deleteTaskFlow(t.id); confirmModalAction(); }],
    ['indent', 6, () => { const t = anyTask(); if (!t) return; selectedTaskId = t.id; indentSelected(); }],
    ['outdent', 5, () => { const t = anyTask(); if (!t) return; selectedTaskId = t.id; outdentSelected(); }],
    ['move', 6, () => { const t = anyTask(), o = anyTask(); if (!t || !o) return; moveTask(t.id, o.id, pick(['before', 'after', 'into', 'end'])); }],
    ['start', 8, () => { const t = anyTask(); if (t) edit(t, 'start', randDate()); }],
    ['finish', 6, () => { const t = anyTask(); if (t) edit(t, 'finish', randDate()); }],
    ['duration', 6, () => { const t = anyTask(); if (t) edit(t, 'duration', String(1 + ri(25))); }],
    ['preds', 9, () => { const t = anyTask(); if (!t) return; const n = ri(4), toks = []; for (let i = 0; i < n; i++) { const o = anyTask(); if (o) toks.push(taskDisplayId(o.id) + pick(['FS', 'SS', 'FF', 'SF', '']) + (rnd() < .4 ? (ri(9) - 3 >= 0 ? '+' : '') + (ri(9) - 3) : '')); } edit(t, 'predecessors', toks.join(', ')); }],
    ['mode', 4, () => { const t = anyTask(); if (t) setTaskMode(t.id, pick(['auto', 'manual'])); }],
    ['drag', 4, () => { const t = pick(leaf()); if (!t || t.taskMode === 'manual' && rnd() < .5) return; const mode = pick(['move', 'resize-left', 'resize-right']); let ns = t.startDate, ne = t.endDate; const d = ri(40) - 15;
      if (mode === 'move') { ns = addDays(t.startDate, d); ne = addDays(t.endDate, d); } else if (mode === 'resize-left') { ns = addDays(t.startDate, d); if (dayNumber(ns) > dayNumber(ne)) ns = ne; } else { ne = addDays(t.endDate, d); if (dayNumber(ne) < dayNumber(ns)) ne = ns; }
      if (t.taskMode !== 'manual') { if (mode === 'move') { ns = nextWorkDay(ns); ne = t.milestone ? ns : finishFor(ns, durationDays(t.startDate, t.endDate)); } else if (mode === 'resize-right') { ne = prevWorkDay(ne); if (dayNumber(ne) < dayNumber(ns)) ne = ns; } else { ns = nextWorkDay(ns); if (dayNumber(ns) > dayNumber(ne)) ns = ne; } }
      dragState = { taskId: t.id, moved: true, previewStart: ns, previewEnd: ne, mode }; onDragMouseUp(); }],
    ['multiClone', 2, () => { const ids = many(); if (ids.length && tasks.length < 50) { setSelection(ids); cloneSelected(); } }],
    ['multiDelete', 2, () => { const ids = many(); if (ids.length && tasks.length > 4) deleteTasksNow([...new Set(ids.flatMap(id => [id, ...descendantIds(id)]))]); }],
    ['multiIndent', 2, () => { const ids = many(); setSelection(ids); if (rnd() < .5) indentSelected(); else outdentSelected(); }],
    ['copyPaste', 3, () => { const ids = many(); if (!ids.length || tasks.length > 50) return; setSelection(ids); const c = buildClip(); if (!c) return; setSelection(many()); pasteTaskPayload(c.json); }],
    ['pasteRows', 2, () => { if (tasks.length > 50) return; setSelection(many()); let x = 'ID\tTask Name\tStart\tFinish\tDuration\tPredecessors\n'; const n = 1 + ri(4); for (let i = 1; i <= n; i++) x += `${i}\t${rnd() < .3 ? '  ' : ''}Row ${i}\t${rnd() < .6 ? randDate() : 'TBD'}\t${rnd() < .3 ? randDate() : ''}\t${rnd() < .5 ? (1 + ri(9)) + ' days' : ''}\t${i > 1 && rnd() < .5 ? (1 + ri(i - 1)) + pick(['FS', 'SS', 'FF', 'SF']) : ''}\n`; pasteTableText(x); }],
    ['clone', 3, () => { const t = anyTask(); if (t && tasks.length < 60) cloneTask(t.id); }],
    ['actualStart', 5, () => { const t = anyTask(); if (t && !hasChildren(t.id)) edit(t, 'actualStart', rnd() < .15 ? '' : randDate()); }],
    ['actualFinish', 5, () => { const t = anyTask(); if (t && !hasChildren(t.id)) edit(t, 'actualFinish', rnd() < .15 ? '' : randDate()); }],
    ['progress', 3, () => { const t = anyTask(); if (t && !hasChildren(t.id)) { t.progress = ri(101); t.updatedAt = Date.now(); save(); render(); } }],
    ['text', 2, () => { const t = anyTask(); if (t) { edit(t, 'name', 'N' + ri(1000)); edit(t, 'resource', pick(['', 'Ann', 'Ben & Co', '<b>x</b>'])); } }],
    ['baselineSet', 3, () => applyBaselineChange(ri(BASELINE_SLOTS), rnd() < .8 ? 'all' : (selectedTaskId && byId(selectedTaskId) ? 'selected' : 'all'), false)],
    ['baselineClear', 2, () => applyBaselineChange(ri(BASELINE_SLOTS), 'all', true)],
    ['compare', 1, () => { const s = setBaselineSlots(); if (s.length) setCompareBaseline(pick(s)); }],
    ['calendar', 2, () => { const sets = [[1,2,3,4,5], [1,2,3,4,5,6], [0,1,2,3,4,5,6], [0,2,4], [6,0]]; const d = pick(sets); calChanged = true; if (d.join() === '1,2,3,4,5') delete project.workDays; else project.workDays = d; if (rnd() < .6) { const hl = []; for (let i = ri(6); i > 0; i--) { const h = { date: randDate() }; if (rnd() < .3) h.to = addDays(h.date, 1 + ri(12)); else if (rnd() < .3) h.yearly = true; hl.push(h); } project.holidays = hl; } else delete project.holidays; project.updatedAt = Date.now(); normalizeData(); save(); render(); }],
    ['collapse', 2, () => { const t = anyTask(); if (t && hasChildren(t.id)) toggleCollapse(t.id); else toggleAllCollapsed(); }],
    ['milestone', 2, () => { const t = anyTask(); if (t && !hasChildren(t.id)) { t.milestone = !t.milestone; if (t.milestone) t.endDate = t.startDate; t.updatedAt = Date.now(); normalizeData(); applyConstraints(t.id); save(); render(); } }],
    ['constraint', 2, () => { const t = anyTask(); if (t && !hasChildren(t.id)) { t.constraintType = pick(['ASAP', 'SNET', 'FNET', 'MSO', 'MFO', 'SNLT', 'FNLT']); t.constraintDate = randDate(); t.updatedAt = Date.now(); normalizeData(); applyConstraints(t.id); save(); render(); } }],
    ['history', 4, () => { if (rnd() < .7) historyUndo(); else historyRedo(); }],
    ['roundtrip', 3, () => { if (!undoStack.length) return; const s0 = stateSig(canonicalText()); historyUndo(); historyRedo(); if (stateSig(canonicalText()) !== s0) throw new Error('undo followed by redo changed the plan'); }],
    ['undo', 4, () => { if (toastUndoAction) triggerToastUndo(); }],
    ['view', 3, () => { setView(pick(['tasks', 'gantt'])); zoom = pick(['week', 'month', 'year']); showBaseline = rnd() < .7; showCriticalPath = rnd() < .3; render(); }],
    ['columns', 2, () => { const c = pick(DEFAULT_COL_ORDER); if (!TASK_COLS[c].locked) toggleColumn(c, rnd() < .5); }],
  ];
  if (!allowCalendar) OPS.splice(OPS.findIndex(o => o[0] === 'calendar'), 1);
  const total = OPS.reduce((s, o) => s + o[1], 0);
  const log = [];
  // start from a small plan
  historyCoalesceMs = 0; toastUndoAction = null; tasks.length = 0; deletedTaskIds.length = 0; delete project.workDays; delete project.holidays; delete project.baselines; delete project.compareBaseline;
  for (let i = 0; i < 6; i++) { const d = addDays('2026-09-07', i * 7); tasks.push({ id: genId(), name: 'S' + i, parentId: null, order: i, startDate: d, endDate: shiftWork(d, 3), progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }); }
  normalizeData(); render(); resetHistory();
  for (let step = 1; step <= steps; step++) {
    let r = rnd() * total, op = OPS[0]; for (const o of OPS) { r -= o[1]; if (r < 0) { op = o; break; } }
    log.push(op[0]); if (log.length > 12) log.shift();
    try { op[2](); } catch (e) { return { ok: false, step, op: op[0], why: 'exception: ' + (e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : e), log }; }
    try { if (currentView === 'gantt') { renderGantt(); } } catch (e) { return { ok: false, step, op: op[0], why: 'gantt render threw: ' + e, log }; }
    for (const t of tasks) if (isStarted(t)) everStarted.add(t.id);
    for (const t of tasks) if (!knownIds.has(t.id)) {   // a copy or a pasted duplicate of a task that once had actual dates is in the same (documented) position as its source: clearing actual dates leaves it where it was
      knownIds.add(t.id); const base = t.name.replace(/ \(copy\)$/, '');
      if (tasks.some(x => x !== t && everStarted.has(x.id) && x.name === base)) everStarted.add(t.id);
    }
    const bad = inv();
    if (bad.length) return { ok: false, step, op: op[0], why: 'invariant: ' + bad.slice(0, 4).join(' ; '), log };
    if (step % 20 === 0) {
      const a1 = canonicalText(); normalizeData(); const a2 = canonicalText();
      if (a2 !== a1) {   // say WHAT changed: the tasks and fields that differ between the two passes
        const A = JSON.parse(a1), B = JSON.parse(a2), am = new Map(A.tasks.map(x => [x.id, x])), diffs = [];
        for (const x of B.tasks) { const o = am.get(x.id); if (!o) { diffs.push('new ' + x.name); continue; } for (const k of new Set([...Object.keys(x), ...Object.keys(o)])) if (JSON.stringify(x[k]) !== JSON.stringify(o[k])) diffs.push(x.name + '.' + k + ': ' + JSON.stringify(o[k]) + ' -> ' + JSON.stringify(x[k])); }
        for (const k of Object.keys(B.project)) if (JSON.stringify(B.project[k]) !== JSON.stringify(A.project[k])) diffs.push('project.' + k);
        return { ok: false, step, op: op[0], why: 'normalizeData is not idempotent: ' + diffs.slice(0, 6).join(' | '), log };
      }
      const before = canonicalText(); const base = JSON.parse(before);
      const changed = mergeData(JSON.parse(before), { respectTombstones: true, base, conflicts: [], changedIds: new Map() });
      if (canonicalText() !== before) return { ok: false, step, op: op[0], why: 'merging the plan with itself changed it', log };
      const txt = canonicalText(), data = JSON.parse(txt); const keepT = tasks, keepP = project, keepD = deletedTaskIds;
      tasks = data.tasks; project = data.project; deletedTaskIds = data.deletedTaskIds; normalizeData();
      const re = canonicalText(); tasks = keepT; project = keepP; deletedTaskIds = keepD;
      if (re !== txt) return { ok: false, step, op: op[0], why: 'save -> load -> save is not stable', log };
    }
    if (step % 10 === 0) {   // the critical path: every float is a whole number, something is critical whenever something takes part, and the last-finishing task always is
      const cp = criticalPathAnalysis(), part = [...cp.float.keys()];
      if (part.some(id => !Number.isInteger(cp.float.get(id)))) return { ok: false, step, op: op[0], why: 'critical path: a float is not a whole number', log };
      if (part.length && !cp.critical.size) return { ok: false, step, op: op[0], why: 'critical path: tasks take part but none is critical', log };
      const fin = id => { const t = byId(id); return dayNumber(linkEnd(t)) < dayNumber(linkStart(t)) ? linkStart(t) : linkEnd(t); };   // (the analysis never lets a task finish before it starts)
      let end = null; for (const id of part) { const e = fin(id); if (end === null || dayNumber(e) > dayNumber(end)) end = e; }
      const last = part.filter(id => fin(id) === end);
      if (last.length && !last.some(id => cp.critical.has(id))) return { ok: false, step, op: op[0], why: 'critical path: nothing that finishes last is critical', log };
    }
    if (step % 60 === 0) {
      for (const cols of ['shown', 'all']) { const blob = buildXlsx({ scope: 'all', gantt: true, columns: cols }); if (!blob || blob.size < 1000) return { ok: false, step, op: op[0], why: 'Excel export produced ' + (blob && blob.size), log }; }
    }
  }
  return { ok: true, steps, tasks: tasks.length, log };
}
"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    seeds = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5, 6]
    for seed in seeds:
        r = pg.evaluate(STRESS_JS, [seed, 400, seed % 2 == 0])
        check(f"stress seed {seed}: 400 random operations, invariants hold after every one (structure, dates, links, Auto tasks obey their links and the calendar, normalisation and merge are idempotent, Excel export works)", r["ok"], r)
    check("no console errors or page errors during the whole run", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
