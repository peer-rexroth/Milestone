from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))

SEED = """(cfg) => { tasks.length = 0; selectedTaskId = null;
  cfg.forEach((c, i) => tasks.push({id: genId(), name: c[0], parentId: null, order: i, startDate: c[1], endDate: c[2], progress: 30, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}));
  zoom = 'week'; currentView = 'gantt'; save(); render(); }"""
CFG = [["Kickoff", "2026-09-07", "2026-09-11"], ["Build", "2026-10-05", "2026-12-18"], ["Rollout", "2027-01-04", "2027-02-26"], ["Review", "2027-03-01", "2027-04-30"]]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for loc in ("de-DE", "en-US"):
        ctx = b.new_context(viewport={"width": 1300, "height": 520}, locale=loc, device_scale_factor=2)
        ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
        pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; }")
        pg.evaluate(SEED, CFG); pg.wait_for_timeout(200)
        print(f"--- locale {loc} ---")

        # ISO week numbers: every Monday and every other weekday, 2019-2032, against an independent reference
        bad = pg.evaluate("""() => { const ref = d => { const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())); const dn = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - dn); const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1)); return [Math.ceil((((t - y0) / 86400000) + 1) / 7), t.getUTCFullYear()]; };
            const bad = []; for (let dn = dayNumber('2019-01-01'); dn <= dayNumber('2032-12-31'); dn++) { const r = ref(new Date(dn * DAY_MS)), m = isoWeekOf(dn); if (m.week !== r[0] || m.year !== r[1]) bad.push([dayNumberToIso(dn), m.week, r[0]]); } return bad.slice(0, 5); }""")
        check("isoWeekOf agrees with the ISO 8601 reference for every day 2019-2032", bad == [], bad)
        check("known edges: 29.12.2025 = CW 1 (2026), 28.12.2026 = CW 53, 04.01.2027 = CW 1",
              pg.evaluate("() => ['2025-12-29', '2026-12-28', '2027-01-04', '2026-09-07'].map(i => isoWeekOf(dayNumber(i)).week)") == [1, 53, 1, 37])

        # ---- Week scale
        ticks = pg.evaluate("() => [...document.querySelectorAll('#ganttHeader .gantt-tick')].map(e => ({text: e.innerText.replace(/\\n/g, ' | '), title: e.title, w: e.getBoundingClientRect().width, l: parseFloat(e.style.left), over: [...e.children, e].some(c => c.scrollWidth > e.clientWidth + 0.5)}))")
        check("Week scale: every tick reads 'CW n'", len(ticks) > 20 and all(t["text"].startswith("CW ") for t in ticks), ticks[:2])
        check("Week scale: each tick is a full 7-day (98px) column, 98px apart", all(abs(t["w"] - 98) < 0.6 for t in ticks[1:-1]) and all(abs((ticks[i + 1]["l"] - ticks[i]["l"]) - 98) < 0.6 for i in range(1, len(ticks) - 2)), [(t["w"], t["l"]) for t in ticks[:4]])
        check("Week scale: no label is clipped or overflowing", not any(t["over"] for t in ticks), [t for t in ticks if t["over"]][:2])
        check("Week scale: tooltip names the whole week (Monday to Sunday)", all(" – " in t["title"] for t in ticks))
        ok = pg.evaluate("""() => [...document.querySelectorAll('#ganttHeader .gantt-tick')].every(e => { const m = e.title.match(/^CW (\\d+): (\\d\\d)\\.(\\d\\d)\\.(\\d{4}) – /); if (!m) return false; const iso = m[4] + '-' + m[3] + '-' + m[2]; const dn = dayNumber(iso); return ((dn + 3) % 7 + 7) % 7 === 0 && isoWeekOf(dn).week === +m[1]; })""")
        check("Week scale: each tick starts on a Monday and its number is that week's", ok)
        texts = [t["text"] for t in ticks]
        check("Week scale: the first tick and the year change show the full date, the others dd.mm.", "CW 1 | 04.01.2027" in " || ".join(texts).replace(" || ", "\n").split("\n") or any(t.startswith("CW 1 | 04.01.2027") or t.startswith("CW 53 | 28.12.2026") for t in texts), texts[:3])
        check("Week scale: a normal tick shows just day and month", any(t == "CW 38 | 14.09." for t in texts) or any(t.endswith("| 21.09.") for t in texts), texts[:6])
        pg.screenshot(path=f"gantt_week_{loc}.png", clip={"x": 330, "y": 50, "width": 900, "height": 200})

        # ---- Year scale
        check("the scale buttons are Week, Month, Year (no Day)", pg.evaluate("() => [...document.querySelectorAll('#zoomTabs .view-tab')].map(e => e.innerText)") == ["Week", "Month", "Year"])
        pg.click("#zoomTabs .view-tab:has-text('Year')"); pg.wait_for_timeout(300)
        yt = pg.evaluate("() => [...document.querySelectorAll('#ganttHeader .gantt-tick')].map(e => ({text: e.innerText.replace(/\\n/g, ' | ').trim(), title: e.title, w: e.getBoundingClientRect().width, cls: e.className, over: [...e.children, e].some(c => c.scrollWidth > e.clientWidth + 0.5)}))")
        check("Year scale: one tick per quarter, labelled Q1-Q4", len(yt) == 4 and all("| Q" in t["text"] or t["text"].startswith("Q") for t in yt), yt[:3])
        check("Year scale: the year is written on each Q1", all(("2026" in t["text"] or "2027" in t["text"]) for t in yt if t["title"].startswith("Q1")), [t for t in yt if t["title"].startswith("Q1")])
        check("Year scale: only Q1 ticks (and the first) carry a year", all(("20" not in t["text"]) for t in yt[1:] if not t["title"].startswith("Q1")), yt)
        check("Year scale: Q1 ticks get the heavier year separator", all("year-start" in t["cls"] for t in yt if t["title"].startswith("Q1")))
        w = {t["title"]: t["w"] for t in yt}
        check("Year scale: quarter widths follow the days (1.5px/day: Q4 = 92d = 138px, Q1 2027 = 90d = 135px, Q2 = 91d = 136.5px)", abs(w["Q4 2026"] - 138) < 0.6 and abs(w["Q1 2027"] - 135) < 0.6 and abs(w["Q2 2027"] - 136.5) < 0.6, w)
        check("Year scale: the first quarter is clipped to the chart's left edge but still labelled", w["Q3 2026"] < 92 * 1.5 and yt[0]["text"] == "2026 | Q3", yt[0])
        check("Year scale: labels aren't clipped", not any(t["over"] for t in yt))
        bars = pg.evaluate("() => [...document.querySelectorAll('.gantt-bar')].map(e => e.getBoundingClientRect().width)")
        check("Year scale: bars are drawn, at least the minimum width", len(bars) == 4 and all(w >= 6 for w in bars), bars)
        pg.screenshot(path=f"gantt_year_{loc}.png", clip={"x": 330, "y": 50, "width": 900, "height": 200})

        # dragging a bar in the year scale moves it by whole days (1.5px per day)
        bar = pg.locator(".gantt-bar", has_text="Build").first
        before = pg.evaluate("() => { const t = tasks.find(x => x.name === 'Build'); return [t.startDate, t.endDate]; }")
        box = bar.bounding_box()
        pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + 10); pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] / 2 + 30, box["y"] + 10, steps=6); pg.mouse.up(); pg.wait_for_timeout(200)
        after = pg.evaluate("() => { const t = tasks.find(x => x.name === 'Build'); return [t.startDate, t.endDate]; }")
        moved = pg.evaluate("([a, b]) => dayNumber(b) - dayNumber(a)", [before[0], after[0]])
        check("Year scale: dragging a bar 30px moves it 20 days", moved == 20 and (pg.evaluate("([a, b]) => dayNumber(b) - dayNumber(a)", [before[1], after[1]]) == 20), (before, after, moved))

        # ---- persistence and the other scales
        pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
        check("the Year scale is remembered after a reload", pg.evaluate("() => zoom") == "year" and pg.locator("#zoomTabs .view-tab.active").inner_text() == "Year")
        pg.click("#zoomTabs .view-tab:has-text('Month')"); pg.wait_for_timeout(250)
        mt = pg.evaluate("() => [...document.querySelectorAll('#ganttHeader .gantt-tick')].map(e => ({text: e.innerText.trim(), w: e.getBoundingClientRect().width}))")
        check("Month scale: still one tick per month, each as wide as the month (5px/day)", len(mt) > 6 and all(abs(t["w"] / 5 - round(t["w"] / 5)) < 0.05 and 28 <= round(t["w"] / 5) <= 31 for t in mt[1:-1]), mt[:4])
        # ---- the default scale is Year, once, for everyone; afterwards the choice is remembered
        pg.evaluate("() => { localStorage.setItem('milestone-prefs', JSON.stringify({theme: 'light', zoom: 'week', view: 'gantt', gridPaneWidth: 400})); }"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
        check("an old saved 'week' (the previous default, saved by the first save) is reset to Year once", pg.evaluate("() => zoom") == "year" and pg.locator("#zoomTabs .view-tab.active").inner_text() == "Year")
        pg.click("#zoomTabs .view-tab:has-text('Week')"); pg.wait_for_timeout(150); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
        check("...but a scale chosen afterwards is remembered", pg.evaluate("() => zoom") == "week")
        pg.evaluate("() => { localStorage.setItem('milestone-prefs', JSON.stringify({theme: 'light', zoom: 'day', zoomRev: 1, view: 'gantt', gridPaneWidth: 400})); }"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
        check("a saved 'day' (removed) falls back to Year", pg.evaluate("() => zoom") == "year" and pg.locator("#zoomTabs .view-tab.active").inner_text() == "Year")
        pg.evaluate("() => { localStorage.clear(); }"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
        check("a fresh install starts on Year", pg.evaluate("() => zoom") == "year")
        pg.evaluate("() => { localStorage.setItem('milestone-v1', JSON.stringify({project: {name: 'Old'}, tasks: [], deletedTaskIds: [], zoom: 'week', theme: 'light'})); localStorage.removeItem('milestone-plans'); localStorage.removeItem('milestone-prefs'); }"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_timeout(200)
        check("an install migrating from the single-project build also starts on Year", pg.evaluate("() => zoom") == "year")

        # ---- the chart under the header: rows line up, arrows join their bars (they used to be drawn 32px too high), link preview
        pg.evaluate("""() => { tasks.length = 0; const mk = (n, i, s, e, preds) => { const t = {id: genId(), name: n, parentId: null, order: i, startDate: s, endDate: e, progress: 0, milestone: false, color: null, notes: '', predecessors: preds || [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}; tasks.push(t); return t.id; };
            const a = mk('Alpha', 0, '2026-09-21', '2026-09-24'); mk('Beta', 1, '2026-09-25', '2026-09-30', [{id: a, type: 'FS', lag: 0}]); mk('Epsilon', 2, '2026-09-22', '2026-09-24'); currentView = 'gantt'; save(); render(); }""")
        for z in ("week", "month", "year"):
            pg.evaluate("z => { zoom = z; save(); render(); }", z); pg.wait_for_timeout(200)
            m = pg.evaluate("""() => { const bars = [...document.querySelectorAll('.gantt-bar')].map(e => e.getBoundingClientRect()); const path = document.querySelector('#ganttDeps path[marker-end]').getBoundingClientRect(); const rows = document.querySelector('.gantt-row-bg').getBoundingClientRect();
                return {headH: document.getElementById('ganttHeader').getBoundingClientRect().height, gridH: document.getElementById('gridHeader').getBoundingClientRect().height, startY: path.top - (bars[0].top + bars[0].height / 2), endY: path.bottom - (bars[1].top + bars[1].height / 2), rowAlign: document.querySelector('#gridRows .grid-row').getBoundingClientRect().top - rows.top}; }""")
            check(f"{z}: header (42px) the same in both panes, rows aligned, arrow runs bar centre to bar centre", abs(m["headH"] - 42) < .5 and abs(m["gridH"] - 42) < .5 and abs(m["rowAlign"]) < .5 and abs(m["startY"]) < 1.5 and abs(m["endY"]) < 1.5, m)
        pg.evaluate("() => { zoom = 'week'; save(); render(); }"); pg.wait_for_timeout(200)
        src = pg.locator(".gantt-bar", has_text="Alpha").first; src.hover(); hb = src.locator(".link-handle").bounding_box()
        pg.mouse.move(hb["x"] + 2, hb["y"] + hb["height"] / 2); pg.mouse.down()
        target = pg.locator(".gantt-bar", has_text="Epsilon").first.bounding_box(); ty = target["y"] + target["height"] / 2; tx = target["x"] + 20
        pg.mouse.move(tx, ty, steps=6)
        prev = pg.evaluate("""() => { const p = document.querySelector('#ganttDeps path[stroke-dasharray]'); if (!p) return null; const m = p.getAttribute('d').match(/L([\\d.\\-]+),([\\d.\\-]+)$/); return [parseFloat(m[1]), parseFloat(m[2]), document.getElementById('ganttDeps').getBoundingClientRect().top]; }""")
        check("link preview ends under the pointer", prev is not None and abs((prev[1] + prev[2]) - ty) < 1.5, (prev, ty))
        pg.mouse.up(); pg.wait_for_timeout(250)
        check("...and dropping on a bar still creates the dependency", pg.evaluate("() => tasks.find(t => t.name === 'Epsilon').predecessors.length") == 1)
        ctx.close()
    print("console errors/warnings:", errors)
    print(f"{sum(results)}/{len(results)} passed")
    b.close()
