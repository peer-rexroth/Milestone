"""New-version notice (as in ClearDesk): when the server's headers for the page differ from the ones the open page was loaded with, a banner offers Reload;
Help > Check for Updates answers either way; the banner can be dismissed (and comes back on request)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1400, "height": 800}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(500)
    ev = pg.evaluate; ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    banner = lambda: ev("() => document.getElementById('updateBanner').classList.contains('show')")
    stub = lambda etag: ev("(e) => { window.fetch = async () => ({ headers: new Headers({ etag: e }) }); }", etag)
    ev("() => { loadedVersionStamp = 'v1'; }")
    stub("v1"); ev("() => checkForNewVersion()"); pg.wait_for_timeout(100)
    check("same headers: no banner", not banner())
    stub("v2"); ev("() => checkForNewVersion()"); pg.wait_for_timeout(100)
    check("different headers: the banner says a new version is ready, with Reload", banner() and "Milestone" in pg.inner_text("#updateBanner") and pg.locator("#updateBanner .btn-primary").inner_text() == "Reload")
    pg.click("#updateBanner .icon-btn"); pg.wait_for_timeout(100)
    check("Not now hides it", not banner())
    ev("() => checkForNewVersion()"); pg.wait_for_timeout(100)
    check("...and it stays hidden on the next automatic check", not banner())
    ev("() => checkForUpdatesNow()"); pg.wait_for_timeout(200)
    check("Check for Updates brings it back and says so", banner() and "new version" in pg.inner_text("#toastMsg"))
    stub("v1"); ev("() => { dismissUpdateBanner(); }"); ev("() => checkForUpdatesNow()"); pg.wait_for_timeout(200)
    check("Check for Updates with nothing new says Milestone is up to date", "up to date" in pg.inner_text("#toastMsg") and not banner(), pg.inner_text("#toastMsg"))
    ev("() => { window.fetch = async () => { throw new Error('offline'); }; }"); ev("() => checkForUpdatesNow()"); pg.wait_for_timeout(200)
    check("offline: it says it could not reach the server", "Could not reach" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    check("the Help menu has Check for Updates", ev("() => [...document.querySelectorAll('#helpMenu .dropdown-item')].some(i => i.textContent.trim() === 'Check for Updates')"))
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
