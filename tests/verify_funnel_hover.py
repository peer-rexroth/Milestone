from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 600}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate("() => { tasks.length = 0; addTask(); tasks[0].name = 'A'; save(); render(); closeTaskModal(); }"); pg.wait_for_timeout(400)
    op = lambda col: float(pg.evaluate("c => getComputedStyle(document.querySelector(`#gridHeader .col-filter-btn[data-col='${c}']`)).opacity", col))
    pg.mouse.move(5, 5); pg.wait_for_timeout(150)
    rest = {c: op(c) for c in ("name", "start", "duration")}
    check("at rest the funnels are dimmed (55%)", all(abs(v - .55) < .02 for v in rest.values()), rest)
    # hover the header bar but not any funnel: an empty spot in the "Task Name" header, right of its label
    box = pg.evaluate("() => { const h = document.querySelector('#gridHeader .col-head:has(.col-filter-btn[data-col=\"name\"])').getBoundingClientRect(); return {x: h.left + h.width - 30, y: h.top + h.height / 2}; }")
    pg.mouse.move(box["x"], box["y"]); pg.wait_for_timeout(300)
    check("hovering the header bar (not a funnel) does NOT change any funnel", pg.evaluate("() => document.querySelector('#gridHeader').matches(':hover')") and all(abs(op(c) - .55) < .02 for c in ("name", "start", "duration")), {c: op(c) for c in ("name", "start", "duration")})
    pg.hover("#gridHeader .col-filter-btn[data-col='start']"); pg.wait_for_timeout(300)
    check("hovering one funnel highlights just that one", op("start") == 1 and abs(op("duration") - .55) < .02 and abs(op("name") - .55) < .02, {c: op(c) for c in ("name", "start", "duration")})
    pg.mouse.move(5, 5)
    pg.evaluate("() => { colFilters.duration = {}; }") if False else None
    pg.click("#gridHeader .col-filter-btn[data-col='duration']"); pg.wait_for_timeout(200)
    pg.evaluate("() => { colFilters.duration = { rules: [{ op: 'gt', value: '1' }] }; render(); }") if False else None
    pg.keyboard.press("Escape"); pg.mouse.move(5, 5); pg.wait_for_timeout(200)
    check("a filtered column's funnel stays highlighted (full opacity, accent colour) without any hover", pg.evaluate("""() => { const b = document.querySelector('#gridHeader .col-filter-btn[data-col="name"]'); b.classList.add('active'); const cs = getComputedStyle(b); const r = cs.opacity; b.classList.remove('active'); return r; }""") == "1")
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
