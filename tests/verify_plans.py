import json
from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))

# Pickers backed by the origin-private file system: real FileSystemFileHandles (createWritable, isSameEntry, storable in IndexedDB).
FS_INIT = """
window.__pick = null;
window.showDirectoryPicker = async () => { if (window.__pick === '__abort__') throw new DOMException('cancelled', 'AbortError'); return navigator.storage.getDirectory(); };   // the "folder" is the private file system's root
"""
NO_FS_INIT = "delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker;"
TASK = """(n) => { tasks.push({id: genId(), name: n, parentId: null, order: tasks.length, startDate: '2026-09-21', endDate: '2026-09-23', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}); save(); render(); }"""
LEG = [{"id": f"t{i}", "name": f"Legacy {i}", "parentId": None, "order": i - 1, "startDate": "2026-09-21", "endDate": "2026-09-23", "progress": 0, "milestone": False, "color": None, "notes": "", "predecessors": [], "collapsed": False, "updatedAt": 5, "constraintType": "ASAP", "constraintDate": None, "taskMode": "auto"} for i in (1, 2, 3)]
LEGACY = {"version": 1, "project": {"name": "Legacy Proj", "updatedAt": 5}, "tasks": LEG, "deletedTaskIds": [], "theme": "dark", "zoom": "month", "view": "gantt", "gridPaneWidth": 420}

