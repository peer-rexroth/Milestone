# -*- coding: utf-8 -*-
"""Plans are linked by FOLDER: the dialog after choosing a folder (existing plan files with their plan name / size / date, a new file named after the plan,
files that are taken or not plans), opening a plan from a folder, a folder Chrome refuses, a missing file (pick another in the same folder, no new picker),
and what survives a reload."""
import json, os
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))
FS_INIT = """
window.__mode = null; window.__picks = 0;
window.showDirectoryPicker = async (o) => { window.__picks++; if (window.__mode === 'abort') throw new DOMException('cancelled', 'AbortError'); if (window.__mode === 'blocked') throw new DOMException('system folder', 'SecurityError'); return navigator.storage.getDirectory(); };
"""
def PLAN(name, tasks, updated=5): return {"version": 1, "project": {"name": name, "updatedAt": updated}, "tasks": [{"id": f"{name[:2]}{i}", "name": t, "parentId": None, "order": i, "startDate": "2026-09-07", "endDate": "2026-09-11", "progress": 0, "milestone": False, "color": None, "predecessors": [], "collapsed": False, "updatedAt": 5, "constraintType": "ASAP", "constraintDate": None, "taskMode": "auto", "resource": "", "actualStart": None, "actualFinish": None} for i, t in enumerate(tasks)], "deletedTaskIds": []}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script(FS_INIT)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") and "Milestone: folder picker failed" not in m.text else None)
    ev = pg.evaluate
    put = lambda name, text: ev("async ([n, t]) => { const r = await navigator.storage.getDirectory(); const h = await r.getFileHandle(n, { create: true }); const w = await h.createWritable(); await w.write(t); await w.close(); if (window.__mtime) {} }", [name, text if isinstance(text, str) else json.dumps(text)])
    ls = lambda: ev("async () => { const r = await navigator.storage.getDirectory(), o = []; for await (const e of r.values()) o.push(e.name); return o.sort(); }")
    toast = lambda: pg.inner_text("#toastMsg")
    settle = lambda: (pg.wait_for_function("() => !fileSyncWriteInFlight && !fileSyncWritePending && !planSwitching", timeout=8000), pg.wait_for_timeout(150))
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_function("() => fileSyncStatus !== 'checking'"); pg.wait_for_selector("#fileSyncModalBg.open")
    folder_open = lambda: ev("() => document.getElementById('folderFilesModalBg').classList.contains('open')")

    # ---------------------------------------------------------------- the link dialog itself
    check("a fresh plan opens the link dialog: 'Choose a folder to continue' with one main button, 'Choose folder…'", pg.inner_text("#fileSyncModalTitle") == "Choose a folder to continue" and "Choose folder" in pg.inner_text("#linkFolderBtn") and pg.locator("#fileSyncModalBg button:has-text('Create new file')").count() == 0 and not pg.locator("#linkSameFolderBtn").is_visible())
    check("...it explains the folder and Chrome's limit (Desktop, Documents, Downloads themselves)", "Documents" in pg.inner_text("#fileSyncModalBg .file-sync-help-body") or "Documents" in pg.evaluate("() => document.querySelector('#fileSyncModalBg .file-sync-help-body').textContent"))
    ev("() => window.__mode = 'blocked'"); pg.click("#linkFolderBtn"); pg.wait_for_timeout(300)
    check("a folder the browser refuses gives a message that says what to do, and the dialog stays", "inside Desktop, Documents or Downloads" in toast() and not folder_open() and pg.locator("#fileSyncModalBg.open").count() == 1, toast())
    ev("() => window.__mode = 'abort'"); pg.click("#linkFolderBtn"); pg.wait_for_timeout(300)
    check("cancelling the picker says nothing and leaves the dialog", not folder_open() and pg.locator("#fileSyncModalBg.open").count() == 1)
    ev("() => window.__mode = null")

    # ---------------------------------------------------------------- what the folder dialog lists
    put("Cost plan.json", PLAN("Cost plan", ["A", "B", "C"], 9)); put("Other.json", PLAN("Other", ["X"], 7)); put("notes.json", '{"hello": 1}'); put("broken.json", "{ nope"); put("merged_Old.json", PLAN("Old", ["Z"])); put("readme.txt", "hi")
    ev("() => { project.name = 'Cost plan'; }")
    pg.click("#linkFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open")
    rows = [r.split("\n")[0] for r in pg.locator("#folderFilesList .folder-row").all_inner_texts()]
    check("the dialog lists the plan files of the folder (and 'Create a new file'), skipping non-plan JSON, broken files, merged_ files and other types", rows == ["Cost plan.json", "Other.json", "Create a new file"] or sorted(rows[:-1]) == ["Cost plan.json", "Other.json"] and rows[-1] == "Create a new file", rows)
    row = pg.locator("#folderFilesList .folder-row:has-text('Cost plan.json')").inner_text()
    check("...each shows its plan name, task count and date", "Cost plan" in row and "3 tasks" in row and "1 task" in pg.locator("#folderFilesList .folder-row:has-text('Other.json')").inner_text(), row)
    check("...the file whose plan has this plan's name is preselected, the button says 'Link'", pg.locator("#folderFilesList .folder-row.chosen").inner_text().startswith("Cost plan.json") and pg.inner_text("#folderFilesOkBtn") == "Link")
    check("...a bar names the folder and offers 'Change folder…'", pg.inner_text("#folderBarName") != "" and pg.locator("#folderFilesModalBg button:has-text('Change folder')").count() == 1 and "Same plan name" in pg.locator("#folderFilesList .folder-row.chosen").inner_text())
    pg.click("#folderFilesList .folder-row:has-text('Other.json')")
    check("clicking another file chooses it", pg.locator("#folderFilesList .folder-row.chosen").inner_text().startswith("Other.json"))
    pg.click("#folderNewName")
    check("clicking the new-file name chooses 'Create a new file' and the button says 'Create and link'", pg.inner_text("#folderFilesOkBtn") == "Create and link" and "chosen" in (pg.get_attribute("#folderFilesList .folder-row[data-i='new']", "class") or ""))
    check("the suggested new name is the plan's name, and it is numbered when that file exists ('Cost plan 2.json')", pg.input_value("#folderNewName") == "Cost plan 2.json", pg.input_value("#folderNewName"))
    pg.fill("#folderNewName", "Other"); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    check("typing a name that already exists is refused with a message (Enter confirms, the dialog stays)", "already exists" in toast() and folder_open() and ls().count("Other.json") == 1, toast())
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("Escape closes the folder dialog but never the mandatory link dialog behind it", not folder_open() and pg.locator("#fileSyncModalBg.open").count() == 1)

    # ---------------------------------------------------------------- linking an existing file (merged), then creating
    pg.click("#linkFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open"); pg.click("#folderFilesList .folder-row:has-text('Cost plan.json')"); pg.click("#folderFilesOkBtn"); pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle()
    check("linking an existing plan file merges its tasks into the plan and links plan, file and folder", ev("() => tasks.map(t => t.name).sort()") == ["A", "B", "C"] and ev("() => fileSyncStatus") == "linked" and ev("() => watchingFolder()") is True and "Cost plan.json" in pg.inner_text("#fileSyncBtn"), ev("() => tasks.map(t => t.name)"))
    check("...the toast says where it linked, and the folder is watched (tooltip)", "Linked to Cost plan.json" in toast() and "watched" in (pg.get_attribute("#fileSyncBtn", "title") or ""), toast())
    picks = ev("() => window.__picks")
    check("...the rest of the folder is not touched (Other.json is as it was)", json.loads(ev("async () => { const r = await navigator.storage.getDirectory(); return (await (await r.getFileHandle('Other.json')).getFile()).text(); }"))["tasks"][0]["name"] == "X")

    # ---------------------------------------------------------------- open a plan from a folder
    pg.click("#planMenuBtn"); pg.click("#planOpenFileItem"); pg.wait_for_selector("#folderFilesModalBg.open")
    check("Open plan from folder: the dialog has no 'create' row, says 'Open a plan', and Cost plan.json (this plan's own file) is greyed out", pg.locator("#folderFilesList .folder-row[data-i='new']").count() == 0 and "Open a plan" in pg.inner_text("#folderFilesTitle") and pg.locator("#folderFilesList .folder-row.taken:has-text('Cost plan.json')").count() == 1)
    check("...the button says 'Open plan'", pg.inner_text("#folderFilesOkBtn") == "Open plan")
    pg.click("#folderFilesList .folder-row:has-text('Other.json')"); pg.click("#folderFilesOkBtn"); pg.wait_for_timeout(500); settle()
    check("opening 'Other.json' makes a new plan named after its project, linked to it and its folder", ev("() => project.name") == "Other" and ev("() => tasks.map(t => t.name)") == ["X"] and ev("() => watchingFolder()") is True and "Other.json" in pg.inner_text("#fileSyncBtn") and ev("() => JSON.parse(localStorage.getItem('milestone-plans')).plans.length") == 2)

    # ---------------------------------------------------------------- reload
    pg.reload(); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_function("() => fileSyncStatus !== 'checking'"); pg.wait_for_timeout(300)
    check("after a reload the plan is still linked to file and folder (no dialog)", ev("() => fileSyncStatus") == "linked" and ev("() => watchingFolder()") is True and pg.locator("#fileSyncModalBg.open").count() == 0 and ev("() => syncDirPerm") == "granted", (ev("() => fileSyncStatus"), ev("() => syncDirPerm")))
    put("Other-LAPTOP.json", PLAN("Other", ["From the other laptop"], 99))
    ev("() => pollFileSync()"); pg.wait_for_timeout(600); settle()
    check("...and the folder is scanned by the ordinary poll: a conflicted copy made meanwhile is merged and renamed", "From the other laptop" in ev("() => tasks.map(t => t.name)") and "merged_Other-LAPTOP.json" in ls())

    # ---------------------------------------------------------------- the file goes missing: pick another in the same folder, no new picker
    ev("async () => { const r = await navigator.storage.getDirectory(); await r.removeEntry('Other.json'); }")
    ev("() => pollFileSync()"); pg.wait_for_selector("#fileSyncModalBg.open", timeout=5000)
    check("a deleted plan file: 'Linked file not found', and 'Pick a file in the same folder' is offered", pg.inner_text("#fileSyncModalTitle") == "Linked file not found" and pg.locator("#linkSameFolderBtn").is_visible())
    before = ev("() => window.__picks")
    pg.click("#linkSameFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open")
    check("...it lists the same folder WITHOUT asking the browser for a folder again", ev("() => window.__picks") == before and pg.locator("#folderFilesList .folder-row:has-text('Cost plan.json')").count() == 1)
    pg.click("#folderNewName"); pg.fill("#folderNewName", "Other again.json"); pg.click("#folderFilesOkBtn"); pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle()
    check("...and a new file created there takes the plan's tasks", ev("() => fileSyncStatus") == "linked" and "Other again.json" in ls() and "Other again.json" in pg.inner_text("#fileSyncBtn"), ls())

    # ---------------------------------------------------------------- disconnect forgets both
    ev("() => unlinkFile()"); pg.wait_for_timeout(500)
    check("disconnecting forgets the file and the folder (the link dialog is back)", ev("() => watchingFolder()") is False and ev("async () => !(await _fsGet(planDirKey(currentPlanId))) && !(await _fsGet(planHandleKey(currentPlanId)))") and pg.locator("#fileSyncModalBg.open").count() == 1)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
