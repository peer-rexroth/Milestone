# -*- coding: utf-8 -*-
"""The chart as a picture (Print / PDF dialog → Picture: Copy / PNG / SVG): one image with every row, standalone SVG with text as text, PNG at 2x (less
for a very tall plan, refused past that), Copy to the clipboard, the Print dialog's options honoured. See "The chart as a picture" in CLAUDE.md."""
import os, re, struct, tempfile, xml.dom.minidom
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
SEED = """(n) => { historyCoalesceMs = 0; project.workDays = [0,1,2,3,4,5,6]; delete project.timeUnit; tasks.length = 0; let o = 0;
  const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: o++, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now() }, x || {});
  tasks.push(mk('g', 'Design phase & <review>', '2030-03-04', '2030-04-12'),
    mk('a', 'Discovery workshop', '2030-03-04', '2030-03-08', { parentId: 'g', progress: 100 }),
    mk('b', 'Information architecture', '2030-03-11', '2030-03-22', { parentId: 'g', progress: 40, predecessors: [{ id: 'a', type: 'FS', lag: 0 }] }),
    mk('c', 'Visual design', '2030-03-25', '2030-04-12', { parentId: 'g', predecessors: [{ id: 'b', type: 'FS', lag: 0 }] }),
    mk('m', 'Launch', '2030-04-15', '2030-04-15', { milestone: true, predecessors: [{ id: 'c', type: 'FS', lag: 0 }] }));
  for (let i = 0; i < n; i++) tasks.push(mk('x' + i, 'Extra ' + i, '2030-04-16', '2030-04-19'));
  normalizeData(); save(); setSelection([]); currentView = 'tasks'; render(); resetHistory(); }"""
