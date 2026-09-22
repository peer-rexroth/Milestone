# -*- coding: utf-8 -*-
"""Export to MS Project (MSPDI XML): the file is well-formed and every element is in the schema's order; it reads back through the app's own MSPDI importer
with everything intact (outline, dates, durations, milestones, manual / TBD tasks, links with type and lag, constraints, actual dates, baselines, resources,
working week, holidays); the menu item downloads a .xml. (Not opened in MS Project itself — the schema order and the round trip are what is checked.)"""
import os, re
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

NS = "{http://schemas.microsoft.com/project}"
# element order of the MSPDI schema (xs:sequence) — only the elements the exporter may write, in schema order
ORDER = {
 "Project": "SaveVersion Name Title CreationDate LastSaved ScheduleFromStart StartDate FinishDate CalendarUID DefaultStartTime DefaultFinishTime MinutesPerDay MinutesPerWeek DaysPerMonth DefaultTaskType DurationFormat WorkFormat WeekStartDay Calendars Tasks Resources Assignments".split(),
 "Calendar": "UID Name IsBaseCalendar IsBaselineCalendar WeekDays Exceptions".split(),
 "WeekDay": "DayType DayWorking WorkingTimes".split(),
 "Exception": "EnteredByOccurrences TimePeriod Occurrences Name Type DayWorking".split(),
 "Task": "UID ID Name Active Manual Type IsNull WBS OutlineNumber OutlineLevel Priority Start Finish Duration ManualStart ManualFinish ManualDuration DurationFormat Milestone Summary PercentComplete PercentWorkComplete ActualStart ActualFinish ConstraintType ConstraintDate Notes PredecessorLink Baseline".split(),
 "PredecessorLink": "PredecessorUID Type CrossProject LinkLag LagFormat".split(),
 "Baseline": "Number Start Finish Duration DurationFormat".split(),
 "Resource": "UID ID Name Type IsNull MaxUnits".split(),
 "Assignment": "UID TaskUID ResourceUID Units".split(),
}
def in_order(el, names):
    tags = [c.tag.replace(NS, "") for c in el]
    idx = [names.index(t) for t in tags if t in names]
    return all(t in names for t in tags) and idx == sorted(idx)

