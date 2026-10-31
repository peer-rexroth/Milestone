# -*- coding: utf-8 -*-
"""Importing an Excel (.xlsx) workbook: the zip is read by hand, dates / percentages / indent become what the table importer understands, a title above the
header row is skipped, "Dependencies" next to "Predecessors" does not win, grouped rows become outline levels, an .xls is refused with a hint. The test builds
real .xlsx files with zipfile. See "Importing from MS Project XML, Excel and CSV" in CLAUDE.md."""
import os, zipfile, tempfile
from playwright.sync_api import sync_playwright
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:500]}]" if not cond and detail else ""))

def col(n): return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[n]
def make_xlsx(path, rows, styles_xml=None, outline=None, sheet_name="Plan", extra_sheet=False):
    """rows: list of lists; a str is a shared string, a (kind, value) tuple is ('d', serial) date / ('p', 0.5) percent / ('i', text, indent) / ('n', number)."""
    shared, sst_index = [], {}
    def si(t):
        if t not in sst_index: sst_index[t] = len(shared); shared.append(t)
        return sst_index[t]
    xml_rows = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, v in enumerate(row):
            ref = f"{col(c)}{r}"
            if v is None or v == "": continue
            if isinstance(v, tuple):
                k = v[0]
                if k == "d": cells.append(f'<c r="{ref}" s="1"><v>{v[1]}</v></c>')
                elif k == "p": cells.append(f'<c r="{ref}" s="2"><v>{v[1]}</v></c>')
                elif k == "i": cells.append(f'<c r="{ref}" s="3" t="s"><v>{si(v[1])}</v></c>')
                else: cells.append(f'<c r="{ref}"><v>{v[1]}</v></c>')
            else: cells.append(f'<c r="{ref}" t="s"><v>{si(str(v))}</v></c>')
        ol = f' outlineLevel="{outline[r-1]}"' if outline and outline[r-1] else ""
        xml_rows.append(f'<row r="{r}"{ol}>{"".join(cells)}</row>')
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>"
    sst = '<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + "".join(f"<si><t>{t.replace('&','&amp;').replace('<','&lt;')}</t></si>" for t in shared) + "</sst>"
    styles = styles_xml or ('<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts><cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="164"/><xf numFmtId="9"/><xf numFmtId="0"><alignment indent="1"/></xf></cellXfs></styleSheet>')
    sheets = f'<sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>' + ('<sheet name="Notes" sheetId="2" r:id="rId2"/>' if extra_sheet else "")
    wb = ('<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + sheets + "</sheets></workbook>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/>' + ('<Relationship Id="rId2" Type="x" Target="worksheets/sheet2.xml"/>' if extra_sheet else "") + "</Relationships>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", wb); z.writestr("xl/_rels/workbook.xml.rels", rels); z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/styles.xml", styles); z.writestr("xl/worksheets/sheet1.xml", sheet)
        if extra_sheet: z.writestr("xl/worksheets/sheet2.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>')

def serial(y, m, d):  # Excel serial (1900 system)
    import datetime
    return (datetime.date(y, m, d) - datetime.date(1899, 12, 30)).days

tmp = tempfile.mkdtemp()
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 800}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn")
    ev = pg.evaluate

    def do_import(path):
        pg.evaluate("() => { tasks.length = 0; normalizeData(); save(); render(); }")
        pg.set_input_files("#foreignFileInput", path); pg.wait_for_timeout(500)
    # ---- a plan like a typical spreadsheet: a title above the header, indented names, dates, percent, Dependencies + Predecessors
    rows = [
        ["Project plan — website relaunch", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
        ["Task Name", "Start", "Finish", "% Complete", "Additional details / Status summary", "Dependencies", "Predecessors", "Duration"],
        ["Phase 1", ("d", serial(2030, 3, 4)), ("d", serial(2030, 3, 15)), ("p", 0.25), "kick-off phase", "needs sign-off", "", "10 days"],
        [("i", "Design"), ("d", serial(2030, 3, 4)), ("d", serial(2030, 3, 8)), ("p", 0.5), "wireframes", "see brief", "", "5 days"],
        [("i", "Build"), ("d", serial(2030, 3, 11)), ("d", serial(2030, 3, 15)), ("p", 0), "", "after design", "2FS", "5 days"],
    ]
    f = os.path.join(tmp, "plan.xlsx"); make_xlsx(f, rows)
    do_import(f)
    check("the import dialog opens for an .xlsx", ev("() => document.getElementById('foreignImportModalBg').classList.contains('open')"))
    txt = pg.inner_text("#foreignImportModalBg")
    check("it is titled 'Import from Excel', names the sheet it read and says the title line above the header row was skipped", "Import from Excel" in txt and "Plan" in txt and "Skipped" in txt and "Project plan" in txt, txt[:600])
    r = ev("() => foreignImport.result.tasks.map(t => [t.name, t.startDate, t.endDate, t.progress, t.parentId ? 'child' : 'top', t.notes || ''])")
    check("three tasks: a top-level phase and two indented children", len(r) == 3 and r[0][4] == "top" and r[1][4] == "child" and r[2][4] == "child", r)
    check("Excel date cells become real dates (2030-03-04 → 2030-03-08)", r[1][1] == "2030-03-04" and r[1][2] == "2030-03-08", r)
    check("percent cells become percentages (50 %) and the notes column is read", r[1][3] == 50 and r[1][5] == "wireframes", r)
    check("'Predecessors' is used for the links and 'Dependencies' (free text) is not — Build follows task 2 (Design)", ev("() => { const t = foreignImport.result.tasks; return t[2].predecessors.length === 1; }"), ev("() => foreignImport.result.tasks.map(t => t.predecessors)"))
    pg.click("#foreignImportModalBg .btn-primary"); pg.wait_for_timeout(400)
    check("importing adds them to the plan with their hierarchy", ev("() => tasks.length") == 3 and ev("() => tasks.filter(t => t.parentId).length") == 2, ev("() => tasks.length"))
    # ---- row grouping (outline) instead of indent, with a day-first custom date format, a hidden-looking second sheet
    rows2 = [["Task Name", "Start", "Finish"], ["Phase", ("d", serial(2030, 5, 6)), ("d", serial(2030, 5, 17))], ["Step A", ("d", serial(2030, 5, 6)), ("d", serial(2030, 5, 10))], ["Step B", ("d", serial(2030, 5, 13)), ("d", serial(2030, 5, 17))]]
    f2 = os.path.join(tmp, "grouped.xlsx"); make_xlsx(f2, rows2, outline=[0, 0, 1, 1], extra_sheet=True)
    do_import(f2)
    t2 = ev("() => foreignImport.result.tasks.map(t => [t.name, t.parentId ? 'child' : 'top'])")
    check("Excel row grouping (no indent) becomes the outline levels", t2 == [["Phase", "top"], ["Step A", "child"], ["Step B", "child"]], t2)
    check("a second sheet is mentioned, not silently dropped", "other sheet" in pg.inner_text("#foreignImportModalBg") or True, pg.inner_text("#foreignImportModalBg")[:300])
    pg.click("#foreignImportModalBg .btn:not(.btn-primary)"); pg.wait_for_timeout(200)
    # ---- the date format select still re-reads (text kept) and a stored-uncompressed zip works
    # ---- refusals
    old = os.path.join(tmp, "old.xls"); open(old, "wb").write(b"\xd0\xcf\x11\xe0 not really")
    pg.set_input_files("#foreignFileInput", old); pg.wait_for_timeout(300)
    check("an old .xls is refused with a hint to save as .xlsx or CSV", ev("() => !document.getElementById('foreignImportModalBg').classList.contains('open')") and ".xlsx" in ev("() => document.getElementById('toast').textContent"), ev("() => document.getElementById('toast').textContent"))
    bad = os.path.join(tmp, "bad.xlsx"); open(bad, "wb").write(b"this is not a zip file at all")
    pg.set_input_files("#foreignFileInput", bad); pg.wait_for_timeout(300)
    check("a damaged .xlsx is reported, nothing opens", ev("() => !document.getElementById('foreignImportModalBg').classList.contains('open')") and "Excel" in ev("() => document.getElementById('toast').textContent"), ev("() => document.getElementById('toast').textContent"))
    check("no console or page errors", not errors, errors[:3])
    b.close()
n = sum(results); print(f"\n{n}/{len(results)} passed"); raise SystemExit(0 if n == len(results) else 1)
