# -*- coding: utf-8 -*-
"""% complete can be edited in the list for a task without sub-tasks (not for a group, not for an empty line)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); editingCell = null; delete project.holidays; delete project.workDays; historyCoalesceMs = 0;
  const mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('g', 'Group', 0), mk('a', 'Alpha', 0, { parentId: 'g', progress: 20 }), mk('b', 'Beta', 1, { parentId: 'g', progress: 60 }), mk('c', 'Gamma', 1, { progress: 10 }), mk('m', 'Go live', 2, { milestone: true, startDate: '2026-09-11', endDate: '2026-09-11' }));
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    def fresh(): ev(SEED); pg.wait_for_timeout(120)
    cell = lambda id_: pg.locator(f".grid-row[data-id='{id_}'] [onclick*=\"'progress'\"]")
    prog = lambda id_: ev("(i) => byId(i).progress", id_)
    def type_(id_, text, key="Enter"):
        cell(id_).click(); pg.wait_for_timeout(200)
        pg.locator("#gridRows .inline-edit").fill(text); pg.keyboard.press(key); pg.wait_for_timeout(200)
    fresh()
    check("the % cell of a task is clickable (editable), a group's is not", cell("c").count() == 1 and cell("g").count() == 0 and "editable" in (pg.locator(".grid-row[data-id='c'] [onclick*=\"'progress'\"]").get_attribute("class") or ""))
    cell("c").click(); pg.wait_for_timeout(200)
    check("clicking opens a text box with the current value selected", pg.locator("#gridRows .inline-edit").count() == 1 and pg.input_value("#gridRows .inline-edit") == "10" and ev("() => { const i = document.querySelector('#gridRows .inline-edit'); return i === document.activeElement && i.selectionStart === 0 && i.selectionEnd === 2; }"))
    box = pg.locator("#gridRows .inline-edit").bounding_box(); col = ev("() => { const r = document.querySelector('.grid-row[data-id=\"c\"]').getBoundingClientRect(); return r.width; }")
    check("...the box fits its column (about 56px wide)", 30 <= box["width"] <= 60, box)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Escape cancels", prog("c") == 10 and pg.locator("#gridRows .inline-edit").count() == 0)
    type_("c", "75")
    check("typing 75 and Enter sets 75 %", prog("c") == 75 and "75%" in pg.inner_text(".grid-row[data-id='c']"), prog("c"))
    type_("c", "40%"); check("'40%' is accepted", prog("c") == 40, prog("c"))
    type_("c", "12,6"); check("'12,6' is accepted and rounded (13)", prog("c") == 13, prog("c"))
    type_("c", "0"); check("0 is fine", prog("c") == 0)
    type_("c", "100"); check("100 is fine", prog("c") == 100)
    type_("c", ""); check("an empty box leaves it as it was", prog("c") == 100)
    for bad in ["abc", "150", "-5", "101"]:
        type_("c", bad)
        check(f"'{bad}' is refused with a message and nothing changes", prog("c") == 100 and "between 0 and 100" in pg.inner_text("#toastMsg"), (prog("c"), pg.inner_text("#toastMsg")))
    type_("c", "55", key="Tab"); pg.wait_for_timeout(100)
    check("leaving the box (Tab / clicking away) saves it too", prog("c") == 55, prog("c"))
    cell("c").click(); pg.wait_for_timeout(200); pg.locator("#gridRows .inline-edit").fill("30"); pg.locator(".grid-row[data-id='a'] > div").first.click(); pg.wait_for_timeout(250)
    check("clicking on another row saves the edit", prog("c") == 30, prog("c"))
    type_("m", "100"); check("a milestone's % can be set", prog("m") == 100)
    # what follows from it
    type_("a", "100")
    check("the group's % is recomputed from its sub-tasks (Alpha 100 %, Beta 60 % → 80 %)", ev("() => Math.round(effectiveDates('g').progress)") == 80 and "80%" in pg.inner_text(".grid-row[data-id='g']"), ev("() => effectiveDates('g').progress"))
    check("...the group's cell has no editor, and starting one by code does nothing", (ev("() => { startInlineEdit('g', 'progress'); return !editingCell; }")))
    check("the edit is one undo step and stamps the task", ev("() => byId('a').updatedAt > 1"))
    ev("() => historyUndo()"); pg.wait_for_timeout(150)
    check("Undo takes it back (Alpha 20 %)", prog("a") == 20, prog("a"))
    ev("() => historyRedo()"); pg.wait_for_timeout(150); check("Redo brings it back", prog("a") == 100)
    check("no dates or links moved by a % edit", ev("() => tasks.every(t => t.startDate === '2026-09-07' || t.id === 'm')"))
    # empty line, Gantt view, filter
    ev("() => { const s = { id: 'sp', name: '', spacer: true, parentId: null, order: 9, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', resource: '', actualStart: null, actualFinish: null }; tasks.push(s); normalizeData(); render(); }")
    check("an empty line's % cell is blank and not editable", pg.locator(".grid-row[data-id='sp'] [onclick*=\"'progress'\"]").count() == 0 and ev("() => { startInlineEdit('sp', 'progress'); return !editingCell; }"))
    ev("() => setView('gantt')"); pg.wait_for_timeout(300)
    ev("() => { colHidden.delete('progress'); gColHidden.delete('progress'); render(); }"); pg.wait_for_timeout(150)
    if cell("c").count():
        type_("c", "66"); check("Gantt view: the % cell edits too, and the bar's fill follows", prog("c") == 66 and ev("() => document.querySelector(\".gantt-bar[data-id='c'] .fill\").style.width") == "66%", ev("() => document.querySelector(\".gantt-bar[data-id='c'] .fill\").style.width"))
    else: check("Gantt view: the % column can be shown", False)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
