from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
TABS = ["start", "scheduling", "progress", "list", "gantt", "data"]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    open_help = lambda: (pg.click("button[title='Help']"), pg.wait_for_selector("#helpModalBg.open"), pg.wait_for_timeout(250))
    visible = lambda: ev("() => [...document.querySelectorAll('#helpModalBg .help-pane')].filter(p => !p.hidden).map(p => p.id.replace('helpPane-', ''))")
    open_help()

    check("the Help button opens the dialog on the first topic, Getting started", visible() == ["start"] and ev("() => document.getElementById('helpTab-start').classList.contains('active')"))
    check("it has six topics in a tab list, each tab controlling its own pane", ev("() => [...document.querySelectorAll('#helpModalBg [role=tab]')].map(t => t.id.replace('helpTab-', ''))") == TABS and ev("() => [...document.querySelectorAll('#helpModalBg [role=tab]')].every(t => document.getElementById(t.getAttribute('aria-controls')))"))
    check("...and the dialog is well-formed: header, the tabbed layout, the footer (nothing spills out of it)", ev("() => [...document.querySelector('#helpModalBg .modal').children].map(c => c.className.split(' ')[0])") == ["modal-header", "help-layout", "modal-footer"] and ev("() => document.querySelector('#helpModalBg').children.length") == 1)

    # ---------------------------------------------------------------- switching
    size0 = ev("() => { const r = document.querySelector('#helpModalBg .modal').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }")
    sizes, ok = [], True
    for t in TABS:
        pg.click(f"#helpTab-{t}"); pg.wait_for_timeout(80)
        v = visible(); sel = ev(f"() => document.getElementById('helpTab-{t}').getAttribute('aria-selected') === 'true' && document.querySelectorAll('#helpModalBg [aria-selected=true]').length === 1")
        sizes.append(ev("() => { const r = document.querySelector('#helpModalBg .modal').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }"))
        ok = ok and v == [t] and sel
    check("clicking each topic shows exactly its pane and marks exactly its tab selected", ok)
    check("the dialog keeps the same size on every topic (it never jumps)", all(s == size0 for s in sizes), (size0, sizes))
    pg.click("#helpTab-list"); pg.evaluate("() => { document.getElementById('helpPane-list').scrollTop = 200; }"); pg.click("#helpTab-gantt"); pg.click("#helpTab-list")
    check("coming back to a topic starts at its top", ev("() => document.getElementById('helpPane-list').scrollTop") == 0)
    check("a long topic scrolls inside its pane, the header, the tab rail and the footer stay put", ev("() => { const p = document.getElementById('helpPane-start'); return p.scrollHeight > p.clientHeight && getComputedStyle(p).overflowY === 'auto'; }") if pg.click("#helpTab-start") is None else False)

    # ---------------------------------------------------------------- keyboard
    pg.focus("#helpTab-start"); pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(60)
    check("ArrowDown on the tab list moves to the next topic and focuses it", visible() == ["scheduling"] and ev("() => document.activeElement.id") == "helpTab-scheduling")
    pg.keyboard.press("End"); pg.keyboard.press("ArrowDown")
    check("End jumps to the last topic and the list wraps around after it", visible() == ["start"], visible())
    pg.keyboard.press("ArrowUp"); check("ArrowUp wraps to the last topic", visible() == ["data"], visible())
    pg.keyboard.press("Home"); check("Home goes to the first", visible() == ["start"])
    check("only the selected tab is in the tab order", ev("() => [...document.querySelectorAll('#helpModalBg [role=tab]')].filter(t => t.tabIndex === 0).length") == 1)

    # ---------------------------------------------------------------- closing and remembering
    pg.click("#helpTab-gantt"); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("Escape closes the dialog", not ev("() => document.getElementById('helpModalBg').classList.contains('open')"))
    open_help()
    check("reopening it returns to the topic you were reading (Gantt chart)", visible() == ["gantt"], visible())
    pg.mouse.click(10, 400); pg.wait_for_timeout(200)
    check("a click on the backdrop closes it too", not ev("() => document.getElementById('helpModalBg').classList.contains('open')"))
    open_help(); pg.click("#helpModalBg .modal-footer .btn"); pg.wait_for_timeout(200)
    check("the Close button closes it", not ev("() => document.getElementById('helpModalBg').classList.contains('open')"))

    # ---------------------------------------------------------------- content
    txt = {t: ev(f"() => document.getElementById('helpPane-{t}').textContent") for t in TABS}
    need = {"start": ["Add Task", "Clone", "Undo and redo", "Ctrl/Cmd", "milestone", "Selecting several tasks", "Copy and paste", "Find a task", "Edit tasks"], "scheduling": ["Auto Scheduled", "Manually Scheduled", "Start No Earlier Than", "circular dependency", "3FS+2"],
            "progress": ["holidays", "Working calendar", "Actual Finish", "baseline", "Variance", "Remaining Duration", "Public holidays"], "list": ["Columns", "Custom fields", "funnel", "(Blanks)"],
            "gantt": ["critical path", "Week / Month / Year", "dependency", "Printing", "Save as PDF"], "data": ["JSON file", "conflicts", "Export to Excel", "Local Backups", "Nothing here ever leaves your machine", "Import MS Project XML", "CSV"]}
    missing = {t: [w for w in ws if w not in txt[t]] for t, ws in need.items()}
    check("every topic covers what belongs to it (features, terms, the security note)", all(not m for m in missing.values()), {t: m for t, m in missing.items() if m})
    counts = ev("() => Object.fromEntries([...document.querySelectorAll('#helpModalBg .help-pane')].map(p => [p.id.replace('helpPane-', ''), [p.querySelectorAll('.help-section').length, p.querySelectorAll('.help-row').length]]))")
    check("each topic is a few titled sections of short icon rows (>= 1 section with rows; 45+ rows overall)", all(c[0] >= 1 and c[1] >= 2 for c in counts.values()) and sum(c[1] for c in counts.values()) >= 45, counts)
    check("every icon is a Font Awesome class (no empty icon slots)", ev("() => [...document.querySelectorAll('#helpModalBg .help-row > i')].every(i => /fa-[a-z-]+/.test(i.className.replace('fa-solid', '')))"))
    check("no paragraph is a wall of text: every row is under 480 characters", ev("() => [...document.querySelectorAll('#helpModalBg .help-row')].every(r => r.textContent.length < 480)"))

    # ---------------------------------------------------------------- looks: contrast in both themes, narrow screens
    def contrast(pg):
        return ev("""() => { const lum = c => { const m = c.match(/[\\d.]+/g).map(Number); const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]); };
          const bg = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; if (!/rgba\\(0, 0, 0, 0\\)|transparent/.test(c)) return c; } return 'rgb(255,255,255)'; };
          const ratio = el => { const a = lum(getComputedStyle(el).color), b2 = lum(bg(el)); return (Math.max(a, b2) + .05) / (Math.min(a, b2) + .05); };
          const q = s => ratio(document.querySelector(s));
          return { body: q('#helpPane-start .help-row > span'), strong: q('#helpPane-start .help-row strong'), title: q('#helpPane-start .help-section-title'), active: q('#helpModalBg .help-nav button.active'), idle: q('#helpTab-list'), code: q('#helpPane-scheduling code') }; }""")
    open_help(); pg.click("#helpTab-start"); pg.wait_for_timeout(100)
    light = contrast(pg)
    check("light theme: body text, bold text, section titles and tabs are readable (contrast >= 4.5, 7 for bold text)", light["body"] >= 4.5 and light["strong"] >= 7 and light["title"] >= 4.5 and light["active"] >= 4.5 and light["idle"] >= 4.5, light)
    pg.keyboard.press("Escape"); ev("() => { if (document.documentElement.dataset.theme !== 'dark') toggleTheme(); }"); open_help(); pg.click("#helpTab-scheduling"); pg.wait_for_timeout(100)
    dark = contrast(pg)
    check("dark theme: the same holds", dark["body"] >= 4.5 and dark["strong"] >= 7 and dark["title"] >= 4.5 and dark["idle"] >= 4.5 and dark["active"] >= 4.5 and dark["code"] >= 4.5, dark)
    pg.keyboard.press("Escape")
    pg.set_viewport_size({"width": 560, "height": 700}); open_help(); pg.wait_for_timeout(200)
    nar = ev("() => { const n = document.querySelector('.help-nav'), m = document.querySelector('#helpModalBg .modal').getBoundingClientRect(); return { dir: getComputedStyle(n).flexDirection, fits: m.right <= innerWidth + 0.5 && m.left >= -0.5, hscroll: document.documentElement.scrollWidth <= innerWidth, paneVisible: !document.querySelector('.help-pane:not([hidden])').hidden }; }")
    check("on a narrow screen the topics become a strip along the top and the dialog still fits the window", nar["dir"] == "row" and nar["fits"] and nar["hscroll"], nar)
    pg.keyboard.press("Escape")
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
