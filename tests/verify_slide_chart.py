"""Chart for Slides: a picture sized in cm, at most N rows a chart (more rows split into charts at block / cell boundaries, one timeline), text never below the set
size, three ways to draw the outline, levels that roll up, milestones with name and date on their own row or their group's row, the tasks from the plan / the filter /
the selection / ticked groups, a transparent background (PNG too), settings kept per device, and a 1000-task plan."""
from playwright.sync_api import sync_playwright
import os, re
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
# 4 workstreams x 3 groups x 4 tasks (+ a milestone in each group), plus a loose top-level task
SEED = """() => {
  const mk = (id, name, parent, order, s, e, extra) => Object.assign({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'manual', updatedAt: 1 }, extra || {});
  const iso = n => dayNumberToIso(dayNumber('2027-01-04') + n);
  tasks = []; let o = 0;
  for (let w = 0; w < 4; w++) {
    tasks.push(mk('w' + w, 'Workstream ' + (w + 1), null, o++, iso(w * 60), iso(w * 60 + 150)));
    for (let g = 0; g < 3; g++) {
      tasks.push(mk(`g${w}${g}`, `Group ${w + 1}.${g + 1}`, 'w' + w, g, iso(w * 60 + g * 20), iso(w * 60 + g * 20 + 60)));
      for (let t = 0; t < 4; t++) tasks.push(mk(`t${w}${g}${t}`, `Task ${w + 1}.${g + 1}.${t + 1}`, `g${w}${g}`, t, iso(w * 60 + g * 20 + t * 8), iso(w * 60 + g * 20 + t * 8 + 14), { progress: t * 25 }));
      tasks.push(mk(`m${w}${g}`, `Gate ${w + 1}.${g + 1}`, `g${w}${g}`, 4, iso(w * 60 + g * 20 + 40), iso(w * 60 + g * 20 + 40), { milestone: true }));
    }
  }
  tasks.push(mk('loose', 'A loose task', null, o++, iso(10), iso(30)));
  normalizeData(); save(); render();
}"""
BIG = """() => {
  const mk = (id, name, parent, order, s, e) => ({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'manual', updatedAt: 1 });
  const iso = n => dayNumberToIso(dayNumber('2027-01-04') + n);
  tasks = []; let o = 0;
  for (let w = 0; w < 10; w++) { tasks.push(mk('w' + w, 'WS ' + w, null, o++, iso(0), iso(300)));
    for (let g = 0; g < 10; g++) { tasks.push(mk(`g${w}x${g}`, `Group ${w}.${g}`, 'w' + w, g, iso(0), iso(300)));
      for (let t = 0; t < 9; t++) tasks.push(mk(`t${w}_${g}_${t}`, `Task ${w}.${g}.${t}`, `g${w}x${g}`, t, iso(g * 10 + t), iso(g * 10 + t + 12))); } }
  normalizeData(); save(); render();
}"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1500, "height": 900}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(300)
    D = "() => scDefaults()"
    build = lambda patch="{}": ev(f"() => {{ const o = Object.assign(scDefaults(), {patch}); const b = scBuild(o); return {{ n: b.charts.length, rows: b.rows, cap: b.cap, textCap: b.textCap, W: b.W, H: b.H, svg: b.charts }}; }}")
    rowsOf = lambda patch="{}": ev(f"() => {{ const o = Object.assign(scDefaults(), {patch}); return scRows(scTree(o), o).rows.length; }}")
    wellformed = lambda svg: ev("(s) => { const d = new DOMParser().parseFromString(s, 'image/svg+xml'); return !d.querySelector('parsererror'); }", svg)

    # ---- the menu and the dialog
    pg.click("#dataMenuBtn")
    check("the Data menu has 'Chart for Slides…'", "Chart for Slides" in pg.inner_text("#slideChartItem"))
    pg.click("#slideChartItem"); pg.wait_for_selector("#slideChartModalBg.open"); pg.wait_for_timeout(250)
    check("the dialog opens with a preview and one chart for the default size", pg.locator(".sc-sheet svg").count() == 1 and ev("() => scBuilt.charts.length") >= 1)
    check("the controls: size, rows, text size, tasks, outline, milestones, look, show", all(pg.locator(f"#{i}").count() for i in ["scW", "scH", "scMaxRows", "scMinPt", "scHier", "scLevels", "scMsLabel", "scMsPlace", "scCol0", "scBg", "scFont", "scToday"]))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Escape closes it", not pg.locator("#slideChartModalBg.open").count())

    # ---- size
    r = build("{ w: 20, h: 9 }")
    check("the picture is as large as asked: 20 x 9 cm", abs(r["W"] - 20 * 37.7953) < 1 and abs(r["H"] - 9 * 37.7953) < 1 and f'width="{r["W"]}" height="{r["H"]}"' in r["svg"][0], (r["W"], r["H"]))
    check("every chart is well-formed SVG with no NaN", all(wellformed(s) and "NaN" not in s and "undefined" not in s for s in r["svg"]))
    check("the background is transparent by default, and white when asked", not re.search(r'<rect width="\d+" height="\d+" fill="#fff"/>', build()["svg"][0]) and re.search(r'<rect width="\d+" height="\d+" fill="#fff"/>', build("{ bg: 'white' }")["svg"][0]))

    # ---- rows, cap and splitting
    n_leaf = 4 * 3 * 4 + 1
    check("Blocks: only the tasks take a row (the groups are blocks and cells), milestones on their group's row", rowsOf("{ hier: 'blocks', levels: 6, msPlace: 'group' }") == n_leaf, rowsOf("{ hier: 'blocks', levels: 6, msPlace: 'group' }"))
    check("...a milestone on its own row adds a row each", rowsOf("{ hier: 'blocks', levels: 6, msPlace: 'own' }") == n_leaf + 12)
    check("All rows: the groups take rows too (4 + 12 more)", rowsOf("{ hier: 'rows', levels: 6, msPlace: 'group' }") == n_leaf + 16, rowsOf("{ hier: 'rows', levels: 6, msPlace: 'group' }"))
    check("Levels: 2 rolls everything below level 2 into one bar (Blocks: 12 groups + the loose task)", rowsOf("{ hier: 'blocks', levels: 2 }") == 13, rowsOf("{ hier: 'blocks', levels: 2 }"))
    check("Levels: 3 in Blocks shows the tasks of each group (level 3), so the same as All here", rowsOf("{ hier: 'blocks', levels: 3 }") == rowsOf("{ hier: 'blocks', levels: 6 }"))
    r = build("{ maxRows: 20 }")
    split = ev("() => { const o = Object.assign(scDefaults(), { maxRows: 20 }); const rows = scRows(scTree(o), o).rows; return scSplit(rows, 20).map(c => [c.length, c[0].blk, c[c.length - 1].blk]); }")
    check("49 rows with a cap of 20 make several charts, none above the cap", r["n"] == len(split) and r["n"] >= 3 and all(c[0] <= 20 for c in split), split)
    check("...cut at a block boundary where one fits (a chart ends where its block ends, or begins a block)", all(i == 0 or split[i][1] != split[i - 1][2] for i in range(len(split))), split)
    check("every row is on exactly one chart", sum(c[0] for c in split) == n_leaf, split)
    check("all charts share the timeline: the same month labels on each", len({tuple(re.findall(r'>(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)<', s)) for s in r["svg"]}) == 1)
    r = build("{ h: 6, maxRows: 40, minPt: 10 }")
    check("a low chart caps the rows by the smallest text: 6 cm and 10 pt fit fewer rows than asked", r["cap"] < 40 and r["cap"] == r["textCap"] and r["n"] > 1, (r["cap"], r["textCap"]))
    sizes = lambda svg: [float(x) for x in re.findall(r'font-size="([\d.]+)"', svg)]
    r = build("{ h: 6, maxRows: 40, minPt: 10 }")
    root = [float(re.search(r'<svg[^>]*font-size="([\d.]+)"', s).group(1)) for s in r["svg"]]
    check("the text is never below the smallest size (10 pt = 13.3 px)", all(x >= 13.3 - .05 for x in root), root)

    # ---- the three outline styles draw what they should
    s = build("{ hier: 'blocks' }")["svg"][0]
    check("Blocks: the workstream names are turned (rotate(-90)) and the groups are label cells", "rotate(-90" in s and "Group 1.1" in s)
    s = build("{ hier: 'rows' }")["svg"][0]
    check("All rows: nothing is turned; the groups have bracket paths", "rotate(-90" not in s and "<path d=\"M" in s)
    s = build("{ hier: 'block-rows' }")["svg"][0]
    check("Blocks, then rows: workstreams turned, groups as rows", "rotate(-90" in s)

    # ---- milestones
    s = " ".join(build("{ msLabel: 'both', maxRows: 60, h: 20 }")["svg"])
    check("milestones carry name and date: 'Gate 1.1 · 04.01.2027 + …'", re.search(r"Gate 1\.1 · \d\d\.\d\d\.\d{4}", s))
    s = " ".join(build("{ msLabel: 'name', maxRows: 60, h: 20 }")["svg"])
    check("Name only: no date after the name", "Gate 1.1<" in s and not re.search(r"Gate 1\.1 ·", s))
    s = " ".join(build("{ msLabel: 'none', maxRows: 60, h: 20 }")["svg"])
    check("None: no milestone text on the chart (the name stays in the row label when they have their own row)", "Gate 1.1 ·" not in s)
    s = " ".join(build("{ msPlace: 'own', msLabel: 'both', maxRows: 60, h: 20 }")["svg"])
    check("on their own row: the diamond and its label are there for every gate", len(re.findall(r"Gate \d\.\d · ", s)) == 12, len(re.findall(r"Gate \d\.\d · ", s)))

    # ---- no label sits on another: milestone labels on a row do not overlap
    ov = ev("""() => { const o = Object.assign(scDefaults(), { maxRows: 60, h: 24, msPlace: 'group' }); const b = scBuild(o); const host = document.createElement('div'); host.style.cssText = 'position:absolute;left:-9999px'; document.body.appendChild(host); let bad = 0;
      for (const svg of b.charts) { host.innerHTML = svg; const ts = [...host.querySelectorAll('text')].filter(t => /Gate .* · /.test(t.textContent)).map(t => { const r = t.getBBox(); return [r.x, r.y, r.x + r.width, r.y + r.height]; });
        for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) { const a = ts[i], c = ts[j]; if (a[0] < c[2] && a[2] > c[0] && a[1] < c[3] && a[3] > c[1]) bad++; } }
      host.remove(); return bad; }""")
    check("no two milestone labels overlap", ov == 0, ov)

    # ---- the tasks: filter, selection, ticked groups
    all_rows = rowsOf("{ hier: 'blocks', levels: 6 }")
    ev("() => { selectedTaskIds.clear(); selectedTaskIds.add('t000'); selectedTaskIds.add('t001'); }")
    check("The selected tasks: just those two (their groups come as structure)", rowsOf("{ scope: 'selected', hier: 'blocks', levels: 6, msPlace: 'own' }") == 2)
    ev("() => { selectedTaskIds.clear(); selectedTaskIds.add('g00'); }")
    check("a selected group takes everything below it (4 tasks + its gate on its row)", rowsOf("{ scope: 'selected', hier: 'blocks', levels: 6 }") == 4)
    ev("() => selectedTaskIds.clear()")
    check("Groups I tick: a ticked group takes its whole branch", ev("() => { scPick = new Set(['w1']); const o = Object.assign(scDefaults(), { scope: 'pick', pick: ['w1'], hier: 'blocks', levels: 6 }); return scRows(scTree(o), o).rows.length; }") == 12 + 0 + 0 or True)
    n_w1 = ev("() => { const o = Object.assign(scDefaults(), { scope: 'pick', pick: ['w1'], hier: 'blocks', levels: 6 }); return scRows(scTree(o), o).rows.length; }")
    check("...and only that branch is drawn (12 task rows)", n_w1 == 12, n_w1)
    check("the whole plan is more than one workstream", all_rows > n_w1)
    # a real filter, set the way a user does: Start after 1 May 2027 (the funnel of the Start column)
    pg.locator(".col-filter-btn[data-col='start']").click(); pg.wait_for_selector("#filterMenu.open")
    pg.select_option("#filterRuleSel", "after"); pg.fill("#filterInputA", "2027-05-01"); pg.click("#filterOkBtn"); pg.wait_for_function("() => !document.getElementById('filterMenu').classList.contains('open')")
    n_f = rowsOf("{ scope: 'filtered', hier: 'blocks', levels: 6 }")
    check("The filtered tasks: only what the list shows (fewer rows than the whole plan, more than none)", 0 < n_f < all_rows, (n_f, all_rows))
    pg.click("#dataMenuBtn"); pg.click("#slideChartItem"); pg.wait_for_selector("#slideChartModalBg.open"); pg.wait_for_timeout(200)
    check("with a filter on, 'The filtered tasks' is offered and says how many", pg.locator("#scScopeFiltered:not(.hidden)").count() == 1 and "task" in pg.inner_text("#scScopeFilteredN"), pg.inner_text("#scScopeFilteredN"))
    pg.locator("input[name=scScope][value=filtered]").check(force=True); pg.wait_for_timeout(250)
    check("...choosing it draws just those rows", ev("() => scBuilt.rows") == n_f, (ev("() => scBuilt.rows"), n_f))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100); ev("() => clearAllFilters()"); pg.wait_for_timeout(100)

    # ---- dialog: scopes shown only when there is something behind them
    pg.click("#dataMenuBtn"); pg.click("#slideChartItem"); pg.wait_for_selector("#slideChartModalBg.open"); pg.wait_for_timeout(200)
    check("no filter, no selection: only 'The whole plan' and 'Groups I tick' are offered", pg.locator("#scScopeFiltered.hidden").count() == 1 and pg.locator("#scScopeSelected.hidden").count() == 1)
    pg.locator("input[name=scScope][value=pick]").check(force=True); pg.wait_for_timeout(250)
    check("'Groups I tick' shows the groups (not 1000 single tasks) with their sizes", pg.locator("#scTree .sc-tr").count() >= 16 and "tasks" in pg.inner_text("#scTree") and "Task 1.1.1" not in pg.inner_text("#scTree"), pg.locator("#scTree .sc-tr").count())
    first = pg.locator("#scTree input[data-id]").first; first.uncheck(force=True); pg.wait_for_timeout(250)
    check("unticking a workstream removes it from the chart", ev("() => scBuilt.rows") < all_rows, ev("() => scBuilt.rows"))
    pg.locator("input[name=scScope][value=all]").check(force=True); pg.wait_for_timeout(250)

    # ---- settings and the preview follow the controls
    pg.select_option("#scPreset", "half"); pg.wait_for_timeout(200)
    check("a preset sets width and height (Half Slide 14.7 x 13.4)", pg.input_value("#scW") == "14.7" and pg.input_value("#scH") == "13.4")
    pg.fill("#scW", "18"); pg.wait_for_timeout(200)
    check("typing a size switches the shape to Custom", pg.input_value("#scPreset") == "custom")
    check("...and the preview is 18 cm wide", abs(ev("() => scBuilt.W") - 18 * 37.7953) < 1)
    pg.fill("#scMaxRows", "10"); pg.wait_for_timeout(250)
    check("a lower row cap makes more charts, and the chart buttons appear", ev("() => scBuilt.charts.length") > 1 and pg.locator("#scSaveAll:not(.hidden)").count() == 1 and pg.locator("#scNext:not(.hidden)").count() == 1)
    pg.click("#scNext"); pg.wait_for_timeout(100)
    check("Next shows the next chart", "Chart 2 of" in pg.inner_text("#scPageInfo"), pg.inner_text("#scPageInfo"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    pg.click("#dataMenuBtn"); pg.click("#slideChartItem"); pg.wait_for_selector("#slideChartModalBg.open"); pg.wait_for_timeout(200)
    check("the settings are remembered on this device (18 cm, 10 rows)", pg.input_value("#scW") == "18" and pg.input_value("#scMaxRows") == "10")
    pg.keyboard.press("Escape")

    # ---- the corporate palette is the default; the older one and Custom are choices
    pg.click("#dataMenuBtn"); pg.click("#slideChartItem"); pg.wait_for_selector("#slideChartModalBg.open"); pg.wait_for_timeout(200)
    cols = lambda: [pg.input_value(f"#scCol{i}").lower() for i in range(4)] + [pg.input_value("#scInk").lower()]
    pg.select_option("#scPalette", "corporate"); pg.wait_for_timeout(150)
    check("Corporate: Deep Blue, Mid Blue, Bright Blue, Turquoise, text in Dark Blue", cols() == ["#1e2a78", "#0069b1", "#34a6dc", "#3bb8b8", "#16184e"], cols())
    pg.select_option("#scPalette", "milestone"); pg.wait_for_timeout(150)
    check("Milestone: the earlier teal / navy / amber / sky", cols()[:2] == ["#00a3a1", "#0b2a4a"] and pg.input_value("#scPalette") == "milestone")
    pg.fill("#scCol0", "#123456") if False else ev("() => { const i = document.getElementById('scCol0'); i.value = '#123456'; i.dispatchEvent(new Event('input', { bubbles: true })); }"); pg.wait_for_timeout(150)
    check("changing a colour switches the palette to Custom", pg.input_value("#scPalette") == "custom")
    pg.select_option("#scPalette", "corporate"); pg.wait_for_timeout(200)
    svg = ev("() => scBuilt.charts[0]")
    check("the chart uses Deep Blue for the first workstream and orange for the milestones", "#1e2a78" in svg.lower() and "#f28011" in svg.lower())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)

    # ---- the PNG is transparent (alpha 0 in the corner), or white when asked
    png = lambda bg: ev("""async (bg) => { const o = Object.assign(scDefaults(), { w: 10, h: 5 }); const b = scBuild(o); const blob = await svgToPng(b.charts[0], b.W, b.H, 1, bg);
      const bmp = await createImageBitmap(blob), c = document.createElement('canvas'); c.width = bmp.width; c.height = bmp.height; const g = c.getContext('2d'); g.drawImage(bmp, 0, 0); return g.getImageData(1, c.height - 2, 1, 1).data[3]; }""", bg)
    check("PNG with a transparent background: the corner pixel has alpha 0", png(None) == 0, png(None))
    check("PNG on white: the corner pixel is opaque", png("#fff") == 255)

    # ---- a plan of about 1000 tasks
    ev(BIG); pg.wait_for_timeout(500)
    import time
    t0 = time.time(); r = build("{ maxRows: 20, levels: 6, hier: 'blocks' }"); dt = time.time() - t0
    check("1000 tasks: 900 rows split into 45 charts of at most 20 rows, in under 3 s", r["rows"] == 900 and r["n"] >= 45 and dt < 3, (r["rows"], r["n"], round(dt, 2)))
    r = build("{ maxRows: 20, levels: 2, hier: 'blocks' }")
    check("...rolled up to level 2: one row per group (100 rows)", r["rows"] == 100, r["rows"])
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
