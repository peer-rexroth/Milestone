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
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
