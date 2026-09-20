import json, re, time
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:400]}]" if not cond and detail else ""))
# Two "devices" = two browser contexts, each with a private file system (OPFS) holding ITS COPY of the shared file. The shared folder is
# simulated by a Python string: before a device touches the file (a save, a poll) it receives the current shared text, afterwards the
# shared text becomes whatever is in its copy — exactly what one file in a synced folder does.
FS_INIT = """
window.__pick = null; window.__writes = 0; window.__ignore = false;
const _mk = async (create, o) => { const r = await navigator.storage.getDirectory(); return r.getFileHandle(window.__pick || 'shared.json', {create}); };
window.showSaveFilePicker = async (o) => _mk(true, o);
window.showOpenFilePicker = async (o) => [await _mk(false, o)];
const _cw = FileSystemFileHandle.prototype.createWritable;
FileSystemFileHandle.prototype.createWritable = async function (...a) { if (!window.__ignore) window.__writes++; return _cw.apply(this, a); };
"""
TASKS = [
  {"id": "ta", "name": "Alpha", "s": "2026-09-07", "e": "2026-09-11"},
  {"id": "tb", "name": "Beta", "s": "2026-09-14", "e": "2026-09-18", "preds": [["ta", "FS", 0]]},
  {"id": "tc", "name": "Gamma", "s": "2026-09-21", "e": "2026-09-25"},
]
SEEDJS = """(specs) => { tasks.length = 0; deletedTaskIds.length = 0; let n = 0;
  for (const sp of specs) tasks.push({id: sp.id, name: sp.name, parentId: null, order: n++, startDate: sp.s, endDate: sp.e, progress: 0, milestone: false, color: null, predecessors: (sp.preds || []).map(([id, type, lag]) => ({id, type, lag})), collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null});
  project.updatedAt = 1; save(); render(); }"""
NEWTASK = "([id, name, s, e]) => { tasks.push({id, name, parentId: null, order: tasks.length, startDate: s, endDate: e, progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: Date.now(), constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null}); save(); }"
class Shared:
    text = None
def make(b, shared):
    ctx = b.new_context(viewport={"width": 1400, "height": 800}); ctx.add_init_script(FS_INIT)
    pg = ctx.new_page(); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None); pg.on("pageerror", lambda e: errors.append(str(e)))
    class D: pass
    d = D(); d.pg = pg; d.shared = shared
    def boot(): pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.wait_for_function("() => fileSyncStatus !== 'checking'"); pg.wait_for_timeout(150)
    def settle(): pg.wait_for_function("() => !fileSyncWriteInFlight && !fileSyncWritePending", timeout=8000); pg.wait_for_timeout(150)
    def read(): return pg.evaluate("async () => { const r = await navigator.storage.getDirectory(); const h = await r.getFileHandle('shared.json'); return (await h.getFile()).text(); }")
    def write(text): pg.evaluate("async t => { window.__ignore = true; const r = await navigator.storage.getDirectory(); const h = await r.getFileHandle('shared.json', {create: true}); const w = await h.createWritable(); await w.write(t); await w.close(); window.__ignore = false; }", text)
    d.boot, d.settle, d.read, d.write = boot, settle, read, write
    def op(fn):   # this device touches the file: it first receives the shared text, and what it leaves behind becomes the shared text
        if shared.text is not None: write(shared.text)
        r = fn(); settle(); shared.text = read(); return r
    d.op = op
    def link_new(): pg.evaluate("() => window.__pick = 'shared.json'"); pg.click("#fileSyncModalBg button:has-text('Create new file')"); pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle(); shared.text = read()
    def link_existing():
        write(shared.text); pg.evaluate("() => window.__pick = 'shared.json'"); pg.click("#fileSyncModalBg button:has-text('Open existing file')"); pg.wait_for_selector("#fileSyncModalBg:not(.open)"); settle(); shared.text = read()
    d.link_new, d.link_existing = link_new, link_existing
    d.poll = lambda: op(lambda: pg.evaluate("() => pollFileSync()"))
    d.edit = lambda name, **kw: op(lambda: pg.evaluate("([n, kw]) => { const t = tasks.find(x => x.name === n); Object.assign(t, kw); t.updatedAt = Date.now(); save(); }", [name, kw]))
    d.run = lambda js, arg=None: op(lambda: pg.evaluate(js, arg))
    d.task = lambda n: pg.evaluate("n => { const t = tasks.find(x => x.name === n); return t ? JSON.parse(JSON.stringify(t)) : null; }", n)
    d.names = lambda: pg.evaluate("() => tasks.map(t => t.name).sort()")
    d.fdata = lambda: json.loads(shared.text)
    d.ftask = lambda n: next((t for t in json.loads(shared.text)["tasks"] if t["name"] == n), None)
    d.writes = lambda: pg.evaluate("() => window.__writes")
    d.conflicts = lambda: pg.evaluate("() => syncConflictLog.map(c => ({kind: c.kind, name: c.name, fields: c.fields.map(f => ({key: f.key, kept: f.kept, mine: f.mine, theirs: f.theirs}))}))")
    d.canon = lambda: pg.evaluate("() => canonicalText()")
    return d
