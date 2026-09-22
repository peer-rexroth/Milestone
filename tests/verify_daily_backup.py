# -*- coding: utf-8 -*-
"""Daily backups: opening (or saving) a folder-linked plan drops one dated snapshot a day into a "Backups" subfolder of
its linked folder — same idea as Pulse's daily backups, simplified since Milestone's folder link is already mandatory.
One file per calendar day, kept forever, invisible to the plan-file list and the conflicted-copy scanner, best-effort
and silent on failure."""
import json, os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
FS_INIT = "window.showDirectoryPicker = async () => navigator.storage.getDirectory();"
def PLAN(name, tasks, updated=5): return {"version": 1, "project": {"name": name, "updatedAt": updated}, "tasks": [{"id": f"{name[:2]}{i}", "name": t, "parentId": None, "order": i, "startDate": "2026-09-07", "endDate": "2026-09-11", "progress": 0, "milestone": False, "color": None, "predecessors": [], "collapsed": False, "updatedAt": 5, "constraintType": "ASAP", "constraintDate": None, "taskMode": "auto", "resource": "", "actualStart": None, "actualFinish": None} for i, t in enumerate(tasks)], "deletedTaskIds": []}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script(FS_INIT)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    ev = pg.evaluate
    ls = lambda path="": ev("async (path) => { let d = await navigator.storage.getDirectory(); for (const seg of path.split('/').filter(Boolean)) d = await d.getDirectoryHandle(seg); const o = []; for await (const e of d.values()) o.push(e.name); return o.sort(); }", path)
    readf = lambda path: ev("async (path) => { const parts = path.split('/'); let d = await navigator.storage.getDirectory(); for (const seg of parts.slice(0, -1)) d = await d.getDirectoryHandle(seg); const h = await d.getFileHandle(parts[parts.length - 1]); return (await h.getFile()).text(); }", path)
    settle = lambda: (pg.wait_for_function("() => !fileSyncWriteInFlight && !fileSyncWritePending && !planSwitching", timeout=8000), pg.wait_for_timeout(150))
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_function("() => fileSyncStatus !== 'checking'"); pg.wait_for_selector("#fileSyncModalBg.open")

    # ---------------------------------------------------------------- linking writes today's backup right away, on the initial "opening" path
    pg.click("#linkFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open"); pg.fill("#folderNewName", "cbm.json"); pg.click("#folderFilesOkBtn"); settle()
    today = ev("() => todayStr()")
    check("linking a plan's folder creates a 'Backups' subfolder", ls() == ["Backups", "cbm.json"], ls())
    check("...with one file for today, named after the plan file plus the date", ls("Backups") == [f"cbm {today}.json"], ls("Backups"))
    saved = json.loads(readf(f"Backups/cbm {today}.json"))
    check("...and it holds the plan's own data", saved.get("project", {}).get("name") == "My Project" and isinstance(saved.get("tasks"), list))

    # ---------------------------------------------------------------- edits the same day do not add a second file
    ev("() => { tasks.push({id: 't-new', name: 'New task', parentId: null, order: tasks.length, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); save(); }")
    settle()
    check("editing the plan later the same day does not add a second backup file", ls("Backups") == [f"cbm {today}.json"], ls("Backups"))
    saved2 = json.loads(readf(f"Backups/cbm {today}.json"))
    check("...the day's file also isn't rewritten once it exists (still the empty plan from before the edit — first writer wins, per the session gate)", len(saved2["tasks"]) == 0, saved2)

    # ---------------------------------------------------------------- a new day gets its own file, and nothing old is ever deleted
    ev("() => { window.__realTodayStr = todayStr; todayStr = () => '2099-01-01'; }")
    ev("() => { tasks.push({id: 't-new2', name: \"Tomorrow's task\", parentId: null, order: tasks.length, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); save(); }")
    settle()
    check("a later calendar day (simulated) gets its own dated file, and the first day's file is kept", sorted(ls("Backups")) == sorted([f"cbm {today}.json", "cbm 2099-01-01.json"]), ls("Backups"))
    saved3 = json.loads(readf("Backups/cbm 2099-01-01.json"))
    check("...the new day's file has the plan as it stood then (2 tasks)", len(saved3["tasks"]) == 2, saved3)
    ev("() => { todayStr = window.__realTodayStr; }")

    check("no console errors or page errors across the whole run", not errors, errors[:5])

    n_ok, n_all = sum(results), len(results)
    print(f"\n{n_ok}/{n_all} checks passed")
    b.close()
    raise SystemExit(0 if n_ok == n_all else 1)