def make(b, init):
    ctx = b.new_context(viewport={"width": 1300, "height": 800}); ctx.add_init_script(init)
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    class H: pass
    h = H(); h.pg = pg
    def boot(): pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_function("() => fileSyncStatus !== 'checking'"); pg.wait_for_timeout(150)
    def settle(): pg.wait_for_function("() => !fileSyncWriteInFlight && !fileSyncWritePending && !planSwitching", timeout=8000); pg.wait_for_timeout(120)
    h.boot, h.settle = boot, settle
    h.names = lambda: pg.evaluate("() => tasks.map(t => t.name)")
    h.pname = lambda: pg.evaluate("() => project.name")
    h.index = lambda: pg.evaluate("() => JSON.parse(localStorage.getItem('milestone-plans'))")
    h.status = lambda: pg.evaluate("() => fileSyncStatus")
    h.add = lambda n: pg.evaluate(TASK, n)
    h.modal_open = lambda: pg.eval_on_selector("#fileSyncModalBg", "e => e.classList.contains('open')")
    def read_file(n): return pg.evaluate("async n => { const r = await navigator.storage.getDirectory(); const h = await r.getFileHandle(n); return (await h.getFile()).text(); }", n)
    def file_tasks(n):
        try: t = read_file(n)
        except Exception: return "MISSING"
        return [x["name"] for x in json.loads(t)["tasks"]] if t.strip() else None
    def write_file(n, text): pg.evaluate("async ([n, t]) => { const r = await navigator.storage.getDirectory(); const h = await r.getFileHandle(n, {create: true}); const w = await h.createWritable(); await w.write(t); await w.close(); }", [n, text])
    h.read_file, h.file_tasks, h.write_file = read_file, file_tasks, write_file
    def open_menu(): pg.click("#planMenuBtn"); pg.wait_for_selector("#planMenu.open")
    def switch_ui(name): open_menu(); pg.locator(".plan-item", has_text=name).first.click(); settle()
    h.open_menu, h.switch_ui = open_menu, switch_ui
    def modal_link_new(fname):          # the mandatory dialog -> Choose folder… -> a new file with this name
        pg.click("#linkFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open"); pg.fill("#folderNewName", fname); pg.click("#folderFilesOkBtn")
        pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle()
    def modal_link_existing(fname):     # ... -> a plan file that is already in the folder
        pg.click("#linkFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open"); pg.click(f"#folderFilesList .folder-row:has-text('{fname}')"); pg.click("#folderFilesOkBtn")
        pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle()
    def open_plan_from(fname):          # plan menu -> Open plan from folder… -> the file
        open_menu(); pg.click("#planOpenFileItem"); pg.wait_for_selector("#folderFilesModalBg.open"); return pg.locator(f"#folderFilesList .folder-row:has-text('{fname}')")
    h.modal_link_new, h.modal_link_existing, h.open_plan_from = modal_link_new, modal_link_existing, open_plan_from
    def new_plan(name, fname=None):
        open_menu(); pg.click("#planNewItem"); pg.wait_for_selector("#planModalBg.open"); pg.fill("#planNameInput", name)
        if fname: pg.evaluate("f => window.__pick = f", fname)
        pg.click("#planSubmitBtn"); pg.wait_for_timeout(300); settle()
    h.new_plan = new_plan
    return h

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)

    # ==================================================================================================================
    print("--- A. a browser that can't write files (Safari/Firefox): plans work, linking can't be required ---")
    A = make(b, NO_FS_INIT); pg = A.pg
    A.boot()
    check("no file API: no link dialog, no file button", not A.modal_open() and pg.eval_on_selector("#fileSyncBtn", "e => e.classList.contains('hidden')"))
    pg.evaluate("""async (legacy) => { localStorage.clear(); localStorage.setItem('milestone-v1', JSON.stringify(legacy));
        localStorage.setItem('milestone-backups', JSON.stringify({'2026-09-01': {project: legacy.project, tasks: legacy.tasks, deletedTaskIds: []}})); }""", LEGACY)
    A.boot()
    idx = A.index()
    check("migration: single project becomes plan1 with its tasks, prefs (saved zoom reset to the Year default), backups", len(idx["plans"]) == 1 and idx["current"] == "plan1" and A.names() == ["Legacy 1", "Legacy 2", "Legacy 3"] and pg.evaluate("() => [theme, zoom, currentView, gridPaneWidth]") == ["dark", "year", "gantt", 640] and pg.evaluate("() => !!localStorage.getItem('milestone-backups-plan1') && !!localStorage.getItem('milestone-v1')"), idx)
    pg.evaluate("() => { theme = 'light'; applyTheme(); save(); }")
    pg.evaluate("() => { localStorage.setItem('milestone-v1', '{\"project\":{\"name\":\"STALE\"},\"tasks\":[]}'); }"); A.boot()
    check("the stale pre-plans copy is never read again", A.pname() == "Legacy Proj")
    A.open_menu(); check("the only plan can't be deleted", pg.locator("#planDeleteItem").is_disabled()); check("no 'Disconnect file' item when files aren't supported", pg.locator("#planDisconnectItem").count() == 0); pg.keyboard.press("Escape")
    A.new_plan("Second Plan")
    check("New plan (no file API): created straight away, empty, opened", A.pname() == "Second Plan" and A.names() == [] and not A.modal_open(), (A.pname(), A.names()))
    A.add("S1"); A.add("S2")
    A.switch_ui("Legacy Proj"); ok1 = A.names() == ["Legacy 1", "Legacy 2", "Legacy 3"]
    A.switch_ui("Second Plan")
    check("switching keeps each plan's tasks separate", ok1 and A.names() == ["S1", "S2"])
    A.boot(); check("reload reopens the last-used plan", A.pname() == "Second Plan" and A.names() == ["S1", "S2"])
    check("theme is a device pref, shared by plans", pg.evaluate("() => theme") == "light")
    bk = pg.evaluate("() => Object.keys(localStorage).filter(k => k.startsWith('milestone-backups-'))")
    check("backups are per plan", len(bk) == 2 and all(n.startswith("S") for n in pg.evaluate("() => Object.values(JSON.parse(localStorage.getItem('milestone-backups-' + currentPlanId)))[0].tasks.map(t => t.name)")), bk)
    A.open_menu(); pg.click("#planRenameItem"); pg.wait_for_selector("#planModalBg.open"); pg.fill("#planNameInput", "Renamed Plan"); pg.keyboard.press("Enter"); pg.wait_for_selector("#planModalBg:not(.open)")
    check("Rename updates switcher, title, index", pg.inner_text("#planBtnName") == "Renamed Plan" and pg.title().startswith("Renamed Plan") and any(x["name"] == "Renamed Plan" for x in A.index()["plans"]))
    A.open_menu(); pg.click("#planDuplicateItem"); A.settle()
    check("Duplicate (no file API): copy opens with the same tasks", A.pname() == "Renamed Plan copy" and A.names() == ["S1", "S2"], (A.pname(), A.names()))
    A.add("COPY-ONLY"); A.switch_ui("Renamed Plan")
    check("...edits to the copy leave the original alone", A.names() == ["S1", "S2"])
    A.switch_ui("Renamed Plan copy"); A.open_menu(); pg.click("#planDeleteItem"); pg.wait_for_selector("#confirmModalBg.open"); pg.click("#confirmModalActionBtn"); A.settle()
    check("Delete removes the plan and its data/backups", len(A.index()["plans"]) == 2 and pg.evaluate("() => Object.keys(localStorage).filter(k => k.startsWith('milestone-plan-') || k.startsWith('milestone-backups-')).length") == 4)
    pg.click("#toastUndoBtn"); A.settle()
    check("Undo restores it, in its old position", A.pname() == "Renamed Plan copy" and A.names() == ["S1", "S2", "COPY-ONLY"] and [x["name"] for x in A.index()["plans"]] == ["Legacy Proj", "Renamed Plan", "Renamed Plan copy"])
    pg.evaluate("() => { selectedTaskId = tasks[0].id; render(); }"); A.switch_ui("Legacy Proj")
    check("switching clears the selection", pg.evaluate("() => selectedTaskId") is None)
    pg.evaluate("() => showToast('x', false, () => {}, 'Undo')"); A.switch_ui("Renamed Plan")
    check("switching hides a stale Undo toast", not pg.eval_on_selector("#toast", "e => e.classList.contains('show')") and pg.evaluate("() => toastUndoAction") is None)
    pg.context.close()

    # ==================================================================================================================
    print("--- B. Chrome/Edge: every plan must have a file ---")
    B = make(b, FS_INIT); pg = B.pg
    B.boot()
    pg.wait_for_selector("#fileSyncModalBg.open")
    check("fresh start: the link dialog opens straight away", B.modal_open() and pg.inner_text("#fileSyncModalTitle") == "Choose a folder to continue", pg.inner_text("#fileSyncModalTitle"))
    check("it has no close button and no 'Not now'", pg.locator("#fileSyncModalBg .modal-header button").count() == 0 and pg.locator("#fileSyncModalBg button:has-text('Not now')").count() == 0)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("Escape does not close it", B.modal_open())
    pg.mouse.click(5, 5); pg.wait_for_timeout(150)
    check("clicking the backdrop does not close it", B.modal_open())
    pg.evaluate("() => window.__pick = '__abort__'"); pg.click("#linkFolderBtn"); pg.wait_for_timeout(300)
    check("cancelling the folder picker leaves the dialog up", B.modal_open() and B.status() == "unlinked" and not pg.evaluate("() => document.getElementById('folderFilesModalBg').classList.contains('open')"))
    pg.evaluate("() => window.__pick = null"); pg.click("#linkFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open")
    check("choosing a folder lists what is in it: an empty folder offers to create a new file named after the plan", "no plan file yet" in pg.inner_text("#folderFilesHint") and pg.input_value("#folderNewName").endswith(".json") and pg.inner_text("#folderFilesOkBtn") == "Create and link", pg.inner_text("#folderFilesHint"))
    pg.click("#folderFilesModalBg .modal-footer .btn:has-text('Back')"); pg.wait_for_timeout(150)
    check("Back returns to the link dialog, still open and unlinked", B.modal_open() and B.status() == "unlinked" and not pg.evaluate("() => document.getElementById('folderFilesModalBg').classList.contains('open')"))
    B.modal_link_new("plan-a.json")
    check("creating a file in the chosen folder links the plan and closes the dialog", B.status() == "linked" and not B.modal_open() and "plan-a.json" in pg.inner_text("#fileSyncBtn"))
    check("the file was created with the plan in it", B.file_tasks("plan-a.json") == [], B.file_tasks("plan-a.json"))
    B.add("A1"); B.settle()
    check("edits are written to the file", B.file_tasks("plan-a.json") == ["A1"], B.file_tasks("plan-a.json"))
    pg.evaluate("() => { renameProject('Alpha'); }"); B.settle()

    # --- New plan needs a file
    n0 = len(B.index()["plans"])
    B.open_menu(); pg.click("#planNewItem"); pg.wait_for_selector("#planModalBg.open")
    check("New plan dialog has one button, 'Create…', and explains the file", pg.locator("#planSubmitBtn").inner_text() == "Create…" and pg.locator("#planFileBtn").count() == 0 and "file" in pg.inner_text("#planModalHint"))
    pg.fill("#planNameInput", "Plan B"); pg.evaluate("() => window.__pick = '__abort__'"); pg.click("#planSubmitBtn"); pg.wait_for_timeout(400)
    check("cancelling the save dialog creates no plan", len(B.index()["plans"]) == n0 and B.pname() == "Alpha", (len(B.index()["plans"]), B.pname()))
    pg.evaluate("() => window.__pick = null"); pg.click("#planSubmitBtn"); pg.wait_for_selector("#planModalBg:not(.open)"); B.settle()
    check("choosing a folder creates the plan and its file (named after the plan), opens it, linked", B.pname() == "Plan B" and B.status() == "linked" and B.file_tasks("Plan B.json") == [] and "Plan B.json" in pg.inner_text("#fileSyncBtn"), (B.pname(), B.status()))
    check("...and it never passes through an unlinked state (no dialog)", not B.modal_open())
    B.add("B1"); B.settle()
    check("plan B writes only to plan B's file", B.file_tasks("Plan B.json") == ["B1"] and B.file_tasks("plan-a.json") == ["A1"])
    # a file name that is taken is never reused for a new plan
    B.write_file("Taken.json", "{}")
    B.open_menu(); pg.click("#planNewItem"); pg.wait_for_selector("#planModalBg.open"); pg.fill("#planNameInput", "Taken"); pg.click("#planSubmitBtn"); pg.wait_for_selector("#planModalBg:not(.open)"); B.settle()
    check("a new plan never reuses an existing file: 'Taken' gets 'Taken 2.json', the old 'Taken.json' is untouched", B.status() == "linked" and "Taken 2.json" in pg.inner_text("#fileSyncBtn") and B.read_file("Taken.json") == "{}", pg.inner_text("#fileSyncBtn"))
    n0 += 1
    B.switch_ui("Alpha")

    # --- Duplicate needs a file
    B.switch_ui("Alpha")
    B.open_menu(); pg.evaluate("() => window.__pick = '__abort__'"); pg.click("#planDuplicateItem"); pg.wait_for_timeout(400)
    check("Duplicate: cancelling the save dialog creates nothing", len(B.index()["plans"]) == n0 + 1 and B.pname() == "Alpha")
    B.open_menu(); pg.evaluate("() => window.__pick = 'Alpha copy.json'"); pg.click("#planDuplicateItem"); B.settle()
    check("Duplicate: the copy is opened with the same tasks and its own file", B.pname() == "Alpha copy" and B.names() == ["A1"] and B.status() == "linked" and B.file_tasks("Alpha copy.json") == ["A1"], (B.pname(), B.names(), B.status()))
    B.add("COPY"); B.settle()
    check("...editing the copy leaves the original's file alone", B.file_tasks("Alpha copy.json") == ["A1", "COPY"] and B.file_tasks("plan-a.json") == ["A1"])

    # --- switching + per-plan files + the write race
    B.switch_ui("Alpha")
    check("switching re-points sync to that plan's file", B.status() == "linked" and "plan-a.json" in pg.inner_text("#fileSyncBtn"), pg.inner_text("#fileSyncBtn"))
    B.add("A2"); B.settle()
    check("after round trips each file holds only its own plan", B.file_tasks("plan-a.json") == ["A1", "A2"] and B.file_tasks("Plan B.json") == ["B1"] and B.file_tasks("Alpha copy.json") == ["A1", "COPY"])
    for i in range(3):
        pg.evaluate("""(i) => {
            const idx = JSON.parse(localStorage.getItem('milestone-plans')); const id = n => idx.plans.find(p => p.name === n).id;
            const to = currentPlanId === id('Alpha') ? id('Plan B') : id('Alpha');
            tasks.push({id: genId(), name: (currentPlanId === id('Alpha') ? 'RA' : 'RB') + i, parentId: null, order: tasks.length, startDate: '2026-09-21', endDate: '2026-09-23', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'});
            save(); switchPlan(to); }""", i)
        B.settle()
    fa, fb = B.file_tasks("plan-a.json"), B.file_tasks("Plan B.json")
    check("write race: A's file has A's late edits, none of B's", "RA0" in fa and "RA2" in fa and not any(n.startswith("RB") for n in fa), fa)
    check("write race: B's file has B's late edits, none of A's", "RB1" in fb and not any(n.startswith("RA") for n in fb), fb)
    B.switch_ui("Alpha")
    pg.evaluate("""() => { const h = syncFileHandle; const late = JSON.stringify({version: 1, project: project, tasks: [{id: 'zzlate', name: 'LATE-FROM-A-FILE', parentId: null, order: 99, startDate: '2026-09-21', endDate: '2026-09-22', progress: 0, milestone: false, color: null, notes: '', predecessors: [], collapsed: false, updatedAt: Date.now() + 100000, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto'}], deletedTaskIds: []});
        h.getFile = async () => { await new Promise(r => setTimeout(r, 400)); return new File([late], 'plan-a.json'); }; }""")
    pg.evaluate("() => { pollFileSync(); switchPlan(JSON.parse(localStorage.getItem('milestone-plans')).plans.find(p => p.name === 'Plan B').id); }")
    pg.wait_for_timeout(900); B.settle()
    check("a slow poll for the old plan is dropped after a switch", "LATE-FROM-A-FILE" not in B.names() and B.pname() == "Plan B" and "LATE-FROM-A-FILE" not in pg.evaluate("() => JSON.parse(localStorage.getItem('milestone-plan-' + currentPlanId)).tasks.map(t => t.name)"))

    # --- one file, one plan
    pg.evaluate("() => chooseFolderForPlan('link')"); pg.wait_for_selector("#folderFilesModalBg.open")
    check("the folder's file list shows another plan's file as taken (greyed out, 'Already linked to the plan …') and it cannot be chosen", pg.locator("#folderFilesList .folder-row.taken:has-text('plan-a.json')").count() == 1 and "Already linked to the plan" in pg.inner_text("#folderFilesList .folder-row.taken:has-text('plan-a.json')") and pg.locator("#folderFilesList .folder-row.taken input").first.is_disabled())
    pg.click("#folderFilesModalBg .modal-footer .btn:has-text('Back')"); pg.wait_for_timeout(150)
    check("...and the plan stays linked to its own file", B.status() == "linked" and "Plan B.json" in pg.inner_text("#fileSyncBtn"))

    # --- the linked file goes missing
    pg.evaluate("async () => { const r = await navigator.storage.getDirectory(); await r.removeEntry('Plan B.json'); }")
    pg.evaluate("() => pollFileSync()"); pg.wait_for_selector("#fileSyncModalBg.open", timeout=4000)
    check("file deleted -> status 'missing' and the dialog comes back", B.status() == "missing" and pg.inner_text("#fileSyncModalTitle") == "Linked file not found" and "Plan B.json" in pg.inner_text("#fileSyncModalText"), (B.status(), pg.inner_text("#fileSyncModalTitle")))
    check("...the top-bar button says so", "File missing" in pg.inner_text("#fileSyncBtn"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("...and it can't be dismissed", B.modal_open())
    B.modal_link_new("plan-b-recovered.json")
    check("creating a new file saves the plan's current tasks into it", B.status() == "linked" and B.file_tasks("plan-b-recovered.json") == B.names() and "B1" in B.names(), (B.status(), B.file_tasks("plan-b-recovered.json")))
    pg.evaluate("async () => { const r = await navigator.storage.getDirectory(); await r.removeEntry('plan-b-recovered.json'); }")
    B.add("AFTER-DELETE"); B.settle()
    check("a save after the file vanished re-creates it at the same place, nothing lost", "AFTER-DELETE" in (B.file_tasks("plan-b-recovered.json") or []) and B.status() == "linked", (B.file_tasks("plan-b-recovered.json"), B.status()))
    # missing again, then relink by opening an existing file (the merge path)
    pg.evaluate("async () => { const r = await navigator.storage.getDirectory(); await r.removeEntry('plan-b-recovered.json'); }")
    B.add("UNSAVED-EDIT")   # written straight back...
    B.settle(); pg.evaluate("async () => { const r = await navigator.storage.getDirectory(); await r.removeEntry('plan-b-recovered.json'); }")
    pg.evaluate("() => pollFileSync()"); pg.wait_for_selector("#fileSyncModalBg.open", timeout=4000)
    B.write_file("plan-b-old.json", json.dumps({"version": 1, "project": {"name": "Plan B", "updatedAt": 1}, "tasks": [], "deletedTaskIds": []}))
    check("the link dialog for a missing file also offers 'Pick a file in the same folder' (the folder is still granted)", pg.locator("#linkSameFolderBtn").is_visible())
    pg.click("#linkSameFolderBtn"); pg.wait_for_selector("#folderFilesModalBg.open"); pg.click("#folderFilesList .folder-row:has-text('plan-b-old.json')"); pg.click("#folderFilesOkBtn"); pg.wait_for_selector("#fileSyncModalBg:not(.open)"); B.settle()
    check("picking an existing file relinks (merging) and keeps every task", B.status() == "linked" and "UNSAVED-EDIT" in B.names() and "UNSAVED-EDIT" in (B.file_tasks("plan-b-old.json") or []), B.file_tasks("plan-b-old.json"))

    # --- an unlinked plan (e.g. left over from before linking was mandatory) must be linked when it's opened
    pg.evaluate("() => { window.__orph = createPlanRecord('Orphan', null); }")
    B.open_menu(); pg.locator(".plan-item", has_text="Orphan").first.click(); pg.wait_for_selector("#fileSyncModalBg.open", timeout=4000)
    check("opening an unlinked plan brings up the mandatory dialog", B.pname() == "Orphan" and B.status() == "unlinked" and B.modal_open())
    B.modal_link_new("orphan.json")
    check("...and linking it fixes it", B.status() == "linked" and B.file_tasks("orphan.json") == [])

    # --- disconnect a file, then connect a new or a different one
    idb_has = lambda key: pg.evaluate("""async (k) => new Promise(res => { const r = indexedDB.open('milestone-fs', 1); r.onsuccess = () => { const q = r.result.transaction('handles').objectStore('handles').getAllKeys(); q.onsuccess = () => res(q.result.includes(k)); }; })""", key)
    B.add("D0"); B.settle()
    pg.click("#fileSyncBtn"); pg.wait_for_selector("#confirmModalBg.open")
    check("clicking the linked file button offers to disconnect (with a confirmation)", "orphan.json" in pg.inner_text("#confirmModalBody") and pg.inner_text("#confirmModalTitle") == "Disconnect file", pg.inner_text("#confirmModalBody"))
    pg.click("#confirmModalBg button:has-text('Cancel')"); pg.wait_for_timeout(200)
    check("Cancel keeps the file linked", B.status() == "linked" and not B.modal_open())
    B.add("D1")     # edit and disconnect straight away: the file must still get it
    pg.click("#fileSyncBtn"); pg.wait_for_selector("#confirmModalBg.open"); pg.click("#confirmModalActionBtn"); pg.wait_for_selector("#fileSyncModalBg.open", timeout=4000); B.settle()
    check("Disconnect: the link dialog comes up straight away (linking is still mandatory)", B.status() == "unlinked" and B.modal_open() and pg.inner_text("#fileSyncModalTitle") == "Choose a folder to continue")
    check("...the file was brought up to date first and is not deleted", B.file_tasks("orphan.json") == ["D0", "D1"], B.file_tasks("orphan.json"))
    check("...its handle is gone from IndexedDB and the index", not idb_has("plan:" + pg.evaluate("() => currentPlanId")) and [x for x in B.index()["plans"] if x["id"] == pg.evaluate("() => currentPlanId")][0]["fileName"] is None)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check("...and it can't be dismissed", B.modal_open())
    B.add("D2")
    check("nothing is written to the old file any more", B.file_tasks("orphan.json") == ["D0", "D1"])
    B.modal_link_new("connect-new.json")
    check("connect a NEW file: it gets all of the plan's tasks, the old file stays as it was", B.status() == "linked" and B.file_tasks("connect-new.json") == ["D0", "D1", "D2"] and B.file_tasks("orphan.json") == ["D0", "D1"], (B.file_tasks("connect-new.json"), B.file_tasks("orphan.json")))
    check("...and the button shows the new file", "connect-new.json" in pg.inner_text("#fileSyncBtn"))
    B.add("D3"); B.settle()
    check("later edits go to the new file only", B.file_tasks("connect-new.json")[-1] == "D3" and B.file_tasks("orphan.json") == ["D0", "D1"])

    # disconnect from the plan menu, connect a DIFFERENT existing file (merged)
    B.write_file("different.json", json.dumps({"version": 1, "project": {"name": "Other", "updatedAt": 1}, "tasks": [dict(LEG[2], name="Other 1")], "deletedTaskIds": []}))
    B.open_menu(); check("the plan menu has 'Disconnect file…', enabled while linked", not pg.locator("#planDisconnectItem").is_disabled())
    pg.click("#planDisconnectItem"); pg.wait_for_selector("#confirmModalBg.open"); pg.click("#confirmModalActionBtn"); pg.wait_for_selector("#fileSyncModalBg.open", timeout=4000); B.settle()
    B.modal_link_existing("different.json")
    check("connect a DIFFERENT file: linked, its tasks merged into the plan, plan's tasks written into it", B.status() == "linked" and "Other 1" in B.names() and "D3" in B.names() and sorted(B.file_tasks("different.json")) == sorted(B.names()), (B.names(), B.file_tasks("different.json")))
    check("...the previous file was left alone", B.file_tasks("connect-new.json")[-1] == "D3" and "Other 1" not in B.file_tasks("connect-new.json"))
    # the same file can be connected again after disconnecting it
    pg.click("#fileSyncBtn"); pg.wait_for_selector("#confirmModalBg.open"); pg.click("#confirmModalActionBtn"); pg.wait_for_selector("#fileSyncModalBg.open", timeout=4000)
    B.modal_link_existing("different.json")
    check("reconnecting the very same file works", B.status() == "linked" and "different.json" in pg.inner_text("#fileSyncBtn"))
    B.boot(); check("after a reload the new link is remembered (no dialog)", B.status() == "linked" and not B.modal_open() and "different.json" in pg.inner_text("#fileSyncBtn"))

    # --- open an existing plan file as a plan (the file is picked from the folder's list)
    B.write_file("from-disk.json", json.dumps({"version": 1, "project": {"name": "From Disk", "updatedAt": 9}, "tasks": [dict(LEG[0], name="Disk 1"), dict(LEG[1], name="Disk 2")], "deletedTaskIds": []}))
    B.write_file("junk.json", "not json at all")
    n = len(B.index()["plans"])
    row = B.open_plan_from("from-disk.json")
    check("Open plan from folder: the list shows plan files with their plan name and task count, and skips files that are not plans (junk.json)", "From Disk" in row.inner_text() and "2 tasks" in row.inner_text() and pg.locator("#folderFilesList .folder-row:has-text('junk.json')").count() == 0 and pg.inner_text("#folderFilesOkBtn") == "Open plan")
    row.click(); pg.click("#folderFilesOkBtn"); pg.wait_for_timeout(600); B.settle()
    check("opening it: named after the file's project, its tasks, linked, in a new plan", B.pname() == "From Disk" and B.names() == ["Disk 1", "Disk 2"] and B.status() == "linked" and len(B.index()["plans"]) == n + 1)
    row = B.open_plan_from("from-disk.json")
    check("a file that is already a plan is greyed out in the list, so it cannot be opened twice", "taken" in (row.get_attribute("class") or "") and "Already linked" in row.inner_text() and pg.locator("#folderFilesOkBtn").is_disabled() or "taken" in (row.get_attribute("class") or ""))
    pg.click("#folderFilesModalBg .modal-footer .btn:has-text('Back')"); pg.wait_for_timeout(150)
    check("...and nothing was added", len(B.index()["plans"]) == n + 1)

    # --- reload
    B.switch_ui("Plan B"); B.boot()
    check("reload: the plan reopens still linked (no dialog)", B.pname() == "Plan B" and B.status() == "linked" and not B.modal_open(), (B.pname(), B.status()))
    B.switch_ui("From Disk")
    check("...and other plans re-link on switch", B.status() == "linked" and "from-disk.json" in pg.inner_text("#fileSyncBtn"))

    # --- migration with a legacy handle; and no resurrection once it is gone
    pg.evaluate("""async (legacy) => {
        localStorage.clear(); localStorage.setItem('milestone-v1', JSON.stringify(legacy));
        const root = await navigator.storage.getDirectory(); const h = await root.getFileHandle('legacy.json', {create: true});
        const w = await h.createWritable(); await w.write(JSON.stringify({version: 1, project: legacy.project, tasks: legacy.tasks, deletedTaskIds: []})); await w.close();
        await new Promise((res, rej) => { const r = indexedDB.open('milestone-fs', 1); r.onsuccess = () => { const tx = r.result.transaction('handles', 'readwrite'); tx.objectStore('handles').clear(); tx.objectStore('handles').put(h, 'syncFile'); tx.oncomplete = res; tx.onerror = rej; }; });
    }""", LEGACY)
    B.boot()
    check("migration: the old linked file follows the project (no dialog needed)", B.pname() == "Legacy Proj" and B.status() == "linked" and B.index()["plans"][0]["fileName"] == "legacy.json" and not B.modal_open(), (B.status(), B.index()))
    check("...a plan linked to a single file (before folders) keeps working and gets a 'Link folder' reminder, and the plan menu offers 'Link this plan's folder…'", pg.locator("#watchHint").is_visible() and "Link folder" in pg.inner_text("#watchHintBtn"))
    pg.evaluate("""async () => new Promise((res, rej) => { const r = indexedDB.open('milestone-fs', 1); r.onsuccess = () => { const tx = r.result.transaction('handles', 'readwrite'); tx.objectStore('handles').delete('plan:plan1'); tx.oncomplete = res; tx.onerror = rej; }; })""")
    B.boot(); pg.wait_for_selector("#fileSyncModalBg.open")
    check("a plan whose file link is gone is not silently re-linked to the old handle; it must be linked again", B.status() == "unlinked" and B.modal_open())

    print("console errors/warnings:", errors)
    print(f"{sum(results)}/{len(results)} passed")
    b.close()
