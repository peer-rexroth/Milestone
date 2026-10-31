"""The five fixes from the UX/UI audit: Reduce Motion, plan-row and resource-row context menus, title-style wording,
no colour literals outside tokens, and the platform-specific Find and replace shortcut."""
from playwright.sync_api import sync_playwright
import os, re
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
HERE = os.path.dirname(os.path.abspath(__file__))
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
NOFS = "delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker"
SEED = """() => { localStorage.clear(); }"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    errors = []
    def page(platform="Win32", **kw):
        pg = b.new_page(viewport={"width": 1400, "height": 900}, **kw); pg.add_init_script(NOFS + "; Object.defineProperty(navigator, 'platform', {get: () => '" + platform + "'})")
        pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(URL); pg.wait_for_selector("#undoBtn")
        pg.evaluate(SEED); pg.reload(); pg.wait_for_selector("#undoBtn"); return pg
    def seed(pg):
        pg.evaluate("""() => { tasks.length = 0; const mk = (n, par) => { tasks.push({id: genId(), name: n, parentId: par || null, order: tasks.length, startDate: '2026-10-21', endDate: '2026-10-23', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}); return tasks[tasks.length - 1].id; }; const g = mk('Group'); mk('Kid', g); mk('Two'); save(); render(); }""")

    # ---------------------------------------------------------------- 1. Reduce Motion
    pg = page(reduced_motion="reduce"); seed(pg)
    pg.evaluate("() => { const i = document.createElement('i'); i.id = 'spinProbe'; i.className = 'fa-solid fa-spinner fa-spin'; document.body.appendChild(i); }")
    d = pg.evaluate("() => parseFloat(getComputedStyle(document.getElementById('spinProbe')).animationDuration)")
    check("Reduce Motion: the spinner's animation is effectively off", d < 0.001, d)
    t = pg.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.modal-bg')).transitionDuration)")
    check("...and transitions are effectively instant", t < 0.001, t)
    pg.close()
    pg = page(); seed(pg)
    pg.evaluate("() => { const i = document.createElement('i'); i.id = 'spinProbe'; i.className = 'fa-solid fa-spinner fa-spin'; document.body.appendChild(i); }")
    check("Without the setting the spinner still turns (1s)", pg.evaluate("() => parseFloat(getComputedStyle(document.getElementById('spinProbe')).animationDuration)") == 1)
    pg.close()

    # ---------------------------------------------------------------- 2. context menus
    pg = page(); seed(pg)
    pg.evaluate("() => { createPlanRecord('Second', null); renderSidebarPlans(); }"); pg.wait_for_timeout(200)
    rows = pg.locator(".sb-plan-row"); check("two plans are listed in the sidebar", rows.count() == 2, rows.count())
    rows.nth(0).click(button="right"); pg.wait_for_selector("#rowMenu.open")
    labels = pg.evaluate("() => [...document.querySelectorAll('#rowMenu .dropdown-item')].map(e => e.textContent.trim())")
    check("plan row menu on the open plan: Rename, Duplicate, Delete (no Open Plan, no Unlink without a file)", labels == ["Rename Plan…", "Duplicate Plan…", "Delete Plan…"], labels)
    check("...Delete is the red last item", pg.evaluate("() => { const i = [...document.querySelectorAll('#rowMenu .dropdown-item')]; return i[i.length - 1].classList.contains('danger'); }"))
    pg.keyboard.press("Escape"); pg.mouse.click(700, 500); pg.wait_for_timeout(150)
    rows.nth(1).click(button="right"); pg.wait_for_selector("#rowMenu.open")
    labels = pg.evaluate("() => [...document.querySelectorAll('#rowMenu .dropdown-item')].map(e => e.textContent.trim())")
    check("another plan's menu starts with Open Plan", labels[0] == "Open Plan" and "Delete Plan…" in labels, labels)
    pg.locator("#rowMenu .dropdown-item", has_text="Rename Plan").click(); pg.wait_for_selector("#planModalBg.open", timeout=4000)
    check("Rename on another plan opens that plan first, then the rename dialog", pg.evaluate("() => project.name") == "Second" and pg.input_value("#planNameInput") == "Second", pg.evaluate("() => project.name"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)

    pg.evaluate("() => { setView('resourceSheet'); project.resources = [{id: genId(), name: 'Ann', type: 'work', maxUnits: 100}]; save(); render(); }"); pg.wait_for_timeout(300)
    row = pg.locator("#resourceSheetBody .rst-row").first
    row.locator(".rst-id").click(button="right"); pg.wait_for_selector("#rowMenu.open")
    labels = pg.evaluate("() => [...document.querySelectorAll('#rowMenu .dropdown-item')].map(e => e.textContent.trim())")
    check("Resource Sheet row menu: Add Resource, Days Off…, Remove Resource", labels == ["Add Resource", "Days Off…", "Remove Resource"], labels)
    pg.locator("#rowMenu .dropdown-item", has_text="Add Resource").click(); pg.wait_for_timeout(200)
    check("...Add Resource adds a row", pg.evaluate("() => project.resources.length") == 2)
    pg.locator("#resourceSheetBody .rst-row").first.locator(".rst-cell").nth(1).click(button="right"); pg.wait_for_selector("#rowMenu.open")
    check("a right-click on a name cell also offers the row menu", pg.locator("#rowMenu .dropdown-item", has_text="Remove Resource").count() == 1)
    pg.keyboard.press("Escape"); pg.mouse.click(700, 80); pg.wait_for_timeout(150)
    pg.locator("#resourceSheetBody .rst-row").first.locator(".rst-cell").nth(1).dblclick(); pg.wait_for_timeout(100)
    pg.evaluate("() => document.activeElement.select()")
    pg.locator("#resourceSheetBody .rst-row").first.locator("input.inline-edit").first.click(button="right"); pg.wait_for_timeout(250)
    check("...but with text selected the browser's own menu stays (no app menu)", pg.evaluate("() => !document.getElementById('rowMenu').classList.contains('open')"))
    pg.close()

    # ---------------------------------------------------------------- 3. wording
    pg = page(); seed(pg)
    pg.evaluate("() => { setView('tasks'); }"); pg.wait_for_timeout(200)
    pg.locator("#gridRows .grid-row", has_text="Two").first.click(button="right"); pg.wait_for_selector("#rowMenu.open")
    labels = pg.evaluate("() => [...document.querySelectorAll('#rowMenu .dropdown-item')].map(e => e.textContent.trim())")
    small = {"a", "an", "the", "of", "to", "in", "on", "and", "or", "for", "by", "at", "from", "with", "as"}
    def title_style(l):
        words = re.sub(r"[…]", "", re.sub(r"⌘\w|Ctrl\+\w", "", l)).replace("-", "- ").split()
        words = [w for w in words if w[0].isalpha()]
        return all(w[0].isupper() or w.lower() in small for w in words[1:]) and words[0][0].isupper()
    bad = [l for l in labels if not title_style(l)]
    check("every task-row menu item is in title style", not bad, bad)
    check("...with the new wording (Edit Task…, Add Task Below)", "Edit Task…" in labels and "Add Task Below" in labels, labels)
    pg.keyboard.press("Escape")
    html = open(os.path.join(HERE, "..", "index.html"), encoding="utf-8").read()
    heads = re.findall(r"<h2[^>]*>([^<]+)(?:</h2>|<span)", html)
    sent = [h for h in heads if re.search(r"\b(?:task|plan|work|backups|settings|resources|replace|pdf|shortcuts|sides)\b", h) and h not in ("Plan file",)]
    check("sheet titles carry no lower-case noun (Local Backups, Plan Settings, Level Resources …)", not sent, sent)
    pg.close()

    # ---------------------------------------------------------------- 4. no colour literals outside tokens
    css = html[html.index("<style"):html.index("</style>")]
    in_print = False; bad = []
    for n, l in enumerate(css.split("\n")):
        t = l.strip()
        if t.startswith("@media print"): in_print = True
        if re.match(r"--[\w-]+:", t) or "--" in t.split(":")[0] and t.split(":")[0].strip().startswith("--"): continue
        if re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", l) and not in_print and not re.search(r"\{ *--[\w-]+:[^;]*\}\s*$", t) and not re.search(r"\{ --[\w-]+:", t):
            bad.append((n, t[:70]))
    check("no hex / rgba literal in a rule outside token definitions and the print block", not bad, bad[:5])

    # ---------------------------------------------------------------- 5. Find and replace shortcut
    pg = page(); seed(pg)
    pg.keyboard.press("Control+h"); pg.wait_for_selector("#replaceModalBg.open", timeout=3000)
    check("non-Mac: Ctrl+H opens Find and replace", pg.evaluate("() => document.getElementById('replaceModalBg').classList.contains('open')")); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.keyboard.press("?"); pg.wait_for_selector("#shortcutsModalBg.open")
    check("...and the Shortcuts sheet lists Ctrl H, not the Mac keys", "⌥" not in pg.inner_text("#shortcutsModalBg"))
    pg.keyboard.press("Escape")
    pg.close()
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.add_init_script(NOFS + "; Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate(SEED); pg.reload(); pg.wait_for_selector("#undoBtn"); seed(pg)
    pg.keyboard.press("Control+h"); pg.wait_for_timeout(300)
    check("Mac: Ctrl+H no longer opens it", not pg.evaluate("() => document.getElementById('replaceModalBg').classList.contains('open')"))
    pg.keyboard.press("Alt+Meta+f"); pg.wait_for_selector("#replaceModalBg.open", timeout=3000)
    check("Mac: ⌥⌘F opens Find and replace", pg.evaluate("() => document.getElementById('replaceModalBg').classList.contains('open')"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.keyboard.press("?"); pg.wait_for_selector("#shortcutsModalBg.open")
    txt = pg.inner_text("#shortcutsModalBg")
    check("Mac: the Shortcuts sheet shows ⌥ ⌘ F for it and no Ctrl+H", "Find and replace in many tasks" in txt and "⌥" in txt and "Ctrl" not in txt.split("Find and replace in many tasks")[0][-40:], txt[:80])
    pg.close()
    b.close()
print("errors:", errors[:3])
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) and not errors else 1)
