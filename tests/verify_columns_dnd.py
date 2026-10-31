# -*- coding: utf-8 -*-
"""Dragging a row in the Columns menu moves the column (Tasks / Gantt menu and the Resources menu), with an accent insertion line while dragging."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 1000}); ctx.add_init_script("localStorage.setItem('milestone-sidebar', '1'); delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    head = lambda: ev("() => [...document.querySelectorAll('#gridHeader .col-head')].map(h => h.querySelector('.col-resizer') ? h.querySelector('.col-resizer').dataset.col : null).filter(Boolean)")
    pg.click("#columnsBtn"); pg.wait_for_selector("#columnsMenu.open")
    check("every row of the Columns menu is draggable", ev("() => [...document.querySelectorAll('#columnsMenu .cols-row')].every(r => r.draggable)"))
    before = head()
    src, dst = pg.locator("#columnsMenu .cols-row[data-col-row='status']"), pg.locator("#columnsMenu .cols-row[data-col-row='start']")
    src.drag_to(dst, target_position={"x": 40, "y": 3}); pg.wait_for_timeout(200)
    after = head()
    check("dragging Status onto the top half of Start puts it just before Start", after.index("status") == after.index("start") - 1 and before.index("status") > before.index("start"), (before, after))
    pg.locator("#columnsMenu .cols-row[data-col-row='status']").drag_to(pg.locator("#columnsMenu .cols-row[data-col-row='progress']"), target_position={"x": 40, "y": 24}); pg.wait_for_timeout(200)
    after2 = head()
    check("dropping on the lower half of a row puts the column after it", after2.index("status") == after2.index("progress") + 1, after2)
    check("the menu stays open and the move is one saved choice", ev("() => document.getElementById('columnsMenu').classList.contains('open')") and ev("() => colOrder.indexOf('status') === colOrder.indexOf('progress') + 1"))
    check("no insertion line is left behind", ev("() => document.querySelectorAll('.cols-row.drop-before, .cols-row.drop-after, .cols-row.dragging').length") == 0)
    check("no page errors", not errors, errors[:3])
n_ok, n_all = sum(results), len(results); print(f"\n{n_ok}/{n_all} checks passed"); raise SystemExit(0 if n_ok == n_all else 1)
