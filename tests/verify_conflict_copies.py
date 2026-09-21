# -*- coding: utf-8 -*-
"""Conflicted copies of the plan file (OneDrive & co.): the folder can be watched; a copy is merged into the plan (the newer task wins) and renamed
merged_<name>, never deleted; other plans' files, invalid files and the app's own exports are left alone; everything is reported."""
import json, os, time
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

# the "folder" is the private file system (OPFS) of the browser context; the pickers hand out its handles
FS_INIT = """
window.__dirPicks = []; window.__startIn = null;
const _root = () => navigator.storage.getDirectory();
window.showSaveFilePicker = async () => (await _root()).getFileHandle('cbm.json', { create: true });
window.showOpenFilePicker = async () => [await (await _root()).getFileHandle('cbm.json')];
window.showDirectoryPicker = async (o) => { window.__dirPicks.push(o || {}); window.__startIn = o && o.startIn && o.startIn.name; return _root(); };
"""
PLAN = lambda tasks, name="Cost plan": {"version": 1, "project": {"name": name, "updatedAt": 5}, "tasks": tasks, "deletedTaskIds": []}
def T(id_, name, updated, **kw):
    t = {"id": id_, "name": name, "parentId": None, "order": 0, "startDate": "2026-09-07", "endDate": "2026-09-11", "progress": 0, "milestone": False, "color": None, "predecessors": [], "collapsed": False, "updatedAt": updated,
         "constraintType": "ASAP", "constraintDate": None, "taskMode": "manual", "resource": "", "actualStart": None, "actualFinish": None}
    t.update(kw); return t

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 800}); ctx.add_init_script(FS_INIT)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    ev = pg.evaluate
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_function("() => fileSyncStatus !== 'checking'"); pg.wait_for_timeout(200)
    ls = lambda: ev("async () => { const r = await navigator.storage.getDirectory(), out = []; for await (const e of r.values()) out.push(e.name); return out.sort(); }")
    put = lambda name, text: ev("async ([n, t]) => { const r = await navigator.storage.getDirectory(); const h = await r.getFileHandle(n, { create: true }); const w = await h.createWritable(); await w.write(t); await w.close(); }", [name, text if isinstance(text, str) else json.dumps(text)])
    read = lambda name: ev("async (n) => { const r = await navigator.storage.getDirectory(); return (await (await r.getFileHandle(n)).getFile()).text(); }", name)
    toast = lambda: pg.inner_text("#toastMsg")
    settle = lambda: (pg.wait_for_function("() => !fileSyncWriteInFlight && !fileSyncWritePending", timeout=8000), pg.wait_for_timeout(150))
    names = lambda: ev("() => tasks.map(t => t.name).sort()")

    # ---------------------------------------------------------------- link a file, then the offer
    pg.click("#fileSyncModalBg button:has-text('Create new file')"); pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle()
    ev("""(p) => { project.name = 'Cost plan'; tasks.length = 0; tasks.push(p[0], p[1]); normalizeData(); save(); render(); }""", [T("ta", "Alpha", 10), T("tb", "Beta", 10)]); settle()
    pg.wait_for_timeout(1500)
    check("after a file is linked, an offer to watch its folder appears (a toast with a 'Watch folder' button)", "watch this folder" in toast() and pg.inner_text("#toastUndoBtn") == "Watch folder" and pg.locator("#toastUndoBtn").is_visible(), toast())
    check("...nothing is watched yet, and the plan menu says so", ev("() => watchingFolder()") is False)
    pg.click("#toastUndoBtn"); pg.wait_for_timeout(500)
    check("clicking it opens the folder picker at the linked file (startIn) and the folder is watched", ev("() => window.__dirPicks.length") == 1 and ev("() => window.__startIn") == "cbm.json" and ev("() => watchingFolder()") is True, ev("() => window.__startIn"))
    check("...the handle is kept for this plan (IndexedDB) and the offer is not made again", ev("async () => { const h = await _fsGet(planDirKey(currentPlanId)); return !!h && h.kind === 'directory'; }") and ev("() => !!localStorage.getItem('milestone-watchasked-' + currentPlanId)"))
    pg.click("#planMenuBtn"); pg.wait_for_timeout(100)
    check("the plan menu has 'Stop watching for conflicted copies' (on)", "Stop watching" in pg.inner_text("#planWatchItem") and "on" in pg.inner_text("#planWatchItem").split("\n")[-1]); pg.keyboard.press("Escape")

    # ---------------------------------------------------------------- what counts as a copy
    check("copy names: OneDrive style, numbered and 'conflicted copy' names are copies", ev("() => ['cbm-DESKTOP-4F2.json', 'cbm (1).json', 'cbm (John\\'s conflicted copy 2026-09-21).json', 'cbm copy.json', 'WORKSTATION01_cbm.json', 'DESKTOP-4F2_cbm.json', 'PC-cbm.json', 'CBM-laptop.JSON'].every(n => isStrayCopyName(n, 'cbm.json', new Set()))"))
    check("...the file itself, files already renamed, another plan's file, the app's own dated exports and other extensions are not", ev("() => ['cbm.json', 'merged_cbm-DESKTOP.json', 'merged_2_cbm-X.json', 'merged_cbm.json', 'cbm-other.json', 'cbm-2026-09-21.json', 'cbm-2026-09-21 (1).json', 'cbm-DESKTOP.txt', 'other.json', 'WORKSTATION01_cbm.txt', 'WORKSTATION01_other.json'].map(n => isStrayCopyName(n, 'cbm.json', new Set(['cbm-other.json'])))") == [False] * 11)

    # ---------------------------------------------------------------- absorbing copies
    base_a = T("ta", "Alpha", 10)
    put("cbm-DESKTOP-4F2.json", PLAN([T("ta", "Alpha edited elsewhere", 900, progress=40), T("tb", "Beta", 10), T("tn", "New from the other PC", 800)]))
    put("cbm-2.json", PLAN([T("zz", "A different plan's task", 999)], name="Another plan"))          # a different plan whose file name starts the same way
    put("cbm-broken.json", "{ this is not json")
    put("cbm-notaplan.json", json.dumps({"hello": "world"}))
    put("cbm-2026-09-21.json", PLAN([T("tx", "From an export", 999)]))                                  # the app's own dated export
    ev("() => window.scrollTo(0, 0)")
    before = ls()
    n = ev("() => scanConflictCopies()"); settle()
    check("a scan absorbs exactly the one real copy", n == 1, n)
    check("...its tasks are in the plan: the newer 'Alpha edited elsewhere' won, the new task arrived", "Alpha edited elsewhere" in names() and "New from the other PC" in names() and "Alpha" not in names(), names())
    check("...and the other plan's task, the broken file's, the export's are NOT", "A different plan's task" not in names() and "From an export" not in names())
    after = ls()
    check("the copy was renamed merged_<name>, not deleted; every other file is untouched", "merged_cbm-DESKTOP-4F2.json" in after and "cbm-DESKTOP-4F2.json" not in after and all(f in after for f in ["cbm-2.json", "cbm-broken.json", "cbm-notaplan.json", "cbm-2026-09-21.json", "cbm.json"]), after)
    check("...the renamed file still holds the copy's text", "Alpha edited elsewhere" in read("merged_cbm-DESKTOP-4F2.json"))
    check("the combined result went to the real file (the other devices read it)", "New from the other PC" in read("cbm.json") and "Alpha edited elsewhere" in read("cbm.json"))
    log = ev("() => syncConflictLog.map(c => [c.kind, c.name, c.renamedTo, c.changed, c.tasks])")
    check("the merge is logged for review (a 'file' entry naming the copy and its new name)", len(log) == 1 and log[0][:4] == ["file", "cbm-DESKTOP-4F2.json", "merged_cbm-DESKTOP-4F2.json", True] and log[0][4] >= 2, log)
    check("...a toast says how many copies and tasks, with a Review button; the badge in the top bar shows '1 merged copy'", "Merged 1 conflicted copy" in toast() and "tasks changed" in toast() and pg.inner_text("#toastUndoBtn") == "Review" and "1 merged copy" in pg.inner_text("#syncConflictBtn"), (toast(), pg.inner_text("#syncConflictBtn")))
    pg.click("#syncConflictBtn"); pg.wait_for_selector("#syncConflictsModalBg.open")
    check("the review dialog describes it (the file, that it was merged and renamed and kept) with only a Dismiss button", "cbm-DESKTOP-4F2.json" in pg.inner_text("#syncConflictsBody") and "merged_cbm-DESKTOP-4F2.json" in pg.inner_text("#syncConflictsBody") and pg.locator("#syncConflictsBody .conflict-actions .btn").count() == 1 and pg.locator("#syncConflictsBody button:has-text('Use mine')").count() == 0)
    pg.click("#syncConflictsBody .conflict-actions .btn"); pg.wait_for_timeout(200)
    check("Dismiss clears the entry and the badge", ev("() => syncConflictLog.length") == 0 and pg.locator("#syncConflictBtn.hidden").count() == 1)
    n2 = ev("() => scanConflictCopies()")
    check("a second scan finds nothing to do (renamed files are skipped)", n2 == 0 and ls() == after, (n2, ls()))

    # ---------------------------------------------------------------- older copies do not overwrite; a second copy with the same name; deletions
    ev("() => { const t = tasks.find(x => x.name === 'Beta'); t.progress = 70; t.updatedAt = Date.now(); save(); }"); settle()
    put("cbm-DESKTOP-4F2.json", PLAN([T("tb", "Beta stale", 20, progress=5), T("ta", "Alpha edited elsewhere", 900)]))
    ev("() => scanConflictCopies()"); settle()
    check("an OLDER copy of a task does not overwrite the newer one here (Beta stays)", "Beta" in names() and "Beta stale" not in names() and ev("() => tasks.find(t => t.name === 'Beta').progress") == 70, names())
    check("the same file name again gets the disambiguating prefix (merged_2_…), the first one stays", "merged_2_cbm-DESKTOP-4F2.json" in ls() and "merged_cbm-DESKTOP-4F2.json" in ls())
    put("cbm (1).json", {**PLAN([T("ta", "Alpha edited elsewhere", 900)]), "deletedTaskIds": [{"id": "tn", "deletedAt": int(time.time() * 1000) + 5000000}]})
    ev("() => scanConflictCopies()"); settle()
    check("a deletion in a copy is respected (tasks deleted there after their last edit go here too)", "New from the other PC" not in names(), names())
    check("...and that copy was renamed too", "merged_cbm (1).json" in ls(), ls())

    # ---------------------------------------------------------------- guards and switching it off
    check("the plan's file itself was never treated as a copy", "cbm.json" in ls() and json.loads(read("cbm.json"))["tasks"] is not None)
    ev("() => stopWatchingFolder()"); pg.wait_for_timeout(300)
    check("stopping the watch forgets the folder (handle removed, menu says 'Watch folder…')", ev("() => watchingFolder()") is False and ev("async () => !(await _fsGet(planDirKey(currentPlanId)))"))
    put("WORKSTATION01_cbm.json", PLAN([T("tq", "Should not be read", 999)]))
    check("without a watched folder a copy is left alone", ev("() => scanConflictCopies()") == 0 and "WORKSTATION01_cbm.json" in ls() and "Should not be read" not in names())
    pg.click("#planMenuBtn"); check("the plan menu offers 'Watch folder for conflicted copies…' again", "Watch folder for conflicted copies" in pg.inner_text("#planWatchItem")); pg.keyboard.press("Escape")
    ev("() => chooseWatchFolder()"); pg.wait_for_timeout(500)
    check("choosing the folder again absorbs what accumulated meanwhile — a 'WORKSTATION01_cbm.json' (workstation name, underscore, file name) is a copy too", "Should not be read" in names() and "merged_WORKSTATION01_cbm.json" in ls(), (names(), ls()))
    # a folder that is not the file's folder is refused
    ev("""() => { window.__realPicker = window.showDirectoryPicker; window.showDirectoryPicker = async () => { const r = await navigator.storage.getDirectory(); return r.getDirectoryHandle('elsewhere', { create: true }); }; }""")
    ev("() => stopWatchingFolder()"); pg.wait_for_timeout(200); ev("() => chooseWatchFolder()"); pg.wait_for_timeout(400)
    check("a folder that does not contain the linked file is refused with a message", ev("() => watchingFolder()") is False and "directly contains" in toast(), toast())
    ev("() => { window.showDirectoryPicker = window.__realPicker; }")
    ev("() => chooseWatchFolder()"); pg.wait_for_timeout(400)
    # unlinking forgets the folder too
    ev("() => unlinkFile()"); pg.wait_for_timeout(500)
    check("disconnecting the file also forgets the watched folder", ev("() => watchingFolder()") is False and ev("async () => !(await _fsGet(planDirKey(currentPlanId)))"))
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
