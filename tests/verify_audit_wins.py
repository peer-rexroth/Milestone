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
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
