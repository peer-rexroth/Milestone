"""The lead/lag box of the task dialog and of the Task Form reads units the way the Predecessors cell does: 2, -1d, +1w, 4h (a bare number is days; hours in a minute-mode plan)."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
SEED = """() => {
  const mk = (id, name, order, s, e, extra) => Object.assign({ id, name, parentId: null, order, startDate: s, endDate: e, progress: 0, predecessors: [], taskMode: 'manual', updatedAt: 1 }, extra || {});
  tasks = [ mk('a','Alpha',0,'2027-01-04','2027-01-08'), mk('b','Beta',1,'2027-01-18','2027-01-22',{ predecessors: [{ id: 'a', type: 'FS', lag: 2 }] }) ];
  normalizeData(); save(); render();
}"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); errors = []
    pg = b.new_page(viewport={"width": 1500, "height": 1000}); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate; ev(SEED); pg.wait_for_timeout(300)
    lag = lambda: ev("() => byId('b').predecessors[0].lag")
    check("parseLagField: bare number = days, units d / w, sign, blank", ev("() => [parseLagField('2'), parseLagField('-1d'), parseLagField('+1w'), parseLagField(''), parseLagField('2 days')]") == [2, -1, 5, 0, 2])
    check("parseLagField refuses nonsense and elapsed units", ev("() => [parseLagField('abc'), parseLagField('2ed'), parseLagField('1.2.3')]") == [None, None, None])
    # task dialog
    ev("() => openTaskModal('b')"); pg.wait_for_timeout(300)
    check("the dialog's lag box is a text box showing the lag as the cell does (+2)", pg.input_value("#predecessorRows .pred-lag-input") == "+2")
    pg.fill("#predecessorRows .pred-lag-input", "1w"); pg.keyboard.press("Tab"); pg.wait_for_timeout(150)
    check("typing 1w reads as 5 working days and shows +5", ev("() => editingPredecessors[0].lag") == 5 and pg.input_value("#predecessorRows .pred-lag-input") == "+5")
    pg.fill("#predecessorRows .pred-lag-input", "-1d"); pg.keyboard.press("Tab"); pg.wait_for_timeout(150)
    check("-1d is a lead of one day", ev("() => editingPredecessors[0].lag") == -1 and pg.input_value("#predecessorRows .pred-lag-input") == "-1")
    pg.fill("#predecessorRows .pred-lag-input", "soon"); pg.keyboard.press("Tab"); pg.wait_for_timeout(200)
    check("nonsense is refused with a message and the old value comes back", ev("() => editingPredecessors[0].lag") == -1 and pg.input_value("#predecessorRows .pred-lag-input") == "-1" and "Can't read" in pg.inner_text("#toast"))
    pg.fill("#predecessorRows .pred-lag-input", "3"); pg.keyboard.press("Tab"); ev("() => saveTaskFromModal()"); pg.wait_for_timeout(300)
    check("saving keeps it (3 days)", lag() == 3, lag())
    # Task Form
    ev("() => { setSelection(['b']); if (!document.getElementById('taskForm') || document.getElementById('taskForm').classList.contains('hidden')) toggleTaskForm(); renderTaskForm(true); }"); pg.wait_for_timeout(400)
    check("the Task Form's lag box shows +3", pg.input_value("#tfPredRows .tf-lag") == "+3", pg.input_value("#tfPredRows .tf-lag") if pg.locator("#tfPredRows .tf-lag").count() else "no box")
    pg.fill("#tfPredRows .tf-lag", "2w"); pg.wait_for_timeout(100)
    ev("() => applyTaskForm()"); pg.wait_for_timeout(400)
    check("typing 2w in the Task Form and saving gives 10 working days", lag() == 10, lag())
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
