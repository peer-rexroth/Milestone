"""The Print dialog's layout: the custom range is two ordinary rows (From, To) that stay inside their group card, the option list has a hairline under the title,
and the picture group sits left of Cancel / Print without a floating note."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1400, "height": 860}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => openPrintModal()"); pg.wait_for_timeout(400)
    box = lambda sel: ev("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; }", sel)
    ev("() => document.getElementById('printFrom').scrollIntoView({block: 'center'})"); pg.wait_for_timeout(100)
    grp = ev("() => { const r = document.getElementById('printFrom').closest('.tgrp').getBoundingClientRect(); return [r.left, r.right]; }")
    for id_ in ("printFrom", "printTo"):
        wrap = ev("(i) => { const w = document.getElementById(i).closest('.dt-wrap') || document.getElementById(i); const r = w.getBoundingClientRect(); return [r.left, r.right]; }", id_)
        check(f"#{id_} and its calendar icon stay inside the group card", wrap[0] >= grp[0] and wrap[1] <= grp[1] + 0.5, (wrap, grp))
    lab = ev("() => { const f = document.querySelector('label[for=printFrom]').getBoundingClientRect(), i = document.getElementById('printFrom').getBoundingClientRect(); return [f.right, i.left]; }")
    check("the From label does not overlap its field", lab[0] <= lab[1] + 0.5, lab)
    check("From and To are separate rows", box("label[for=printFrom]")[3] <= box("label[for=printTo]")[2] + 1)
    check("focusing a date picks the custom range", ev("() => { document.getElementById('printFrom').focus(); return document.getElementById('printRangeCustom').checked; }"))
    hd = ev("() => { const h = document.querySelector('#printModalBg .modal-header').getBoundingClientRect(), l = document.querySelector('.print-layout'); return [h.bottom, l.getBoundingClientRect().top, getComputedStyle(l).borderTopWidth]; }")
    check("a hairline separates the title from the scrolling options", hd[2] == "1px" and hd[1] >= hd[0] - 0.5, hd)
    check("'% Complete' is written like the other column names", "% Complete" in ev("() => document.querySelector('label.trow:has(#printCol-progress)').textContent"))
    ft = ev("() => { const f = document.querySelector('#printModalBg .modal-footer'); return [...f.children].map(c => c.className || c.id || c.tagName); }")
    check("the footer has the picture group, then Cancel and Print (no note text)", ev("() => document.querySelector('#printModalBg .print-tip').textContent.trim()") == "" and ev("() => document.getElementById('printGo').getBoundingClientRect().right <= document.querySelector('#printModalBg .modal').getBoundingClientRect().right"), ft)
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
