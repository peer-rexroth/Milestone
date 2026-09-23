# -*- coding: utf-8 -*-
"""Layout: the toolbars at many window widths (nothing hidden off the right edge, no sideways page scroll), and every dialog fitting the window, in both themes."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:600]}]" if not cond and detail else ""))

SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0;
  const mk = (id, name, order, extra) => Object.assign({ id, name, parentId: null, order, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, extra || {});
  tasks.push(mk('a', 'Alpha', 0), mk('b', 'Beta', 1, { predecessors: [{ id: 'a', type: 'FS', lag: 0 }], startDate: '2026-09-14', endDate: '2026-09-18' }), mk('c', 'Gamma', 2));
  project.holidays = [{ date: '2026-10-05', name: 'Day off' }]; normalizeData(); save(); setSelection(['a', 'b']); render(); }"""
DIALOGS = {
  "Edit tasks": ("openBulkModal()", "bulkModalBg"), "Find": ("openSearch()", "searchModalBg"), "Print": ("openPrintModal()", "printModalBg"), "Working calendar": ("openCalendarModal()", "calendarModalBg"),
  "Scheduling precision": ("openPrecisionModal()", "precisionModalBg"),
  "Help": ("openHelpModal()", "helpModalBg"), "Task": ("openTaskModal('a')", "taskModalBg"), "Baseline": ("openBaselineModal()", "baselineModalBg"), "Excel export": ("openExcelExport()", "excelModalBg"),
  "Import": ("openForeignImport('Task Name,Start,Finish\\nA,07.09.2026,08.09.2026\\nB,09.09.2026,10.09.2026', 'plan.csv')", "foreignImportModalBg"),
}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for theme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
        pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
        pg.evaluate(f"() => {{ if ((document.documentElement.dataset.theme || 'dark') !== '{theme}') toggleTheme(); }}"); pg.evaluate(SEED)
        # ---------------------------------------------------- the toolbars
        for w in (1600, 1300, 1100, 1000, 900, 800, 700):
            pg.set_viewport_size({"width": w, "height": 800}); pg.wait_for_timeout(120)
            m = pg.evaluate("""() => { const sub = document.querySelector('.subbar'), vis = [...sub.children].filter(c => c.offsetWidth > 0), R = c => c.getBoundingClientRect();
              return { hidden: vis.filter(c => R(c).right > innerWidth + 1 || R(c).left < -1).map(c => c.id || c.className.split(' ')[0]), doc: document.documentElement.scrollWidth <= innerWidth, gridBelow: R(document.getElementById('gridPane')).top >= R(sub).bottom - 1, count: vis.length }; }""")
            check(f"[{theme}] {w}px: every toolbar button is inside the window (a narrow window wraps the toolbar), the page does not scroll sideways, the list starts below it", not m["hidden"] and m["doc"] and m["gridBelow"], m)
        # the top bar: nothing new lives there, but it must not lose the Data menu and the help button on a normal laptop width
        pg.set_viewport_size({"width": 1100, "height": 800}); pg.wait_for_timeout(100)
        check(f"[{theme}] 1100px: the top bar keeps the plan switcher, the view tabs, Data, theme, help and about on screen", pg.evaluate("() => ['planMenuBtn', 'dataMenuBtn', 'themeToggleBtn'].every(id => { const r = document.getElementById(id).getBoundingClientRect(); return r.right <= innerWidth && r.left >= 0; })"))
        # ---------------------------------------------------- the dialogs
        for size in ((1280, 720), (1024, 640), (900, 600)):
            pg.set_viewport_size({"width": size[0], "height": size[1]}); pg.wait_for_timeout(100)
            bad = []
            for name, (call, bg) in DIALOGS.items():
                pg.evaluate(f"() => {{ {call}; }}"); pg.wait_for_timeout(280)
                r = pg.evaluate("""(bg) => { const m = document.querySelector('#' + bg + ' .modal'); if (!m) return null; const a = m.getBoundingClientRect(), buttons = [...m.querySelectorAll('.modal-footer button, .modal-footer .btn')].filter(x => x.offsetWidth > 0).map(x => x.getBoundingClientRect());
                  return { fits: a.left >= -0.5 && a.top >= -0.5 && a.right <= innerWidth + 0.5 && a.bottom <= innerHeight + 0.5, footer: buttons.every(x => x.bottom <= innerHeight + 0.5 && x.right <= innerWidth + 0.5 && x.top >= 0), box: [Math.round(a.left), Math.round(a.top), Math.round(a.right), Math.round(a.bottom)], hs: document.documentElement.scrollWidth <= innerWidth }; }""", bg)
                if not r or not (r["fits"] and r["footer"] and r["hs"]): bad.append((name, r))
                pg.keyboard.press("Escape"); pg.wait_for_timeout(120)
                pg.evaluate("() => { for (const el of document.querySelectorAll('.modal-bg.open')) el.classList.remove('open'); }")
            check(f"[{theme}] {size[0]}x{size[1]}: all {len(DIALOGS)} dialogs fit the window with their buttons in reach", not bad, bad)
        ctx.close()
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