SEED = """() => { tasks.length = 0; deletedTaskIds.length = 0; setSelection([]); project.name = 'Cost plan'; project.workDays = [1, 2, 3, 4, 6]; project.holidays = [{ date: '2026-12-24', to: '2026-12-28', name: 'Christmas' }, { date: '2026-05-01', name: 'Labour Day', yearly: true }]; project.fieldNames = { text1: 'Cost centre' }; project.baselines = {}; historyCoalesceMs = 0;
  const mk = (id, n, o, e) => Object.assign({ id, name: n, parentId: null, order: o, startDate: '2026-09-07', endDate: '2026-09-11', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null }, e || {});
  tasks.push(mk('g', 'Website & <relaunch>', 0), mk('a', 'Design', 0, { parentId: 'g', resource: 'Anna, Ben', progress: 100, actualStart: '2026-09-07', actualFinish: '2026-09-11', baselines: { 0: ['2026-09-07', '2026-09-10'] } }),
    mk('b', 'Build', 1, { parentId: 'g', startDate: '2026-09-14', endDate: '2026-09-25', progress: 40, resource: 'Ben', predecessors: [{ id: 'a', type: 'FS', lag: 1 }], constraintType: 'SNET', constraintDate: '2026-09-14', custom: { text1: 'CC-104' }, baselines: { 0: ['2026-09-14', '2026-09-24'] } }),
    mk('sp', '', 2, { spacer: true, parentId: 'g', taskMode: 'manual' }),
    mk('c', 'Decide vendor', 3, { parentId: 'g', taskMode: 'manual', startText: 'TBD', endText: 'TBD' }),
    mk('m', 'Go live', 1, { milestone: true, startDate: '2026-10-05', endDate: '2026-10-05', predecessors: [{ id: 'b', type: 'FF', lag: -2 }] }),
    mk('d', 'Pinned manual', 2, { taskMode: 'manual', startDate: '2026-10-12', endDate: '2026-10-16', predecessors: [{ id: 'm', type: 'SS', lag: 3 }] }));
  project.baselines = { 0: { setAt: '2026-09-01' } }; normalizeData(); save(); render(); }"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1400, "height": 800}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev(SEED); pg.wait_for_timeout(150)
    xml = ev("() => buildMspdi()")
    root = ET.fromstring(xml)
    check("the export is well-formed XML in the MSPDI namespace with a Project root", root.tag == NS + "Project", root.tag)
    check("Project: elements in schema order; title and file name; 480 minutes a day", in_order(root, ORDER["Project"]) and root.find(NS + "Title").text == "Cost plan" and root.find(NS + "Name").text == "Cost plan.xml" and root.find(NS + "MinutesPerDay").text == "480" and root.find(NS + "MinutesPerWeek").text == "2400", [c.tag for c in root][:12])
    cal = root.find(f"{NS}Calendars/{NS}Calendar")
    check("the base calendar: elements in order, 7 WeekDays with Sunday = DayType 1 … Saturday = 7 (working Mon, Tue, Wed, Thu, Sat here)", in_order(cal, ORDER["Calendar"]) and [(w.find(NS + "DayType").text, w.find(NS + "DayWorking").text) for w in cal.iter(NS + "WeekDay")] == [("1", "0"), ("2", "1"), ("3", "1"), ("4", "1"), ("5", "1"), ("6", "0"), ("7", "1")])
    check("...working days carry their working times (08:00–12:00, 13:00–17:00), days off none", all(in_order(w, ORDER["WeekDay"]) for w in cal.iter(NS + "WeekDay")) and len(list(cal.iter(NS + "WorkingTime"))) == 10)
    exc = list(cal.iter(NS + "Exception"))
    dates = sorted(e.find(f"{NS}TimePeriod/{NS}FromDate").text[:10] for e in exc)
    check("holidays are exceptions: the break (24.–28.12.) as one period, the yearly Labour Day expanded for the project's years ±1", all(in_order(e, ORDER["Exception"]) for e in exc) and "2026-12-24" in dates and dates.count("2026-05-01") == 1 and "2025-05-01" in dates and "2027-05-01" in dates, dates)
    check("...the break's period ends on the 28th, each exception is a non-working day", [e.find(f"{NS}TimePeriod/{NS}ToDate").text[:10] for e in exc if e.find(NS + "Name") is not None and e.find(NS + "Name").text == "Christmas"] == ["2026-12-28"] and all(e.find(NS + "DayWorking").text == "0" for e in exc))
    tasks_ = list(root.find(NS + "Tasks"))
    names = [t.find(NS + "Name").text for t in tasks_]
    check("tasks in outline order with the empty line left out, names with & and < escaped correctly", names == ["Website & <relaunch>", "Design", "Build", "Decide vendor", "Go live", "Pinned manual"], names)
    check("every Task has its elements in schema order", all(in_order(t, ORDER["Task"]) for t in tasks_), [c.tag.replace(NS, "") for c in tasks_[2]])
    tk = {t.find(NS + "Name").text: t for t in tasks_}
    g = lambda name, tag: (lambda e: e.text if e is not None else None)(tk[name].find(NS + tag))
    check("outline: level and WBS (the group is 1, its tasks 1.1, 1.2 — the empty line takes no number)", [g(n, "OutlineLevel") for n in names] == ["1", "2", "2", "2", "1", "1"] and [g(n, "WBS") for n in names] == ["1", "1.1", "1.2", "1.3", "2", "3"], [g(n, "WBS") for n in names])
    check("the group is a summary with its rolled-up dates and progress; a milestone has zero duration and one date", g("Website & <relaunch>", "Summary") == "1" and g("Website & <relaunch>", "Start")[:10] == "2026-09-07" and g("Go live", "Milestone") == "1" and g("Go live", "Duration") == "PT0H0M0S" and g("Go live", "Start") == g("Go live", "Finish"))
    check("durations are working days of THIS plan's calendar (Mon–Thu + Sat) × 8 h — Design 4 days = PT32H0M0S, Build 9 days = PT72H0M0S — and dates are 08:00 / 17:00", g("Design", "Duration") == "PT32H0M0S" and g("Build", "Duration") == "PT72H0M0S" and g("Design", "Start") == "2026-09-07T08:00:00" and g("Design", "Finish") == "2026-09-11T17:00:00")
    check("manual tasks are Manual=1 with ManualStart / ManualFinish / ManualDuration; the task with TBD dates has none of them and says so in its Notes", g("Pinned manual", "Manual") == "1" and g("Pinned manual", "ManualStart") is not None and g("Decide vendor", "Manual") == "1" and g("Decide vendor", "Start") is None and "TBD" in g("Decide vendor", "Notes"))
    check("progress, actual dates and the constraint (Start No Earlier Than = 4, with its date) are written", g("Build", "PercentComplete") == "40" and g("Design", "ActualStart") == "2026-09-07T08:00:00" and g("Design", "ActualFinish") == "2026-09-11T17:00:00" and g("Build", "ConstraintType") == "4" and g("Build", "ConstraintDate")[:10] == "2026-09-14")
    check("custom field values go into the Notes under the field's name", "Cost centre: CC-104" in g("Build", "Notes"), g("Build", "Notes"))
    links = {n: [(l.find(NS + "PredecessorUID").text, l.find(NS + "Type").text, l.find(NS + "LinkLag").text) for l in tk[n].findall(NS + "PredecessorLink")] for n in names}
    check("links: UIDs, MS Project's type numbers (FS 1, FF 0, SS 3) and the lag in tenths of a minute (+1 day = 4800, −2 days = −9600)", links["Build"] == [("2", "1", "4800")] and links["Go live"] == [("3", "0", "-9600")] and links["Pinned manual"] == [("5", "3", "14400")], links)
    check("each link's elements are in order, and the group has none", all(in_order(l, ORDER["PredecessorLink"]) for l in root.iter(NS + "PredecessorLink")) and not links["Website & <relaunch>"])
    bl = tk["Build"].findall(NS + "Baseline")
    check("baselines: Build's Baseline 0 (14.–24.09.), Design's; the group's is the rollup of its tasks", len(bl) == 1 and bl[0].find(NS + "Start").text[:10] == "2026-09-14" and bl[0].find(NS + "Finish").text[:10] == "2026-09-24" and all(in_order(x, ORDER["Baseline"]) for x in root.iter(NS + "Baseline")) and len(tk["Website & <relaunch>"].findall(NS + "Baseline")) == 1)
    res = [(r.find(NS + "UID").text, r.find(NS + "Name").text) for r in root.iter(NS + "Resource")]
    asg = [(a.find(NS + "TaskUID").text, a.find(NS + "ResourceUID").text) for a in root.iter(NS + "Assignment")]
    check("resources: Anna and Ben once each, and an assignment per task and person (Design: Anna + Ben, Build: Ben)", res == [("1", "Anna"), ("2", "Ben")] and asg == [("2", "1"), ("2", "2"), ("3", "2")] and all(in_order(r, ORDER["Resource"]) for r in root.iter(NS + "Resource")) and all(in_order(a, ORDER["Assignment"]) for a in root.iter(NS + "Assignment")), (res, asg))

    # ---------------------------------------------------------------- reads back through the app's own MSPDI importer
    back = ev("""(x) => { const r = parseMspdi(x); const byName = n => r.tasks.find(t => t.name === n); const nm = id => (r.tasks.find(t => t.id === id) || {}).name;
      return { project: r.project, warnings: r.warnings, tasks: r.tasks.map(t => ({ n: t.name, p: nm(t.parentId), s: t.startDate, e: t.endDate, ms: t.milestone, mode: t.taskMode, prog: t.progress, res: t.resource, aS: t.actualStart, aF: t.actualFinish, ct: t.constraintType, cd: t.constraintDate, sT: t.startText, preds: t.predecessors.map(l => [nm(l.id), l.type, l.lag]), base: t.baselines || null })) }; }""", xml)
    T = {t["n"]: t for t in back["tasks"]}
    check("read back: the same tasks in the same outline (Design, Build and Decide vendor inside the group)", [t["n"] for t in back["tasks"]] == names and T["Design"]["p"] == "Website & <relaunch>" and T["Go live"]["p"] is None)
    check("...dates, milestone, progress, actual dates, manual mode and the TBD task survive", (T["Build"]["s"], T["Build"]["e"]) == ("2026-09-14", "2026-09-25") and T["Go live"]["ms"] and T["Build"]["prog"] == 40 and T["Design"]["aS"] == "2026-09-07" and T["Design"]["aF"] == "2026-09-11" and T["Pinned manual"]["mode"] == "manual" and T["Decide vendor"]["sT"] == "TBD")
    check("...links keep their type and lag (FS+1, FF−2, SS+3), the constraint and its date, the resources", T["Build"]["preds"] == [["Design", "FS", 1]] and T["Go live"]["preds"] == [["Build", "FF", -2]] and T["Pinned manual"]["preds"] == [["Go live", "SS", 3]] and (T["Build"]["ct"], T["Build"]["cd"]) == ("SNET", "2026-09-14") and T["Design"]["res"] == "Anna, Ben" and T["Build"]["res"] == "Ben")
    check("...baselines (Build 14.–24.09.) and the plan's working week and holidays", T["Build"]["base"] == {"0": ["2026-09-14", "2026-09-24"]} and back["project"]["workDays"] == [1, 2, 3, 4, 6] and any(h["date"] == "2026-12-24" and h.get("to") == "2026-12-28" for h in back["project"]["holidays"]), (back["project"], back["warnings"]))
    check("...no import warnings", back["warnings"] == [], back["warnings"])

    # ---------------------------------------------------------------- the menu item
    pg.click("#dataMenuBtn")
    with pg.expect_download() as dl: pg.click("#mspdiExportItem")
    d = dl.value
    check("Data → Export MS Project XML downloads '<plan name>.xml' and says how to open it in MS Project", d.suggested_filename == "Cost plan.xml" and "MS Project" in pg.inner_text("#toastMsg") and "6 tasks" in pg.inner_text("#toastMsg"), (d.suggested_filename, pg.inner_text("#toastMsg")))
    path = d.path(); text = open(path, encoding="utf-8").read()
    check("...the file is UTF-8 with an XML declaration and parses", text.startswith('<?xml version="1.0" encoding="UTF-8"') and ET.fromstring(text.encode("utf-8")).tag == NS + "Project")
    ev("() => { tasks.length = 0; save(); render(); }"); pg.click("#dataMenuBtn"); pg.click("#mspdiExportItem"); pg.wait_for_timeout(200)
    check("an empty plan says there is nothing to export", "Nothing to export" in pg.inner_text("#toastMsg"))
    # a plan with no dates and odd characters still gives a valid file
    ev("""() => { tasks.length = 0; project.holidays = undefined; delete project.holidays; delete project.workDays; delete project.baselines; tasks.push({ id: 'z', name: 'Only \\u0001 a "quote" ✓ ünï', parentId: null, order: 0, startDate: '2026-09-07', endDate: '2026-09-07', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'manual', startText: 'TBD', endText: 'TBD', resource: '', actualStart: null, actualFinish: null }); normalizeData(); }""")
    x2 = ev("() => buildMspdi()"); r2 = ET.fromstring(x2)
    check("a plan whose only task has no dates (and control characters / quotes / accents in its name) still exports a valid file with the default working week", r2.find(f"{NS}Tasks/{NS}Task/{NS}Name").text == 'Only  a "quote" ✓ ünï' and len(list(r2.iter(NS + "WeekDay"))) == 7 and sum(1 for w in r2.iter(NS + "WeekDay") if w.find(NS + "DayWorking").text == "1") == 5)
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
