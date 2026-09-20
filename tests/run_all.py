#!/usr/bin/env python3
"""Runs the Milestone test suites (each is a Playwright script that drives the real app in headless Chromium).

    python3 tests/run_all.py                    # every suite + a short stress run (seeds 1-6)
    python3 tests/run_all.py verify_pull undo   # only suites whose name contains one of these words
    python3 tests/run_all.py --stress 100       # a long stress run (seeds 1-100); --stress 0 skips it
    python3 tests/run_all.py --jobs 4           # how many suites run at once (default 3)
    python3 tests/run_all.py --url http://127.0.0.1:8937/milestone.html

If nothing answers at the URL, a static server for the repository folder is started on port 8937 for the run.
Needs:  pip install playwright openpyxl  &&  python3 -m playwright install chromium
Exit status 0 = everything passed.
"""
import argparse, concurrent.futures as cf, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STRESS = "verify_stress"

def suites():
    return sorted(f[:-3] for f in os.listdir(HERE) if re.match(r"(verify|drive)_.*\.py$", f) and f[:-3] != STRESS)

def reachable(url):
    try:
        urllib.request.urlopen(url, timeout=2).read(1); return True
    except Exception:
        return False

def run(name, url, extra=(), timeout=1800):
    t0 = time.time()
    env = dict(os.environ, MILESTONE_URL=url)
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, name + ".py"), *extra], capture_output=True, text=True, env=env, timeout=timeout, cwd=HERE)
        out, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        out, code = "TIMEOUT", 1
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    summary = re.findall(r"^(\d+)/(\d+)(?: passed)?\s*$|(\d+) checks passed", out, flags=re.M)
    ok = code == 0 and not fails and "Traceback" not in out and out != "TIMEOUT" and (bool(summary) or name.startswith("drive_"))
    label = " ".join(f"{a}/{b}" if a else f"{c} checks" for a, b, c in summary[-1:]) or ("no summary" if not fails else "")
    return name, ok, label, fails, out, time.time() - t0

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="*", help="run only suites whose name contains one of these words")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--stress", type=int, default=6, help="number of stress seeds (0 = skip)")
    ap.add_argument("--url", default=os.environ.get("MILESTONE_URL", "http://127.0.0.1:8937/milestone.html"))
    a = ap.parse_args()
    server = None
    if not reachable(a.url):
        port = re.search(r":(\d+)/", a.url)
        server = subprocess.Popen([sys.executable, "-m", "http.server", port.group(1) if port else "8937", "--bind", "127.0.0.1"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if reachable(a.url): break
            time.sleep(0.1)
        else:
            print("could not start a server for", a.url); return 2
    names = [n for n in suites() if not a.only or any(w in n for w in a.only)]
    jobs = [(n, ()) for n in names]
    if a.stress and (not a.only or any(w in STRESS for w in a.only)): jobs.append((STRESS, tuple(str(i) for i in range(1, a.stress + 1))))
    if not jobs: print("nothing matches", a.only); return 2
    results = []
    try:
        with cf.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
            for r in ex.map(lambda j: run(j[0], a.url, j[1]), jobs):
                results.append(r); print(("ok    " if r[1] else "FAIL  ") + f"{r[0]:<26}{r[2]:<16}{r[5]:6.1f}s", flush=True)
    finally:
        if server: server.terminate()
    bad = [r for r in results if not r[1]]
    for name, _, _, fails, out, _ in bad:
        print(f"\n--- {name} ---")
        print("\n".join(fails[:8]) if fails else "\n".join(out.splitlines()[-15:]))
    print(f"\n{len(results) - len(bad)}/{len(results)} suites passed")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
