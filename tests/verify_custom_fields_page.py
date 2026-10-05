# -*- coding: utf-8 -*-
"""Plan settings → Custom fields, the rebuilt page: type cards when empty, a compact add row (with how many are left) afterwards, a column header,
the 'In list' switch (the Tasks view's columns, on this device), the slot meter, the one-line intro. See "Custom fields" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
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
    ctx = b.new_context(viewport={"width": 1440, "height": 860}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    def open_page():
        pg.click("#planSettingsBtn"); pg.wait_for_selector(".modal-bg.open"); pg.click(".modal-bg.open [data-settings-tab='fields']"); pg.wait_for_selector("#fieldsModalBg.open"); pg.wait_for_timeout(200)
    modal_open = lambda i: ev("(i) => document.getElementById(i).classList.contains('open')", i)
    # ================================================== empty
    ev(SEED, False); open_page()
    check("the intro is one line (no more paragraph about the Columns menu)", pg.inner_text("#fieldsModalBg .cal-hint") == "Extra information for your tasks, kept with this plan.")
    cards = pg.locator("#fieldsAdd .fld-card")
    check("with no field yet the four kinds are cards: Text, Number, Date, Yes / No — each with what it is for and an example", cards.count() == 4 and [c.split("\n")[0] for c in cards.all_inner_texts()] == ["Text", "Number", "Date", "Yes / No"] and all("e.g." in c for c in cards.all_inner_texts()), cards.all_inner_texts())
    check("...no column header, no meter, and the old 'Add field ▾' button is gone", not pg.is_visible("#fieldsHead") and pg.inner_text("#fieldsMeter") == "" and pg.locator("#fieldsAddBtn").count() == 0)
    fit = ev("() => [...document.querySelectorAll('#fieldsAdd .fld-card')].filter(c => c.scrollWidth > c.clientWidth + 1 || c.scrollHeight > c.clientHeight + 1).length")
    check("every card shows its whole text (nothing clipped)", fit == 0)
    pg.click("#fieldsAdd .fld-card[data-kind='text']"); pg.wait_for_timeout(120)
    check("clicking a card adds that field and puts the cursor in its name box (placeholder: an example name)", ev("() => document.activeElement.classList.contains('fld-name')") and pg.locator("#fieldsRows .fld-row").count() == 1 and pg.get_attribute("#fieldsRows .fld-name", "placeholder") == "Customer")
    check("...the page now has its column header (Type, Name, In list, Used) and the cards give way to a compact add row", pg.is_visible("#fieldsHead") and pg.inner_text("#fieldsHead").replace("\n", " ").upper().split() == ["TYPE", "NAME", "IN", "LIST", "USED"] and pg.locator("#fieldsAdd .fld-card").count() == 0 and pg.locator("#fieldsAdd .fld-chip").count() == 4)
    check("...each chip says how many of its kind are left (Text 4 left, the others 5)", [c.replace("\n", " ") for c in pg.locator("#fieldsAdd .fld-chip").all_inner_texts()] == ["Text 4 left", "Number 5 left", "Date 5 left", "Yes / No 5 left"], pg.locator("#fieldsAdd .fld-chip").all_inner_texts())
    check("...and the meter counts the fields: '1 of 20 possible fields in use — up to five of each kind.'", pg.inner_text("#fieldsMeter") == "1 of 20 possible fields in use — up to five of each kind.", pg.inner_text("#fieldsMeter"))
    check("a new field's 'In list' switch is on (you made it to use it), and its Used cell is empty", pg.locator("#fieldsRows .fld-show-in").is_checked() and pg.inner_text("#fieldsRows .fld-uses").strip() == "")
    pg.keyboard.type("Squad"); pg.click("#fieldsAdd .fld-chip[data-kind='number']"); pg.wait_for_timeout(120); pg.keyboard.type("Story points")
    pg.click("#fieldsAdd .fld-chip[data-kind='flag']"); pg.wait_for_timeout(120); pg.keyboard.type("Billable")
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
    check("the meter says 3 of 20 and the chips count what is left (Text 4, Number 4, Date 5, Yes / No 4)", pg.inner_text("#fieldsMeter").startswith("3 of 20") and [c.replace("\n", " ") for c in pg.locator("#fieldsAdd .fld-chip").all_inner_texts()] == ["Text 4 left", "Number 4 left", "Date 5 left", "Yes / No 4 left"], [c for c in pg.locator("#fieldsAdd .fld-chip").all_inner_texts()])
    pg.locator("#fieldsRows .fld-row").nth(1).locator(".fld-switch").click()
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("switching 'In list' counts as a change: closing asks 'Discard your changes?'", modal_open("confirmModalBg")); pg.click("#confirmModalBg button:has-text('Keep editing')"); pg.wait_for_timeout(100)
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
        pg.click("#fieldsAdd .fld-card[data-kind='text']" if i == 0 else "#fieldsAdd .fld-chip[data-kind='text']"); pg.wait_for_timeout(80); pg.keyboard.type(f"T{i}")
    check("all five of a kind used: its button is disabled and says 'all used', with a tooltip", pg.locator("#fieldsAdd .fld-chip[data-kind='text']").is_disabled() and "all used" in pg.locator("#fieldsAdd .fld-chip[data-kind='text']").inner_text() and "All five" in pg.get_attribute("#fieldsAdd .fld-chip[data-kind='text']", "title"))
    # layout
    lay = ev("() => { const b = document.querySelector('#fieldsModalBg .modal-body'); const rows = [...document.querySelectorAll('#fieldsRows .fld-row')]; return { bodyX: b.scrollWidth <= b.clientWidth + 1, rows: rows.every(r => r.scrollWidth <= r.clientWidth + 1), aligned: new Set(rows.map(r => Math.round(r.querySelector('.fld-name').getBoundingClientRect().left))).size === 1 && Math.abs(document.querySelector('#fieldsHead span:nth-child(2)').getBoundingClientRect().left - rows[0].querySelector('.fld-name').getBoundingClientRect().left) < 2 }; }")
    check("five rows fit the page: no sideways scroll, every row inside its width, the column header lines up with the name boxes", lay["bodyX"] and lay["rows"] and lay["aligned"], lay)
    pg.click("#fieldsModalBg .modal-footer .btn:has-text('Cancel')"); pg.wait_for_timeout(100)
    if modal_open("confirmModalBg"): pg.click("#confirmModalBg button:has-text('Discard')"); pg.wait_for_timeout(150)
    # narrow
    ev(SEED, False); pg.set_viewport_size({"width": 720, "height": 700}); open_page()
    fit = ev("() => [...document.querySelectorAll('#fieldsAdd .fld-card')].filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.textContent.trim().slice(0, 12))")
    check("in a 720px window the four cards still show their whole text", not fit, fit)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100); pg.set_viewport_size({"width": 1440, "height": 860})
    # the task dialog's own Add field menu is unchanged
    ev(SEED, False); ev("() => openTaskModal('a')"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(300); pg.click("#taskTabBtnCustom"); pg.wait_for_timeout(150)
    pg.click("#cfAddBtn"); pg.wait_for_timeout(120)
    check("the task dialog's Custom tab keeps its own 'Add field ▾' menu (by type)", pg.locator("#cfAddMenu .dropdown-item").count() == 4)
    pg.keyboard.press("Escape"); pg.keyboard.press("Escape")
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
