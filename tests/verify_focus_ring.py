"""Focus is visible: the focus tokens exist in both themes, and the sidebar's Find capsule keeps its fill and shows the accent ring while it has the cursor."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); errors = []
    for scheme in ("light", "dark"):
        pg = b.new_page(viewport={"width": 1400, "height": 800}, color_scheme=scheme); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
        pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
        ev = pg.evaluate
        tok = ev("() => [getComputedStyle(document.documentElement).getPropertyValue('--focus-ring').trim(), getComputedStyle(document.documentElement).getPropertyValue('--focus-edge').trim()]")
        check(f"{scheme}: --focus-ring and --focus-edge are defined", all(tok), tok)
        rest = ev("() => getComputedStyle(document.getElementById('sbSearch')).backgroundColor")
        pg.locator("#searchInput").focus(); pg.wait_for_timeout(150)
        f = ev("() => { const c = getComputedStyle(document.getElementById('sbSearch')); return [c.backgroundColor, c.boxShadow]; }")
        check(f"{scheme}: the Find capsule has a ring while focused", f[1] != "none" and "3px" in f[1], f)
        check(f"{scheme}: ...and does not lose its fill (it is not transparent)", f[0] not in ("rgba(0, 0, 0, 0)", "transparent"), (rest, f))
        pg.keyboard.press("Escape"); pg.close()
    # every keyboard-focus rule that draws something uses the shared ring token (or says "none": the Task Form rows tint instead)
    pg = b.new_page(viewport={"width": 1400, "height": 800}); pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn")
    bad = pg.evaluate("""() => { const out = [], walk = rules => { for (const r of rules) { if (r.cssRules && !r.selectorText) { walk(r.cssRules); continue; } const sel = r.selectorText || '';
      if (!/:focus-visible/.test(sel)) continue; const t = r.cssText.replace(/^[^{]*/, ''); const draws = /(outline|box-shadow)\\s*:/.test(t); if (!draws) continue;
      const ok = /focus-ring|focus-edge/.test(t) || /(outline|box-shadow)\\s*:\\s*none/.test(t) && !/(outline|box-shadow)\\s*:\\s*[^;n]/.test(t.replace(/(outline|box-shadow)\\s*:\\s*none[^;]*;?/g, '')); if (!ok) out.push(sel); } };
      for (const sh of document.styleSheets) { try { walk(sh.cssRules); } catch (e) {} } return out; }""")
    check("every :focus-visible rule that draws a ring uses --focus-ring / --focus-edge (no plain accent outlines, no 2px variants)", bad == [], bad)
    # ...and the one that was written wrongly once (a colour as a box-shadow) really draws: Tab onto a colour well of the slide chart
    pg.evaluate("() => { document.getElementById('fileSyncModalBg').classList.remove('open'); openSlideChart(); const s = document.getElementById('scPalette'); s.value = 'custom'; s.dispatchEvent(new Event('change', { bubbles: true })); }"); pg.wait_for_timeout(300)
    pg.evaluate("() => { if (document.getElementById('scMore').classList.contains('hidden')) scToggleMore(); }"); pg.wait_for_timeout(150)
    pg.keyboard.press("Tab"); pg.focus("#scCol0"); pg.wait_for_timeout(100)
    on = pg.evaluate("() => { const e = document.activeElement; const c = getComputedStyle(e); return [e.id, c.outlineStyle, c.outlineWidth, e.tagName + '.' + e.className]; }")
    check("a colour well of the slide chart shows a 3px ring when reached with the keyboard", on[0].startswith("scCol") and on[1] == "solid" and on[2] == "3px", on)
    pg.close()
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
