# -*- coding: utf-8 -*-
"""Right-click quick action (Mark complete) and Find searching Notes: what it changes, what it skips, one history step, the menu's place, and the
Find window's note snippet and ranking. See "Quick actions" and "Find a task" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """() => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.timeUnit; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }, x || {});
  tasks.push(mk('g', 'Phase', '2030-03-04', '2030-03-22'),
    mk('a', 'Discovery', '2030-03-04', '2030-03-08', { parentId: 'g', progress: 40, notes: 'Waiting for the vendor contract before we can start\\nsecond line' }),
    mk('b', 'Build', '2030-03-11', '2030-03-15', { parentId: 'g', color: 'red' }),
    mk('c', 'Vendor review', '2030-03-18', '2030-03-22', { parentId: 'g', progress: 100, notes: 'nothing to see' }),
    mk('d', 'Launch', '2030-03-25', '2030-03-25', { milestone: true, resource: 'Anna' }),
    mk('e', 'Plain', '2030-03-26', '2030-03-27', { notes: 'The Vendor said later' }));
  tasks.push(mk('sp', '', '2030-03-04', '2030-03-04', { spacer: true }));
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; for (const k of Object.keys(colFilters)) colFilters[k] = null; filterPinned.clear(); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 820}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(250)
    prog = lambda i: ev("(i) => tasks.find(t => t.id === i).progress", i)
    col = lambda i: ev("(i) => tasks.find(t => t.id === i).color", i)
    toast = lambda: ev("() => document.getElementById('toastMsg').textContent")
    def rclick(i, x=300): pg.locator(f"#gridRows .grid-row[data-id='{i}']").click(button="right", position={"x": x, "y": 10}); pg.wait_for_timeout(150)
    mi = lambda t: pg.locator(f"#rowMenu .dropdown-item:has-text('{t}')")
    # ================================================== Mark complete
    rclick("a")
    check("the row menu has 'Mark complete' in the first block, right under Edit task… (both change the task you clicked), and no colour swatches", mi("Mark complete").count() == 1 and pg.locator("#rowMenu .menu-swatch").count() == 0 and ev("() => [...document.querySelectorAll('#rowMenu > *')].map(e => e.classList.contains('dropdown-sep') ? '|' : [...e.childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim().replace(/\\s.*/, '')).join(' ')") == "Edit Mark | Add Add | Duplicate Copy Cut Paste | Indent Outdent | Delete")
    mi("Mark complete").click(); pg.wait_for_timeout(250)
    check("Mark complete sets the task to 100% (40 → 100), and says so with how to undo", prog("a") == 100 and "100% complete" in toast() and "undoes" in toast(), toast())
    check("...it changed only that task (updatedAt moved on it alone)", ev("() => tasks.filter(t => t.updatedAt > 1).map(t => t.id).sort()") == ["a", "g"] or ev("() => tasks.filter(t => t.updatedAt > 1).map(t => t.id).sort()") == ["a"], ev("() => tasks.filter(t => t.updatedAt > 1).map(t => t.id)"))
    ev("() => historyUndo()"); pg.wait_for_timeout(200)
    check("one Undo step takes it back (100 → 40)", prog("a") == 40, prog("a"))
    rclick("c")
    check("an already complete task: 'Mark complete' is disabled", mi("Mark complete").is_disabled())
    pg.keyboard.press("Escape")
    rclick("g")
    check("a group (its % is worked out from its tasks) can't be marked: disabled", mi("Mark complete").is_disabled())
    pg.keyboard.press("Escape")
    ev("() => { setSelection(['a', 'b', 'c', 'g', 'd']); render(); }"); pg.wait_for_timeout(100)
    rclick("b")
    mi("Mark complete").click(); pg.wait_for_timeout(250)
    check("with several selected it completes every open task without sub-tasks (Discovery, Build, Launch) and leaves the group and the finished one alone", [prog(i) for i in "abcd"] == [100, 100, 100, 100] and "3 tasks" in toast(), (toast(), [prog(i) for i in "abcd"]))
    check("...the group's own % follows from its tasks (rollup 100)", ev("() => effectiveDates('g').progress") == 100)
    ev("() => historyUndo()"); pg.wait_for_timeout(200)
    check("...and that is one undo step too", [prog(i) for i in "abcd"] == [40, 0, 100, 0], [prog(i) for i in "abcd"])
    # filtered: the task stays visible
    ev("() => { colFilters.progress = { type: 'rule', rule: 'lt', a: '50' }; render(); }"); pg.wait_for_timeout(150)
    ev("() => { setSelection(['b']); render(); }"); rclick("b"); mi("Mark complete").click(); pg.wait_for_timeout(250)
    check("under a filter that the new % no longer matches, the edited row stays in the list (pinned), like any edit", pg.locator("#gridRows .grid-row[data-id='b']").count() == 1)
    ev("() => { for (const k of Object.keys(colFilters)) colFilters[k] = null; filterPinned.clear(); } "); ev(SEED); pg.wait_for_timeout(200)
    # empty line / empty area
    ev("() => { setSelection(['sp']); render(); }"); pg.locator("#gridRows .grid-row.spacer-row").click(button="right", position={"x": 200, "y": 10}); pg.wait_for_timeout(150)
    check("an empty line has no Mark complete (nothing to complete)", mi("Mark complete").count() == 0)
    pg.keyboard.press("Escape")
    pg.mouse.click(700, 760, button="right"); pg.wait_for_timeout(150)
    check("the empty area of the list has none either", pg.locator("#rowMenu").inner_text().find("Mark complete") < 0)
    pg.keyboard.press("Escape")
    # Gantt right-click
    ev("() => { currentView = 'gantt'; render(); }"); pg.wait_for_timeout(300)
    pg.locator("#gridRows .grid-row[data-id='b']").click(button="right", position={"x": 300, "y": 10}); pg.wait_for_timeout(150)
    mi("Mark complete").click(); pg.wait_for_timeout(250)
    check("the same menu in the Gantt view works (Build → 100%)", prog("b") == 100)
    ev("() => { currentView = 'tasks'; render(); }")
    # ================================================== Find in Notes
    ev(SEED); pg.wait_for_timeout(200)
    S = lambda q: ev("(q) => searchTasks(q).map(h => [h.t.id, !!h.note])", q)
    check("Find finds a task by a word in its notes: 'vendor' → Vendor review (name), Discovery (note), Plain (note)", sorted(S("vendor")) == sorted([["c", False], ["a", True], ["e", True]]), S("vendor"))
    check("...a task whose NAME matches ranks above those that only their notes mention (Vendor review first)", S("vendor")[0][0] == "c", S("vendor"))
    check("...is case-insensitive ('VENDOR contract' needs both words in the same task: Discovery's note)", S("VENDOR contract") == [["a", True]], S("VENDOR contract"))
    check("...every word must match, across name and notes ('discovery contract' → Discovery: name + note)", S("discovery contract") == [["a", True]], S("discovery contract"))
    check("...a word in nobody's notes finds nothing; @resource searches are unaffected (notes aren't searched there)", S("zzzz") == [] and S("@vendor") == [] and S("@anna") == [["d", False]])
    check("...a task whose name matches shows no snippet", all(not n for i, n in S("launch")))
    pg.keyboard.press("Control+k"); pg.fill("#searchInput", "vendor contract"); pg.wait_for_timeout(250)
    snip = pg.locator("#searchResults .sr").first.locator(".sr-note")
    check("the result shows the matching stretch of the note under the path, with the words marked", snip.count() == 1 and "Waiting for the vendor contract" in snip.inner_text() and snip.locator("mark").count() >= 1, snip.inner_text() if snip.count() else "")
    check("...on one line (the note's line breaks are flattened to spaces), cut with an ellipsis when long", "\n" not in snip.inner_text() and ev("() => { const e = document.querySelector('#searchResults .sr-note'); return e.scrollHeight <= e.clientHeight + 2; }"))
    ev("() => { tasks.find(t => t.id === 'e').notes = 'x'.repeat(300) + ' vendor ' + 'y'.repeat(300); }"); pg.fill("#searchInput", "vendor"); pg.wait_for_timeout(250)
    long_ = pg.locator("#searchResults .sr:has-text('Plain') .sr-note").inner_text()
    check("a long note is shown only around the hit (about 90 characters, with … at the cut ends)", "vendor" in long_ and len(long_) < 130 and long_.startswith("…") and long_.rstrip().endswith("…"), long_)
    check("the empty Find window says notes can be searched", "note" in ev("() => { document.getElementById('searchInput').value = ''; renderSearch(); return document.getElementById('searchResults').textContent; }"))
    foot = ev("() => { const f = document.getElementById('searchFoot'); return [f.scrollHeight, f.clientHeight, f.getBoundingClientRect().height]; }")
    check("the Find window's footer stays on one line (the Replace… link, the hints and the count all fit)", foot[2] < 40, foot)
    pg.keyboard.press("Escape")
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
