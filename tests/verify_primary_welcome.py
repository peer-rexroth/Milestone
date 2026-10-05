# -*- coding: utf-8 -*-
"""One primary colour (UX review #10): commit buttons (OK, Save…) are the same blue as every active state, in both themes, with
white text that stays readable; green is left for status. And the first-run welcome in the folder dialog (isFirstRun(): a brand-new,
empty, never-linked install). See "One primary colour" and "First-run welcome" in CLAUDE.md."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
STUB = "window.showDirectoryPicker = async () => { throw new DOMException('x', 'AbortError'); }; delete window.showOpenFilePicker; delete window.showSaveFilePicker;"
NOFS = "delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker"
LUM = """(c) => { const m = c.match(/\\d+(\\.\\d+)?/g).map(Number); const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    # ================================================== primary colour (no file API: no blocking dialog)
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script(NOFS)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => { const b = document.createElement('button'); b.id = 'probePrimary'; b.className = 'btn btn-primary'; b.textContent = 'OK'; document.body.appendChild(b); const d = document.createElement('button'); d.id = 'probeDanger'; d.className = 'btn btn-primary btn-danger'; d.textContent = 'Delete'; document.body.appendChild(d); }")
    css = lambda sel, prop: ev("([s, p]) => getComputedStyle(document.querySelector(s))[p]", [sel, prop])
    for theme in ("light", "dark"):
        ev("(t) => { document.documentElement.setAttribute('data-theme', t === 'dark' ? 'dark' : ''); if (t !== 'dark') document.documentElement.removeAttribute('data-theme'); }", theme)
        pg.wait_for_timeout(100)
        bg, fg, ac, pr = css("#probePrimary", "backgroundColor"), css("#probePrimary", "color"), ev("() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"), ev("() => getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()")
        l1, l2 = ev(LUM, bg), ev(LUM, fg)
        ratio = (max(l1, l2) + .05) / (min(l1, l2) + .05)
        check(f"{theme}: a primary button is blue (not green) — its fill is --primary", bg == css("#probePrimary", "borderTopColor") and ev("(c) => { const m = c.match(/\\d+/g).map(Number); return m[2] > m[1] && m[2] > m[0]; }", bg), bg)
        check(f"{theme}: white text on it has contrast >= 4.5:1", ratio >= 4.5, round(ratio, 2))
        check(f"{theme}: a destructive confirm stays red", ev("(c) => { const m = c.match(/\\d+/g).map(Number); return m[0] > m[2] && m[0] > m[1]; }", css("#probeDanger", "backgroundColor")))
    ev("() => document.documentElement.removeAttribute('data-theme')")
    check("the light primary is the accent blue itself (one blue for toggles, tabs and commit buttons)", ev("() => getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() === getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"))
    check("green stays for status: a complete status pill is still green", ev("() => { const r = document.createElement('span'); r.className = 'status-pill st-complete'; document.body.appendChild(r); const m = getComputedStyle(r).color.match(/\\d+/g).map(Number); r.remove(); return m[1] > m[0] && m[1] > m[2]; }"))
    pg.hover("#probePrimary"); pg.wait_for_timeout(100)
    check("hover keeps it blue", ev("(c) => { const m = c.match(/\\d+/g).map(Number); return m[2] > m[1]; }", css("#probePrimary", "backgroundColor")))
    ev("() => { document.getElementById('probePrimary').disabled = true; }"); pg.hover("#probePrimary", force=True); pg.wait_for_timeout(100)
    check("disabled + hover keeps the fill (no white-on-white)", ev("(c) => { const m = c.match(/\\d+/g).map(Number); return m[2] > m[1] && m[2] > 150; }", css("#probePrimary", "backgroundColor")))
    check("no 'task-green' left behind a commit button in the stylesheet", "var(--task-green); border-color" not in ev("() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } }).filter(r => r.selectorText === '.btn-primary').map(r => r.cssText).join(' ')"))
    ctx.close()

    # ================================================== first-run welcome (a file API is present: the folder dialog opens)
    ctx = b.new_context(viewport={"width": 1100, "height": 700}); ctx.add_init_script(STUB)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#fileSyncModalBg.open"); ev = pg.evaluate
    check("brand-new install: the dialog is a welcome — 'Welcome to Milestone'", pg.inner_text("#fileSyncModalTitle") == "Welcome to Milestone")
    txt = pg.inner_text("#fileSyncModalText")
    check("...it asks where the plans should live, says nothing leaves the computer, and still has one main button", "Where should your plans live?" in txt and "nothing leaves your computer" in txt and "Choose folder" in pg.inner_text("#linkFolderBtn"))
    check("...it is still mandatory: no close button, Escape leaves it open", pg.locator("#fileSyncModalBg .modal-header button").count() == 0 and (pg.keyboard.press("Escape") or True) and ev("() => document.getElementById('fileSyncModalBg').classList.contains('open')"))
    check("cancelling the picker keeps the welcome", (pg.click("#linkFolderBtn") or True) and (pg.wait_for_timeout(300) or True) and pg.inner_text("#fileSyncModalTitle") == "Welcome to Milestone")
    pg.reload(); pg.wait_for_selector("#fileSyncModalBg.open")
    check("reloading before choosing a folder shows the welcome again (the flag is only set by a link)", pg.inner_text("#fileSyncModalTitle") == "Welcome to Milestone")
    ev("() => { fileSyncStatus = 'linked'; updateFileSyncUI(); }")
    check("once a plan is linked the welcome is remembered as seen", ev("() => localStorage.getItem('milestone-welcomed')") == "1" and ev("() => isFirstRun()") is False)
    ev("() => { fileSyncStatus = 'unlinked'; openFileSyncModal(); }")
    check("...so a later Disconnect shows the plain 'Choose a folder to continue'", pg.inner_text("#fileSyncModalTitle") == "Choose a folder to continue")
    ctx.close()
    # an existing install: a plan with tasks, never linked (the migrated Plan 1) gets the plain dialog
    ctx = b.new_context(viewport={"width": 1100, "height": 700}); ctx.add_init_script(STUB)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#fileSyncModalBg.open")
    ev = pg.evaluate
    ev("() => { tasks.push({ id: 'x1', name: 'Existing work', parentId: null, order: 0, startDate: '2030-03-04', endDate: '2030-03-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now() }); normalizeData(); save(); }")
    pg.reload(); pg.wait_for_selector("#fileSyncModalBg.open")
    check("an existing, unlinked plan that has tasks gets the plain dialog, not the welcome", pg.inner_text("#fileSyncModalTitle") == "Choose a folder to continue")
    ctx.close()
    b.close()

check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
