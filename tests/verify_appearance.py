# -*- coding: utf-8 -*-
"""The Appearance popover (the aA button in the sidebar's tools capsule), as in ClearDesk: Text Size (Small 90 / Medium 100 / Large 115 / Extra Large 130%),
Appearance (Light | Dark, only while Match System is off) and the Match System switch. Text size is a per-device pref in the prefs and zooms the window
(#window), not the menus and dialogs; the theme follows the system until a choice is made."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 860}, color_scheme="light"); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    pg.click("#themeToggleBtn"); pg.wait_for_selector("#appearanceMenu.open")
    check("the popover is ClearDesk's panel: 210px wide, a Text Size row of four sizes (Medium selected) and a Match System switch that is on", round(ev("() => document.getElementById('appearanceMenu').getBoundingClientRect().width")) == 210 and pg.locator("#appearanceMenu .ap-seg:not(.ap-two) .ap-btn").count() == 4 and pg.locator("#appearanceMenu .ap-seg:not(.ap-two) .ap-btn.on").count() == 1 and pg.get_attribute(".ap-match", "aria-checked") == "true")
    check("...with Match System on, Light | Dark stay visible but dimmed and disabled, the current look marked, and the row says 'Currently Light'", pg.locator("#appearanceMenu .ap-two.ap-off").count() == 1 and pg.locator("#appearanceMenu .ap-two .ap-btn:disabled").count() == 2 and pg.locator("#appearanceMenu .ap-two .ap-btn.on").inner_text().strip() == "Light" and "Currently Light" in pg.inner_text(".ap-match"))
    pg.click("#appearanceMenu .ap-seg:not(.ap-two) .ap-btn >> nth=2"); pg.wait_for_timeout(150)
    check("Large (115%) zooms the window, not the menu, and the popover stays open", ev("() => document.getElementById('window').style.zoom") == "1.15" and ev("() => document.getElementById('appearanceMenu').classList.contains('open')"))
    pg.reload(); pg.wait_for_selector("#undoBtn")
    check("the text size is remembered on this device", ev("() => document.getElementById('window').style.zoom") == "1.15" and ev("() => uiScale") == 1.15)
    ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    pg.click("#themeToggleBtn"); pg.wait_for_selector("#appearanceMenu.open"); pg.click(".ap-match"); pg.wait_for_timeout(150)
    check("switching Match System off enables Light | Dark and keeps the current look", pg.locator("#appearanceMenu .ap-two.ap-off").count() == 0 and pg.locator("#appearanceMenu .ap-two .ap-btn:disabled").count() == 0 and ev("() => themePref") == "light" and ev("() => document.documentElement.dataset.theme") == "light")
    pg.click("#appearanceMenu .ap-two .ap-btn >> nth=1"); pg.wait_for_timeout(150)
    check("Dark switches the theme and the choice is a saved preference", ev("() => document.documentElement.dataset.theme") == "dark" and ev("() => JSON.parse(localStorage.getItem('milestone-prefs')).themePref") == "dark")
    pg.click(".ap-match"); pg.wait_for_timeout(150)
    check("Match System back on returns to the system look (light here) and dims Light | Dark again", ev("() => themePref") == "auto" and ev("() => document.documentElement.dataset.theme") == "light" and pg.locator("#appearanceMenu .ap-two.ap-off").count() == 1)
    pg.mouse.click(150, 450); pg.wait_for_timeout(150)
    check("a click outside closes the popover", not ev("() => document.getElementById('appearanceMenu').classList.contains('open')"))
    check("no page errors", not errors, errors[:3])
n_ok, n_all = sum(results), len(results); print(f"\n{n_ok}/{n_all} checks passed"); raise SystemExit(0 if n_ok == n_all else 1)
