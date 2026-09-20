# -*- coding: utf-8 -*-
"""Robustness: garbage into every parser, hostile names into every new dialog, big plans, features used together, accessibility basics."""
from playwright.sync_api import sync_playwright
import os, re, io, json
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:600]}]" if not cond and detail else ""))

# ---- helpers that run in the page --------------------------------------------------------------------------------------------------
HELPERS = r"""
window.__prng = seed => { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; };
// Everything a plan must satisfy, whatever produced it. Returns a list of problems.
window.__planProblems = (list, opts) => {
  const bad = [], ids = new Set(list.map(t => t.id)), ISO = /^\d{4}-\d{2}-\d{2}$/, byId = new Map(list.map(t => [t.id, t]));
  if (ids.size !== list.length) bad.push('duplicate ids');
  for (const t of list) {
    if (typeof t.name !== 'string' || (!t.name.length && !t.spacer) || t.name.length > 200) bad.push('bad name ' + JSON.stringify(t.name).slice(0, 40));
    if (!ISO.test(t.startDate) || !ISO.test(t.endDate) || dayNumberToIso(dayNumber(t.startDate)) !== t.startDate || dayNumberToIso(dayNumber(t.endDate)) !== t.endDate) bad.push('bad date on ' + t.name);
    else if (dayNumber(t.endDate) < dayNumber(t.startDate)) bad.push('end before start on ' + t.name);
    if (t.milestone && t.startDate !== t.endDate) bad.push('milestone with two dates ' + t.name);
    if (!Number.isInteger(t.progress) || t.progress < 0 || t.progress > 100) bad.push('progress ' + t.progress);
    if (t.parentId && !byId.has(t.parentId)) bad.push('dangling parent on ' + t.name);
    for (const p of t.predecessors || []) { if (!byId.has(p.id)) bad.push('dangling link on ' + t.name); else if (p.id === t.id) bad.push('self link'); if (!['FS', 'SS', 'FF', 'SF'].includes(p.type) || !Number.isInteger(p.lag)) bad.push('bad link ' + JSON.stringify(p)); }
    if (typeof t.resource !== 'string' || t.resource.length > 200) bad.push('bad resource');
    for (const k of ['startText', 'endText', 'durText']) if (t[k] != null && (typeof t[k] !== 'string' || t[k].length > 60)) bad.push('bad ' + k);
    if (!Number.isFinite(t.order)) bad.push('bad order');
  }
  for (const t of list) { let n = 0, c = t; while (c && c.parentId && n++ < 1000) c = byId.get(c.parentId); if (n >= 1000) bad.push('parent cycle'); }
  return [...new Set(bad)];
};
window.__livePlanProblems = () => { const b = window.__planProblems(tasks); const a = canonicalText(); normalizeData(); if (canonicalText() !== a) b.push('normalizeData not idempotent'); return b; };
window.__planSig = () => { const j = JSON.parse(canonicalText()); j.deletedTaskIds = []; return stateSig(stableStringify(j, 2)); };   // (stateSig expects the indented canonical form)
window.__mkTask = (id, name, order, extra) => Object.assign({ id, name, parentId: null, order, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
"""

FUZZ_TABLE = r"""([seed, n]) => {
  const rnd = __prng(seed), pick = a => a[Math.floor(rnd() * a.length)];
  const bits = ['Task Name', 'Start', 'Finish', 'Duration', '% Complete', 'Predecessors', 'ID', 'Outline Level', 'WBS', 'Milestone', 'Resource Names', 'Actual Start', 'Constraint Type', 'Vorgangsname', 'Anfang',
    ',', ';', '\t', '"', '""', '\n', '\r\n', '\r', ' ', '  ', '.', '-', '/', ':', '%', '◆', 'ä', 'é', '😀', '<b>', '&amp;', '\\', '\u0000', ' ', '﻿', 'TBD', '5 days', '0 days', '99999999999', '-5', '1e9', 'NaN',
    '07.09.2026', '2026-09-07', '31.02.2026', '13/45/2026', 'Mon 07.09.26', '7 Sep 2026', '3FS+2', '3;4SS-1', '1EA', 'x', 'Yes', 'No', 'Start No Earlier Than', '1', '2', '3', '10', '1.2.3', '1.', '..', 'A'.repeat(300)];
  const out = [], bad = [], errs = {};
  for (let i = 0; i < n; i++) {
    let s = ''; const len = Math.floor(rnd() * 60); for (let k = 0; k < len; k++) s += pick(bits);
    if (rnd() < .5) s = 'ID,Task Name,Start,Finish,Duration,% Complete,Predecessors,Outline Level\n' + s;
    try {
      const res = tasksFromTable(parseDelimited(s, rnd() < .3 ? pick([',', ';', '\t']) : undefined), { dateFormat: pick(['auto', 'dmy', 'mdy', 'ymd']) });
      const p = __planProblems(res.tasks); if (p.length) bad.push({ s: s.slice(0, 120), p });
    } catch (e) { const k = e && e.constructor ? e.constructor.name : typeof e; errs[k + ': ' + String(e.message).slice(0, 50)] = (errs[k + ': ' + String(e.message).slice(0, 50)] || 0) + 1; if (k !== 'Error') bad.push({ s: s.slice(0, 120), thrown: k + ' ' + e.message }); }
  }
  return { bad: bad.slice(0, 3), nbad: bad.length, errs };
}"""

