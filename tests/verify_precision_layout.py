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
    G = """() => { const R = s => document.querySelector('#calendarModalBg ' + s).getBoundingClientRect(); const ed = R('#workHoursEditor'), opt = R('#precisionMinute').bottom;
      return { panelTop: ed.top - R('.precision-opt:last-child').bottom, wd: R('.wh-day-row'), cap: R('.wh-breaks .wh-cap'), list: R('#whBreakList'), add: R('.wh-break-add'), det: R('#whDayDetails'), ed, padTop: R('.wh-day-row').top - ed.top, padBottom: ed.bottom - R('#whDayDetails').bottom }; }"""
    g = ev(G)
    check("the editor panel is 14px below the last option (it used to be 2px)", 12 <= g["panelTop"] <= 20, g["panelTop"])
    check("14px inside the panel at the top and at the bottom", 12 <= g["padTop"] <= 16 and 12 <= g["padBottom"] <= 16, (g["padTop"], g["padBottom"]))
    check("the 'Breaks' caption is 14px under the working-day row", 12 <= g["cap"]["top"] - g["wd"]["bottom"] <= 18, g["cap"]["top"] - g["wd"]["bottom"])
    check("the caption and the break list are 8px apart (they used to touch)", 6 <= g["list"]["top"] - g["cap"]["bottom"] <= 12, g["list"]["top"] - g["cap"]["bottom"])
    check("the break list and the add row are 8px apart (they used to touch)", 6 <= g["add"]["top"] - g["list"]["bottom"] <= 12, g["add"]["top"] - g["list"]["bottom"])
    check("the 'Different hours on some days' section is 14px under the add row, behind its own thin line", 12 <= g["det"]["top"] - g["add"]["bottom"] <= 18, g["det"]["top"] - g["add"]["bottom"])
    cap = ev("() => [...document.querySelectorAll('#calendarModalBg .wh-cap')].map(e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight])")
    check("both captions (Working day, Breaks) use the small semibold style of a field label (12px / 600), not the 13px regular body text", cap == [["12px", "600"], ["12px", "600"]], cap)
    check("the folded state fits the window (Calendar and the working hours share one page, so the body may scroll, never sideways) at 1400 × 860", ev("() => { const m = document.querySelector('#calendarModalBg .modal-body'); return m.scrollWidth <= m.clientWidth + 1 && m.closest('.modal').getBoundingClientRect().bottom <= innerHeight; }"))
    pg.click("#whDayDetails summary"); pg.wait_for_timeout(150); pg.select_option("#whDayAddSelect", "5"); pg.click("#whDayAddRow button"); pg.wait_for_timeout(200)
    o = ev("() => { const R = s => document.querySelector('#calendarModalBg ' + s).getBoundingClientRect(); return { sum: R('#whDayDetails summary'), note: R('#whDayDetails > .cal-sec-note'), row: R('#whDayRows .whd-row'), add: R('#whDayAddRow') }; }")
    check("opened: summary, note, the day row and the add row are each 8–14px apart", all(7 <= a <= 15 for a in (o["note"]["top"] - o["sum"]["bottom"], o["row"]["top"] - o["note"]["bottom"], o["add"]["top"] - o["row"]["bottom"])), [o["note"]["top"] - o["sum"]["bottom"], o["row"]["top"] - o["note"]["bottom"], o["add"]["top"] - o["row"]["bottom"]])
    check("...a day row stays on one line (it is 44px or less tall) and the page does not scroll sideways", ev("() => document.querySelector('#whDayRows .whd-row').getBoundingClientRect().height") < 44 and ev("() => { const m = document.querySelector('#calendarModalBg .modal-body'); return m.scrollWidth <= m.clientWidth + 1 && m.closest('.modal').getBoundingClientRect().bottom <= innerHeight; }"))
    # 12-hour clock: boxes fit
    ev("() => applyDisplayFormat('dd.mm.yyyy', '12h')"); pg.wait_for_timeout(200)
    fit = ev("() => ['whStart', 'whEnd', 'whBreakFrom', 'whBreakTo'].filter(i => { const e = document.getElementById(i); return e.scrollWidth > e.clientWidth + 1; })")
    check("in the 12-hour clock the working-hours boxes still show their whole text", not fit, fit)
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
