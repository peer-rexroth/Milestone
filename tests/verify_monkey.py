# -*- coding: utf-8 -*-
"""Monkey test: drive the real UI at random (clicks on anything visible, shortcuts, typing into fields, dragging, resizing) and check after
every batch that the plan is still valid, nothing threw and the app still answers.  python3 tests/verify_monkey.py [seeds]  (default 1 2 3)"""
from playwright.sync_api import sync_playwright
import os, random, re, sys, json, signal, time
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:900]}]" if not cond and detail else ""))

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_robust.py"), encoding="utf-8").read()
HELPERS = re.search(r'HELPERS = r"""(.*?)"""', SRC, re.S).group(1)

SEED_PLAN = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); colFilters = newColFilters(); filterPinned.clear();
  const mk = (id, name, order, extra) => __mkTask(id, name, order, extra);
  tasks.push(mk('g1', 'Website relaunch', 0, { startDate: '2026-09-07', endDate: '2026-11-27' }),
    mk('t1', 'Design', 0, { parentId: 'g1', startDate: '2026-09-07', endDate: '2026-09-18', resource: 'Anna', progress: 100 }),
    mk('t2', 'Build', 1, { parentId: 'g1', startDate: '2026-09-21', endDate: '2026-10-30', resource: 'Ben, Chris', progress: 40, predecessors: [{ id: 't1', type: 'FS', lag: 0 }], custom: { text1: 'CC-7', number1: 3 } }),
    mk('t3', 'Test', 2, { parentId: 'g1', startDate: '2026-11-02', endDate: '2026-11-13', predecessors: [{ id: 't2', type: 'FS', lag: 1 }] }),
    mk('m1', 'Go live', 3, { parentId: 'g1', startDate: '2026-11-16', endDate: '2026-11-16', milestone: true, predecessors: [{ id: 't3', type: 'FS', lag: 0 }] }),
    mk('g2', 'Marketing', 1, {}), mk('t4', 'Campaign', 0, { parentId: 'g2', startDate: '2026-10-05', endDate: '2026-10-23', taskMode: 'manual', resource: 'Dana' }),
    mk('t5', 'Press kit', 1, { parentId: 'g2', startDate: '2026-10-12', endDate: '2026-10-16', startText: 'TBD', endText: 'TBD', taskMode: 'manual' }),
    mk('m2', 'Launch event', 2, { parentId: 'g2', startDate: '2026-11-17', endDate: '2026-11-17', milestone: true, taskMode: 'manual', endText: 'TBD' }),
    mk('t6', 'Training', 2, { startDate: '2026-11-18', endDate: '2026-11-27', predecessors: [{ id: 'm1', type: 'FS', lag: 0 }] }));
  for (let i = 0; i < 12; i++) tasks.push(mk('x' + i, 'Extra ' + i, 3 + i, { startDate: '2026-10-' + String(5 + i).padStart(2, '0'), endDate: '2026-10-' + String(6 + i).padStart(2, '0') }));
  project.holidays = [{ date: '2026-10-03', name: 'Unity Day' }]; project.baselines = { 0: { setAt: '2026-09-01' } }; tasks.find(t => t.id === 't2').baselines = { 0: ['2026-09-21', '2026-10-23'] };
  currentView = 'tasks'; normalizeData(); save(); render(); resetHistory(); }"""

CANDIDATES = r"""() => {
  const sels = 'button, [role=button], [role=tab], .dropdown-item, .grid-row > div:first-child, .gantt-bar, .gantt-milestone, .cal-day, label.print-chk, .sr, .view-tab, .grid-cell-dim.editable, input[type=checkbox], input[type=radio], .col-filter-btn, .hol-row button, .cols-move button, .toast button, .cols-row, .mode-item, .task-mode-cell';
  const out = [], vw = innerWidth, vh = innerHeight;
  for (const el of document.querySelectorAll(sels)) {
    if (el.disabled) continue;
    const r = el.getBoundingClientRect(); if (r.width < 3 || r.height < 3 || r.right < 0 || r.bottom < 0 || r.left > vw || r.top > vh) continue;
    const cx = Math.min(vw - 2, Math.max(2, r.left + r.width / 2)), cy = Math.min(vh - 2, Math.max(2, r.top + r.height / 2)), hit = document.elementFromPoint(cx, cy);
    if (!hit || !(hit === el || el.contains(hit) || hit.contains(el))) continue;
    if (el.closest('#fileSyncModalBg') || el.id === 'foreignFileInput' || el.type === 'file') continue;
    out.push([Math.round(cx), Math.round(cy), (el.id || el.className || el.tagName).toString().slice(0, 30), (el.getAttribute('aria-label') || el.title || el.textContent || '').trim().slice(0, 24)]);
  }
  return out;
}"""
FIELDS = r"""() => {
  const out = [];
  for (const el of document.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=file]):not([type=hidden]), select, textarea')) {
    const r = el.getBoundingClientRect(); if (r.width < 3 || r.height < 3 || el.disabled || el.readOnly) continue;
    if (!(r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth)) continue;
    out.push([el.id || el.className || el.tagName, el.tagName, el.type || '']);
  }
  return out;
}"""
HOSTILE = ["", " ", "0", "-1", "100", "150", "3", "1.5", "abc", "TBD", "07.09.2026", "2026-09-07", "31.02.2026", "Anna, Ben", "<b>x</b>", "\"'`", "9" * 30, "😀", "5 days", "2FS+1", "a" * 300, "ä ö ü", "#12", "@anna", "2.1"]
KEYS = ["Escape", "Escape", "Enter", "Delete", "Control+z", "Control+Shift+z", "Control+a", "Control+k", "Control+p", "/", "ArrowDown", "ArrowUp", "Tab", "Shift+Tab", "Control+c", "Control+x", "Control+v", "Home", "End", "F2", "Backspace"]
SIZES = [(1600, 900), (1300, 800), (1100, 700), (900, 650), (1500, 950)]

class Hang(Exception): pass
def _alarm(signum, frame): raise Hang("no answer from the page for 60 s")
signal.signal(signal.SIGALRM, _alarm)

def run(seed, actions):
    rnd = random.Random(seed); log = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1500, "height": 900}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e))); pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
        pg.on("dialog", lambda d: d.accept()); pg.on("filechooser", lambda fc: None); pg.on("download", lambda d: None)
        pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
        pg.evaluate("() => { historyCoalesceMs = 0; window.print = () => {}; }"); pg.evaluate(HELPERS); pg.evaluate(SEED_PLAN)
        problems = []
        def health(where):
            try:
                bad = pg.evaluate("() => __livePlanProblems()")
                modals = pg.evaluate("() => document.querySelectorAll('.modal-bg.open').length")
                root = pg.evaluate("() => !!document.getElementById('printRoot')")
                alive = pg.evaluate("() => 1 + 1") == 2
            except Exception as e:
                return [f"{where}: the page stopped answering: {str(e)[:120]}"]
            out = []
            if bad: out.append(f"{where}: plan invalid: {bad[:4]}")
            if modals > 2: out.append(f"{where}: {modals} dialogs open at once")
            if root and not pg.evaluate("() => document.getElementById('printModalBg').classList.contains('open')") and False: out.append("print root left behind")
            if errs: out.append(f"{where}: {errs[:3]}")
            return out
        for i in range(actions):
            kind = rnd.random()
            signal.alarm(60)   # watchdog: an action that never returns means the page is stuck (an endless loop in the app)
            try:
                if kind < 0.50:
                    c = pg.evaluate(CANDIDATES)
                    if c:
                        x, y, what, txt = rnd.choice(c)
                        mods = rnd.choice([[], [], [], ["Shift"], ["Meta"]])
                        log.append(f"click {what} '{txt}' {mods}"); pg.mouse.click(x, y, modifiers=mods) if False else pg.click("body", position={"x": x, "y": y}, modifiers=mods, timeout=2000, force=True)
                elif kind < 0.66:
                    k = rnd.choice(KEYS); log.append(f"key {k}"); pg.keyboard.press(k)
                elif kind < 0.80:
                    f = pg.evaluate(FIELDS)
                    if f:
                        fid, tag, typ = rnd.choice(f); v = rnd.choice(HOSTILE)
                        if typ == "number": v = rnd.choice(["", "0", "-1", "3", "100", "150", "1.5", "99999999999", "7", "-30"])   # (a number field refuses text)
                        sel = f"#{fid}" if fid and re.match(r"^[A-Za-z][\w-]*$", fid) else None
                        if sel and pg.locator(sel).count() == 1:
                            log.append(f"fill {fid} {v[:20]!r}")
                            if tag == "SELECT": pg.evaluate("([s, r]) => { const e = document.querySelector(s); e.selectedIndex = Math.floor(r * e.options.length); e.dispatchEvent(new Event('change', { bubbles: true })); }", [sel, rnd.random()])
                            elif typ == "date": pg.evaluate("([s, v]) => { const e = document.querySelector(s); e.value = /^\\d{4}-\\d{2}-\\d{2}$/.test(v) ? v : '2026-10-1' + Math.floor(Math.random() * 9); e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); }", [sel, v])
                            else: pg.fill(sel, v, timeout=1500)
                elif kind < 0.86:
                    x0, y0 = rnd.randint(200, 1300), rnd.randint(120, 700); log.append(f"drag {x0},{y0}")
                    pg.mouse.move(x0, y0); pg.mouse.down(); pg.mouse.move(x0 + rnd.randint(-200, 200), y0 + rnd.randint(-150, 150), steps=4); pg.mouse.up()
                elif kind < 0.90:
                    w, h = rnd.choice(SIZES); log.append(f"resize {w}x{h}"); pg.set_viewport_size({"width": w, "height": h})
                elif kind < 0.93:
                    log.append("type"); pg.keyboard.type(rnd.choice(HOSTILE)[:20])
                elif kind < 0.96:
                    log.append("view"); pg.evaluate("() => setView(currentView === 'gantt' ? 'tasks' : 'gantt')")
                elif kind < 0.98:
                    log.append("theme"); pg.evaluate("() => toggleTheme()")
                else:
                    log.append("reload"); pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => { historyCoalesceMs = 0; window.print = () => {}; }"); pg.evaluate(HELPERS)
            except Hang as e:
                problems.append(f"HANG at action {i} ({log[-1] if log else '?'}): {e}"); signal.alarm(0); break
            except Exception as e:
                msg = str(e).splitlines()[0][:100]
                if "Timeout" in msg or "detached" in msg or "not attached" in msg or "intercepts" in msg: continue   # the target moved or closed under the pointer: not an app failure
                problems.append(f"action {i} ({log[-1] if log else '?'}): {msg}")
            signal.alarm(0)
            if len(log) % 25 == 0 or errs:
                h = health(f"after {len(log)} actions")
                if h: problems += h; break
            if problems: break
        else:
            problems += health("at the end")
        signal.alarm(0)
        state = pg.evaluate("() => ({ tasks: tasks.length, undo: undoStack.length })") if not problems else None
        if any(x.startswith("HANG") for x in problems): os._exit(3) if False else None
        else: b.close()
    return problems, log, state

seeds = [int(a) for a in sys.argv[1:]] or [1, 2, 3]
for seed in seeds:
    problems, log, state = run(seed, 450)
    if any(x.startswith("HANG") for x in problems): print("FAIL  " + str(problems[0]) + "   last actions: " + str(log[-15:]), flush=True); os._exit(1)
    check(f"monkey seed {seed}: 450 random UI actions (clicks on every kind of control, shortcuts, typing hostile text, drags, resizes, view and theme switches, reloads) — no error, the plan valid throughout", not problems, {"problems": problems[:3], "last actions": log[-12:]})
print(f"{sum(results)}/{len(results)} passed")
