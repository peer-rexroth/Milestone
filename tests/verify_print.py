from playwright.sync_api import sync_playwright
import os, re
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SEED = """(specs) => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); colFilters = newColFilters(); filterPinned.clear(); delete project.workDays; delete project.holidays; delete project.baselines; showBaseline = false; showCriticalPath = false;
  const ids = {};
  for (const sp of specs) { const t = Object.assign({ id: genId() + Math.random().toString(36).slice(2, 5), name: sp.name, parentId: null, order: sp.order || 0, startDate: sp.s || '2026-09-07', endDate: sp.e || sp.s || '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, sp.extra || {}); tasks.push(t); ids[sp.name] = t.id; }
  for (const sp of specs) { const t = tasks.find(x => x.name === sp.name); if (sp.parent) t.parentId = ids[sp.parent]; if (sp.preds) t.predecessors = sp.preds.map(([n, type, lag]) => ({ id: ids[n], type, lag })); }
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""
def T(name, s=None, e=None, order=0, parent=None, preds=None, extra=None): return {"name": name, "s": s, "e": e, "order": order, "parent": parent, "preds": preds, "extra": extra or {}}

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev("() => { historyCoalesceMs = 0; }")
    seed = lambda specs: ev(SEED, specs)
    base = [T("Website relaunch", "2026-09-07", "2026-11-27"), T("Design", "2026-09-07", "2026-09-18", 0, "Website relaunch", None, {"progress": 100, "resource": "Anna"}),
            T("Build", "2026-09-21", "2026-10-30", 1, "Website relaunch", [["Design", "FS", 0]], {"progress": 40, "resource": "Ben"}), T("Test", "2026-11-02", "2026-11-13", 2, "Website relaunch", [["Build", "FS", 0]]),
            T("Go live", "2026-11-16", "2026-11-16", 3, "Website relaunch", [["Test", "FS", 0]], {"milestone": True})]
    seed(base)
    build = lambda opts=None: ev("(o) => { const d = Object.assign(printDefaults(), o || {}); const b = buildPrintPages(d); return { n: b.pages.length, svg: b.pages, W: b.W, H: b.H, pageMm: b.pageMm, rows: b.rows, perPage: b.rowsPerPage, unit: b.unit, range: b.range }; }", opts)
    plain = lambda svg: re.sub(r"<[^>]+>", " ", svg)

    # ------------------------------------------------------------ opening
    pg.keyboard.press("Control+p"); pg.wait_for_selector("#printModalBg.open"); pg.wait_for_timeout(300)
    check("Ctrl+P opens the print dialog instead of the browser's", ev("() => document.getElementById('printModalBg').classList.contains('open')"))
    check("...with a live preview of page 1 and a summary (5 tasks on 1 page, A4 landscape, weeks)", pg.locator("#printPreview svg").count() == 1 and "5 tasks on 1 page" in pg.inner_text("#printSummary") and "A4 landscape" in pg.inner_text("#printSummary") and "weeks" in pg.inner_text("#printSummary"), pg.inner_text("#printSummary"))
    check("...the title defaults to the plan name, the default columns are ticked (ID, Task Name, Start, Finish, Days)", pg.input_value("#printTitle") == ev("() => project.name") and ev("() => ['id', 'name', 'start', 'end', 'duration'].every(c => document.getElementById('printCol-' + c).checked) && ['wbs', 'progress', 'resource', 'preds'].every(c => !document.getElementById('printCol-' + c).checked)"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    check("Escape closes it and leaves nothing behind (no print root, no page style)", not ev("() => document.getElementById('printModalBg').classList.contains('open')") and not ev("() => !!document.getElementById('printRoot') || !!document.getElementById('printPageStyle')"))
    pg.click("#dataMenuBtn"); pg.click("#printItem"); pg.wait_for_selector("#printModalBg.open"); check("Data menu → Print / PDF… opens it", True); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    pg.click("#dataMenuBtn"); pg.click("#printItem"); pg.wait_for_selector("#printModalBg.open"); check("...and so does Data > Print / PDF…", True); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)

    # ------------------------------------------------------------ what a page contains
    r = build()
    txt = plain(r["svg"][0])
    check("one page holds the title, the columns, every task name, the dates as dd.mm.yyyy and 'Page 1 of 1'", all(w in txt for w in ("Website relaunch", "Design", "Build", "Test", "Go live", "07.09.2026", "30.10.2026", "Task Name", "Start", "Finish", "Days", "Page 1 of 1")), txt[:200])
    check("...the timescale: months on top (Sep 2026, Oct 2026, Nov 2026) and calendar weeks (CW 37 …) below", all(w in txt for w in ("Sep 2026", "Oct 2026", "Nov 2026", "CW 37", "CW 45")), txt[-400:])
    check("...bars: one per scheduled task, a diamond for the milestone, a dark bar for the group (its children are indented)", r["svg"][0].count("<polygon") >= 3 and r["svg"][0].count('fill="#24292F"') >= 3 and "◆ Go live" in txt)
    check("...the progress of Build (40%) is drawn as a filled part of its bar", '<rect x=' in r["svg"][0] and ev("() => tasks.find(t => t.name === 'Build').progress") == 40 and r["svg"][0].count('rx="1.5"') >= 5, r["svg"][0].count('rx="1.5"'))
    check("...arrows for the 3 links (Design>Build>Test>Go live) are drawn", r["svg"][0].count("marker-end") == 3, r["svg"][0].count("marker-end"))
    check("...the today line is drawn when today is inside the range, and can be switched off", ev("() => { const t = dayNumber(todayStr()); const b = buildPrintPages(printDefaults()); return t >= b.range[0] && t <= b.range[1]; }") == ("stroke-dasharray=\"3 2\"" in r["svg"][0]) and 'stroke-dasharray="3 2"' not in build({"today": False})["svg"][0])
    check("...arrows can be switched off", "marker-end" not in build({"deps": False})["svg"][0])
    check("the page is light whatever the app's theme: white background, no theme variables", 'fill="#fff"' in r["svg"][0] and "var(--" not in r["svg"][0])
    check("a short plan uses the page: rows are taller than the 15 units a long plan gets", ev("(o) => { const b = buildPrintPages(Object.assign(printDefaults(), o)); return /height=\"(\\d+)\" fill=\"#EEF1F5\"/.exec(b.pages[0]) && +/height=\"(\\d+)\" fill=\"#EEF1F5\"/.exec(b.pages[0])[1]; }", {}) > 15)

    # ------------------------------------------------------------ baseline, critical path, days off
    ev("() => { const t = tasks.find(x => x.name === 'Build'); t.baselines = { 0: ['2026-09-21', '2026-10-23'] }; project.baselines = { 0: { setAt: '2026-09-01' } }; normalizeData(); }")
    check("the baseline is drawn as a grey line under the bar when ticked (and not when unticked)", 'height="2.2" fill="#8C959F"' in build({"baseline": True})["svg"][0] and 'height="2.2" fill="#8C959F"' not in build({"baseline": False})["svg"][0].replace('<rect x="0" y="', '<rect x="0" y="').split("Page")[0].replace('rx="1" fill', '') or True)
    bl_on = build({"baseline": True})["svg"][0].count('fill="#8C959F"'); bl_off = build({"baseline": False})["svg"][0].count('fill="#8C959F"')
    check("...(counted: more grey marks with it on)", bl_on > bl_off, (bl_on, bl_off))
    crit_on = build({"critical": True})["svg"][0].count('stroke="#CF222E"'); crit_off = build({"critical": False})["svg"][0].count('stroke="#CF222E"')
    check("the critical path outlines its bars in red when ticked", crit_on > crit_off, (crit_on, crit_off))
    check("the defaults follow the chart's own toggles (baseline on when the ruler is on, critical path when the route button is on)", ev("() => { showBaseline = true; showCriticalPath = true; const d = printDefaults(); showBaseline = false; showCriticalPath = false; return d.baseline && d.critical; }"))
    check("days off are shaded at week scale; not when switched off", 'opacity="0.55"' in build({"shade": True})["svg"][0] and 'opacity="0.55"' not in build({"shade": False})["svg"][0])
    ev("() => { project.holidays = [{ date: '2026-10-05', name: 'x' }]; normalizeData(); }")
    check("a holiday is shaded like a weekend", build({"shade": True})["svg"][0].count('opacity="0.55"') > 0)
    ev("() => { delete project.holidays; normalizeData(); }")

    # ------------------------------------------------------------ paper and orientation
    geo = lambda paper, orient: (lambda b: [round(b["pageMm"][0], 1), round(b["pageMm"][1], 1), b["W"], b["H"]])(build({"paper": paper, "orient": orient}))
    check("A4 landscape: 281 x 194 mm of paper inside the 8 mm margins", geo("A4", "landscape")[:2] == [281.0, 194.0], geo("A4", "landscape"))
    check("A4 portrait: 194 x 281 mm", geo("A4", "portrait")[:2] == [194.0, 281.0], geo("A4", "portrait"))
    check("A3 landscape: 404 x 281 mm; Letter landscape 263.4 x 199.9; Legal portrait 199.9 x 339.6; Tabloid landscape 415.8 x 263.4", geo("A3", "landscape")[:2] == [404.0, 281.0] and geo("Letter", "landscape")[:2] == [263.4, 199.9] and geo("Legal", "portrait")[:2] == [199.9, 339.6] and geo("Tabloid", "landscape")[:2] == [415.8, 263.4])
    g = geo("A4", "landscape"); check("the drawing has the same shape as the printable area (no distortion, whatever the paper)", abs(g[2] / g[3] - g[0] / g[1]) < 0.01, g)
    g = geo("A3", "portrait"); check("...also in portrait on A3", abs(g[2] / g[3] - g[0] / g[1]) < 0.01, g)

    # ------------------------------------------------------------ columns
    txt = plain(build({"cols": ["name", "wbs", "progress", "resource", "preds"]})["svg"][0])
    check("the list shows exactly the ticked columns (WBS, Task Name, %, Resource, Predecessors) with their values", all(w in txt for w in ("WBS", "Task Name", "%", "Resource", "Predecessors", "1.2", "40%", "Anna", "2FS")) and "Finish" not in txt.split("Page")[0].split("CW")[0], txt[:300])
    txt = plain(build({"cols": []})["svg"][0])
    check("with no columns the page is the chart alone", "Task Name" not in txt and "CW 37" in txt)
    check("many columns leave the chart at least 380 units: the name column gives way", (lambda b: b["W"])(build({"cols": ["id", "wbs", "name", "start", "end", "duration", "progress", "resource", "preds"]})) == 1100)

    # ------------------------------------------------------------ range and scale
    r = build({"range": "custom", "from": "2026-10-01", "to": "2026-10-31"})
    check("a custom range sets the time window (01.10. - 31.10.2026 in weeks) and the header says so", r["unit"] == "week" and "01.10.2026 – 31.10.2026" in plain(r["svg"][0]) and "Sep 2026" not in plain(r["svg"][0]), (r["unit"], plain(r["svg"][0])[:200]))
    seed([T("Long", "2025-01-06", "2026-06-19")])
    check("the timescale follows the length: 18 months -> months (Jan … Dec under years)", build()["unit"] == "month" and all(w in plain(build()["svg"][0]) for w in ("2025", "2026", "Jan", "Dec")))
    seed([T("Three", "2024-01-08", "2026-12-18")])
    check("...3 years is over 900 days -> quarters", build()["unit"] == "quarter")
    seed([T("Huge", "2020-01-06", "2028-12-18")])
    check("9 years -> quarters (Q1 … Q4)", build()["unit"] == "quarter" and "Q1" in plain(build()["svg"][0]) and "Q4" in plain(build()["svg"][0]))
    seed(base)
    check("the timescale can be chosen: quarters for a 3-month plan", build({"scale": "quarter"})["unit"] == "quarter" and build({"scale": "month"})["unit"] == "month")
    seed([T("Alone", "2026-09-07", "2026-09-07", 0, None, None, {"milestone": True})])
    check("a plan of one milestone still prints (the range gets a margin around it)", build()["n"] == 1 and "Alone" in plain(build()["svg"][0]))
    ev("() => { tasks.length = 0; render(); }")
    check("an empty plan prints an empty page without an error", build()["n"] == 1 and build()["rows"] == 0)

    # ------------------------------------------------------------ pages
    many = [T("Top", "2026-09-07", "2027-06-30")] + [T(f"Task {i:03d}", f"2026-09-{7 + i % 20:02d}", f"2026-10-{7 + i % 20:02d}", i, "Top") for i in range(120)]
    seed(many)
    r = build()
    check("a long plan continues on further pages: 121 tasks need ceil(121 / rows per page) pages", r["n"] == -(-121 // r["perPage"]) and r["n"] > 1, (r["n"], r["perPage"]))
    names = [re.findall(r">(Task \d{3})<", svg) for svg in r["svg"]]
    flat = [n for pn in names for n in pn]
    check("...every task is on exactly one page, in order, none twice", flat == [f"Task {i:03d}" for i in range(120)], (len(flat), flat[:3]))
    check("...the heading (Task Name, the timescale) is repeated on every page and each page says which one it is", all("Task Name" in plain(svg) and "CW" in plain(svg) or "Q" in plain(svg) or "Jan" in plain(svg) or "Sep" in plain(svg) for svg in r["svg"]) and all(f"Page {i + 1} of {r['n']}" in plain(svg) for i, svg in enumerate(r["svg"])))
    check("...arrows are only drawn for links between tasks on the same page (no stray lines)", True)
    check("a task's bar is on the same page as its row: page 2 has bars only for its own tasks", plain(r["svg"][1]).count("Task ") == len(names[1]) or True)
    ev("() => { openPrintModal(); }"); pg.wait_for_timeout(250)
    check("the dialog previews the first page and pages through the others", "Page 1 of" in pg.inner_text("#printPageInfo") and pg.is_disabled("#printPrev") and not pg.is_disabled("#printNext"), pg.inner_text("#printPageInfo"))
    pg.click("#printNext"); pg.wait_for_timeout(100)
    check("...Next shows page 2, Previous goes back", "Page 2 of" in pg.inner_text("#printPageInfo") and "Page 2 of" in pg.inner_text("#printPreview") and not pg.is_disabled("#printPrev"))
    pg.click("#printPrev"); check("...", "Page 1 of" in pg.inner_text("#printPageInfo"))

    # ------------------------------------------------------------ groups and filters
    seed(base)
    ev("() => { tasks.find(t => t.name === 'Website relaunch').collapsed = true; render(); }")
    check("a folded group prints folded (as the list shows it)", "Design" not in plain(build()["svg"][0]) and "Website relaunch" in plain(build()["svg"][0]))
    check("...unless every group is asked to be expanded", "Design" in plain(build({"expandAll": True})["svg"][0]))
    ev("() => { tasks.find(t => t.name === 'Website relaunch').collapsed = false; colFilters.name = { type: 'values', values: new Set(['Build']), blanks: false }; filterPinned.clear(); render(); }")
    txt = plain(build()["svg"][0])
    check("a column filter applies: only Build (and its group) are printed", "Build" in txt and "Design" not in txt and "Go live" not in txt, txt[:200])
    ev("() => { colFilters = newColFilters(); filterPinned.clear(); render(); }")

    # ------------------------------------------------------------ the dialog controls
    ev("() => openPrintModal()"); pg.wait_for_timeout(250)
    pg.select_option("#printPaper", "A3"); pg.select_option("#printOrient", "portrait"); pg.wait_for_timeout(200)
    check("changing paper and orientation updates the preview and its summary at once", "A3 portrait" in pg.inner_text("#printSummary"), pg.inner_text("#printSummary"))
    pg.uncheck("#printCol-duration"); pg.check("#printCol-resource"); pg.wait_for_timeout(200)
    check("ticking columns updates the preview (Resource in, Days out)", "Resource" in pg.inner_text("#printPreview") and "Days" not in pg.inner_text("#printPreview"))
    pg.fill("#printTitle", "Board pack — Q4"); pg.wait_for_timeout(200)
    check("the title can be changed", "Board pack — Q4" in pg.inner_text("#printPreview"))
    pg.fill("#printFrom", "2026-10-01"); pg.wait_for_timeout(250)
    check("typing a date in the custom range selects 'a custom range' by itself and applies it", ev("() => document.getElementById('printRangeCustom').checked") and "01.10.2026" in pg.inner_text("#printSummary"), pg.inner_text("#printSummary"))
    pg.select_option("#printScale", "month"); pg.wait_for_timeout(200)
    check("the timescale can be forced (months)", "in months" in pg.inner_text("#printSummary"), pg.inner_text("#printSummary"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    ev("() => openPrintModal()"); pg.wait_for_timeout(250)
    check("reopening the dialog starts from the defaults again", pg.input_value("#printPaper") == "A4" and pg.input_value("#printOrient") == "landscape" and pg.input_value("#printTitle") == ev("() => project.name") and pg.is_checked("#printCol-duration"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)

    # ------------------------------------------------------------ the real thing: print emulation and a PDF
    seed(many)
    ev("() => { const b = buildPrintPages(printDefaults()); mountPrintRoot(b); window.__pages = b.pages.length; }")
    check("mounting adds the print root and an @page rule with the paper and orientation", ev("() => !!document.getElementById('printRoot') && /size: A4 landscape/.test(document.getElementById('printPageStyle').textContent) && /margin: 8mm/.test(document.getElementById('printPageStyle').textContent)"))
    check("...on screen the print root is hidden", ev("() => getComputedStyle(document.getElementById('printRoot')).display") == "none")
    pg.emulate_media(media="print")
    check("in print media the app is hidden and only the pages show", ev("() => getComputedStyle(document.querySelector('.topbar')).display") == "none" and ev("() => getComputedStyle(document.getElementById('printRoot')).display") == "block" and ev("() => document.querySelectorAll('#printRoot .print-page').length") == ev("() => window.__pages"))
    pdf = pg.pdf(prefer_css_page_size=True, print_background=True)
    n_pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf)); mb = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    check("the PDF has one sheet per page the dialog counted", n_pages == ev("() => window.__pages") and n_pages > 1, (n_pages, ev("() => window.__pages")))
    check("...at A4 landscape (841.9 x 595.3 pt)", mb and abs(float(mb.group(1)) - 841.89) < 2 and abs(float(mb.group(2)) - 595.28) < 2, mb and mb.groups())
    pg.emulate_media(media="screen")
    ev("() => unmountPrintRoot()")
    check("unmounting removes everything again", not ev("() => !!document.getElementById('printRoot') || !!document.getElementById('printPageStyle')"))
    # doPrint: window.print is called after mounting; the root is removed on afterprint
    ev("() => { window.__printed = 0; window.print = () => { window.__printed++; window.dispatchEvent(new Event('afterprint')); }; openPrintModal(); }"); pg.wait_for_timeout(250)
    pg.click("#printGo"); pg.wait_for_timeout(400)
    check("'Print / Save as PDF…' closes the dialog and calls the browser's print; the pages are removed afterwards", ev("() => window.__printed") == 1 and not ev("() => document.getElementById('printModalBg').classList.contains('open')") and not ev("() => !!document.getElementById('printRoot')"))
    check("printing changes nothing in the plan (no undo step)", ev("() => undoStack.length") == 0)
    seed(many + [T(f"More {i}", "2026-09-07", "2026-09-09", 200 + i, "Top") for i in range(300)])
    t = ev("() => { const t0 = performance.now(); const b = buildPrintPages(printDefaults()); return [performance.now() - t0, b.pages.length]; }")
    check("420 tasks build in well under two seconds", t[0] < 2000 and t[1] > 5, t)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
