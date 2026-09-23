# -*- coding: utf-8 -*-
"""Baseline…, Reschedule remaining work… and Working calendar… moved out of the plan (switcher) menu into their own
"Schedule" toolbar dropdown — an explicit user request ("is the plan dropdown overloaded?"): that menu had grown to
11+ items spanning switch/create/schedule/manage, with switching plans — its actual, most frequent job — sitting above
three dialog-openers. Scheduling precision… joined it later as its own dialog (moved out of Working calendar, again on
request, for its own discoverability). Same toggle/render/close shape as the Data and plan menus (mutual exclusivity,
click-outside, Escape)."""
import os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn")

    # ---------------------------------------------------------------- the split itself
    pg.click("#planMenuBtn"); pg.wait_for_selector("#planMenu.open")
    plan_items = pg.locator("#planMenu .dropdown-item").all_inner_texts()
    check("the plan menu no longer has Baseline / Reschedule / Working calendar", pg.locator("#planBaselineItem").count() == 0 and pg.locator("#planRescheduleItem").count() == 0 and pg.locator("#planCalendarItem").count() == 0, plan_items)
    check("...but still has New plan, Rename, Duplicate, Delete", any("New plan" in x for x in plan_items) and any("Rename plan" in x for x in plan_items) and any("Duplicate plan" in x for x in plan_items) and any("Delete plan" in x for x in plan_items), plan_items)
    pg.keyboard.press("Escape")

    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    sched_items = pg.locator("#scheduleMenu .dropdown-item").all_inner_texts()
    check("the Schedule menu has exactly Baseline, Reschedule remaining work, Working calendar, Scheduling precision, in that order",
          len(sched_items) == 4 and "Baseline" in sched_items[0] and "Reschedule remaining work" in sched_items[1] and "Working calendar" in sched_items[2] and "Scheduling precision" in sched_items[3], sched_items)
    check("Baseline's hint is there (not set at first)", "not set" in sched_items[0], sched_items[0])
    check("Working calendar's hint is there (Mon–Fri by default)", "Mon–Fri" in sched_items[2], sched_items[2])
    check("Scheduling precision's hint is there (Days by default)", "Days" in sched_items[3], sched_items[3])

    # ---------------------------------------------------------------- opening a dialog from it closes the menu, not the dialog
    pg.click("#planBaselineItem"); pg.wait_for_selector("#baselineModalBg.open")
    check("opening Baseline… from the Schedule menu closes the menu", pg.locator("#scheduleMenu.open").count() == 0)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes the dialog (not stuck open)", pg.locator("#baselineModalBg.open").count() == 0)

    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    pg.click("#planRescheduleItem"); pg.wait_for_selector("#rescheduleModalBg.open")
    check("opening Reschedule… also closes the Schedule menu", pg.locator("#scheduleMenu.open").count() == 0)
    pg.keyboard.press("Escape")

    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    pg.click("#planCalendarItem"); pg.wait_for_selector("#calendarModalBg.open")
    check("opening Working calendar… also closes the Schedule menu", pg.locator("#scheduleMenu.open").count() == 0)
    pg.keyboard.press("Escape")

    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    pg.click("#planPrecisionItem"); pg.wait_for_selector("#precisionModalBg.open")
    check("opening Scheduling precision… also closes the Schedule menu", pg.locator("#scheduleMenu.open").count() == 0)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes the precision dialog too", pg.locator("#precisionModalBg.open").count() == 0)

    # ---------------------------------------------------------------- mutual exclusivity, click-outside, Escape
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    pg.click("#dataMenuBtn"); pg.wait_for_selector("#dataMenu.open")
    check("opening Data closes an already-open Schedule menu", pg.locator("#scheduleMenu.open").count() == 0)
    pg.keyboard.press("Escape")

    pg.click("#dataMenuBtn"); pg.wait_for_selector("#dataMenu.open")
    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    check("...and the other way round: opening Schedule closes an already-open Data menu", pg.locator("#dataMenu.open").count() == 0)
    pg.click("body", position={"x": 5, "y": 400})
    pg.wait_for_timeout(100)
    check("clicking outside closes the Schedule menu", pg.locator("#scheduleMenu.open").count() == 0)

    pg.click("#scheduleMenuBtn"); pg.wait_for_selector("#scheduleMenu.open")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    check("Escape closes the Schedule menu", pg.locator("#scheduleMenu.open").count() == 0)

    check("no console errors or page errors across the whole run", not errors, errors[:5])
    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
