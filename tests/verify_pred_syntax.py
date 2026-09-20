# -*- coding: utf-8 -*-
"""The list's Predecessors cell reads links the way MS Project writes them (and the way paste/import read them): 3, 3FS, 3SS+2d, 4FF-1w, 4h, several
separated by , or ; and the German EA/AA/EE/AE. Elapsed and percentage lags are refused with a message. The label it writes back is unchanged (3FS+2)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); editingCell = null; delete project.holidays; delete project.workDays; historyCoalesceMs = 0;
  const mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('a', 'A', 0), mk('b', 'B', 1), mk('c', 'C', 2), mk('d', 'D', 3), mk('g', 'Group', 4), mk('k', 'Kid', 0, { parentId: 'g' }), mk('e', 'E', 5));
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(150)
    # ids: A=1 B=2 C=3 D=4 Group=5 Kid=6 E=7.  Parse for task D (#4).
    def parse(text): return ev("(t) => { const r = parsePredecessorString(t, 'd'); return r === null ? null : r.map(l => byId(l.id).name + ' ' + l.type + ' ' + l.lag); }", text)
    toast = lambda: pg.inner_text("#toastMsg")
    for text, want in [
        ("1", ["A FS 0"]), ("1FS", ["A FS 0"]), ("1fs", ["A FS 0"]), ("2SS+2", ["B SS 2"]), ("2SS+2d", ["B SS 2"]), ("2ss +2 days", ["B SS 2"]), ("2FF-1w", ["B FF -5"]), ("3SF-1 week", ["C SF -5"]),
        ("1FS+8h", ["A FS 1"]), ("1FS+16h", ["A FS 2"]), ("1FS+2 Tage", ["A FS 2"]), ("1FS+1 Woche", ["A FS 5"]), ("2FS+1,5d", None),
        ("1EA+1", ["A FS 1"]), ("1AA", ["A SS 0"]), ("2EE-1", ["B FF -1"]), ("3AE", ["C SF 0"]),
        ("1, 2FS+1", ["A FS 0", "B FS 1"]), ("1;2SS", ["A FS 0", "B SS 0"]), ("1; 2FS+1w, 3", ["A FS 0", "B FS 5", "C FS 0"]), ("1, 1SS", ["A FS 0"]), ("", []), ("  ", []),
    ]:
        got = parse(text)
        check(f"'{text}' → {want}" if want is not None else f"'{text}' (a decimal comma splits the list) is refused, not misread", got == want if want is not None else got is None, (got, toast()))
    ev(SEED); pg.wait_for_timeout(100)
    for text, needle in [("1FS+2ed", "Elapsed lags"), ("1FS+2ew", "Elapsed lags"), ("1FS+50%", "Percentage lags"), ("1FS+2xyz", "Can't read the lag"), ("1FS+99999d", "at most 9,999"), ("abc", "Can't parse"), ("1 2", "Can't parse"), ("1FS+", "Can't parse"),
                         ("99", "No task #99"), ("4", "can't depend on itself"), ("5", "summary task"), ("1, 2FS+2ed", "Elapsed lags")]:
        got = parse(text)
        check(f"'{text}' is refused with '{needle}…' — and says 'predecessors unchanged'", got is None and needle in toast() and "predecessors unchanged" in toast(), (got, toast()))
    # end to end through the cell
    def type_cell(name_id, text):
        pg.locator(f".grid-row[data-id='{name_id}'] [onclick*=\"'predecessors'\"]").click(); pg.wait_for_timeout(200)
        pg.locator("#gridRows .inline-edit").fill(text); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    type_cell("d", "1FS+1w; 2ss-2d")
    check("typed in the cell: '1FS+1w; 2ss-2d' → two links, in working days", ev("() => byId('d').predecessors.map(p => byId(p.id).name + ' ' + p.type + ' ' + p.lag).join()") == "A FS 5,B SS -2", ev("() => JSON.stringify(byId('d').predecessors)"))
    check("...the cell then shows the label as before ('1FS+5, 2SS-2') — the display did not change", "1FS+5, 2SS-2" in pg.inner_text(".grid-row[data-id='d']"), pg.inner_text(".grid-row[data-id='d']"))
    type_cell("d", "1FS+3ed")
    check("a refused edit changes nothing and the message shows", ev("() => byId('d').predecessors.length") == 2 and "Elapsed" in toast())
    type_cell("d", "")
    check("an empty cell clears the links", ev("() => byId('d').predecessors.length") == 0)
    type_cell("e", "3EA+2")
    check("German letters work in the cell (3EA+2 → Finish-to-Start, lag 2)", ev("() => JSON.stringify(byId('e').predecessors.map(p => [byId(p.id).name, p.type, p.lag]))") == '[["C","FS",2]]', ev("() => JSON.stringify(byId('e').predecessors)"))
    ev("() => startInlineEdit('a', 'predecessors')"); pg.wait_for_timeout(200)
    check("the cell's tooltip explains the syntax ('Like MS Project: 3, 3FS, 3SS+2d …')", "MS Project" in (pg.get_attribute("#gridRows .inline-edit", "title") or ""))
    pg.keyboard.press("Escape")
    # the reader used by paste / import is unchanged (it accepts the same and more)
    check("paste / import keep their own leniency (an unknown unit still reads as days there)", ev("() => { const r = parsePredText('1FS+2xyz'); return r.bad.length === 0 && r.links[0].lag === 2; }") and ev("() => parsePredText('1FS+2xyz', true).bad.length") == 1)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