def png_size(b): return struct.unpack(">II", b[16:24]) if b[:8] == b"\x89PNG\r\n\x1a\n" else None
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 860}, accept_downloads=True, permissions=["clipboard-read", "clipboard-write"]); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED, 0); pg.wait_for_timeout(250)
    def open_print():
        pg.click("#dataMenuBtn"); pg.click("#printItem"); pg.wait_for_selector("#printModalBg.open"); pg.wait_for_timeout(300)
    def grab(kind):
        with pg.expect_download() as d: pg.click({"png": "#printPng", "svg": "#printSvg"}[kind])
        path = os.path.join(tempfile.mkdtemp(), "f." + kind); d.value.save_as(path); return d.value.suggested_filename, open(path, "rb").read()
    open_print()
    check("the Print dialog has a Picture group: Copy, PNG and SVG", all(pg.locator(i).count() == 1 for i in ("#printCopyImg", "#printPng", "#printSvg")))
    check("they are all in view in the dialog's footer (nothing cut off)", ev("() => ['printCopyImg', 'printPng', 'printSvg', 'printGo'].every(id => { const r = document.getElementById(id).getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight; })"))
    nm, raw = grab("svg"); svg = raw.decode("utf-8")
    check("SVG: named after the plan and the date", re.fullmatch(r".+-\d{4}-\d{2}-\d{2}\.svg", nm), nm)
    try: xml.dom.minidom.parseString(raw); ok = True
    except Exception as e: ok = False
    check("SVG: well-formed XML with a declaration", ok and svg.startswith("<?xml"))
    m = re.search(r'<svg[^>]*viewBox="0 0 (\d+) (\d+)"[^>]*width="(\d+)" height="(\d+)"', svg)
    check("SVG: a fixed size (viewBox and width/height agree, 1400 units wide), not 100%", m and m.group(1) == m.group(3) == "1400" and m.group(2) == m.group(4) and 'width="100%"' not in svg, svg[:300])
    check("SVG: the text is text (task names are <text>, escaped), not paths", ">Discovery workshop<" in svg and "Design phase &amp; &lt;review&gt;" in svg)
    H = int(m.group(2)); rows = 5
    check("SVG: ONE image for every row — height = header + rows × 18 + footer", H == 30 + 30 + rows * 18 + 16, H)
    check("SVG: bars, a milestone diamond, dependency arrows and the today/legend parts are drawn", svg.count("<rect") > 20 and "<polygon" in svg and "<path" in svg and "marker-end" in svg)
    nmp, rawp = grab("png"); sz = png_size(rawp)
    check("PNG: a real PNG named .png", sz is not None and nmp.endswith(".png"), nmp)
    check("PNG: 2x — 2800 px wide, height 2 × the drawing's", sz == (2800, 2 * H), (sz, H))
    # options are honoured
    pg.uncheck("#printDeps"); pg.wait_for_timeout(100)
    _, raw2 = grab("svg"); s2 = raw2.decode("utf-8")
    check("the dialog's options apply: with 'Dependency arrows' off there are no arrows", "marker-end" not in s2 and "marker-end" in svg)
    pg.check("#printDeps"); pg.uncheck("#printCol-duration"); pg.wait_for_timeout(100)
    _, raw3 = grab("svg")
    check("...and an unticked column is gone from the picture", raw3.decode("utf-8").count("<text") < svg.count("<text"))
    pg.check("#printCol-duration")
    pg.fill("#printTitle", "Q2 launch plan"); pg.dispatch_event("#printTitle", "input"); pg.wait_for_timeout(100)
    _, raw4 = grab("svg")
    check("...and the title", "Q2 launch plan" in raw4.decode("utf-8"))
    # paper does not matter
    pg.select_option("#printPaper", "A3"); pg.select_option("#printOrient", "portrait"); pg.wait_for_timeout(100)
    _, raw5 = grab("svg"); m5 = re.search(r'viewBox="0 0 (\d+) (\d+)"', raw5.decode("utf-8"))
    check("the picture ignores the paper and orientation (still 1400 wide, same height)", m5 and m5.group(1) == "1400" and int(m5.group(2)) == H)
    # copy
    pg.click("#printCopyImg"); pg.wait_for_function("() => /Copied|refused|can.t copy/.test(document.getElementById('toastMsg').textContent)", timeout=8000)
    toast = ev("() => document.getElementById('toastMsg').textContent")
    clip = ev("async () => { try { const items = await navigator.clipboard.read(); return items.length ? items[0].types : []; } catch (e) { return ['error:' + e.message]; } }")
    check("Copy puts a PNG on the clipboard and says so", "image/png" in clip and "Copied the chart" in toast, (clip, toast))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    # a tall plan
    ev(SEED, 1000); pg.wait_for_timeout(300); open_print()
    nmt, rawt = grab("png"); szt = png_size(rawt)
    Ht = 30 + 30 + 1005 * 18 + 16
    check("a tall plan (1,005 rows): the PNG scale drops so no side passes 16,000 px, the shape stays", szt and max(szt) <= 16000 and abs(szt[1] / szt[0] - Ht / 1400) < 0.01, (szt, Ht))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    ev(SEED, 2500); pg.wait_for_timeout(500); open_print()
    pg.click("#printPng"); pg.wait_for_timeout(800)
    check("a plan too tall even for 0.5x refuses the PNG and points to SVG", "too tall" in ev("() => document.getElementById('toastMsg').textContent"), ev("() => document.getElementById('toastMsg').textContent"))
    nms, raws = grab("svg")
    check("...while the SVG still works for it", len(raws) > 100000 and b"</svg>" in raws[-10:])
    pg.keyboard.press("Escape")
    # unaffected: normal print preview still paginated
    ev(SEED, 60); pg.wait_for_timeout(300); open_print()
    check("the normal print preview is still paginated (60 rows don't fit one A4 page)", "2 page" in pg.inner_text("#printSummary") or "3 page" in pg.inner_text("#printSummary") or "pages" in pg.inner_text("#printSummary"), pg.inner_text("#printSummary"))
    b.close()
check("no console errors", not errors, errors)
print(f"\n{sum(results)}/{len(results)}"); raise SystemExit(0 if all(results) else 1)
