# -*- coding: utf-8 -*-
"""Plan settings after the tidy-up: the plan's name in every header, five tabs (Currency merged into Formats), a Formats page that applies at once with
'This plan' / 'This device' badges, Scheduling rules without the duplicated new-task mode and with the rare setting under Advanced, a Calendar tab
with the days-off list first and labelled holiday years. See "Plan settings" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => { historyCoalesceMs = 0; project.name = 'Website relaunch'; project.holidays = [{ date: '2030-12-25', name: 'Christmas', yearly: true }, { date: '2030-12-26', name: 'Boxing Day' }]; tasks.length = 0; normalizeData(); save(); render(); updateProjectNameUI(); resetHistory(); }")
    bg = lambda: ev("() => [...document.querySelectorAll('.modal-bg.open')].map(m => m.id)")
    pg.click("#planSettingsBtn"); pg.wait_for_selector(".modal-bg.open"); pg.wait_for_timeout(150)
    tabs = [t.strip() for t in pg.locator(".modal-bg.open .settings-tab").all_inner_texts()]
    check("five tabs: Calendar, Precision, Scheduling rules, Custom fields, Formats (Currency is part of Formats now)", tabs == ["Calendar", "Precision", "Scheduling rules", "Custom fields", "Formats"], tabs)
    check("the five tabs fit the 680px dialog without scrolling sideways", ev("() => { const t = document.querySelector('.modal-bg.open .settings-tabs'); return t.scrollWidth <= t.clientWidth; }"))
    # ================================================== plan name in every header
    names = {}
    for t, mid in (("calendar", "calendarModalBg"), ("precision", "precisionModalBg"), ("rules", "rulesModalBg"), ("fields", "fieldsModalBg"), ("format", "formatModalBg")):
        pg.click(f".modal-bg.open [data-settings-tab='{t}']"); pg.wait_for_timeout(150)
        names[t] = pg.inner_text(f"#{mid} .modal-header")
    check("every tab's header names the plan: 'Plan settings — Website relaunch'", all("Plan settings" in v and "— Website relaunch" in v for v in names.values()), names)
    ev("() => { project.name = 'Intranet'; save(); render(); updateProjectNameUI(); }"); pg.wait_for_timeout(100)
    check("...and follows a rename", "— Intranet" in pg.inner_text("#formatModalBg .modal-header"))
    ev("() => { project.name = 'A very long plan name that would push the title and the summary chip right out of the header of the dialog'; updateProjectNameUI(); }"); pg.click(".modal-bg.open [data-settings-tab='calendar']"); pg.wait_for_timeout(150)
    chip = ev("() => { const h = document.querySelector('#calendarModalBg .modal-header'), c = document.querySelector('#calendarModalBg .ps-plan'), x = document.querySelector('#calendarModalBg .modal-header > button'); return { cut: c.scrollWidth > c.clientWidth, closeVisible: x.getBoundingClientRect().right <= h.getBoundingClientRect().right + 1, h: h.getBoundingClientRect().height }; }")
    check("a very long name is cut with an ellipsis (the close button stays in place, the header stays one line)", chip["cut"] and chip["closeVisible"] and chip["h"] < 70, chip)
    ev("() => { project.name = 'Intranet'; updateProjectNameUI(); }")
    # ================================================== Calendar
    check("Calendar: the working week no longer repeats the plan's name (it is in the header now)", "of “" not in pg.inner_text("#calendarModalBg .cal-sec"))
    titles = [t.strip() for t in pg.locator("#calendarModalBg .cal-sec-title").all_inner_texts()]
    check("Calendar order: Working week, Days off in this plan (the list comes first), Public holidays, Another day off", [t.split("\n")[0] for t in titles][:4] == ["WORKING WEEK", "DAYS OFF IN THIS PLAN", "PUBLIC HOLIDAYS", "ANOTHER DAY OFF"] or [t.upper().split("\n")[0] for t in titles][:4] == ["WORKING WEEK", "DAYS OFF IN THIS PLAN", "PUBLIC HOLIDAYS", "ANOTHER DAY OFF"], titles)
    check("...the two holidays are listed before the forms (Christmas yearly, Boxing Day)", pg.locator("#holList .hol-row").count() == 2)
    ly = ev("() => [document.getElementById('holList').getBoundingClientRect().top, document.getElementById('holRegion').getBoundingClientRect().top, document.getElementById('holFrom').getBoundingClientRect().top]")
    check("...by position: list above the public-holiday form above the single-day form", ly[0] < ly[1] < ly[2], ly)
    labs = [l.strip() for l in pg.locator("#calendarModalBg .hol-preset label").all_inner_texts()]
    check("the public-holiday row has labels: Country or region, From year, To year", labs == ["Country or region", "From year", "To year"], labs)
    rowy = ev("() => { const m = id => { const r = document.getElementById(id).getBoundingClientRect(); return (r.top + r.bottom) / 2; }; const btn = document.querySelector('#calendarModalBg .hol-preset .btn').getBoundingClientRect(); return [m('holRegion'), m('holYearFrom'), m('holYearTo'), (btn.top + btn.bottom) / 2]; }")
    check("...and the region, both years and the button are still on one row (centres within 3px)", max(rowy) - min(rowy) < 3, rowy)
    # ================================================== Scheduling rules
    pg.click(".modal-bg.open [data-settings-tab='rules']"); pg.wait_for_timeout(150)
    check("Scheduling rules: just the Status date and, folded under Advanced, the constraint-dates switch — the new-task mode is gone (the Add menu has it)", pg.is_visible("#rulesStatusDateInput") and pg.locator("#rulesNewAuto").count() == 0 and pg.locator("#rulesNewManual").count() == 0 and not ev("() => document.getElementById('rulesAdv').open") and not pg.is_visible("#honorConstraintDatesInput"))
    check("...its explanations are one short line each", all(len(t) < 190 for t in pg.locator("#rulesModalBg .cal-hint").all_inner_texts()), [len(t) for t in pg.locator("#rulesModalBg .cal-hint").all_inner_texts()])
    pg.click("#rulesAdv summary"); pg.wait_for_timeout(100)
    check("opening Advanced shows the switch, on by default", pg.is_visible("#honorConstraintDatesInput") and pg.is_checked("#honorConstraintDatesInput"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("the Add menu still has the new-task mode (the one place for it)", ev("() => { return document.getElementById('newModeAuto') && document.getElementById('newModeManual') ? true : false; }"))
    # ================================================== Formats
    pg.click("#planSettingsBtn"); pg.click(".modal-bg.open [data-settings-tab='format']"); pg.wait_for_selector("#formatModalBg.open"); pg.wait_for_timeout(200)
    check("Formats: Currency first, then Dates and times; scope badges 'This plan' and 'This device'", [x.strip() for x in pg.locator("#formatModalBg .scope-badge").all_inner_texts()] == ["This plan", "This device"] and ev("() => document.querySelector('#formatModalBg .cal-sec-title').textContent.trim().startsWith('Currency')"))
    pg.select_option("#planCurrencyInput", "USD"); pg.wait_for_timeout(250)
    check("a currency applies at once, no Save (the plan, the preview, formatted money)", ev("() => project.currencyCode") == "USD" and "$" in pg.inner_text("#planCurrencyPreview") and "$" in ev("() => fmtCurrency(5)"))
    check("...as one Undo step", ev("() => { historyUndo(); return project.currencyCode; }") is None)
    pg.wait_for_timeout(150)
    check("...and Undo is reflected the next time the page is shown", ev("() => { renderFormatModal(); return document.getElementById('planCurrencyInput').value; }") == "EUR")
    fit = ev("() => [...document.querySelectorAll('#formatModalBg .fmt-tile b, #formatModalBg .fmt-tile small, #formatModalBg #fmtSystemBtn, #formatModalBg .fmt-cur select')].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.textContent.trim())")
    body = ev("() => { const m = document.querySelector('#formatModalBg .modal-body'); return [m.scrollHeight, m.clientHeight, m.scrollWidth, m.clientWidth]; }")
    check("the page shows everything without scrolling (currency, tiles, preview) and nothing is clipped", not fit and body[0] <= body[1] and body[2] <= body[3], (fit, body))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    # custom fields from the task dialog: stands alone, no plan chip
    ev("() => { tasks.push({ id: 'a', name: 'A', parentId: null, order: 0, startDate: '2030-03-04', endDate: '2030-03-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }); normalizeData(); save(); render(); openTaskModal('a'); }"); pg.wait_for_timeout(300)
    pg.click("#taskTabBtnCustom"); pg.click("#taskTabCustom .btn-link"); pg.wait_for_selector("#fieldsModalBg.open"); pg.wait_for_timeout(150)
    check("Custom fields opened over the task dialog stands alone: titled 'Custom fields', no tabs, no plan chip", pg.inner_text("#fieldsModalTitle") == "Custom fields" and pg.inner_text("#fieldsPlanChip") == "")
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
