# -*- coding: utf-8 -*-
"""Plan settings → Custom fields, the rebuilt page: type cards when empty, a compact add row (with how many are left) afterwards, a column header,
the 'In list' switch (the Tasks view's columns, on this device), the slot meter, the one-line intro. See "Custom fields" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """(withFields) => { historyCoalesceMs = 0; delete project.fieldNames; tasks.length = 0; let o = 0;
  const mk = (id, name, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: '2030-03-04', endDate: '2030-03-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1 }, x || {});
  tasks.push(mk('a', 'A', withFields ? { custom: { text1: 'Web', number1: 5 } } : {}), mk('b', 'B', withFields ? { custom: { text1: 'App', flag1: true } } : {}));
  if (withFields) project.fieldNames = { text1: 'Squad', number1: 'Story points', flag1: 'Billable' };
  for (const id of Object.keys(CUSTOM_FIELDS)) { colHidden.add(id); gColHidden.add(id); }
  normalizeData(); save(); render(); resetHistory(); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 860}); ctx.add_init_script("localStorage.setItem('milestone-sidebar', '0'); delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    def open_page():
        pg.click("#planSettingsBtn"); pg.wait_for_selector(".modal-bg.open"); pg.click(".modal-bg.open [data-settings-tab='fields']"); pg.wait_for_selector("#fieldsModalBg.open"); pg.wait_for_timeout(200)
    modal_open = lambda i: ev("(i) => document.getElementById(i).classList.contains('open')", i)
    def add(kind): pg.click("#fieldsAdd .fld-addbtn"); pg.wait_for_timeout(60); pg.click(f"#cfAddMenu [data-kind='{kind}']"); pg.wait_for_timeout(80)
    # ================================================== empty
    ev(SEED, False); open_page()
    check("the empty page says 'No Custom Fields' with one Add Field button (no paragraph, no cards)", "No Custom Fields" in pg.inner_text("#fieldsAdd") and pg.locator("#fieldsAdd .fld-addbtn").count() == 1 and pg.locator("#fieldsModalBg .cal-hint").count() == 0 and pg.locator("#fieldsAdd .fld-card").count() == 0)
    pg.click("#fieldsAdd .fld-addbtn"); pg.wait_for_timeout(100)
    kinds = pg.locator("#cfAddMenu .dropdown-item").all_inner_texts()
    check("the button opens a menu of the four kinds: Text, Number, Date, Yes / No", [k.split("\n")[0] for k in kinds] == ["Text", "Number", "Date", "Yes / No"], kinds)
    ev("() => closeCfAddMenu()"); pg.wait_for_timeout(100)
    check("...no column header, no meter, and the old 'Add field ▾' button is gone", pg.locator("#fieldsHead").count() == 0 and pg.locator("#fieldsMeter").count() == 0 and pg.locator("#fieldsAddBtn").count() == 0)
    add('text')
    check("choosing a kind adds that field and puts the cursor in its name box (placeholder: Name)", ev("() => document.activeElement.classList.contains('fld-name')") and pg.locator("#fieldsRows .fld-row").count() == 1 and pg.get_attribute("#fieldsRows .fld-name", "placeholder") == "Name")
    check("...the rows are one tinted group, followed by an 'Add Field…' row", pg.locator("#fieldsRows.tgrp").count() == 1 and "Add Field" in pg.inner_text("#fieldsAdd .tadd"))
    pg.click("#fieldsAdd .fld-addbtn"); pg.wait_for_timeout(100)
    check("...the menu says how many of a kind are left only when none are (Text is still free)", all(not b.is_disabled() for b in pg.locator("#cfAddMenu .dropdown-item").all()))
    ev("() => closeCfAddMenu()"); pg.wait_for_timeout(100); pg.locator("#fieldsRows .fld-name").last.click()

    check("a new field's 'In list' switch is on (you made it to use it), and its Used cell is empty", pg.locator("#fieldsRows .fld-show-in").is_checked() and pg.inner_text("#fieldsRows .fld-uses").strip() == "")
    pg.keyboard.type("Squad"); add('number'); pg.keyboard.type("Story points")
    add('flag'); pg.keyboard.type("Billable")
    pg.locator("#fieldsRows .fld-row").nth(2).locator(".fld-switch").click()
    check("the switch toggles (Billable off)", not pg.locator("#fieldsRows .fld-row").nth(2).locator(".fld-show-in").is_checked())
    pg.click("#fieldsModalBg .btn-primary"); pg.wait_for_timeout(300)
    names = ev("() => project.fieldNames")
    check("Save creates the three fields", names == {"text1": "Squad", "number1": "Story points", "flag1": "Billable"}, names)
    hidden = ev("() => ['text1', 'number1', 'flag1'].map(id => colHidden.has(id))")
    check("...and the switch decided the Tasks list: Squad and Story points are columns now, Billable (switched off) is not", hidden == [False, False, True], hidden)
    check("...the columns are really in the list header", "SQUAD" in pg.inner_text("#gridHeader").upper() and "STORY POINTS" in pg.inner_text("#gridHeader").upper() and "BILLABLE" not in pg.inner_text("#gridHeader").upper())
    check("...the Gantt view's own column set is untouched (still hidden there)", ev("() => ['text1', 'number1', 'flag1'].every(id => gColHidden.has(id))"))
    # ================================================== existing fields
    ev(SEED, True); ev("() => { colHidden.delete('text1'); save(); render(); }"); open_page()
    rows = ev("() => [...document.querySelectorAll('#fieldsRows .fld-row')].map(r => [r.querySelector('.fld-kind').innerText.trim(), r.querySelector('.fld-name').value, r.querySelector('.fld-show-in').checked, r.querySelector('.fld-uses').innerText.trim()])")
    check("existing fields list with kind, name, their 'In list' state as it is now (Squad shown, the others hidden) and how many tasks use them", rows == [["Text", "Squad", True, "2 tasks"], ["Number", "Story points", False, "1 task"], ["Yes / No", "Billable", False, "1 task"]], rows)

    pg.locator("#fieldsRows .fld-row").nth(1).locator(".fld-switch").click()
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("the rows give the name the room: it is the widest part, and kind, usage, switch and remove line up from row to row", ev("() => { const rows = [...document.querySelectorAll('#fieldsRows .fld-row')]; if (rows.length < 2) return true; const x = (r, s) => Math.round(r.querySelector(s).getBoundingClientRect().x); return rows[0].querySelector('.fld-name').getBoundingClientRect().width > 150 && ['.fld-kind', '.fld-show', '.fld-remove'].every(s => rows.every(r => Math.abs(x(r, s) - x(rows[0], s)) <= 1)); }"))
    check("switching 'In list' counts as a change: closing asks 'Discard your changes?'", modal_open("confirmModalBg")); pg.click("#confirmModalBg button:has-text('Keep Editing')"); pg.wait_for_timeout(100)
    pg.click("#fieldsModalBg .btn-primary"); pg.wait_for_timeout(250)
    check("saving applies it: Story points is a column now; Squad (unchanged) still is", ev("() => [colHidden.has('number1'), colHidden.has('text1')]") == [False, False])
    ev("() => { openFieldsModal(); }"); pg.wait_for_selector("#fieldsModalBg.open"); pg.wait_for_timeout(150)
    pg.locator("#fieldsRows .fld-row").nth(0).locator(".fld-switch").click(); pg.click("#fieldsModalBg .btn-primary"); pg.wait_for_timeout(250)
    check("and switching one off hides that column again (Squad), nothing else moves", ev("() => [colHidden.has('text1'), colHidden.has('number1'), colHidden.has('flag1')]") == [True, False, True])
    ev("() => { openFieldsModal(); }"); pg.wait_for_selector("#fieldsModalBg.open"); pg.wait_for_timeout(150)
    pg.locator("#fieldsRows .fld-row").nth(2).locator(".fld-remove").click(); pg.wait_for_timeout(100)
    check("a row marked for removal dims its switch (it can't be changed) and the note says how many will go", "none" in ev("() => getComputedStyle(document.querySelector('#fieldsRows .fld-row.removed .fld-show')).pointerEvents") and "1 field will be removed" in pg.inner_text("#fieldsNote"))
    pg.click("#fieldsModalBg .modal-footer .btn:has-text('Cancel')"); pg.wait_for_timeout(150)
    # full kind
    ev(SEED, False); open_page()
    for i in range(5):
        add('text'); pg.keyboard.type(f"T{i}")
    pg.click("#fieldsAdd .fld-addbtn"); pg.wait_for_timeout(100)
    check("all five of a kind used: its menu row is disabled and says 'all 5 in use'", pg.locator("#cfAddMenu [data-kind='text']").is_disabled() and "all 5 in use" in pg.locator("#cfAddMenu [data-kind='text']").inner_text())
    ev("() => closeCfAddMenu()"); pg.wait_for_timeout(100)
    # layout
    lay = ev("() => { const b = document.querySelector('#fieldsModalBg .modal-body'); const rows = [...document.querySelectorAll('#fieldsRows .fld-row')]; return { bodyX: b.scrollWidth <= b.clientWidth + 1, rows: rows.every(r => r.scrollWidth <= r.clientWidth + 1), aligned: new Set(rows.map(r => Math.round(r.querySelector('.fld-name').getBoundingClientRect().left))).size === 1 }; }")
    check("five rows fit the page: no sideways scroll, every row inside its width, the name fields line up", lay["bodyX"] and lay["rows"] and lay["aligned"], lay)
    pg.click("#fieldsModalBg .modal-footer .btn:has-text('Cancel')"); pg.wait_for_timeout(100)
    if modal_open("confirmModalBg"): pg.click("#confirmModalBg button:has-text('Discard')"); pg.wait_for_timeout(150)
    # narrow
    ev(SEED, False); pg.set_viewport_size({"width": 720, "height": 700}); open_page()
    fit = ev("() => [...document.querySelectorAll('#fieldsRows .fld-row, #fieldsAdd .empty-state')].filter(c => c.scrollWidth > c.clientWidth + 1).length")
    check("in a 720px window the four cards still show their whole text", not fit, fit)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100); pg.set_viewport_size({"width": 1440, "height": 860})
    ev(SEED, False); ev("() => openTaskModal('a')"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(300); pg.click("#taskTabBtnCustom"); pg.wait_for_timeout(150)
    pg.keyboard.press("Escape"); pg.keyboard.press("Escape")
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
