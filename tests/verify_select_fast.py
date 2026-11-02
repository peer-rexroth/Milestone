"""A click that only moves the selection does not re-render the list and the chart (it was ~50 ms a click): refreshSelection() moves the marks on the rows that are
there. This checks that the page it leaves (list, chart, arrows, status bar, toolbar, selection chip) is exactly what a full render() gives, for a click, a ctrl-click and a
shift-click in the Tasks and the Gantt view, and that a click is quick."""
from playwright.sync_api import sync_playwright
import os
URL = os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/index.html")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS  " if cond else "FAIL  ") + name + (f"   [{detail}]" if not cond and detail else ""))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1500, "height": 900}); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script("delete window.showOpenFilePicker; delete window.showSaveFilePicker; delete window.showDirectoryPicker")
    pg.goto(URL); pg.wait_for_selector("#undoBtn"); pg.evaluate("() => localStorage.clear()"); pg.reload(); pg.wait_for_selector("#undoBtn"); pg.wait_for_timeout(500)
    pg.evaluate("() => document.querySelectorAll('.modal-bg.open').forEach(m => m.classList.remove('open'))")
    pg.evaluate("""()=>{tasks=[];for(let g=0;g<5;g++){const gid='g'+g;tasks.push({id:gid,name:'Group '+g,parentId:null,order:g,startDate:'2027-01-04',endDate:'2027-06-30',progress:0,predecessors:[],taskMode:'auto',updatedAt:1});
      for(let i=0;i<6;i++)tasks.push({id:gid+'_'+i,name:'Task '+g+'.'+i,parentId:gid,order:i,startDate:'2027-01-04',endDate:'2027-02-'+(10+i),progress:0,predecessors:i?[{id:gid+'_'+(i-1),type:'FS',lag:0}]:[],taskMode:'auto',updatedAt:1})}
      normalizeData();save();render()}""")
    res=[]
    for view in ("tasks","gantt"):
        pg.evaluate(f"()=>setView('{view}')"); pg.wait_for_timeout(300)
        for step in ("click a row","click another","ctrl-click","shift-click","click first"):
            pg.evaluate("""s=>{const rows=[...document.querySelectorAll('.grid-row')];const ev=(i,o)=>rows[i].dispatchEvent(new MouseEvent('click',Object.assign({bubbles:true},o||{})));
              ({'click a row':()=>ev(3),'click another':()=>ev(8),'ctrl-click':()=>ev(5,{ctrlKey:true}),'shift-click':()=>ev(11,{shiftKey:true}),'click first':()=>ev(0)})[s]()}""",step)
            fast=pg.evaluate("()=>[document.getElementById('gridRows').innerHTML,document.getElementById('ganttRows').innerHTML,document.getElementById('ganttDeps').innerHTML,document.getElementById('statusbar').innerHTML,document.getElementById('subbar').innerHTML,document.getElementById('selChip').outerHTML]")
            pg.evaluate("()=>render()")
            full=pg.evaluate("()=>[document.getElementById('gridRows').innerHTML,document.getElementById('ganttRows').innerHTML,document.getElementById('ganttDeps').innerHTML,document.getElementById('statusbar').innerHTML,document.getElementById('subbar').innerHTML,document.getElementById('selChip').outerHTML]")
            names=["list","chart","arrows","statusbar","toolbar","chip"]
            diff=[n for n,a,c in zip(names,fast,full) if a!=c]
            check(f"{view}: {step} leaves the page a full render would", not diff, diff)
    ms = pg.evaluate("""()=>{const rows=[...document.querySelectorAll('.grid-row')];const r=[];for(let i=0;i<6;i++){const t=performance.now();rows[3+i].click();r.push(Math.round((performance.now()-t)*10)/10)}return r}""")
    check("a click takes under 30 ms (a full render took 45-65)", sorted(ms)[len(ms)//2] < 30, ms)

    # opening and closing a cell editor redraws one row; the page must equal a full render()
    snap = "() => [document.getElementById('gridRows').innerHTML, document.getElementById('ganttRows').innerHTML, document.getElementById('statusbar').innerHTML]"   # (not the toolbar: the Undo button's step count follows a timer of its own)
    for view in ("tasks", "gantt"):
        pg.evaluate(f"() => setView('{view}')"); pg.wait_for_timeout(300)
        for field in ("name", "start", "duration", "progress", "predecessors"):
            pg.evaluate("f => { const id = document.querySelectorAll('.grid-row')[4].dataset.id; startInlineEdit(id, f); }", field); pg.wait_for_timeout(80)
            fast = pg.evaluate(snap); pg.evaluate("() => render()"); full = pg.evaluate(snap)
            check(f"{view}: opening the {field} editor leaves the page a full render would", fast == full)
            pg.evaluate("() => { cancelInlineEdit(); }"); fast = pg.evaluate(snap); pg.evaluate("() => render()"); full = pg.evaluate(snap)
            check(f"{view}: cancelling the {field} editor leaves the page a full render would", fast == full)
    ms = pg.evaluate("""() => { const T = f => { const t = performance.now(); f(); return performance.now() - t; }; const r = [];
      for (let i = 0; i < 5; i++) { const id = document.querySelectorAll('.grid-row')[4].dataset.id; r.push(T(() => startInlineEdit(id, 'name'))); r.push(T(() => cancelInlineEdit())); } return r.map(x => Math.round(x * 10) / 10); }""")
    check("opening and cancelling an editor each take under 30 ms (a full render took 40-60)", sorted(ms)[len(ms) // 2] < 30, ms)
    check("no page errors", not errors, errors[:3])
    b.close()
print(f"{sum(results)}/{len(results)} passed"); raise SystemExit(0 if all(results) else 1)
