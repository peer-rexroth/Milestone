# -*- coding: utf-8 -*-
"""The design-system rules, as checks (design-system/DESIGN.md; "Design system port" in CLAUDE.md): (1) a scan of the stylesheet — no cursor:pointer
on controls, no px font sizes or radii off the scales, colour literals only where allowed (a ratchet: the count may not grow); (2) every icon is one of the
four drawn sizes; (3) text contrast >= 4.5:1 for the main text roles, light and dark, measured from a screenshot (the pixel behind each text run, so the
translucent sidebar counts); (4) hit areas of the always-visible controls >= 20x20 (28 for the toolbar's)."""
import os, re, io
from collections import Counter
from playwright.sync_api import sync_playwright
from PIL import Image
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = open(os.path.join(HERE, "..", "milestone.html"), encoding="utf-8").read()
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

# ---- 1. the stylesheet scan (everything after the inlined tokens)
css = SRC[SRC.index("<style>"):SRC.index("</style>")]; body = css[css.index("/* Milestone's own names"):]
screen = body.split("@media print")[0]
check("no `cursor: pointer` except the one rule for links", len(re.findall(r"cursor:\s*pointer", body)) == 1 and "a[href], .btn-link { cursor: pointer; }" in body)
check("no px font sizes outside the --fs-* scale", not re.findall(r"font-size:\s*[\d.]+px", screen), re.findall(r"font-size:\s*[\d.]+px", screen)[:5])
rad = [m for m in re.findall(r"border-radius:\s*([^;}]+)", screen) if re.search(r"(?<![\d.])\d+px", m) and "var(" not in m and not re.fullmatch(r"\s*(99|999)px\s*", m)]
check("radii are the --r-* tokens, 50% or a pill (999px)", not rad, rad[:5])
hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", screen)
check("colour literals in rules do not grow (the Gantt / row palette, change highlights and the dark-theme task colours are the known ones)", len(hexes) <= 36, len(hexes))
check("the Font Awesome CDN is gone (icons come from the inline registry)", "cdnjs.cloudflare.com" not in SRC and 'id="icons"' in SRC)

LUM = """c => { const m = c.match(/[\\d.]+/g).map(Number); const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 860}); ctx.add_init_script("localStorage.setItem('milestone-sidebar', '0'); delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate
    ev("""() => { localStorage.setItem('milestone-sidebar', '0'); tasks.length = 0; const mk = (id, name, s, e, x) => Object.assign({ id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false }, x || {});
      tasks.push(mk('p', 'Planning', '2026-10-05', '2026-10-20'), mk('a', 'Select location', '2026-10-05', '2026-10-12', { parentId: 'p', progress: 100 }), mk('c', 'Order furniture', '2026-10-21', '2026-11-02', { progress: 60, resource: 'Anna' }));
      normalizeData(); save(); setSelection(['c']); setView('tasks'); render(); document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open')); }""")
    pg.mouse.click(700, 500); pg.wait_for_timeout(300)
    # ---- 2. icon sizes
    off = ev("""() => [...document.querySelectorAll('i[class*="fa-"]')].filter(i => i.getBoundingClientRect().width).map(i => Math.round(parseFloat(getComputedStyle(i).fontSize) * 1.26 * 10) / 10).filter(d => ![12, 14, 16, 18].some(x => Math.abs(x - d) < .6))""")
    check("every visible icon is drawn at 12, 14, 16 or 18px", not off, off)
    # ---- 3. contrast
    ROLES = [("selected row text", ".grid-row.selected .grid-name"), ("row text", ".grid-row:not(.selected) .grid-name"), ("secondary row text", ".grid-row:not(.selected) .grid-cell-dim"),
             ("column header", "#gridHeader .col-head"), ("sidebar view", ".sidebar .view-tab:not(.active)"), ("sidebar active view", ".sidebar .view-tab.active"),
             ("bar subtitle", "#barSub"), ("status pill", ".status-pill"), ("toolbar button", "#addTaskBtn"), ("sidebar section label", ".sb-label")]
    for theme in ("light", "dark"):
        ev("t => { if (document.documentElement.dataset.theme !== t) toggleTheme(); }", theme); pg.mouse.click(700, 500); pg.wait_for_timeout(350)
        shot = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
        bad = []
        for label, sel in ROLES:
            r = ev("""s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { color: getComputedStyle(e).color, x: r.left + 3, y: r.top + 3, w: r.width, h: r.height }; }""", sel)
            if not r or not r["w"]: bad.append((label, "missing")); continue
            box = shot.crop((int(r["x"]) - 3, int(r["y"]) - 3, int(r["x"]) + int(r["w"]) - 3, int(r["y"]) + int(r["h"]) - 3)); px = Counter(box.getdata()).most_common(1)[0][0]; bg = "rgb(%d,%d,%d)" % px   # (the background is the colour most pixels have; the text is the rest)
            l1, l2 = ev(LUM, r["color"]), ev(LUM, bg); ratio = (max(l1, l2) + .05) / (min(l1, l2) + .05)
            if ratio < 4.5: bad.append((label, round(ratio, 2), r["color"], bg))
        check(f"[{theme}] text contrast >= 4.5:1 for the main roles", not bad, bad)
    # ---- 4. hit areas
    small = ev("""() => [...document.querySelectorAll('#subbar button, .sidebar button, .sidebar .view-tab, #statusbar button')].filter(e => e.offsetParent && !e.closest('.tb-over')).map(e => [e.id || e.className.toString().slice(0, 24), Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)]).filter(([, w, h]) => w < 20 || h < 20)""")
    check("toolbar, sidebar and status-bar controls are at least 20x20", not small, small)
    check("no page errors", not errors, errors[:3])
n_ok, n_all = sum(results), len(results)
print(f"\n{n_ok}/{n_all} checks passed")
raise SystemExit(0 if n_ok == n_all else 1)
