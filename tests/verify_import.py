from playwright.sync_api import sync_playwright
import os, json
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

SUMMARY = """(csv, opts) => { const res = tasksFromTable(parseDelimited(csv, opts && opts.delim), opts || {}); const nm = id => (res.tasks.find(t => t.id === id) || {}).name || null;
  return { warnings: res.warnings, info: res.info, tasks: res.tasks.map(t => ({ n: t.name, p: nm(t.parentId), s: t.startDate, e: t.endDate, ms: t.milestone, pr: t.progress, res: t.resource, mode: t.taskMode, sT: t.startText, eT: t.endText, as: t.actualStart, af: t.actualFinish, ct: t.constraintType, cd: t.constraintDate, preds: t.predecessors.map(q => [nm(q.id), q.type, q.lag]), o: t.order })) }; }"""

MSPDI = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Project xmlns="http://schemas.microsoft.com/project"><Name>Plan.xml</Name><Title>Website relaunch</Title><CreationDate>2026-08-01T09:00:00</CreationDate><MinutesPerDay>480</MinutesPerDay><CalendarUID>1</CalendarUID>
<Calendars><Calendar><UID>1</UID><Name>Standard</Name><IsBaseCalendar>1</IsBaseCalendar><WeekDays>
<WeekDay><DayType>1</DayType><DayWorking>0</DayWorking></WeekDay><WeekDay><DayType>2</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>3</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>4</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>5</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>6</DayType><DayWorking>1</DayWorking></WeekDay><WeekDay><DayType>7</DayType><DayWorking>0</DayWorking></WeekDay></WeekDays>
<Exceptions><Exception><EnteredByOccurrences>0</EnteredByOccurrences><TimePeriod><FromDate>2026-12-24T00:00:00</FromDate><ToDate>2027-01-01T23:59:00</ToDate></TimePeriod><Name>Shutdown</Name><Type>1</Type><DayWorking>0</DayWorking></Exception>
<Exception><TimePeriod><FromDate>2026-10-03T00:00:00</FromDate><ToDate>2026-10-03T23:59:00</ToDate></TimePeriod><Name>Unity Day</Name><DayWorking>0</DayWorking></Exception>
<Exception><TimePeriod><FromDate>2026-09-19T00:00:00</FromDate><ToDate>2026-09-19T23:59:00</ToDate></TimePeriod><Name>Working Saturday</Name><DayWorking>1</DayWorking></Exception></Exceptions></Calendar></Calendars>
<Tasks>
<Task><UID>0</UID><ID>0</ID><Name>Website relaunch</Name><OutlineLevel>0</OutlineLevel><Summary>1</Summary></Task>
<Task><UID>1</UID><ID>1</ID><Name>Design</Name><OutlineLevel>1</OutlineLevel><Summary>1</Summary><Start>2026-09-07T08:00:00</Start><Finish>2026-09-18T17:00:00</Finish></Task>
<Task><UID>2</UID><ID>2</ID><Name>Wireframes</Name><OutlineLevel>2</OutlineLevel><Start>2026-09-07T08:00:00</Start><Finish>2026-09-11T17:00:00</Finish><Duration>PT40H0M0S</Duration><PercentComplete>100</PercentComplete><ActualStart>2026-09-07T08:00:00</ActualStart><ActualFinish>2026-09-11T17:00:00</ActualFinish><Baseline><Number>0</Number><Start>2026-09-07T08:00:00</Start><Finish>2026-09-10T17:00:00</Finish></Baseline></Task>
<Task><UID>3</UID><ID>3</ID><Name>Visual design</Name><OutlineLevel>2</OutlineLevel><Start>2026-09-14T08:00:00</Start><Finish>2026-09-18T17:00:00</Finish><Duration>PT40H0M0S</Duration><PercentComplete>40</PercentComplete><ConstraintType>4</ConstraintType><ConstraintDate>2026-09-14T08:00:00</ConstraintDate><PredecessorLink><PredecessorUID>2</PredecessorUID><Type>1</Type><CrossProject>0</CrossProject><LinkLag>4800</LinkLag><LagFormat>7</LagFormat></PredecessorLink></Task>
<Task><UID>4</UID><ID>4</ID><Name>Build</Name><OutlineLevel>1</OutlineLevel><Start>2026-09-21T08:00:00</Start><Finish>2026-10-02T17:00:00</Finish><Duration>PT80H0M0S</Duration><Manual>1</Manual><PredecessorLink><PredecessorUID>3</PredecessorUID><Type>3</Type><LinkLag>-9600</LinkLag></PredecessorLink><PredecessorLink><PredecessorUID>2</PredecessorUID><Type>0</Type></PredecessorLink><PredecessorLink><PredecessorUID>99</PredecessorUID><Type>1</Type></PredecessorLink></Task>
<Task><UID>5</UID><ID>5</ID><Name>Go live</Name><OutlineLevel>1</OutlineLevel><Start>2026-10-05T08:00:00</Start><Finish>2026-10-05T08:00:00</Finish><Duration>PT0H0M0S</Duration><Milestone>1</Milestone><PredecessorLink><PredecessorUID>4</PredecessorUID><Type>2</Type></PredecessorLink></Task>
<Task><UID>6</UID><ID>6</ID><Name>Blank row</Name><IsNull>1</IsNull><OutlineLevel>1</OutlineLevel></Task>
</Tasks>
<Resources><Resource><UID>0</UID><Name>Unassigned</Name></Resource><Resource><UID>1</UID><Name>Anna</Name></Resource><Resource><UID>2</UID><Name>Ben</Name></Resource></Resources>
<Assignments><Assignment><UID>1</UID><TaskUID>3</TaskUID><ResourceUID>1</ResourceUID></Assignment><Assignment><UID>2</UID><TaskUID>3</TaskUID><ResourceUID>2</ResourceUID></Assignment><Assignment><UID>3</UID><TaskUID>4</TaskUID><ResourceUID>2</ResourceUID></Assignment></Assignments></Project>"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1500, "height": 900}, accept_downloads=True); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    ev = pg.evaluate
    ev("() => { historyCoalesceMs = 0; }")
    csv = lambda text, opts=None: ev(SUMMARY, [text, opts]) if False else ev("([t, o]) => (" + SUMMARY + ")(t, o)", [text, opts])
    T = lambda r, n: next(t for t in r["tasks"] if t["n"] == n)

    # ------------------------------------------------------------ the delimited-text reader
    check("delimiter detection: comma, semicolon and tab", ev("() => [detectDelimiter('a,b,c\\n1,2,3'), detectDelimiter('a;b;c\\n1;2;3'), detectDelimiter('a\\tb\\tc\\n1\\t2\\t3'), detectDelimiter('a;b,c;d\\n1;2,5;3')]") == [",", ";", "\t", ";"])
    rows = ev("() => parseDelimited('Name,Note\\n\"Smith, John\",\"He said \"\"hi\"\"\"\\n\"Two\\nlines\",x\\n\\n')")
    check("quoted cells: a comma inside, doubled quotes, a line break inside; empty lines dropped", rows == [["Name", "Note"], ["Smith, John", 'He said "hi"'], ["Two\nlines", "x"]], rows)
    check("a byte-order mark and CRLF line ends are handled", ev("() => parseDelimited('\\uFEFFa;b\\r\\n1;2\\r\\n')") == [["a", "b"], ["1", "2"]])

    # ------------------------------------------------------------ dates and durations
    d = ev("() => ['2026-09-07', '07.09.2026', '7.9.26', '07/09/2026', 'Mon 07.09.26', 'Mo, 07.09.2026', '7 Sep 2026', 'September 7, 2026', '7. Sept. 2026', '07.09.2026 08:00', '2026-09-07T08:00:00', 'Mon 09/13/26 8:00 AM', '31.02.2026', 'TBD', '', '13/25/2026'].map(s => parseTableDate(s))")
    check("dates as people write them (ISO, dd.mm.yyyy, 2-digit years, weekday names, month names, times of day); impossible ones and text give null", d == ["2026-09-07"] * 11 + ["2026-09-13", None, None, None, None], d)
    check("slash dates: detected day-first, month-first when the second number is above 12 (03/25/2026); explicit formats win", ev("() => [parseTableDate('03/04/2026'), parseTableDate('03/25/2026'), parseTableDate('25/03/2026'), parseTableDate('03/04/2026', 'mdy'), parseTableDate('03/04/2026', 'dmy'), parseTableDate('2026-03-04', 'ymd')]") == ["2026-04-03", "2026-03-25", "2026-03-25", "2026-03-04", "2026-04-03", "2026-03-04"])
    du = ev("() => ['5', '5 days', '5d', '5 Tage', '2w', '2 weeks', '16h', '1.5 days', '1,5 d', '0 days', '3d?', '2 mo', '480 min', 'TBD', ''].map(parseTableDuration)")
    check("durations in working days: plain, days, Tage, weeks, hours, minutes, months, estimated (?)", du == [5, 5, 5, 5, 10, 10, 2, 2, 2, 0, 3, 40, 1, None, None], du)
    pt = ev("() => ['3', '3FS', '3SS+2d', '4;5FF-1 day', '3EA+2 Tage', '3AA', '3EE-1', '3AE+1w', 'x', '3FS+50%'].map(s => parsePredText(s))")
    check("MS Project predecessor text: types (English and German), lags in days / weeks, several links, errors reported", pt[0]["links"] == [{"ref": "3", "type": "FS", "lag": 0}] and pt[2]["links"][0] == {"ref": "3", "type": "SS", "lag": 2} and [l["ref"] for l in pt[3]["links"]] == ["4", "5"] and pt[3]["links"][1]["lag"] == -1 and pt[4]["links"][0]["type"] == "FS" and pt[4]["links"][0]["lag"] == 2 and pt[5]["links"][0]["type"] == "SS" and pt[6]["links"][0]["type"] == "FF" and pt[7]["links"][0]["type"] == "SF" and pt[7]["links"][0]["lag"] == 5 and pt[8]["bad"] == ["x"] and pt[9]["bad"] == ["3FS+50%"], pt)

    # ------------------------------------------------------------ CSV into tasks
    en = csv("ID,Task Name,Start,Finish,Duration,% Complete,Predecessors,Resource Names,Outline Level\n1,Design,07.09.2026,18.09.2026,10 days,50%,,,1\n2,Wireframes,07.09.2026,11.09.2026,5 days,100%,,Anna,2\n3,Visual design,14.09.2026,18.09.2026,5 days,20%,2FS+1d,\"Anna, Ben\",2\n4,Build,21.09.2026,,10 days,0%,3,Ben,1\n5,Go live,05.10.2026,,0 days,0%,4,,1\n")
    check("an English MS Project-style CSV: 5 tasks, two levels, 3 links", len(en["tasks"]) == 5 and en["info"]["levels"] == 2 and en["info"]["links"] == 3 and en["info"]["header"], en["info"])
    check("...hierarchy: Wireframes and Visual design are inside Design; Build is top level", T(en, "Wireframes")["p"] == "Design" and T(en, "Visual design")["p"] == "Design" and T(en, "Build")["p"] is None and T(en, "Design")["p"] is None)
    check("...dates, % and resources are read (Visual design 14.-18.09., 20%, 'Anna, Ben')", T(en, "Visual design")["s"] == "2026-09-14" and T(en, "Visual design")["e"] == "2026-09-18" and T(en, "Visual design")["pr"] == 20 and T(en, "Visual design")["res"] == "Anna, Ben" and T(en, "Wireframes")["pr"] == 100)
    check("...links follow the ID column, with their type and lag: Visual design after Wireframes FS+1, Build after Visual design", T(en, "Visual design")["preds"] == [["Wireframes", "FS", 1]] and T(en, "Build")["preds"] == [["Visual design", "FS", 0]], T(en, "Visual design")["preds"])
    check("...a start and a duration give the finish in WORKING days (Build 21.09. + 10 days = 02.10.); 0 days makes a milestone", T(en, "Build")["e"] == "2026-10-02" and T(en, "Go live")["ms"] and T(en, "Go live")["s"] == "2026-10-05" and T(en, "Go live")["e"] == "2026-10-05", (T(en, "Build")["e"], T(en, "Go live")))
    de = csv("Vorgangsname;Anfang;Ende;Dauer;% Abgeschlossen;Vorgänger;Ressourcennamen;Gliederungsebene\nProjekt;Mo 07.09.26;Fr 25.09.26;15 Tage;0%;;;1\nPlanung;Mo 07.09.26;Fr 11.09.26;5 Tage;100%;;Anna;2\nUmsetzung;Mo 14.09.26;Fr 25.09.26;10 Tage;10%;2EA+2 Tage;Ben;2\n")
    check("a German export (semicolons, Vorgangsname / Anfang / Ende / Dauer, 'Mo 07.09.26', '5 Tage', '2EA+2 Tage')", len(de["tasks"]) == 3 and T(de, "Planung")["s"] == "2026-09-07" and T(de, "Planung")["e"] == "2026-09-11" and T(de, "Umsetzung")["preds"] == [["Planung", "FS", 2]] and T(de, "Planung")["p"] == "Projekt" and T(de, "Umsetzung")["pr"] == 10 and T(de, "Umsetzung")["res"] == "Ben", de)
    q = csv('Task Name,Start,Finish\n"Review, sign-off ""v2""",07.09.2026,08.09.2026\n')
    check("a quoted name with a comma and quotes stays one name", q["tasks"][0]["n"] == 'Review, sign-off "v2"', q["tasks"][0])
    ind = csv("Task Name,Start,Finish\nPhase 1,07.09.2026,18.09.2026\n  Step A,07.09.2026,11.09.2026\n  Step B,14.09.2026,18.09.2026\n    Detail,14.09.2026,15.09.2026\nPhase 2,21.09.2026,25.09.2026\n")
    check("no level column: the indentation of the names gives the outline (Step A/B in Phase 1, Detail in Step B)", T(ind, "Step A")["p"] == "Phase 1" and T(ind, "Detail")["p"] == "Step B" and T(ind, "Phase 2")["p"] is None, [(t["n"], t["p"]) for t in ind["tasks"]])
    wbs = csv("WBS,Task Name,Start,Finish\n1,Alpha,07.09.2026,11.09.2026\n1.1,Beta,07.09.2026,08.09.2026\n1.2,Gamma,09.09.2026,11.09.2026\n2,Delta,14.09.2026,15.09.2026\n")
    check("...or a WBS / outline number column (1, 1.1, 1.2, 2)", T(wbs, "Beta")["p"] == "Alpha" and T(wbs, "Gamma")["p"] == "Alpha" and T(wbs, "Delta")["p"] is None)
    tbd = csv("Task Name,Start,Finish,Duration\nDecide vendor,TBD,,\nPilot,14.09.2026,TBD,\nRollout,,,5 days\n")
    check("dates that are missing or text (TBD) become a Manually Scheduled task with the text kept; a known start alone is kept as the start", T(tbd, "Decide vendor")["mode"] == "manual" and T(tbd, "Decide vendor")["sT"] == "TBD" and T(tbd, "Pilot")["mode"] == "manual" and T(tbd, "Pilot")["s"] == "2026-09-14" and T(tbd, "Pilot")["eT"] == "TBD" and T(tbd, "Rollout")["mode"] == "manual", tbd["tasks"])
    check("a table without a header: one column is a list of names", [t["n"] for t in csv("Alpha\nBeta\nGamma\n")["tasks"]] == ["Alpha", "Beta", "Gamma"])
    hdrless = csv("Alpha,07.09.2026,11.09.2026\nBeta,14.09.2026,18.09.2026\n")
    check("...several columns without a header are read as Name, Start, Finish (a name that looks like a date is not taken for a header)", [t["n"] for t in hdrless["tasks"]] == ["Alpha", "Beta"] and hdrless["tasks"][1]["s"] == "2026-09-14", hdrless["tasks"])
    fmt = csv("Task Name,Start,Finish\nA,03/04/2026,03/06/2026\n", {"dateFormat": "mdy"})
    check("the date format can be set (03/04/2026 as month first = 4 March)", fmt["tasks"][0]["s"] == "2026-03-04" and fmt["tasks"][0]["e"] == "2026-03-06")
    bad = csv("ID,Task Name,Predecessors\n1,A,\n2,B,9\n3,C,1FS+50%\n4,D,4\n")
    check("links to tasks that don't exist, unreadable ones and links to itself are dropped with a note each", len(bad["warnings"]) == 2 and all(not t["preds"] for t in bad["tasks"]) and any("no task 9" in w for w in bad["warnings"]), bad["warnings"])
    cons = csv("Task Name,Start,Constraint Type,Constraint Date,Actual Start,Actual Finish\nA,07.09.2026,Start No Earlier Than,10.09.2026,,\nB,07.09.2026,,,08.09.2026,09.09.2026\n")
    check("constraint type/date and actual dates columns are read", T(cons, "A")["ct"] == "SNET" and T(cons, "A")["cd"] == "2026-09-10" and T(cons, "B")["as"] == "2026-09-08" and T(cons, "B")["af"] == "2026-09-09")
    pc = csv("Task Name,% Complete\nA,50%\nB,0.5\nC,75\nD,150%\nE,\n")
    check("percentages: '50%', 0.5 (a fraction), 75, over 100 capped, blank = 0", [t["pr"] for t in pc["tasks"]] == [50, 50, 75, 100, 0], pc["tasks"])
    ms = csv("Task Name,Start,Milestone\n◆ Kick-off,07.09.2026,\nSign,08.09.2026,Yes\nWork,09.09.2026,No\n")
    check("milestones: a ◆ in front of the name (our own export) or a Milestone column", T(ms, "Kick-off")["ms"] and T(ms, "Sign")["ms"] and not T(ms, "Work")["ms"], ms["tasks"])
    check("a table with no usable name column explains itself", "task names" in (ev("() => { try { tasksFromTable([['12', '13'], ['14', '15']], { defaultCols: ['start', 'end'] }); return 'no error'; } catch (e) { return e.message; } }")), ev("() => { try { tasksFromTable([['12', '13']], { defaultCols: ['start', 'end'] }); return 'no error'; } catch (e) { return e.message; } }"))

    # ------------------------------------------------------------ MS Project XML
    m = ev("(x) => { const r = parseMspdi(x); const nm = id => (r.tasks.find(t => t.id === id) || {}).name || null; return { project: r.project, warnings: r.warnings, info: r.info, tasks: r.tasks.map(t => ({ n: t.name, p: nm(t.parentId), s: t.startDate, e: t.endDate, ms: t.milestone, pr: t.progress, res: t.resource, mode: t.taskMode, as: t.actualStart, af: t.actualFinish, ct: t.constraintType, cd: t.constraintDate, base: t.baselines || null, sT: t.startText, preds: t.predecessors.map(q => [nm(q.id), q.type, q.lag]) })) }; }", MSPDI)
    check("MS Project XML: the project summary task and the empty row are left out; 5 tasks in two levels", [t["n"] for t in m["tasks"]] == ["Design", "Wireframes", "Visual design", "Build", "Go live"] and m["info"]["levels"] == 2 and m["project"]["name"] == "Website relaunch", m["info"])
    check("...the outline: Wireframes and Visual design are in Design", T(m, "Wireframes")["p"] == "Design" and T(m, "Visual design")["p"] == "Design" and T(m, "Build")["p"] is None)
    check("...dates come from Start/Finish; % complete, actual dates, milestone, constraint (Start No Earlier Than) are read", T(m, "Visual design")["s"] == "2026-09-14" and T(m, "Visual design")["e"] == "2026-09-18" and T(m, "Visual design")["pr"] == 40 and T(m, "Wireframes")["as"] == "2026-09-07" and T(m, "Wireframes")["af"] == "2026-09-11" and T(m, "Go live")["ms"] and T(m, "Visual design")["ct"] == "SNET" and T(m, "Visual design")["cd"] == "2026-09-14")
    check("...links: types (0 FF, 1 FS, 2 SF, 3 SS), lags from tenths of minutes at 480 min/day (4800 = +1 day, -9600 = -2 days), a link to a missing task dropped with a note", T(m, "Visual design")["preds"] == [["Wireframes", "FS", 1]] and T(m, "Build")["preds"] == [["Visual design", "SS", -2], ["Wireframes", "FF", 0]] and T(m, "Go live")["preds"] == [["Build", "SF", 0]] and any("UID 99" in w for w in m["warnings"]), (T(m, "Build")["preds"], m["warnings"]))
    check("...a manually scheduled task stays manual; resources come from the assignments (Unassigned is not a resource)", T(m, "Build")["mode"] == "manual" and T(m, "Visual design")["res"] == "Anna, Ben" and T(m, "Build")["res"] == "Ben" and T(m, "Wireframes")["res"] == "")
    check("...the working week (Mon-Fri), the non-working exceptions as holidays (a range and a single day; the working Saturday is not one), baseline 0 on a task", m["project"]["workDays"] == [1, 2, 3, 4, 5] and m["project"]["holidays"] == [{"date": "2026-12-24", "to": "2027-01-01", "name": "Shutdown"}, {"date": "2026-10-03", "name": "Unity Day"}] and T(m, "Wireframes")["base"] == {"0": ["2026-09-07", "2026-09-10"]} and m["info"]["baselines"] == 1, (m["project"], T(m, "Wireframes")["base"]))
    check("...a baseline on a group is ignored; the project keeps when it was set", T(m, "Design")["base"] is None and m["project"]["baselines"]["0"]["setAt"] == "2026-08-01", m["project"].get("baselines"))
    err = ev("() => { const r = []; for (const x of ['<a><b></a>', '<Other/>', 'hello']) { try { parseMspdi(x); r.push('no error'); } catch (e) { r.push(e.message); } } return r; }")
    check("broken XML and XML that is not an MS Project file give a clear message", "not valid XML" in err[0] and "not an MS Project" in err[1] and ("not valid XML" in err[2] or "not an MS Project" in err[2]), err)

    # ------------------------------------------------------------ the dialog: preview, append, replace
    ev("() => { tasks.length = 0; deletedTaskIds.length = 0; project.name = 'My Project'; delete project.workDays; delete project.holidays; delete project.baselines; save(); render(); resetHistory(); }")
    ev("() => { const a = newImportedTask('Existing A', null, 0), b = newImportedTask('Existing B', null, 1); tasks.push(a, b); save(); render(); resetHistory(); }")
    csvtext = "ID,Task Name,Start,Finish,Predecessors,Outline Level\n1,Group,07.09.2026,11.09.2026,,1\n2,Child 1,07.09.2026,08.09.2026,,2\n3,Child 2,09.09.2026,11.09.2026,2,2\n"
    pg.click("#dataMenuBtn"); check("the Data menu has 'Import MS Project XML / CSV…'", "MS Project" in pg.inner_text("#foreignImportItem"))
    pg.keyboard.press("Escape")
    pg.set_input_files("#foreignFileInput", files=[{"name": "plan.csv", "mimeType": "text/csv", "buffer": csvtext.encode("utf-8")}]); pg.wait_for_selector("#foreignImportModalBg.open"); pg.wait_for_timeout(200)
    sm = pg.inner_text("#foreignImportSummary")
    check("choosing a CSV opens the preview: 3 tasks, 1 group in 2 levels, 1 link, the first tasks listed", "3 tasks" in sm and "1 group in 2 levels" in sm and "1 link" in sm and "Child 1" in sm and "07.09.2026" in sm, sm)
    check("...CSV offers the date format choice, and (no calendar in it) no calendar checkbox", not ev("() => document.getElementById('foreignImportFmtField').classList.contains('hidden')") and ev("() => document.getElementById('foreignImportCalRow').classList.contains('hidden')"))
    pg.click("#foreignImportGo"); pg.wait_for_timeout(250)
    names = ev("() => childrenOf(null).map(t => t.name)")
    check("'Add' appends after the existing tasks and keeps the hierarchy: Existing A, Existing B, Group (with Child 1 and Child 2)", names == ["Existing A", "Existing B", "Group"] and ev("() => childrenOf(tasks.find(t => t.name === 'Group').id).map(t => t.name)") == ["Child 1", "Child 2"], names)
    check("...the link inside the import points at the imported task, and the imported top task is selected", ev("() => { const c2 = tasks.find(t => t.name === 'Child 2'), c1 = tasks.find(t => t.name === 'Child 1'); return c2.predecessors.length === 1 && c2.predecessors[0].id === c1.id; }") and ev("() => selectedTaskIds.size") == 1)
    check("...the toast says how many and that Ctrl+Z takes it back", "Imported 3 tasks" in pg.inner_text("#toastMsg") and "Ctrl+Z" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    check("Ctrl+Z undoes the whole import in one step", ev("() => tasks.map(t => t.name).sort()") == ["Existing A", "Existing B"], ev("() => tasks.map(t => t.name)"))
    # replace + calendar, from XML
    pg.set_input_files("#foreignFileInput", files=[{"name": "plan.xml", "mimeType": "text/xml", "buffer": MSPDI.encode("utf-8")}]); pg.wait_for_selector("#foreignImportModalBg.open"); pg.wait_for_timeout(200)
    sm = pg.inner_text("#foreignImportSummary"); warn = pg.inner_text("#foreignImportWarn")
    check("choosing MS Project XML: 5 tasks, groups, links, the working week, holidays and a baseline are listed; the unknown predecessor is a note; no date format choice", "5 tasks" in sm and "4 links" in sm and "working week Mon–Fri" in sm and "2 holidays" in sm and "1 baseline" in sm and "UID 99" in warn and ev("() => document.getElementById('foreignImportFmtField').classList.contains('hidden')"), (sm, warn))
    check("...the calendar checkbox is offered and ticked", ev("() => !document.getElementById('foreignImportCalRow').classList.contains('hidden') && document.getElementById('foreignImportCal').checked"))
    ev("() => { window.existingIds = tasks.map(t => t.id); }")
    pg.check("input[name=fiMode][value=replace]")
    with pg.expect_download() as dl:
        pg.click("#foreignImportGo")
    fname = dl.value.suggested_filename; pg.wait_for_timeout(250)
    check("'Replace' first downloads a backup of the plan", fname.startswith("milestone-backup-before-import"), fname)
    check("...then the plan holds exactly the imported tasks, the old ones are tombstoned so a synced file learns they are gone", ev("() => tasks.map(t => t.name).sort()") == ["Build", "Design", "Go live", "Visual design", "Wireframes"] and ev("() => existingIds.every(id => deletedTaskIds.some(d => d.id === id))"))
    check("...with the file's calendar: Mon-Fri, the holidays, baseline 0 (and it is the compared one)", ev("() => project.workDays === undefined && project.holidays.length === 2 && [...setBaselineSlots()].includes(0)"), ev("() => [project.workDays, project.holidays]"))
    check("...Auto tasks sit on working days and the finished task keeps its actual dates", ev("() => { const w = tasks.find(t => t.name === 'Wireframes'); return w.startDate === '2026-09-07' && w.actualFinish === '2026-09-11' && w.progress === 100; }"))
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    check("Ctrl+Z brings the previous tasks back", ev("() => tasks.map(t => t.name).sort()") == ["Existing A", "Existing B"], ev("() => tasks.map(t => t.name)"))

    # ------------------------------------------------------------ encodings and refusals
    latin = "Vorgangsname;Anfang;Ende;Vorgänger\nPlanung für Q3;07.09.2026;11.09.2026;\nÜbergabe;14.09.2026;14.09.2026;1\n".encode("cp1252")
    pg.set_input_files("#foreignFileInput", files=[{"name": "de.csv", "mimeType": "text/csv", "buffer": latin}]); pg.wait_for_selector("#foreignImportModalBg.open"); pg.wait_for_timeout(200)
    check("a CSV saved by German Excel in Windows-1252 is read correctly (umlauts intact)", "Planung für Q3" in pg.inner_text("#foreignImportSummary") and "Übergabe" in pg.inner_text("#foreignImportSummary"), pg.inner_text("#foreignImportSummary"))
    pg.select_option("#foreignImportFmt", "mdy"); pg.wait_for_timeout(150)
    check("changing the date format re-reads the file (07.09.2026 is not a month-first date: the dates become text)", "TBD" in pg.inner_text("#foreignImportSummary") or "without dates" in pg.inner_text("#foreignImportSummary") or "07.09.2026" in pg.inner_text("#foreignImportSummary"), pg.inner_text("#foreignImportSummary"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("Escape closes the import dialog without changing anything", not ev("() => document.getElementById('foreignImportModalBg').classList.contains('open')") and ev("() => tasks.length") == 2)
    pg.set_input_files("#foreignFileInput", files=[{"name": "plan.mpp", "mimeType": "application/octet-stream", "buffer": b"\xd0\xcf\x11\xe0"}]); pg.wait_for_timeout(200)
    check("a binary .mpp explains how to export XML instead", "Save As" in pg.inner_text("#toastMsg") and "XML" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    pg.set_input_files("#foreignFileInput", files=[{"name": "plan.xlsx", "mimeType": "application/vnd.ms-excel", "buffer": b"PK"}]); pg.wait_for_timeout(200)
    check("an Excel workbook points to copy-and-paste or CSV", "paste" in pg.inner_text("#toastMsg") or "CSV" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    pg.set_input_files("#foreignFileInput", files=[{"name": "empty.csv", "mimeType": "text/csv", "buffer": b"Task Name,Start\n"}]); pg.wait_for_timeout(200)
    check("a file without tasks says so", "No tasks" in pg.inner_text("#toastMsg"), pg.inner_text("#toastMsg"))
    check("no console errors", not errors, errors[:5])
    print("console errors/warnings:", errors[:5]); print(f"{sum(results)}/{len(results)} passed"); b.close()