def two_devices(b):
    sh = Shared(); A, B = make(b, sh), make(b, sh)
    A.boot(); A.link_new(); A.run(SEEDJS, TASKS); B.boot(); B.link_existing()
    return A, B, sh

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    A, B, sh = two_devices(b)
    check("setup: device B joined A's file and has the same three tasks", B.names() == ["Alpha", "Beta", "Gamma"] and A.names() == B.names(), (A.names(), B.names()))
    check("the file text is canonical: sorted keys, tasks in id order", (lambda d: [t["id"] for t in d["tasks"]] == sorted(t["id"] for t in d["tasks"]) and list(d["tasks"][0].keys()) == sorted(d["tasks"][0].keys()))(A.fdata()), list(A.fdata()["tasks"][0].keys())[:5])

    # ================================================================ different fields of the same task: both kept (write-time merge)
    A.edit("Alpha", resource="Ann"); time.sleep(0.05)
    B.pg.evaluate("() => { const t = tasks.find(x => x.name === 'Alpha'); t.progress = 40; t.updatedAt = Date.now(); persistLocal(); }")   # B edits (not yet saved to the file) ...
    B.edit("Gamma", resource="Zed")                                                                                                        # ... then saves: the file already holds A's change
    aB = B.task("Alpha")
    check("write-time merge: B's save merged A's change instead of overwriting it (Alpha has A's Resource AND B's % Complete)", aB["resource"] == "Ann" and aB["progress"] == 40, aB)
    check("...and the FILE now holds both changes plus B's other edit", B.ftask("Alpha")["resource"] == "Ann" and B.ftask("Alpha")["progress"] == 40 and B.ftask("Gamma")["resource"] == "Zed")
    check("...no conflict (different fields), no badge", B.conflicts() == [] and B.pg.locator("#syncConflictBtn.hidden").count() == 1)
    A.poll()
    check("A polls: gets B's changes, keeps its own — both devices now identical", A.task("Alpha")["progress"] == 40 and A.task("Alpha")["resource"] == "Ann" and A.task("Gamma")["resource"] == "Zed" and A.canon() == B.canon())
    w0 = (A.writes(), B.writes())
    for _ in range(3): A.poll(); B.poll()
    check("...and they STAY converged: repeated polling by both causes no further writes (no ping-pong)", (A.writes(), B.writes()) == w0 and A.canon() == B.canon(), (w0, (A.writes(), B.writes())))

    # ================================================================ the same field: a conflict; the newer edit wins and is reported
    A.edit("Beta", resource="from A"); time.sleep(0.06)
    B.pg.evaluate("() => { const t = tasks.find(x => x.name === 'Beta'); t.resource = 'from B'; t.updatedAt = Date.now(); persistLocal(); }")
    B.poll()   # B has an unsynced edit and now meets A's: a genuine conflict, found by the poll
    c = B.conflicts()
    check("both changed Beta's Resource: the NEWER edit (B's) is kept, and the conflict is logged with both values", B.task("Beta")["resource"] == "from B" and len(c) == 1 and c[0]["name"] == "Beta" and c[0]["fields"][0]["key"] == "resource" and c[0]["fields"][0]["kept"] == "mine" and c[0]["fields"][0]["theirs"] == "from A", c)
    check("...a badge '1 conflict' appears next to the file indicator and a toast offers Review", "1 conflict" in B.pg.inner_text("#syncConflictBtn") and "Review" in B.pg.inner_text("#toast"), (B.pg.inner_text("#syncConflictBtn"), B.pg.inner_text("#toast")))
    B.pg.click("#syncConflictBtn"); B.pg.wait_for_selector("#syncConflictsModalBg.open")
    txt = B.pg.inner_text("#syncConflictsBody")
    check("Review lists it: task name, the field, 'Yours' / 'The other version' values, which one was kept", "Beta" in txt and "Resource" in txt and "from A" in txt and "from B" in txt and "KEPT" in txt.upper(), txt)
    B.op(lambda: B.pg.click("#syncConflictsBody button:has-text('Use theirs')"))
    check("'Use theirs' takes the other version (from A), removes the entry, closes the modal, and the file follows", B.task("Beta")["resource"] == "from A" and B.conflicts() == [] and B.pg.locator("#syncConflictsModalBg.open").count() == 0 and B.ftask("Beta")["resource"] == "from A" and B.pg.locator("#syncConflictBtn.hidden").count() == 1, (B.task("Beta")["resource"], B.conflicts()))
    A.poll()
    check("...and A receives that decision (no new conflict on A)", A.task("Beta")["resource"] == "from A" and A.conflicts() == [], (A.task("Beta")["resource"], A.conflicts()))
    # write-time conflict (both edited, the second device saves)
    A.edit("Gamma", resource="g-A"); time.sleep(0.06)
    B.pg.evaluate("() => { const t = tasks.find(x => x.name === 'Gamma'); t.resource = 'g-B'; t.updatedAt = Date.now(); persistLocal(); }")
    B.edit("Alpha", progress=55)      # B's save reads the file (A's g-A) and merges it into its unsynced g-B
    check("a conflict is also found when B SAVES (write-time merge): the newer g-B stays, one conflict is logged", B.task("Gamma")["resource"] == "g-B" and len(B.conflicts()) == 1 and B.conflicts()[0]["name"] == "Gamma", (B.task("Gamma")["resource"], B.conflicts()))
    B.pg.evaluate("() => clearSyncConflicts()"); A.poll()

    # ================================================================ new tasks on both sides, a deletion, an edit after a delete
    A.run(NEWTASK, ["tx", "FromA", "2026-10-05", "2026-10-06"])
    B.op(lambda: B.pg.evaluate(NEWTASK, ["ty", "FromB", "2026-10-07", "2026-10-08"]))   # B's save merges A's new task
    check("a task added on each side: B's save keeps A's new task and its own; the file has both", "FromA" in B.names() and "FromB" in B.names() and {t["name"] for t in B.fdata()["tasks"]} >= {"FromA", "FromB"}, B.names())
    A.poll()
    B.run("() => { const t = tasks.find(x => x.name === 'FromA'); tasks = tasks.filter(x => x !== t); tombstone(deletedTaskIds, t.id); save(); }")
    A.poll()
    check("B deletes 'FromA' (tombstone): A polls and the task is gone there too", "FromA" not in A.names() and "FromB" in A.names(), A.names())
    B.run("() => { const t = tasks.find(x => x.name === 'FromB'); tasks = tasks.filter(x => x !== t); tombstone(deletedTaskIds, t.id); save(); }"); time.sleep(0.05)
    A.pg.evaluate("() => { const t = tasks.find(x => x.name === 'FromB'); t.resource = 'edited after'; t.updatedAt = Date.now(); persistLocal(); }")
    A.poll()
    check("a delete does not beat an edit made after it: 'FromB' survives on A with its newer edit", A.task("FromB") is not None and A.task("FromB")["resource"] == "edited after", A.task("FromB"))

    # ================================================================ the schedule is re-checked after a merge
    A2, B2, sh2 = two_devices(b)
    A2.run("() => { const t = tasks.find(x => x.name === 'Alpha'); t.startDate = '2026-09-14'; t.endDate = '2026-09-25'; t.updatedAt = Date.now(); cascadeSchedule(t.id); save(); }")
    beta_a = A2.task("Beta")
    B2.pg.evaluate("() => { const t = tasks.find(x => x.name === 'Beta'); t.resource = \"B's note\"; t.updatedAt = Date.now(); persistLocal(); }")
    B2.edit("Gamma", resource="x")
    bb = B2.task("Beta")
    check("A moved Alpha later (its cascade moved Beta); B edited only Beta's Resource: after B merges, Beta has A's new dates AND B's note", bb["startDate"] == beta_a["startDate"] and bb["endDate"] == beta_a["endDate"] and bb["resource"] == "B's note", (bb, beta_a))
    A3, B3, sh3 = two_devices(b)
    payload = json.loads(sh3.text)   # a file where Alpha moved later but Beta was NOT re-planned (e.g. written by something that doesn't schedule)
    for t in payload["tasks"]:
        if t["name"] == "Alpha": t["startDate"], t["endDate"], t["updatedAt"] = "2026-09-21", "2026-09-25", 9_000_000_000_000
    sh3.text = json.dumps(payload)
    B3.poll(); bt = B3.task("Beta")
    check("a merge that brings a later predecessor re-plans its successor: Beta (auto, 14.09) is pushed after Alpha's new finish (25.09) -> 28.09", bt["startDate"] == "2026-09-28", bt)
    check("...and the toast says tasks were re-planned", "re-planned" in B3.pg.inner_text("#toast"), B3.pg.inner_text("#toast"))

    # ================================================================ determinism
    check("canonical text ignores the order of tasks and of keys inside a task", B.pg.evaluate("""() => { const a = canonicalText(); const saved = tasks.slice(); tasks.reverse(); tasks.forEach((t, i) => { const o = {}; Object.keys(t).reverse().forEach(k => o[k] = t[k]); tasks[i] = o; }); const b = canonicalText(); tasks.length = 0; tasks.push(...saved); return a === b; }"""))
    A4, B4, sh4 = two_devices(b)
    same_ts = 5000000000000
    A4.pg.evaluate("ts => { const t = tasks.find(x => x.name === 'Gamma'); t.resource = 'aaa'; t.updatedAt = ts; persistLocal(); }", same_ts)
    B4.pg.evaluate("ts => { const t = tasks.find(x => x.name === 'Gamma'); t.resource = 'zzz'; t.updatedAt = ts; persistLocal(); }", same_ts)
    A4.op(lambda: A4.pg.evaluate("() => save()")); B4.poll(); A4.poll(); B4.poll(); A4.poll()
    check("same field, same timestamp on both devices: both pick the same winner (content decides), so they converge", A4.task("Gamma")["resource"] == B4.task("Gamma")["resource"] and A4.canon() == B4.canon(), (A4.task("Gamma")["resource"], B4.task("Gamma")["resource"]))

    # ================================================================ offline edits survive a reload (the base is kept per plan)
    A5, B5, sh5 = two_devices(b)
    plan_id = A5.pg.evaluate("() => currentPlanId")
    check("the last-synced state is kept per plan in localStorage (the base of the next merge)", A5.pg.evaluate("id => !!localStorage.getItem('milestone-syncbase-' + id)", plan_id))
    A5.pg.evaluate("() => { const t = tasks.find(x => x.name === 'Alpha'); t.resource = 'offline A'; t.updatedAt = Date.now(); persistLocal(); }")   # edited, page closed before it reached the file
    B5.edit("Alpha", progress=70)
    A5.op(lambda: (A5.pg.reload(), A5.pg.wait_for_selector("#addTaskBtn"), A5.pg.wait_for_function("() => fileSyncStatus !== 'checking'")))   # reopening the app: it meets the shared file (with B's change) again
    tt = A5.task("Alpha")
    check("A edited offline (Resource), B edited another field (% Complete) meanwhile: after A reloads and syncs, BOTH survive (three-way merge with the saved base)", tt["resource"] == "offline A" and tt["progress"] == 70, tt)
    check("...and the file gets A's offline work too", A5.ftask("Alpha")["resource"] == "offline A" and A5.ftask("Alpha")["progress"] == 70, A5.ftask("Alpha"))

    # ================================================================ plan settings, conflicts UI
    A6, B6, sh6 = two_devices(b)
    A6.run("() => { project.workDays = [1,2,3,4,5,6]; project.updatedAt = Date.now(); save(); }"); time.sleep(0.05)
    B6.pg.evaluate("() => { project.name = 'Renamed on B'; project.updatedAt = Date.now(); persistLocal(); }")
    B6.run("() => { save(); }")
    check("plan settings merge field by field: A's working calendar AND B's new plan name both survive, no conflict", B6.pg.evaluate("() => project.name") == "Renamed on B" and B6.pg.evaluate("() => calendarLabel()") == "Mon–Sat" and B6.conflicts() == [], (B6.pg.evaluate("() => project.name"), B6.pg.evaluate("() => calendarLabel()")))
    A7, B7, sh7 = two_devices(b)
    A7.run("() => { project.workDays = [1,2,3,4,5,6]; project.updatedAt = Date.now(); save(); }"); time.sleep(0.06)
    B7.pg.evaluate("() => { project.workDays = [0,1,2,3,4,5,6]; project.updatedAt = Date.now(); persistLocal(); }")
    B7.poll()
    cc = B7.conflicts()
    check("both changed the working calendar: B's (newer) is kept and 'Plan settings' shows up as a conflict", B7.pg.evaluate("() => calendarLabel()") == "Every day" and len(cc) == 1 and cc[0]["kind"] == "plan" and cc[0]["fields"][0]["key"] == "workDays", cc)
    B7.pg.click("#syncConflictBtn"); B7.pg.wait_for_selector("#syncConflictsModalBg.open"); B7.op(lambda: B7.pg.click("#syncConflictsBody button:has-text('Use theirs')"))
    check("...'Use theirs' switches the calendar to A's (Mon–Sat)", B7.pg.evaluate("() => calendarLabel()") == "Mon–Sat")
    A8, B8, sh8 = two_devices(b)
    A8.edit("Gamma", resource="a1"); time.sleep(0.05); A8.edit("Alpha", resource="a2"); time.sleep(0.05)
    B8.pg.evaluate("() => { for (const [n, v] of [['Gamma', 'b1'], ['Alpha', 'b2']]) { const t = tasks.find(x => x.name === n); t.resource = v; t.updatedAt = Date.now(); } persistLocal(); }")
    B8.poll()
    check("two conflicts at once: the badge says '2 conflicts'", "2 conflicts" in B8.pg.inner_text("#syncConflictBtn"), B8.pg.inner_text("#syncConflictBtn"))
    B8.pg.click("#syncConflictBtn"); B8.pg.wait_for_selector("#syncConflictsModalBg.open"); B8.pg.click("#syncConflictsBody .conflict-card:first-child button:has-text('Dismiss')"); B8.pg.wait_for_timeout(150)
    check("'Dismiss' removes one entry without changing anything (badge '1 conflict')", "1 conflict" in B8.pg.inner_text("#syncConflictBtn"))
    B8.pg.click("#syncConflictsModalBg button:has-text('Dismiss all')"); B8.pg.wait_for_timeout(150)
    check("'Dismiss all' clears the log, hides the badge and closes the modal", B8.conflicts() == [] and B8.pg.locator("#syncConflictBtn.hidden").count() == 1 and B8.pg.locator("#syncConflictsModalBg.open").count() == 0)
    B8.pg.evaluate("() => { syncConflictLog.push({kind: 'task', id: 'ta', name: 'Alpha', at: Date.now(), fields: [{key: 'resource', mine: 'x', theirs: 'y', kept: 'mine'}]}); updateSyncConflictsUI(); openSyncConflictsModal(); }"); B8.pg.keyboard.press("Escape"); B8.pg.wait_for_timeout(150)
    check("Escape closes the conflicts dialog", B8.pg.locator("#syncConflictsModalBg.open").count() == 0)
    # first link: no base -> no conflict reporting
    sh9 = Shared(); A9 = make(b, sh9); A9.boot(); A9.link_new(); A9.run(SEEDJS, TASKS); C9 = make(b, sh9); C9.boot(); C9.link_existing()
    check("linking an existing file has no earlier state to merge against: no conflicts are reported", C9.conflicts() == [] and C9.names() == ["Alpha", "Beta", "Gamma"])
    # a single device
    sh10 = Shared(); S = make(b, sh10); S.boot(); S.link_new(); S.run(SEEDJS, TASKS); w = S.writes()
    S.edit("Alpha", resource="solo")
    check("a single device: one edit = one file write, nothing else", S.writes() == w + 1 and S.ftask("Alpha")["resource"] == "solo", (w, S.writes()))
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
