# -*- coding: utf-8 -*-
"""Find and replace (Ctrl+H): the dialog, the live preview, scopes, fields, match case / whole cell, regex characters taken literally, empty names refused,
resource rewriting through the Task Type triangle, notes and custom fields, one undo step, the Find palette link. See "Find and replace" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """() => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.timeUnit; delete project.fieldNames; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }, x || {});
  tasks.push(mk('g', 'Phase 1', '2030-03-04', '2030-03-15'),
    mk('a', 'Design review', '2030-03-04', '2030-03-08', { parentId: 'g', resource: 'Anna, Ben', notes: 'Review with Anna and the review board' }),
    mk('b', 'Build (v1.0)', '2030-03-11', '2030-03-15', { parentId: 'g', resource: 'Anna[50%]', custom: { text1: 'Team A' } }),
    mk('c', 'Test Review', '2030-03-18', '2030-03-19', { custom: { text1: 'Team B' } }),
    mk('d', 'review', '2030-03-20', '2030-03-21'));
  tasks.push(mk('sp', '', '2030-03-04', '2030-03-04', { spacer: true }));
  project.fieldNames = { text1: 'Squad' };
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(250)
    name = lambda i: ev("(i) => tasks.find(t => t.id === i).name", i)
    isopen = lambda: ev("() => document.getElementById('replaceModalBg').classList.contains('open')")
    def fill(find=None, with_=None, field=None, case=None, whole=None, scope=None):
        if find is not None: pg.fill("#frFind", find)
        if with_ is not None: pg.fill("#frWith", with_)
        if field: pg.select_option("#frField", field)
        if case is not None: pg.set_checked("#frCase", case)
        if whole is not None: pg.set_checked("#frWhole", whole)
        if scope: pg.check(f"input[name='frScope'][value='{scope}']")
        pg.wait_for_timeout(80)
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(250)
    check("Ctrl+H opens Find and replace, with the cursor in Find", isopen() and ev("() => document.activeElement.id") == "frFind")
    check("the 'In' list offers Task Name, Resource, Notes and the custom text field in use (by its plan name)", pg.locator("#frField option").all_inner_texts() == ["Task Name", "Resource", "Notes", "Squad"], pg.locator("#frField option").all_inner_texts())
    check("with nothing typed the button is disabled and the hint says what to do", pg.is_disabled("#frBtn") and "Type the text to find" in pg.inner_text("#frHint"))
    check("with one or no selection and no filter there is no scope question", not pg.is_visible("#frScopeBlock"))
    fill(find="review", with_="X")
    check("case-insensitive by default: 'review' matches Design review, Test Review and review (3 tasks, 3 matches)", "3 matches in 3 tasks" in pg.inner_text("#frHint"), pg.inner_text("#frHint"))
    check("the preview lists them in outline order with struck-out matches and the inserted text", pg.locator("#frList .rs-row").count() == 3 and pg.locator("#frList mark").count() == 3, pg.inner_text("#frList"))
    fill(case=True)
    check("Match case: only the lower-case ones (Design review, review) = 2", "2 matches in 2 tasks" in pg.inner_text("#frHint"), pg.inner_text("#frHint"))
    fill(case=False, whole=True)
    check("Match the whole cell: only the task named exactly 'review' (any case)", "1 match in 1 task" in pg.inner_text("#frHint"), pg.inner_text("#frHint"))
    fill(whole=False, find="(v1.0)", with_="[v2]")
    check("regular-expression characters are plain text: '(v1.0)' finds exactly 'Build (v1.0)'", "1 match in 1 task" in pg.inner_text("#frHint"), pg.inner_text("#frHint"))
    fill(find="Build", with_="$& $1 \\\\n")
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("the replacement is literal too ('$&' stays '$&')", name("b").startswith("$& $1 \\\\n"), name("b"))
    ev("() => historyUndo()"); pg.wait_for_timeout(200)
    check("...and Undo restores it", name("b") == "Build (v1.0)", name("b"))
    # a real replace
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    fill(find="review", with_="check", field="name")
    check("Replace button says how many matches", "Replace 3 matches" in pg.inner_text("#frBtn"), pg.inner_text("#frBtn"))
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("Replace all changes every match (keeping the rest of the name)", [name("a"), name("c"), name("d")] == ["Design check", "Test check", "check"], [name("a"), name("c"), name("d")])
    check("the dialog closed and the toast says how many, and that Ctrl/Cmd+Z undoes it", not isopen() and "Replaced 3 matches in 3 tasks" in ev("() => document.getElementById('toastMsg').textContent") and "undoes" in ev("() => document.getElementById('toastMsg').textContent"))
    st = ev("() => Object.fromEntries(tasks.map(t => [t.id, t.updatedAt]))")
    check("untouched tasks keep their stamp; changed ones are re-stamped (so a sync carries them)", st["b"] < st["a"] and st["a"] == st["c"] == st["d"] and st["a"] > 1000, st)
    ev("() => historyUndo()"); pg.wait_for_timeout(200)
    check("one Undo step brings all three names back", [name("a"), name("c"), name("d")] == ["Design review", "Test Review", "review"], [name("a"), name("c"), name("d")])
    # empty name refused
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    fill(find="review", with_="", field="name", whole=True, case=False)
    check("a replacement that would empty a name skips that task and says so", "skipped" in pg.inner_text("#frHint") and pg.is_disabled("#frBtn"), pg.inner_text("#frHint"))
    check("...the preview names the skipped task", "would be empty" in pg.inner_text("#frList"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Escape closes it", not isopen())
    # resource
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    fill(find="Anna", with_="Anne", field="resource", whole=False)
    check("Resource: 'Anna' is in two tasks (Anna, Ben and Anna[50%])", "2 matches in 2 tasks" in pg.inner_text("#frHint"), pg.inner_text("#frHint"))
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("a resource share keeps its percentage: 'Anne, Ben' and 'Anne[50%]'", ev("() => [tasks.find(t => t.id === 'a').resource, tasks.find(t => t.id === 'b').resource]") == ["Anne, Ben", "Anne[50%]"])
    check("the pool gained 'Anne' by itself (the usual auto-populate)", "Anne" in ev("() => (project.resources || []).map(r => r.name)"))
    # notes
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    fill(find="board", with_="committee", field="notes", whole=False)
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("Notes work too", ev("() => tasks.find(t => t.id === 'a').notes") == "Review with Anna and the review committee")
    # custom text field
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    fill(find="Team", with_="Squad", field="text1")
    check("a custom text field is replaced by its plan name 'Squad' in the list", "2 matches in 2 tasks" in pg.inner_text("#frHint"))
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("...and the values changed", ev("() => [tasks.find(t => t.id === 'b').custom.text1, tasks.find(t => t.id === 'c').custom.text1]") == ["Squad A", "Squad B"])
    # clearing a custom value via whole cell with empty replacement
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    fill(find="Squad B", with_="", field="text1", whole=True)
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("replacing a custom value with nothing clears it (the key is gone)", ev("() => !('custom' in tasks.find(t => t.id === 'c')) || !('text1' in tasks.find(t => t.id === 'c').custom)"))
    # selected scope
    ev("() => { setSelection(['a', 'c']); render(); }")
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    check("with two or more selected, the scope question appears, defaulting to the selection", pg.is_visible("#frScopeBlock") and ev("() => document.querySelector('input[name=frScope]:checked').value") == "selected")
    fill(find="e", with_="E", field="name", case=True, whole=False)
    pg.click("#frBtn"); pg.wait_for_timeout(250)
    check("only the selected tasks changed ('Design review' and 'Test check' got capital E; 'review' untouched)", "E" in name("a") and name("d") == "review", [name("a"), name("c"), name("d")])
    # filter scope
    ev("() => { setSelection([]); colFilters.name = { type: 'values', values: new Set(['review']), blanks: false }; render(); }")
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    check("with a filter on, 'Only the N tasks matching the current filter' is offered", pg.is_visible("#frScopeFilteredRow"))
    fill(find="view", with_="VIEW", field="name", case=True, scope="filtered")
    check("...and the preview is limited to them", "1 match in 1 task" in pg.inner_text("#frHint"), pg.inner_text("#frHint"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    ev("() => { for (const k of Object.keys(colFilters)) colFilters[k] = null; render(); }")
    # find palette link
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(250); pg.fill("#searchInput", "Test"); pg.wait_for_timeout(150)
    check("the Find window has a 'Find and replace…' link", pg.locator("#searchFoot button:has-text('Replace')").count() == 1)
    pg.click("#searchFoot button:has-text('Replace')"); pg.wait_for_timeout(250)
    check("it opens the dialog with what was typed in Find already filled in, and closes the palette", isopen() and pg.input_value("#frFind") == "Test" and not ev("() => document.getElementById('searchModalBg').classList.contains('open')"))
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(150)
    check("Ctrl+H again closes it", not isopen())
    # shortcuts sheet
    ev("() => document.activeElement && document.activeElement.blur()"); pg.keyboard.press("?"); pg.wait_for_timeout(200)
    check("the shortcuts sheet lists Ctrl+H", "Find and replace" in pg.inner_text("#shortcutsBody"))
    pg.keyboard.press("Escape")
    # empty plan
    ev("() => { tasks.length = 0; save(); render(); }")
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(200)
    check("with no tasks it says so and doesn't open", not isopen() and "Nothing to replace" in ev("() => document.getElementById('toastMsg').textContent"))
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
