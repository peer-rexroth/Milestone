from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html")
errors, results = [], []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{str(detail)[:300]}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 2600, "height": 700}); ctx.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.goto(URL); pg.wait_for_selector("#addTaskBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#addTaskBtn")
    pg.evaluate("() => { tasks.length = 0; addTask(); tasks[0].name = 'A'; tasks[0].resource = 'A very long resource list, Anna, Ben, Carla, David, Eva, Frank'; save(); render(); }"); pg.wait_for_timeout(200)
    check("every column except Task Name has a fixed px width in its definition (incl. Resource and every custom field)",
          pg.evaluate("() => Object.entries(TASK_COLS).filter(([id]) => id !== 'name').every(([, c]) => /^\\d+px$/.test(c.width)) && CUSTOM_FIELD_KINDS.every(k => /^\\d+px$/.test(k.width))") if pg.evaluate("() => typeof CUSTOM_FIELD_KINDS !== 'undefined'") else
          pg.evaluate("() => Object.entries(TASK_COLS).filter(([id]) => id !== 'name').every(([, c]) => /^\\d+px$/.test(c.width))"))
    def widths():
        return pg.evaluate("() => { const cols = getComputedStyle(document.getElementById('gridHeader')).gridTemplateColumns.split(' ').map(parseFloat); const order = [...document.querySelectorAll('#gridHeader .col-filter-btn')].map(x => x.dataset.col); const o = {}; order.forEach((c, i) => o[c] = cols[1 + i]); return o; }")
    w1 = widths()
    check("Resource shown: it is 140px, the Task Name column is the only one taking the spare width", pg.evaluate("() => colHidden.delete('resource') || true") and (pg.evaluate("() => { render(); return 1; }") or True) and widths()["resource"] == 140 and widths()["name"] > 400, widths())
    w2 = widths()
    check("the long resource text is cut with an ellipsis and its tooltip shows all of it", pg.evaluate("() => { const c = [...document.querySelectorAll('#gridRows .grid-row > div')].find(e => e.title && e.title.startsWith('A very long')); return !!c && c.scrollWidth > c.clientWidth && getComputedStyle(c).textOverflow === 'ellipsis'; }"))
    pg.evaluate("() => { for (const c of ['actualStart', 'remaining', 'status']) colHidden.delete(c); render(); }"); pg.wait_for_timeout(120)
    w3 = widths()
    check("showing more columns doesn't change the width of any other fixed column", all(w3[c] == w2[c] for c in w2 if c not in ('name',)), (w2, w3))
    pg.evaluate("() => { colHidden.add('resource'); render(); }"); pg.wait_for_timeout(120)
    w4 = widths()
    check("hiding Resource gives its width to Task Name only (nothing else moves)", all(w4[c] == w3[c] for c in w4 if c != 'name') and w4["name"] > w3["name"], (w3, w4))
    # ---- the WBS column holds eight levels (2.2.2.2.2.2.2.2)
    wb = pg.evaluate("""() => {
      tasks.length = 0; let parent = null;   // at every level a first sibling and then the one the outline continues in: the deepest is 2.2.2.2.2.2.2.2
      const mk = (id, parentId, order) => ({ id, name: id, parentId, order, startDate: '2026-09-07', endDate: '2026-09-08', progress: 0, milestone: false, color: null, predecessors: [], collapsed: false, updatedAt: 1, constraintType: 'ASAP', constraintDate: null, taskMode: 'auto', resource: '', actualStart: null, actualFinish: null });
      for (let d = 0; d < 8; d++) { tasks.push(mk('f' + d, parent, 0)); const n = mk('n' + d, parent, 1); tasks.push(n); parent = n.id; }
      normalizeData(); colHidden.delete('wbs'); render();
      const cell = [...document.querySelectorAll('#gridRows .grid-row')].map(r => [...r.children].find(c => /^\\d+(\\.\\d+)+$/.test(c.textContent.trim()))).filter(Boolean).find(c => c.textContent.trim() === '2.2.2.2.2.2.2.2');
      const head = [...document.querySelectorAll('#gridHeader > *')].find(h => h.textContent.trim().startsWith('WBS'));
      return { found: !!cell, text: cell && cell.textContent, fits: cell && cell.scrollWidth <= cell.clientWidth, width: head.getBoundingClientRect().width, headFits: head.scrollWidth <= head.clientWidth + 0.5 };
    }""")
    check("the WBS column is 104px wide", wb["width"] == 104, wb)
    check("the deepest code of an eight-level outline, 2.2.2.2.2.2.2.2, is shown in full (no ellipsis) in its cell", wb["found"] and wb["fits"], wb)
    check("...and the WBS header (label and filter funnel) still fits", wb["headFits"], wb)
    print("console errors/warnings:", errors); print(f"{sum(results)}/{len(results)} passed"); b.close()