FUZZ_SCALARS = r"""([seed, n]) => {
  const rnd = __prng(seed), pick = a => a[Math.floor(rnd() * a.length)], bad = [];
  const bits = ['0', '1', '9', '12', '31', '99', '2026', '26', '.', '-', '/', ' ', 'T', ':', 'Mon', 'Sep', 'Sept.', 'März', 'd', 'w', 'h', 'Tage', '%', '+', ',', 'FS', 'SS', 'EA', 'x', '?', '😀', '\u0000', '00', '1e3', '-0'];
  for (let i = 0; i < n; i++) {
    let s = ''; for (let k = Math.floor(rnd() * 12); k > 0; k--) s += pick(bits);
    try {
      const d = parseTableDate(s, pick(['auto', 'dmy', 'mdy', 'ymd'])); if (d != null && dayNumberToIso(dayNumber(d)) !== d) bad.push('date ' + s + ' -> ' + d);
      const u = parseTableDuration(s); if (u != null && (!Number.isInteger(u) || u < 0)) bad.push('dur ' + s + ' -> ' + u);
      const p = parsePredText(s); for (const l of p.links) if (!/^\d+$/.test(l.ref) || !Number.isInteger(l.lag) || !['FS', 'SS', 'FF', 'SF'].includes(l.type)) bad.push('pred ' + s + ' -> ' + JSON.stringify(l));
      importHeaderField(s); isTrueWord(s);
    } catch (e) { bad.push('threw on ' + JSON.stringify(s) + ': ' + e.message); }
  }
  return bad.slice(0, 5);
}"""

