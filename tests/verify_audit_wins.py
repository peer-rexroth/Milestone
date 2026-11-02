"""Four small accessibility fixes from the 2026-11-01 UX/UI audit: link-style buttons readable in the dark theme (M-01), the group chevron has a name, a state and a 20px+ target
(M-02), the status pill on a selected row keeps 4.5:1 (M-03), and every dialog puts focus inside itself when it opens, never on the close button (M-05)."""
from playwright.sync_api import sync_playwright
from PIL import Image
import io, os, re
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
SEED = """() => {
  const mk = (id, name, parent, order, s, e, extra) => Object.assign({ id, name, parentId: parent, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'manual', updatedAt: 1 }, extra || {});
  tasks = [ mk('a','Alpha',null,0,'2027-01-04','2027-02-26'), mk('a1','A one','a',0,'2027-01-04','2027-01-29'), mk('a2','A two','a',1,'2027-02-01','2027-02-26',{ taskMode: 'auto' }), mk('b','Beta',null,1,'2027-03-01','2027-04-30'), mk('b1','B one','b',0,'2027-03-01','2027-03-31') ];
  normalizeData(); save(); render();
}"""
def lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= .03928 else (((v / 255) + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])
def ratio(a, b): hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b)); return (hi + .05) / (lo + .05)
def rgb(css): v = [float(x) for x in re.findall(r"[\d.]+", css)][:3]; return v
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); errors = []
    for theme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme=theme); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
        ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(300)
        # M-02
        info = ev("() => [...document.querySelectorAll('.grid-row .chevron:not(.empty)')].map(e => [e.getAttribute('aria-label'), e.getAttribute('aria-expanded'), e.title, e.tabIndex])")
        check(f"[{theme}] a group chevron is named, says whether it is expanded, and is in the tab order", info and all(i[0] and i[1] in ("true", "false") and i[2] and i[3] == 0 for i in info) and info[0][0] == "Collapse group", info)
        ev("() => toggleCollapse('a')"); pg.wait_for_timeout(200)
        check(f"[{theme}] collapsing a group flips the chevron to 'Expand group' / aria-expanded=false", ev("() => { const c = document.querySelector('.grid-row .chevron:not(.empty)'); return [c.getAttribute('aria-label'), c.getAttribute('aria-expanded')]; }") == ["Expand group", "false"])
        ev("() => toggleCollapse('a')"); pg.wait_for_timeout(200)
        hit = ev("""() => { const e = document.querySelector('.grid-row .chevron:not(.empty)'); const r = e.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; let w = 0, h = 0; const ok = (x, y) => { const t = document.elementFromPoint(x, y); return t && (t === e || e.contains(t)); };
          for (let d = 1; d <= 20; d++) { if (ok(cx - d, cy) && ok(cx + d, cy)) w = d * 2; else break; } for (let d = 1; d <= 20; d++) { if (ok(cx, cy - d) && ok(cx, cy + d)) h = d * 2; else break; } return [w, h]; }""")
        check(f"[{theme}] its effective hit area is at least 20 x 20", hit[0] >= 20 and hit[1] >= 20, hit)
        check(f"[{theme}] leaf rows keep an invisible, unfocusable placeholder", ev("() => [...document.querySelectorAll('.grid-row .chevron.empty')].every(e => e.getAttribute('aria-hidden') === 'true' && e.tabIndex === -1)"))
        # M-03
        ev("() => { setSelection(['a2']); render(); }"); pg.wait_for_timeout(300); pg.mouse.move(900, 800)
        pill = ev("""() => { const e = document.querySelector('.grid-row.selected .status-pill'); const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height, color: getComputedStyle(e).color }; }""")
        pg.add_style_tag(content=".grid-row.selected .status-pill { color: transparent !important }"); pg.wait_for_timeout(100)
        img = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
        px = img.getpixel((int(pill["x"] + 3), int(pill["y"] + pill["h"] / 2)))
        check(f"[{theme}] the status pill on a selected row keeps 4.5:1 (white on the pill)", ratio(rgb(pill["color"]), px) >= 4.5, round(ratio(rgb(pill["color"]), px), 2))
        # M-01
        ev("() => { setSelection([]); openSlideChart(); }"); pg.wait_for_timeout(500)
        link = ev("""() => { const e = [...document.querySelectorAll('#slideChartModalBg .btn-link')].find(x => x.offsetParent); return e ? { c: getComputedStyle(e).color, x: e.getBoundingClientRect().left, y: e.getBoundingClientRect().top, h: e.getBoundingClientRect().height } : null; }""")
        if link:
            pg.add_style_tag(content="#slideChartModalBg .btn-link { color: transparent !important }"); pg.wait_for_timeout(100)
            img = Image.open(io.BytesIO(pg.screenshot())).convert("RGB"); px = img.getpixel((int(link["x"] + 1), int(link["y"] + link["h"] / 2)))
            check(f"[{theme}] a link-style button in a dialog is readable (4.5:1)", ratio(rgb(link["c"]), px) >= 4.5, round(ratio(rgb(link["c"]), px), 2))
        else: check(f"[{theme}] a link-style button is visible in the Chart for Slides dialog", False)
        ev("() => closeSlideChart()")
        # M-05
        if theme == "light":
            opens = {"reschedule": "openRescheduleModal()", "level": "openLevelModal()", "rules": "openRulesModal()", "format": "openFormatModal()", "fields": "openFieldsModal()", "print": "openPrintModal()", "slides": "openSlideChart()", "help": "openHelpModal()", "shortcuts": "openShortcuts()", "about": "openAboutModal()", "import": "openImportModal()"}
            bad = {}
            for n, js in opens.items():
                ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); document.activeElement.blur(); }")
                ev("() => " + js); pg.wait_for_timeout(350)
                r = ev("""() => { const bg = document.querySelector('.modal-bg.open'); const a = document.activeElement; return [bg.contains(a), a.closest('.modal-header') ? 'header' : (a.id || a.className || a.tagName).toString().slice(0, 24)]; }""")
                if not r[0] or r[1] == 'header': bad[n] = r
            check("dialogs that did not place focus themselves now get it inside, and never on the close button", not bad, bad)
            ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); document.activeElement.blur(); openPrintModal(); }"); pg.wait_for_timeout(350)
            check("Print puts the cursor in its Title field", ev("() => document.activeElement.id") == "printTitle", ev("() => document.activeElement.id"))
            ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); document.activeElement.blur(); openAboutModal(); }"); pg.wait_for_timeout(350)
            check("a dialog with nothing to fill in (About) focuses the dialog itself, so Return does not press a button", ev("() => document.activeElement.classList.contains('modal')"))
            ev("() => { document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); }")
        ctx.close()
    # the focus ring of the last row of a dialog is not cut off (Rename Plan)
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => openPlanModal()"); pg.wait_for_timeout(500)
    gap = pg.evaluate("() => { const row = document.querySelector('#planModalBg .trow'); const body = row.closest('.modal-body'); return Math.round(body.getBoundingClientRect().bottom - row.getBoundingClientRect().bottom); }")
    check("the focus ring (3px) under the last row of Rename Plan fits inside the dialog body instead of being cut off", gap >= 3 and pg.evaluate("() => document.activeElement.id") == "planNameInput", gap)
    pg.close()
    # icons: every close glyph is the registry's xmark, and the inline drawings that were outside the registry are registry icons now
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html"), encoding="utf-8").read()
    check("no text '×' is used as an icon any more (23 close buttons use the xmark icon)", "&times;" not in src and src.count('aria-label="Close"><i class="fa-solid fa-xmark"></i></button>') >= 20)
    check("the sidebar toggle, the Task Form step buttons and the folder line use registry icons", all(x in src for x in ('fa-sidebar', 'fa-chevron-left', 'fa-chevron-right', 'fa-folder')) and 'M10 3L5 8l5 5' not in src and 'x="1.5" y="2.5" width="13"' not in src)
    # small fixes (M-06, M-08, M-09, M-12, M-14, M-15, M-22): source checks
    import re as _re
    css = src[src.index("<style>"):src.index("</style>", src.index("<style>"))]
    check("no font weight outside 400 / 500 / 600 / 700 in the stylesheet", not _re.findall(r"font-weight:\s*(?!400|500|600|700|inherit|normal|bold)\d+", css), _re.findall(r"font-weight:\s*\d+", css)[:5])
    check("no px radius off the ladder (only the r-* tokens, 50%, 999px, 0, 22% for the app icon)", not [x for x in _re.findall(r"border-radius:\s*([^;}]+)", css) if _re.search(r"(?<![\w.-])\d+(\.\d+)?px", x) and "var(--r-" not in x and "999px" not in x and "calc(" not in x], [x for x in _re.findall(r"border-radius:\s*([^;}]+)", css) if _re.search(r"(?<![\w.-])\d+(\.\d+)?px", x) and "var(--r-" not in x and "999px" not in x][:5])
    check("the retired --radius alias is gone", "var(--radius)" not in src and "--radius:" not in src)
    titles = [t for t in _re.findall(r'\btitle="([^"$]*)"', src[src.index("</style>"):])]
    check("no static tooltip is longer than 75 characters", not [t for t in titles if len(t) > 75], [t[:40] for t in titles if len(t) > 75][:5])
    check("two theme-color metas (light, dark) and a manifest colour that matches the light one", len(_re.findall(r'<meta name="theme-color"', src)) == 2 and '"theme_color": "#f5f6f9"' in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifest.json"), encoding="utf-8").read())
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(300)
    check("Import is an alert dialog (role alertdialog)", pg.evaluate("() => document.querySelector('#importModalBg .modal').getAttribute('role')") == "alertdialog")
    pg.click("body", position={"x": 700, "y": 600}); pg.keyboard.press("Control+Comma" if not pg.evaluate("() => IS_MAC") else "Meta+Comma"); pg.wait_for_timeout(300)
    check("Cmd+, (Ctrl+, off a Mac) opens Plan settings, as the tooltip says", pg.evaluate("() => !!document.querySelector('.modal-bg.open .settings-modal')"))
    check("the Plan settings tooltip names the shortcut of this platform", pg.evaluate("() => document.getElementById('planSettingsBtn').title.endsWith(IS_MAC ? '(⌘,)' : '(Ctrl+,)')"))
    pg.close()
    # an installed app's window puts the app name in front of the page title itself: the plan's name alone there, "<plan> · Milestone" in a tab
    pg = b.new_page(); pg.goto(URL); pg.wait_for_selector("#undoBtn"); ev = pg.evaluate
    tab = ev("() => document.title")
    ev("() => { const m = window.matchMedia.bind(window); window.matchMedia = q => q.includes('standalone') ? { matches: true, media: q, addEventListener() {}, removeEventListener() {} } : m(q); updateProjectNameUI(); }")
    inst = ev("() => document.title")
    check("the page title is '<plan> · Milestone' in a tab and just the plan in an installed window (the window adds 'Milestone - ' itself)", tab.endswith(" · Milestone") and inst == tab[:-len(" · Milestone")], [tab, inst])
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
