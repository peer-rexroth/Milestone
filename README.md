# Milestone

A local-first project planner — a task list and Gantt chart with a work-breakdown
hierarchy, task dependencies, auto-scheduling and resource planning — that runs entirely
in your browser and keeps your plans on your own device. No account, no server, no tracking.

- **Tasks and Gantt**: nested tasks whose groups roll up dates and progress, milestones,
  Finish-to-Start / Start-to-Start / Finish-to-Finish / Start-to-Finish links with lag,
  auto-scheduling (moving a task moves its dependents), constraints and a critical path
- **Resources**: a resource pool, assignments with units, a resource plan that shows
  who is overbooked, and levelling
- **Calendar and detail**: working days and holidays, hour-and-minute scheduling,
  baselines with variance, a status date and progress line
- **Plans**: several independent plans, each linked to its own `.json` file you choose
  (Chrome / Edge); the plan also lives in the browser, with automatic backups and an
  Undo history
- **Import and export**: MS Project XML, Excel and CSV in; Excel, CSV, MS Project XML, PDF/print and
  the plan file out
- Installable as a PWA, with offline support, a New Task shortcut and a new-version notice

## Running it

Clone the repo, then from inside it:

```
./start-milestone.command
```

This serves the folder on `http://127.0.0.1:8937` and opens it in Chrome or Edge
(Safari can't install this kind of PWA on macOS). `./stop-milestone.command` stops the
server again.

You can also open `index.html` directly in a browser (`file://`) for a quick look, but
installing the app, offline support and linking a plan file need it to be served over
`http://`.

Once it's open, click the install icon in the browser's address bar (or the browser's menu
→ "Install Milestone…") to install it as a standalone app.

## Publishing (Cloudflare Pages)

The app is plain static files, so any static host works. For Cloudflare: connect the repo,
leave the framework preset empty, set the build command to `./build-site.sh` and the output
directory to `dist` (`wrangler.jsonc` does the same for a `wrangler deploy`). `./build-site.sh`
copies only the app's own files into `dist/`. `_headers` makes the page, the service worker
and the manifest revalidate on every visit, so a new deploy shows up as the "new version"
notice. Data lives in each browser per address, so a new address starts empty: export your
plans on the old one and import them on the new one.

## No build step

Everything — HTML, CSS and JavaScript — lives in the single `index.html` file; there is no
bundler, package manager or dependency. `CLAUDE.md` describes how it is put together.

## Tests

Each `tests/verify_*.py` is a Playwright script that drives the real app in headless
Chromium; see [tests/README.md](tests/README.md).

```
python3 tests/run_all.py
```

## License

Copyright © 2026 Peer Rexroth. All rights reserved — see [LICENSE](LICENSE).