FUZZ_XML = r"""([xml, seed, n]) => {
  const rnd = __prng(seed), pick = a => a[Math.floor(rnd() * a.length)], out = { ok: 0, errors: {}, bad: [] };
  const junk = ['', ' ', '0', '-1', '99999999999', 'abc', '<x/>', '&', '&amp;', ']]>', '<![CDATA[<img src=x>]]>', '2026-13-45T00:00:00', '\u0000', '😀', 'PT-5H', 'PTXH', '1e400'];
  for (let i = 0; i < n; i++) {
    let x = xml;
    for (let k = 1 + Math.floor(rnd() * 5); k > 0; k--) {
      const a = Math.floor(rnd() * x.length), b = Math.min(x.length, a + Math.floor(rnd() * 60)), m = rnd();
      if (m < .3) x = x.slice(0, a) + x.slice(b);
      else if (m < .5) x = x.slice(0, b) + x.slice(a, b) + x.slice(b);
      else if (m < .8) { const r = /<(\w+)>([^<]*)<\/\1>/g; const all = [...x.matchAll(r)]; if (all.length) { const t = all[Math.floor(rnd() * all.length)]; x = x.slice(0, t.index) + `<${t[1]}>${pick(junk)}</${t[1]}>` + x.slice(t.index + t[0].length); } }
      else x = x.slice(0, a) + pick(junk) + x.slice(a);
    }
    try {
      const r = parseMspdi(x); out.ok++;
      const p = __planProblems(r.tasks); if (p.length) out.bad.push({ p, x: x.length });
    } catch (e) { const k = (e && e.constructor && e.constructor.name) || typeof e; out.errors[k] = (out.errors[k] || 0) + 1; if (k !== 'Error') out.bad.push({ thrown: k + ': ' + e.message }); }
  }
  out.bad = out.bad.slice(0, 3); return out;
}"""

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?><Project xmlns="http://schemas.microsoft.com/project"><Title>T</Title><MinutesPerDay>480</MinutesPerDay><CalendarUID>1</CalendarUID>
<Calendars><Calendar><UID>1</UID><IsBaseCalendar>1</IsBaseCalendar><WeekDays><WeekDay><DayType>1</DayType><DayWorking>0</DayWorking></WeekDay><WeekDay><DayType>2</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>7</DayType><DayWorking>0</DayWorking></WeekDay></WeekDays>
<Exceptions><Exception><TimePeriod><FromDate>2026-12-24T00:00:00</FromDate><ToDate>2027-01-01T23:59:00</ToDate></TimePeriod><Name>Shutdown</Name><DayWorking>0</DayWorking></Exception></Exceptions></Calendar></Calendars>
<Tasks><Task><UID>0</UID><OutlineLevel>0</OutlineLevel></Task>
<Task><UID>1</UID><Name>Design</Name><OutlineLevel>1</OutlineLevel><Start>2026-09-07T08:00:00</Start><Finish>2026-09-18T17:00:00</Finish></Task>
<Task><UID>2</UID><Name>Wireframes</Name><OutlineLevel>2</OutlineLevel><Start>2026-09-07T08:00:00</Start><Finish>2026-09-11T17:00:00</Finish><Duration>PT40H0M0S</Duration><PercentComplete>100</PercentComplete><ActualStart>2026-09-07T08:00:00</ActualStart><Baseline><Number>0</Number><Start>2026-09-07T08:00:00</Start><Finish>2026-09-10T17:00:00</Finish></Baseline></Task>
<Task><UID>3</UID><Name>Visual</Name><OutlineLevel>2</OutlineLevel><Start>2026-09-14T08:00:00</Start><Finish>2026-09-18T17:00:00</Finish><Duration>PT40H0M0S</Duration><ConstraintType>4</ConstraintType><ConstraintDate>2026-09-14T08:00:00</ConstraintDate><PredecessorLink><PredecessorUID>2</PredecessorUID><Type>1</Type><LinkLag>4800</LinkLag><LagFormat>7</LagFormat></PredecessorLink></Task>
<Task><UID>4</UID><Name>Go live</Name><OutlineLevel>1</OutlineLevel><Start>2026-09-21T08:00:00</Start><Finish>2026-09-21T08:00:00</Finish><Duration>PT0H0M0S</Duration><Milestone>1</Milestone><Manual>1</Manual><PredecessorLink><PredecessorUID>3</PredecessorUID><Type>3</Type></PredecessorLink></Task></Tasks>
<Resources><Resource><UID>1</UID><Name>Anna</Name></Resource></Resources><Assignments><Assignment><TaskUID>3</TaskUID><ResourceUID>1</ResourceUID></Assignment></Assignments></Project>"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev("() => { historyCoalesceMs = 0; window.print = () => {}; }"); ev(HELPERS)

    # ============================================================ 1. garbage into the parsers
    r = ev(FUZZ_TABLE, [1, 2500])
    check("table parser: 2,500 random garbage tables — nothing but the documented Error, and every task that comes out is a valid task", r["nbad"] == 0, r)
    r = ev(FUZZ_TABLE, [2, 2500])
    check("...and another 2,500 (different seed)", r["nbad"] == 0, r)
    bad = ev(FUZZ_SCALARS, [3, 20000])
    check("date, duration and predecessor readers: 20,000 random fragments — never throw, always a real date / whole number / clean link", not bad, bad)
    r = ev(FUZZ_XML, [SAMPLE_XML, 4, 800])
    check("MS Project XML reader: 800 random mutations (deleted, duplicated, replaced and hostile values) — either a clear Error or valid tasks", not r["bad"] and r["ok"] + sum(r["errors"].values()) == 800, r)
    check("...the mutations do exercise both outcomes (some parse, some are refused)", r["ok"] > 50 and sum(r["errors"].values()) > 10, r)
    big = ev("() => { const rows = ['Task Name,Start,Finish,Predecessors']; for (let i = 0; i < 20000; i++) rows.push('Task ' + i + ',07.09.2026,08.09.2026,' + (i ? i : '')); const t0 = performance.now(); const r = tasksFromTable(parseDelimited(rows.join('\\n'))); return { n: r.tasks.length, ms: performance.now() - t0, links: r.info.links }; }")
    check("a 20,000-row CSV with links reads in a few seconds", big["n"] == 20000 and big["ms"] < 8000 and big["links"] == 19999, big)
    huge = ev("() => { try { const t0 = performance.now(); const s = 'a,'.repeat(200000) + '\\n' + 'b,'.repeat(200000); const r = parseDelimited(s); return [r.length, r[0].length, performance.now() - t0]; } catch (e) { return String(e); } }")
    check("a 400,000-cell CSV line is read without a stack or memory problem", isinstance(huge, list) and huge[0] == 2 and huge[2] < 4000, huge)

    # ============================================================ 2. random pasted text into a real plan
    ev("""() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]);
      tasks.push(__mkTask('a1', 'Alpha', 0), __mkTask('a2', 'Beta', 1, { predecessors: [{ id: 'a1', type: 'FS', lag: 0 }], startDate: '2026-09-09', endDate: '2026-09-10' }), __mkTask('a3', 'Gamma', 2), __mkTask('a4', 'Kid', 0, { parentId: 'a3' }));
      normalizeData(); save(); render(); resetHistory(); }""")
    out = ev("""(seed) => { const rnd = __prng(seed), pick = a => a[Math.floor(rnd() * a.length)], probs = [];
      const bits = ['Task Name', 'Start', 'Finish', 'Duration', 'ID', 'Predecessors', '\\t', '\\n', ',', ' ', '  ', 'Alpha', '07.09.2026', '5 days', 'TBD', '2FS', '1SS+1', '"', '◆ ', '3', '10', '%', '50%', '😀', '<script>window.__pwn=1</script>'];
      let steps = 0;
      for (let i = 0; i < 300; i++) {
        let s = ''; for (let k = Math.floor(rnd() * 40); k > 0; k--) s += pick(bits);
        const ids = tasks.map(t => t.id); if (rnd() < .5 && ids.length) setSelection([pick(ids)]); else setSelection([]);
        const before = __planSig(), idsBefore = new Set(tasks.map(t => t.id));
        try { pasteFrom(s, ''); } catch (e) { probs.push('threw: ' + e.message + ' on ' + JSON.stringify(s).slice(0, 80)); continue; }
        const p = __livePlanProblems(); if (p.length) probs.push(p.join(';') + ' after ' + JSON.stringify(s).slice(0, 80));
        if (__planSig() !== before) { steps++; historyUndo(); if (__planSig() !== before) probs.push('undo did not restore after ' + JSON.stringify(s).slice(0, 60)); else if (deletedTaskIds.some(d => idsBefore.has(d.id))) probs.push('undo tombstoned a task that existed before'); else historyRedo(); }
        if (tasks.length > 250) { tasks.length = 4; tasks[3].parentId = 'a3'; normalizeData(); save(); render(); resetHistory(); }
      }
      return { probs: probs.slice(0, 4), n: probs.length, steps, pwn: window.__pwn || null };
    }""", 7)
    check("300 pieces of random text pasted into a real plan: the plan stays valid after each one, each is a single undo step that restores it exactly (the only trace: tombstones for the tasks the undo removed), nothing throws", out["n"] == 0 and out["steps"] > 30, out)
    check("...and pasted text is never executed (a <script> in a name did nothing)", out["pwn"] is None)

    # ============================================================ 3. hostile names in every new dialog
    X = '"><img src=x onerror="window.__xss=1"><b>x</b>'
    ev("""(X) => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); delete project.holidays;
      tasks.push(__mkTask('h1', X + ' Task', 0, { resource: X + ' res', custom: { text1: X + ' cf' } }), __mkTask('h2', 'Child ' + X, 0, { parentId: 'h1', predecessors: [] }), __mkTask('h3', 'Other', 1, { predecessors: [{ id: 'h2', type: 'FS', lag: 0 }] }));
      project.name = X + ' Plan'; project.holidays = [{ date: '2026-10-05', name: X }]; project.fieldNames = { text1: X + ' Field' }; normalizeData(); save(); colHidden.delete('text1'); render(); resetHistory(); window.__xss = undefined; }""", X)
    pg.wait_for_timeout(150)
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(150); pg.fill("#searchInput", "task"); pg.wait_for_timeout(150)
    res_html = ev("() => document.getElementById('searchResults').innerHTML")
    check("Find: a hostile task name and resource are shown as text, not as markup", "<img" not in res_html.replace("&lt;img", "") and ev("() => window.__xss") is None and "&lt;img" in res_html, res_html[:200])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ev("() => { setSelection([tasks[0].id, tasks[1].id]); render(); openBulkModal(); }"); pg.wait_for_timeout(200)
    bh = ev("() => document.getElementById('bulkModalBg').innerHTML")
    check("Edit tasks: a hostile custom-field name is escaped in the dialog", "<img src=x" not in bh and ev("() => window.__xss") is None)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ev("() => { openCalendarModal(); }"); pg.wait_for_timeout(200)
    check("Working calendar: a hostile holiday name is escaped in the list", "<img src=x" not in ev("() => document.getElementById('holList').innerHTML") and ev("() => window.__xss") is None)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ev("() => { openPrintModal(); }"); pg.wait_for_timeout(300)
    check("Print: the SVG page and the title field escape hostile names (preview and printed pages)", "<img src=x" not in ev("() => document.getElementById('printPreview').innerHTML") and ev("() => window.__xss") is None and "<img src=x" not in ev("() => printBuilt.pages.join('')"))
    ev("() => { mountPrintRoot(printBuilt); }"); pg.wait_for_timeout(100)
    check("...also in the print root", ev("() => window.__xss") is None and ev("() => document.querySelectorAll('#printRoot img').length") == 0)
    ev("() => { unmountPrintRoot(); closePrintModal(); }")
    ev("() => { setSelection([tasks[0].id]); }")
    tsv = ev("() => buildClip().tsv")
    check("Copy: a hostile name goes into the clipboard table as plain text (tabs and line breaks inside names cannot break the table)", ev("(X) => { tasks[0].name = 'a\\tb\\nc ' + X; const t = buildClip().tsv; tasks[0].name = X + ' Task'; return t.split('\\n').length === 1 + subtreeTasks(selectionRoots()).length && t.split('\\n').every(l => l.split('\\t').length === t.split('\\n')[0].split('\\t').length); }", X))
    xml = f"<?xml version='1.0'?><Project xmlns='http://schemas.microsoft.com/project'><Title>{X.replace('<', '&lt;').replace('>', '&gt;').replace(chr(34), '&quot;')}</Title><Tasks><Task><UID>1</UID><Name><![CDATA[{X}]]></Name><OutlineLevel>1</OutlineLevel><Start>2026-09-07T08:00:00</Start><Finish>2026-09-08T17:00:00</Finish></Task></Tasks></Project>"
    ev("(x) => { openForeignImport(x, 'evil <img src=x onerror=window.__xss=1>.xml'); }", xml); pg.wait_for_timeout(250)
    ih = ev("() => document.getElementById('foreignImportModalBg').innerHTML")
    check("Import preview: a hostile task name and even a hostile file name are escaped", "<img src=x" not in ih and ev("() => window.__xss") is None and "&lt;img" in ih, ih[:150])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ev("(X) => { pasteTableText('Task Name\\tResource\\n' + X + '\\t' + X); render(); }", X); pg.wait_for_timeout(150)
    check("Paste from Excel: hostile cell text becomes an ordinary name, rendered as text in the list", ev("() => window.__xss") is None and ev("() => document.querySelectorAll('#gridRows img').length") == 0)
    check("no hostile markup was executed anywhere (window.__xss was never set)", ev("() => window.__xss") is None)

    # ============================================================ 4. a big plan
    perf = ev("""() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); delete project.holidays;
      let n = 0; const mk = (name, par, order, extra) => { const t = __mkTask('b' + (n++), name, order, Object.assign({ parentId: par }, extra || {})); tasks.push(t); return t; };
      for (let g = 0; g < 20; g++) { const gt = mk('Phase ' + g, null, g); for (let s = 0; s < 10; s++) { const st = mk('Stream ' + g + '.' + s, gt.id, s); for (let k = 0; k < 6; k++) { const d = 7 + (k * 3 % 20); mk('Task ' + g + '.' + s + '.' + k, st.id, k, { startDate: '2026-10-' + String(d).padStart(2, '0'), endDate: '2026-10-' + String(d + 1).padStart(2, '0'), resource: ['Anna', 'Ben', 'Chris'][k % 3] }); } } }
      const leaves = tasks.filter(t => t.name.startsWith('Task ')); for (let i = 1; i < leaves.length; i += 3) leaves[i].predecessors = [{ id: leaves[i - 1].id, type: 'FS', lag: 0 }];
      const T = {}, time = (k, f) => { const t0 = performance.now(); const r = f(); T[k] = Math.round(performance.now() - t0); return r; };
      time('normalize', () => normalizeData()); time('save', () => save()); time('render tasks', () => render()); time('render gantt', () => { setView('gantt'); render(); setView('tasks'); render(); });
      time('critical path', () => criticalPathAnalysis()); time('search', () => searchTasks('task 7')); time('print pages', () => buildPrintPages(Object.assign(printDefaults(), { expandAll: true })));
      time('canonical', () => canonicalText()); time('excel', () => buildXlsx({ scope: 'all', gantt: true, columns: 'shown' }));
      setSelection(tasks.map(t => t.id)); time('copy all', () => buildClip());
      const clip = buildClip(); T.clipKB = Math.round(clip.tsv.length / 1024);
      time('paste all', () => pasteTaskPayload(clip.json));
      time('undo paste', () => historyUndo()); time('redo paste', () => historyRedo()); time('undo again', () => historyUndo());
      T.tasks = tasks.length; return T; }""")
    check("a plan of 1,460 tasks (20 phases, 200 streams, 1,200 tasks, links): every operation stays interactive", perf["tasks"] == 1420 and all(perf[k] < 4000 for k in ("normalize", "save", "render tasks", "render gantt", "critical path", "search", "print pages", "canonical", "excel", "copy all", "paste all", "undo paste", "redo paste")), perf)
    print("      timings (ms):", {k: v for k, v in perf.items()})
    check("...and the plan is still valid after paste, undo, redo, undo", ev("() => __livePlanProblems().length") == 0, ev("() => __livePlanProblems()"))
    hist = ev("""() => { for (let i = 0; i < 120; i++) { tasks[i].progress = (i % 99) + 1; tasks[i].updatedAt = Date.now(); save(); } return { steps: undoStack.length, kb: Math.round(undoStack.reduce((n, e) => n + e.text.length, 0) / 1024) }; }""")
    check("the undo history keeps at most 100 steps and stays within its memory cap even for this plan", hist["steps"] <= 100 and hist["kb"] < 40000, hist)
    ev("() => { resetHistory(); }")

    # ============================================================ 4b. absurd numbers cannot freeze the app (found by the monkey test: a duration of 99999999999 in the dialog)
    ev("""() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]);
      tasks.push(__mkTask('n1', 'One', 0), __mkTask('n2', 'Two', 1, { predecessors: [{ id: 'n1', type: 'FS', lag: 0 }], startDate: '2026-09-09', endDate: '2026-09-10' }), __mkTask('n3', 'Manual', 2, { taskMode: 'manual' }));
      project.holidays = [{ date: '2026-10-05', name: 'x' }, { date: '2026-12-24', to: '2027-01-01' }]; delete project.workDays; normalizeData(); save(); render(); resetHistory(); }""")
    def timed(js, arg=None):
        return ev("([js, arg]) => { const t0 = performance.now(); const r = (new Function('arg', js))(arg); return [r, Math.round(performance.now() - t0)]; }", [js, arg])
    r, ms = timed("return [/^\\d{4}-/.test(dayNumberToIso(addWorkNum(dayNumber('2026-09-07'), 1e12))), /^\\d{4}-/.test(dayNumberToIso(addWorkNum(dayNumber('2026-09-07'), -1e12))), /^\\d{4}-/.test(shiftWork('2026-09-07', 1e15)), /^\\d{4}-/.test(finishFor('2026-09-07', 99999999999))];")
    check("the working-day arithmetic caps a move at 40,000 days: 1e12 or 1e15 days with holidays in the plan return a real date at once", r == [True, True, True, True] and ms < 1500, (r, ms))
    r, ms = timed("const t = byId('n1'); openTaskModal('n1'); const i = document.getElementById('taskDurationInput'); i.value = '99999999999'; i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); saveTaskFromModal(); return [durationDays(t.startDate, t.endDate) <= 9999, /^\\d{4}-\\d{2}-\\d{2}$/.test(t.endDate), dayNumber(t.endDate) < dayNumber('2200-01-01')];")
    check("a duration of 99999999999 typed into the task dialog is limited to 9,999 days and saves in well under a second (it used to freeze the page)", r == [True, True, True] and ms < 3000, (r, ms))
    ev("() => { closeTaskModal && closeTaskModal(); }")
    ev("() => { const a = byId('n1'), t = byId('n2'); a.startDate = '2026-09-07'; a.endDate = '2026-09-08'; t.startDate = '2026-09-09'; t.endDate = '2026-09-10'; }")   # (the dialog step above made One very long, and Two follows it)
    r, ms = timed("const t = byId('n2'); const before = [t.startDate, t.endDate]; editingCell = { id: 'n2', field: 'duration' }; commitInlineEdit('n2', 'duration', '99999999999'); return [before.join() === [t.startDate, t.endDate].join(), document.getElementById('toastMsg').textContent];")
    check("inline: the same number in the Duration cell is refused with a message and changes nothing", r[0] is True and "at most 9,999" in r[1] and ms < 1500, (r, ms))
    r, ms = timed("const t = byId('n3'); editingCell = { id: 'n3', field: 'duration' }; commitInlineEdit('n3', 'duration', '99999999999'); return [document.getElementById('toastMsg').textContent, t.durText];")
    check("...also for a manually scheduled task (the same limit)", "at most 9,999" in r[0] and ms < 1500, (r, ms))
    r, ms = timed("const t = byId('n2'); editingCell = { id: 'n2', field: 'predecessors' }; commitInlineEdit('n2', 'predecessors', '1FS+99999999999'); return [t.predecessors.length, t.predecessors[0] && t.predecessors[0].lag, document.getElementById('toastMsg').textContent];")
    check("a predecessor lag of 99999999999 typed in the list is refused and the existing link stays", r[0] == 1 and r[1] == 0 and "at most 9,999" in r[2] and ms < 1500, (r, ms))
    r, ms = timed("const t = byId('n2'); t.predecessors = [{ id: 'n1', type: 'FS', lag: 1e12 }]; normalizeData(); applyConstraints('n2'); return [t.predecessors[0].lag, /^\\d{4}-/.test(t.startDate)];")
    check("a lag of 1e12 that arrives from a file, a merge or an import is clamped to 9,999 when the plan is normalised", r[0] == 9999 and r[1] is True and ms < 3000, (r, ms))
    r, ms = timed("const res = tasksFromTable(parseDelimited('Task Name,Start,Duration,Predecessors\\nA,07.09.2026,99999999999,\\nB,07.09.2026,5 days,1FS+99999999999')); return [res.tasks.map(t => [t.taskMode, t.endText, t.predecessors.length]), res.warnings.length, res.tasks.every(t => /^\\d{4}-/.test(t.endDate))];")
    check("CSV / pasted rows: an absurd duration is not a duration (that task is 'TBD' until it has a real one), an absurd lag is an unreadable link — nothing hangs", r[0][0][0] == "manual" and r[0][1][2] == 0 and r[1] >= 1 and r[2] and ms < 1500, (r, ms))
    r, ms = timed("setSelection(['n1', 'n2']); openBulkModal(); document.getElementById('bulkOn-shift').checked = true; document.getElementById('bulkVal-shift').value = '99999999999'; applyBulkEdit(); const a = document.getElementById('toastMsg').textContent; document.getElementById('bulkOn-shift').checked = false; document.getElementById('bulkOn-pred').checked = true; document.getElementById('bulkVal-predId').value = '3'; document.getElementById('bulkVal-predLag').value = '99999999999'; applyBulkEdit(); return [a, document.getElementById('toastMsg').textContent];")
    check("bulk edit: 'Move dates by' 99999999999 and a lag of 99999999999 are refused with a message", "working days" in r[0] and "at most 9,999" in r[1] and ms < 1500, (r, ms))
    ev("() => { closeBulkModal(); }")
    r, ms = timed("const d = { version: 1, project: { name: 'x', updatedAt: 5 }, tasks: [__mkTask('j1', 'J1', 0, { predecessors: [{ id: 'j2', type: 'FS', lag: 1e300 }] }), __mkTask('j2', 'J2', 1, { predecessors: [{ id: 'j1', type: 'SS', lag: -1e300 }] })], deletedTaskIds: [] }; tasks.length = 0; tasks.push(...d.tasks); normalizeData(); const c = taskCycleSet(); return [tasks.map(t => t.predecessors[0].lag), __planProblems(tasks).length];")
    check("a plan file with lags of ±1e300 (and a cycle) loads: lags clamped, the plan valid", r[0] == [9999, -9999] and r[1] == 0 and ms < 1500, (r, ms))
    ev("() => { delete project.holidays; tasks.length = 0; normalizeData(); save(); render(); resetHistory(); }")

    # ============================================================ 5. the new features used together
    ev("""() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); delete project.holidays; delete project.workDays; delete project.baselines;
      tasks.push(__mkTask('c1', 'Group', 0, { startDate: '2026-09-07', endDate: '2026-10-02' }), __mkTask('c2', 'Design', 0, { parentId: 'c1', startDate: '2026-09-07', endDate: '2026-09-11', resource: 'Anna' }),
        __mkTask('c3', 'Build', 1, { parentId: 'c1', startDate: '2026-09-14', endDate: '2026-09-25', predecessors: [{ id: 'c2', type: 'FS', lag: 0 }], resource: 'Ben' }), __mkTask('c4', 'Test', 2, { parentId: 'c1', startDate: '2026-09-28', endDate: '2026-10-02', predecessors: [{ id: 'c3', type: 'FS', lag: 0 }] }),
        __mkTask('c5', 'Release', 1, { startDate: '2026-10-05', endDate: '2026-10-05', milestone: true, taskMode: 'manual' }));
      normalizeData(); save(); render(); resetHistory(); }""")
    start = ev("() => __planSig()")
    steps = ev("""() => { const log = [];
      const step = (name, f) => { const b = stateSig(canonicalText()); f(); log.push([name, stateSig(canonicalText()) !== b]); };
      step('select+bulk resource', () => { setSelection([byId('c2').id, byId('c3').id]); document.getElementById('bulkModalBg'); openBulkModal(); document.getElementById('bulkOn-resource').checked = true; document.getElementById('bulkVal-resource').value = 'Team A'; applyBulkEdit(); });
      step('bulk shift +3', () => { setSelection([byId('c3').id]); openBulkModal(); document.getElementById('bulkOn-shift').checked = true; document.getElementById('bulkVal-shift').value = '3'; applyBulkEdit(); });
      step('copy+paste', () => { setSelection([byId('c2').id, byId('c3').id]); const c = buildClip(); setSelection([byId('c5').id]); pasteTaskPayload(c.json); });
      step('import csv (append)', () => { const r = tasksFromTable(parseDelimited('Task Name,Start,Finish\\nImported A,05.10.2026,06.10.2026\\nImported B,07.10.2026,08.10.2026')); applyImportedTasks(r, 'append', {}); });
      step('holiday preset', () => { project.holidays = holidayPreset('DE-BY', 2026, 2026).map(h => ({ date: h.date, name: h.name })); project.updatedAt = Date.now(); normalizeData(); save(); render(); });
      step('clone group', () => { setSelection([byId('c1').id]); cloneSelected(); });
      step('delete two', () => { setSelection(tasks.filter(t => t.name === 'Imported A' || t.name === 'Imported B').map(t => t.id)); deleteTasksNow(selectedIds()); });
      step('indent', () => { setSelection([byId('c5').id]); indentSelected(); });
      return log; }""")
    check("ten mixed operations across the new features each change the plan", all(changed for _, changed in steps), steps)
    check("...the plan is valid after them all", ev("() => __livePlanProblems().length") == 0, ev("() => __livePlanProblems()"))
    end_state = ev("() => __planSig()")
    n_undo = ev("() => { let n = 0; while (undoStack.length && n < 50) { historyUndo(); n++; } return n; }")
    check("undoing every step brings the plan back to EXACTLY where it started (tasks and settings; the removed tasks are tombstoned so a synced file learns they are gone)", ev("() => __planSig()") == start and ev("() => deletedTaskIds.every(d => !tasks.some(t => t.id === d.id))"), n_undo)
    ev("() => { let n = 0; while (redoStack.length && n < 50) { historyRedo(); n++; } }")
    check("...and redoing them all reaches exactly the final state again", ev("() => __planSig()") == end_state)
    ev("() => { save(); }"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev(HELPERS)
    check("after a reload the plan is byte-for-byte what was saved, and saving again changes nothing", ev("() => __planSig()") == end_state and ev("() => { const a = canonicalText(); normalizeData(); save(); return canonicalText() === a; }"))
    # filters + selection + bulk
    ev("""() => { colFilters = newColFilters(); filterPinned.clear(); colFilters.name = { type: 'values', values: new Set(['Design', 'Build']), blanks: false }; render(); }""")
    sel = ev("() => { setSelection(visibleTaskList().map(v => v.task.id)); return selectedIds().map(id => byId(id).name); }")
    check("with a filter on, 'select all' selects only what is shown (not the hidden tasks)", "Test" not in sel and "Design" in sel and "Build" in sel, sel)
    ev("() => { colFilters = newColFilters(); filterPinned.clear(); setSelection([]); render(); }")
    # merge safety with field-level changes from two 'devices'
    m = ev("""() => { const base = JSON.parse(canonicalText()); const mine = tasks.find(t => t.name === 'Design'); const theirs = JSON.parse(canonicalText());
      const th = theirs.tasks.find(t => t.name === 'Design'); th.resource = 'Remote'; th.updatedAt = Date.now() + 1000;   // the other device changed the resource
      mine.startDate = '2026-09-08'; mine.updatedAt = Date.now() + 500;                                                     // this device (a bulk shift) changed the dates
      const conflicts = []; mergeData(theirs, { respectTombstones: true, base, conflicts }); const d = tasks.find(t => t.name === 'Design'); return { res: d.resource, start: d.startDate, conflicts: conflicts.length }; }""")
    check("a bulk-edited field and a field changed on another device merge without losing either (three-way merge keeps both)", m["res"] == "Remote" and m["start"] == "2026-09-08" and m["conflicts"] == 0, m)

    # ============================================================ 6. accessibility basics of the new UI
    a11y = ev("""() => { const bad = []; const label = el => (el.getAttribute('aria-label') || el.title || el.textContent || el.value || el.placeholder || '').trim();   // (textContent: a closed dialog has no innerText)
      for (const id of ['undoBtn', 'redoBtn', 'copyBtn', 'pasteBtn', 'bulkEditBtn', 'deleteTaskBtn', 'cloneTaskBtn', 'indentBtn', 'outdentBtn', 'addMenuBtn', 'searchBtn', 'selChip']) { const el = document.getElementById(id); if (!el || !label(el)) bad.push('button ' + id); }
      for (const modal of ['searchModalBg', 'bulkModalBg', 'foreignImportModalBg', 'printModalBg', 'calendarModalBg', 'helpModalBg']) for (const el of document.querySelectorAll('#' + modal + ' button')) if (!label(el)) bad.push(modal + ' button without a name: ' + el.outerHTML.slice(0, 60));
      for (const modal of ['searchModalBg', 'bulkModalBg', 'foreignImportModalBg', 'printModalBg', 'calendarModalBg']) for (const el of document.querySelectorAll('#' + modal + ' input:not([type=hidden]), #' + modal + ' select')) { const has = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || (el.id && document.querySelector('label[for="' + el.id + '"]')) || el.closest('label') || el.placeholder || el.title; if (!has) bad.push(modal + ' field without a label: ' + (el.id || el.outerHTML.slice(0, 50))); }
      return bad; }""")
    check("the new toolbar buttons and dialog controls all have an accessible name (label, aria-label, title or visible text)", not a11y, a11y[:6])
    check("no console errors during the whole robustness run", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
