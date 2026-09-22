import io
from PIL import Image
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:250]}]" if not cond and detail else ""))
lum = lambda px: 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]
def icon_contrast(png):
    """(direction, contrast) of the calendar icon at the right end of a date field against the field's background."""
    img = Image.open(io.BytesIO(png)).convert("RGB"); w, h = img.size
    bg = lum(img.getpixel((w // 2, 5))); ink = [lum(img.getpixel((x, y))) for x in range(w - 60, w - 8) for y in range(h)]
    dk, lt = bg - min(ink), max(ink) - bg
    return ("lighter" if lt > dk else "darker"), max(dk, lt)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); ctx = b.new_context(viewport={"width": 1300, "height": 900}, device_scale_factor=2); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate("""() => { tasks.length = 0; tasks.push({id: genId(), name: 'T', parentId: null, order: 0, startDate: '2026-09-19', endDate: '2026-09-22', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); colHidden.delete('actualStart'); save(); render(); }""")
    scheme = lambda: pg.evaluate("() => document.documentElement.style.colorScheme || getComputedStyle(document.documentElement).colorScheme")
    for theme, want in (("light", "light"), ("dark", "dark")):
        pg.evaluate("t => { theme = t; applyTheme(); }", theme); pg.wait_for_timeout(100)
        check(f"{theme} theme: the page declares color-scheme: {want}", scheme() == want, scheme())
        pg.evaluate("() => openTaskModal(tasks[0].id)"); pg.wait_for_selector("#taskModalBg.open"); pg.wait_for_timeout(250)
        bad = pg.evaluate("w => [...document.querySelectorAll('input[type=date]')].filter(i => getComputedStyle(i).colorScheme !== w).map(i => i.id || i.className)", want)
        check(f"{theme} theme: every date field (dialog, constraint, actuals) uses it", not bad, bad)
        for fid in ("taskStartInput", "taskEndInput", "taskActualStartInput", "taskActualFinishInput"):
            d, c = icon_contrast(pg.locator(f"#{fid}").screenshot())
            ok = (d == "darker") if theme == "light" else (d == "lighter" and c > 120)
            check(f"{theme} theme: the calendar icon in {fid} is {'dark on the light field' if theme == 'light' else 'light on the dark field (not black)'}", ok, (d, round(c)))
        pg.evaluate("() => closeTaskModal()")
    # the date editor inside the list, and the filter panel's date rule, in dark
    pg.evaluate("() => { theme = 'dark'; applyTheme(); }")
    pg.locator("#gridRows .grid-row").first.locator(":scope > div").nth(4).click(); pg.wait_for_selector(".inline-edit")
    check("dark theme: the inline date editor in the list too", pg.evaluate("() => getComputedStyle(document.querySelector('.inline-edit')).colorScheme") == "dark")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    pg.locator(".col-filter-btn[data-col='start']").click(); pg.wait_for_selector("#filterMenu.open"); pg.select_option("#filterRuleSel", "equals"); pg.wait_for_timeout(100)
    d, c = icon_contrast(pg.locator("#filterInputA").screenshot())
    check("dark theme: and the filter panel's date field", d == "lighter" and c > 120, (d, round(c)))
    pg.keyboard.press("Escape")
    # switching back restores the light look
    pg.evaluate("() => { theme = 'light'; applyTheme(); }"); pg.wait_for_timeout(100)
    check("switching back to light restores the light scheme", scheme() == "light")
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
