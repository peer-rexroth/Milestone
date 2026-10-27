# -*- coding: utf-8 -*-
"""Plan settings → Precision: the working-hours editor's spacing — the caption, the break list and the add row no longer touch; blocks 14px apart;
captions in the small semibold grey of a field label; the per-weekday section's note, rows and add row spaced; nothing scrolls. See "Precision page spacing"."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev("() => { project.timeUnit = 'minute'; normalizeData(); save(); render(); }")
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_selector("#calendarModalBg.open"); pg.wait_for_timeout(300)
    G = """() => { const R = s => document.querySelector('#calendarModalBg ' + s).getBoundingClientRect(), ed = R('#workHoursEditor');
      return { panelTop: R('.wh-day-row').top - R('.precision-opt:last-child').bottom, dayBottom: R('.wh-day-row').bottom, cap: R('.wh-breaks .wh-cap'), grp: R('.wh-breaks-grp'), det: R('#whDayDetails'), grpBottom: R('.wh-breaks-grp').bottom }; }"""
    g = ev(G)
    check("the working-hours rows sit 12–30px below the last precision option (groups, not a nested panel)", 12 <= g["panelTop"] <= 30, g["panelTop"])
    check("the 'Breaks' caption is one group-gap under the working-day row", 12 <= g["cap"]["top"] - g["dayBottom"] <= 26, g["cap"]["top"] - g["dayBottom"])
    check("the caption and the break group are 4–8px apart", 3 <= g["grp"]["top"] - g["cap"]["bottom"] <= 9, g["grp"]["top"] - g["cap"]["bottom"])
    check("the 'Different hours on some days' section is one group-gap under the break group", 12 <= g["det"]["top"] - g["grpBottom"] <= 26, g["det"]["top"] - g["grpBottom"])
    cap = ev("() => [...document.querySelectorAll('#calendarModalBg .wh-cap')].map(e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight])")
    check("the 'Breaks' caption uses the small semibold caption style (12px / 600)", cap == [["12px", "600"]], cap)
    check("the folded state fits the window (Calendar and the working hours share one page, so the body may scroll, never sideways) at 1400 × 860", ev("() => { const m = document.querySelector('#calendarModalBg .modal-body'); return m.scrollWidth <= m.clientWidth + 1 && m.closest('.modal').getBoundingClientRect().bottom <= innerHeight; }"))
    pg.click("#whDayDetails summary"); pg.wait_for_timeout(150); pg.select_option("#whDayAddSelect", "5"); pg.click("#whDayAddBtn"); pg.wait_for_timeout(200)
    o = ev("() => { const R = s => document.querySelector('#calendarModalBg ' + s).getBoundingClientRect(); return { sum: R('#whDayDetails summary'), note: R('#whDayDetails summary'), row: R('#whDayRows .whd-row'), add: R('#whDayAddRow') }; }")
    check("opened: the summary, the day row and the add row are each 4–14px apart", all(4 <= v <= 15 for v in (o["row"]["top"] - o["sum"]["bottom"], o["add"]["top"] - o["row"]["bottom"])), [o["row"]["top"] - o["sum"]["bottom"], o["add"]["top"] - o["row"]["bottom"]])
    check("...a day row stays on one line (it is 44px or less tall) and the page does not scroll sideways", ev("() => document.querySelector('#whDayRows .whd-row').getBoundingClientRect().height") < 44 and ev("() => { const m = document.querySelector('#calendarModalBg .modal-body'); return m.scrollWidth <= m.clientWidth + 1 && m.closest('.modal').getBoundingClientRect().bottom <= innerHeight; }"))
    # 12-hour clock: boxes fit
    ev("() => applyDisplayFormat('dd.mm.yyyy', '12h')"); pg.wait_for_timeout(200)
    fit = ev("() => ['whStart', 'whEnd', 'whBreakFrom', 'whBreakTo'].filter(i => { const e = document.getElementById(i); return e.scrollWidth > e.clientWidth + 1; })")
    check("in the 12-hour clock the working-hours boxes still show their whole text", not fit, fit)
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
