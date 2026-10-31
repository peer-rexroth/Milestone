"""The About dialog is ClearDesk's: a round close button top left, the app icon, name, tagline, version, credits and fine print; Esc and the button close it; the Help dialog's close button is an icon, centred."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={"width": 1300, "height": 800}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); ev = pg.evaluate; ev("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    ev("() => openAboutModal()"); pg.wait_for_timeout(250)
    check("the app icon (the file, not a drawing) is 88px", ev("() => { const i = document.querySelector('#aboutModalBg img.about-icon'); return !!i && /icon-192\\.png$/.test(i.getAttribute('src')) && i.getBoundingClientRect().width === 88; }"))
    check("name, tagline and credits are there, centred", ev("() => ['about-name', 'about-tag', 'about-credits'].every(c => { const e = document.querySelector('#aboutModalBg .' + c), m = document.querySelector('#aboutModalBg .about-modal'); return e && e.textContent.trim() && Math.abs((e.getBoundingClientRect().left + e.getBoundingClientRect().right) / 2 - (m.getBoundingClientRect().left + m.getBoundingClientRect().right) / 2) < 2; })"))
    check("there is no version number in it", "ersion" not in ev("() => document.querySelector('#aboutModalBg .about-modal').textContent"))
    check("a round 28px close button sits top left", ev("() => { const b = document.querySelector('#aboutModalBg .about-close'), m = document.querySelector('#aboutModalBg .about-modal').getBoundingClientRect(), r = b.getBoundingClientRect(); return r.width === 28 && r.height === 28 && r.left - m.left < 20 && r.top - m.top < 20 && getComputedStyle(b).borderRadius === '50%'; }"))
    pg.click("#aboutModalBg .about-close"); pg.wait_for_timeout(150)
    check("the close button closes it", not ev("() => document.getElementById('aboutModalBg').classList.contains('open')"))
    ev("() => openAboutModal()"); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Esc closes it", not ev("() => document.getElementById('aboutModalBg').classList.contains('open')"))
    ev("() => openHelpModal()"); pg.wait_for_timeout(250)
    check("the Help dialog's close button holds an icon, not a text ×", ev("() => { const b = document.querySelector('#helpModalBg .modal-header button[aria-label=Close]'); return !!b.querySelector('i.fa-xmark') && b.textContent.trim() === ''; }"))
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
