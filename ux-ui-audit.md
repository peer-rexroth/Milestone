# Milestone: UX/UI audit (consistency, design system, Apple HIG, documentation)

Audited 2026-11-01 against `/Users/peer/Documents/Dev/Milestone` at commit `12ac393` (working tree clean). Read-only: the only file written is this report; measuring scripts and screenshots live outside the project.

**Status (2026-11-01, later the same day): the four quick wins are built: M-01, M-02, M-03 and M-05** (test: `tests/verify_audit_wins.py`, 16 checks; the full suite passes, 129 / 129). One correction to M-05 found while building it: the 12 dialogs did not put focus on the ✕; they did not move focus at all (it stayed on whatever the page had, usually the body), because my first measurement ran with a toolbar button still focused. The fix is the same. M-23 (the four inline drawings) and the 23 text `×` close glyphs are also done (they use the registry's `sidebar`, `chevron-left`, `chevron-right`, `folder` and `xmark`). **Small fixes built later the same day:** M-06 (Import is an `alertdialog`; its button order Cancel · Merge · Replace stays, as CLAUDE.md records), M-08, M-09 (new tokens `--r-bar` 7 and `--r-mark` 2; the `--radius` alias is gone), M-12 (labels narrower than 26 px are left out, 18 px on the Day and Hours scales), M-13 (the bar title keeps 64 px), M-14 (the 14 long tooltips are shortened; and the "(⌘,)" hint named a shortcut that did not exist, so ⌘, / Ctrl+, now opens Plan settings and is in the Shortcuts sheet), M-15 (two `theme-color` metas, manifest `#f2f3f7`, the theme switch updates both) and M-22. Still open: M-04, M-07, M-10, M-11, M-16 to M-21 (decisions and documentation).

This replaces the 2026-10-30 report (F-01 … F-18, all built, decided or ignored at the owner's request; it is kept in git history, last at commit `8db430a`). Findings here are **M-xx**, root causes **RC-x**. I did not re-report any closed F-item; where one has partly come back it is marked in section 7.

Two things about the brief: Milestone has no `cleardesk.html` (its source of truth is `index.html`), and the brief's "Tasks / Notes / Prompts" modes are ClearDesk's. For Milestone I audited its own screens: Tasks (list), Gantt, Resource Sheet / Resource Plan, the sidebar, the status bar, the Task Form, and the dialogs. The dialog gap in the brief (14 px) differs from `DESIGN.md` / `DIALOG-SHELL.md` (16 px); Milestone's dialogs do not use a gap at all (they are header / body / footer bars, see M-18).

---

## 1. Summary

- **Target platform:** a local-first PWA (Chrome / Edge on macOS first) that imitates macOS. macOS HIG applied.
- **UI stack:** one file, `index.html` (15,086 lines: icon registry in `<head>`, CSS lines 201–2325, script from line 3491), no build step. The design system is a **copy of ClearDesk's** (`design-system/DESIGN.md` is ClearDesk's guide with one line changed; `tokens.css` differs from the app by 43 variables; `icons.json` has 118 of the 171 icons the app draws).
- **Verified:** code and browser. Static scans of the whole file (colour, size, weight, radius, spacing, cursor, transition, z-index, icon and tooltip inventories); then headless Chrome (Playwright, light and dark): computed styles of every visible element in Tasks, Gantt and Resource Sheet; contrast sampled from rendered pixels for every visible text run in the three views (selected and unselected) and in 9 dialogs; accessible names; hit areas by `elementFromPoint`; focus order and focus rings by real Tab presses; 19 dialogs opened and closed with Esc and a scrim click; reduced motion; sidebar thresholds at 1400 / 1101 / 1100 / 1099 / 800 / 700 px; platform strings rewritten for Windows. HIG pages fetched: Keyboards, Toolbars, Sheets, Accessibility, Icons, Context menus.
- **Overall assessment:** very consistent for a single hand-written file, and visibly tidier than at the last audit. No `transition: all`, only `--dur-fast` / `--dur-base` plus one `.12s`, no native `alert()` / `confirm()`, the arrow cursor on every control (79 buttons and rows measured in Gantt), Tab walks the whole page in order (unlike ClearDesk, nothing swallows it), one 3 px focus ring on every control tried, Reduce Motion handled, all 26 dialogs carry `role`, `aria-modal` and a label. Contrast passes everywhere except three places. The weak spots are (1) **link-style buttons are unreadable in dark dialogs**, (2) **the group chevrons in the task list are unnamed, tiny buttons**, (3) **eleven dialogs open without moving focus in**, and above all (4) **the design-system documents describe ClearDesk, not Milestone**: the Gantt, the Print / Chart for Slides dialogs, the task dialog and Milestone's own tokens have no written rules.
- **Top 5 issues**
  1. **M-01 (High):** `.btn-link` text uses `--accent`: 2.58 : 1 on the dark dialog surface (Chart for Slides "More Options", "Add Slide Names…"; 14 uses in all). Same class of bug as old F-08, fixed only for the Resource Sheet links.
  2. **M-02 (Medium):** the expand / collapse chevron of every group row is a focusable `<button>` with no name, no `aria-expanded` and a 14 × 14 px hit area.
  3. **M-03 (Medium):** the "On Schedule" status pill on a selected (blue) row is 4.07 : 1 in both themes.
  4. **M-05 (Medium):** 11 of 18 dialogs measured did not move focus into themselves when they opened (Print, Chart for Slides, Rules, Format, Fields, Reschedule, Level, Import, Help, Shortcuts, About); Print has a Title field it should have focused.
  5. **M-16 (Medium, documentation):** `DESIGN.md`, `tokens.css`, `icons.json` and `DIALOG-SHELL.md` describe ClearDesk; Milestone's 30 own tokens, 53 own icons, 8 dialog widths and the whole Gantt are undocumented.

---

## 2. Root causes

| ID | Root cause | Related findings | Recommended fix | Effort |
|---|---|---|---|---|
| RC-A | The design system was copied from ClearDesk and never adapted: it documents ClearDesk's modes, widths, tokens and exceptions | M-16, M-17, M-18, M-19, M-20, M-21 | Write a Milestone chapter (Gantt, bars, timeline, list, task dialog, Print / Chart for Slides, exports) and regenerate `tokens.css` / `icons.json` from the app; move Milestone's exceptions (now in CLAUDE.md) into a `DESIGN.md` §12 of its own | L |
| RC-B | One-off controls rendered without the shared accessibility helpers (name, state, hit-area growth) | M-02, M-11 | Give chevrons and Gantt handles the same treatment `.col-filter-btn` has (title → `aria-label`, `aria-expanded`, invisible `::before`) | S |
| RC-C | Link and pill colours are chosen per component from `--accent` instead of the text-blue token that is readable on both themes | M-01, M-03 | `.btn-link` and links use `--blue-text`; the selected-row pill gets its own darker fill; add both to the contrast test | S |
| RC-D | Dialog openers set focus by hand, each in its own way | M-05 | One focus rule driven by the `open` class (the way ClearDesk does, audit V-01): first text field, else primary button; never the ✕ | S |
| RC-E | The Gantt added its own radii, weights and cursors outside the scales | M-08, M-09, M-10, M-22 | Add `--r-bar` (7), a weight token or use 600, and write the grab / crosshair cursors into the guide | S |
| RC-F | A few strings written outside the tooltip rules | M-14 | Shorten the 10 long titles, run the glyph rewrite over `title` attributes | S |

---

## 3. Quick wins (High or Medium severity, Effort S)

| ID | Finding | Fix |
|---|---|---|
| M-01 | Dark-mode link text 2.58 : 1 (built) | `.btn-link { color: var(--blue-text) }` (index.html:884) and the same for `a[href]` |
| M-02 | Unnamed 14 px group chevrons (built) | add `title`, `aria-expanded` and a `::before` hit area (index.html:6904, 4881, CSS 1120) |
| M-03 | "On Schedule" pill 4.07 : 1 on the selected row (built) | darker pill fill or white text on the selected state |
| M-05 | Focus stays outside the dialog | focus the first field, else the primary button (built) |

---

## 4. Inventory

### 4.1 Component duplication, colour and surfaces (§2.1, §2.4, §5, §11)

| Variant | Source | Where / how often |
|---|---|---|
| Surfaces, text, borders, status, glass | token (154 variables; 139 shared names with ClearDesk, but Milestone also uses `--panel`, `--panel-2`, `--text-dim`, `--text-faint`, `--task-*`, `--status-*`, `--warning`, `--row-h`, `--head-h`, `--accent-hover`, `--primary`: none in `tokens.css`) | everywhere (M-16) |
| Colour literals in rules outside a token definition | **literal**: 6 lines (down from 25 at the last audit): 328 / 329 (dropdown border re-definitions), 576 (`rgba(255,255,255,.22)` dark sidebar toggle), 1270 (print `#fff`), 1492 (`#fff`, `rgba(0,0,0,.25)` on the Gantt resize handle), 2060 (`#000` mask gradient) | 2 allowed, 2 are token-style, 2 are literals (M-22) |
| Inline `style="…"` | 66 lines, **0 with a colour** | |
| JS hex strings | **literal** (needed because SVG, Excel, print and PNG leave the app): 30 (Gantt / print palette, the Chart for Slides Corporate palette `#1E2A78 #0069B1 #34A6DC #3BB8B8 #24778D`, orange `#F28011`, red `#E7001D`, status colours) | documented? no (M-21) |
| Native `alert` / `confirm` / `prompt` | none | 0 |
| Dialog shells | 26 `.modal-bg`: `.modal.insp` (inspector groups), `.modal.wide.settings-modal` ×4, `.modal.alert` ×2, `.modal.help-modal` ×2, one `about` | 26 |
| `!important` | 34 | |
| Light / dark | both themes measured; contrast: 0 failures except M-01, M-03 | |
| Glass | 7 lines with `backdrop-filter`; chrome only (sidebar, menus, dialogs, toast) | as documented |
| Reduced transparency / contrast / motion | all three media queries exist (345, 2323) | |

### 4.2 Typography (§2.2)

| Variant | Source | Count |
|---|---|---|
| `--fs-11 / 12 / 13 / 14 / 15 / 17 / 22` | token | 45 (11) · 129 (12) · 58 (13) · 32 (14) · 5 (15) · 4 (17) · 2 (22) |
| Literal px font sizes | none | 0 |
| Weights | 600 ×83, 500 ×31, 400 ×11, 700 ×9, **650 ×1** (`.gantt-slip`, line 1496) | M-08 |
| Computed sizes on screen | 11, 12, 13, 14, 15, 17 | none off-scale, none below 10 |
| Help / Shortcuts / About titles | 22 / 700 (documented as a window title) | |

### 4.3 Radius, spacing, depth (§2.3)

| Variant | Source | Count |
|---|---|---|
| `--r-xs / s / m / l / xl` | token | 38 / 37 / 23 / 4 / 3 |
| `999px`, `50%` | documented | 39, 33 |
| `7px` ×3 (Gantt bar 20 px high; `.ap-btn`), `3.5px` (milestone diamond), `2px` ×3 (group bar, handles), `12px` (`.gantt-card`: equals `--r-l`), `4px` (the focus ring on `.tick`: equals `--r-xs`), `var(--radius)` (retired alias, `.help-tip` line 2168) | **literal / off-scale** | 11 (M-09) |
| `22%` | documented (About icon) | 1 |
| Spacing values off the 2…40 scale | 3 (9), 5 (4), 7 (5), 15, 18 (7), 22 (3), 26 (2), 30 (5), 52 (2), 56 (4), 60 | 43 uses, none documented (M-19) |
| z-index | 0–6, 60, 61, 70, 80, 81, 90, 95, 100, 130, 200, 210, 390, 400, 500, **9998, 9999** (column-drag ghost) | 23 values; only 200 / 210 documented (M-19) |

### 4.4 Icons (§4)

| Variant | Source | Count |
|---|---|---|
| Masked `fa-NAME` icons from the registry | registry (171 names in the app) | 116 names used; every registry name referenced; 0 unknown |
| `icons.json` | 118 names, **53 fewer** than the app (`chart-gantt`, `route`, `file-excel`, `gear`, `moon`, `toggle-on`, …) | M-17 |
| Rendered boxes 10 / 11 / 13 / 14 px (= 12 / 14 / 16 / 18 drawn) | token sizes | no other size |
| Inline `<svg>` | 4 drawings outside the registry: a book / panel glyph (line 2333), a folder (2886), two chevron strokes (9920) | M-23 |
| Stroke weight measured | 1.33 at 16 px | on the scale |

### 4.5 Motion and interaction (§2.5, §3)

| Variant | Source | Count |
|---|---|---|
| Declared transitions | 17: `--dur-fast`, `--dur-base`, one literal `.12s` (line 2075), spin 1 s, jump flash 1.4 s | |
| Transitions on rows / bars | `.grid-row`, `.gantt-bar`: none (0 s) | pass |
| Computed durations in the three views | only the toast (0.2 s) | |
| Reduced motion | all durations → 1e-6 s | pass |
| `cursor` | default ×21 (every control), pointer ×1 (links), `grab` ×2 and `grabbing` ×2 (Gantt bars, row drag, column ghost), `ew-resize` ×2, `col-resize` ×4, `row-resize`, `text`, `crosshair` (link handle), `not-allowed` | M-10 |
| Focus ring | 3 px `--focus-ring` outline on `button.view-tab`, `.icon-btn`, `.sb-plan-main`, `.btn`, `.id-toggle`, `.col-filter-btn`, `.chevron`; the sidebar resizer shows none (`outline: none`, opacity change only) | consistent; resizer needs visual check |

### 4.6 Dialogs and controls (§5, §6)

| Item | Measured |
|---|---|
| Widths | 320 About, 340 alert, 400 Import, 440 Plan / Sync, 560 Task / Baseline / Reschedule / Level / Recurring / Edit Tasks, 680 Rules / Format / Calendar / Fields, 840 Help / Shortcuts, 1040 Print / Chart for Slides |
| Padding / gap | `.modal` padding 0 and no gap: the three bars (header, body, footer) carry their own |
| Titles | 17 / 600 start on sheets, 17 / 600 centred on the alert and Import, 22 / 700 on Help, Shortcuts and About |
| Radius | 16 px on all |
| Buttons | Cancel · primary (Task, Plan, Reschedule, Level, Rules, Calendar, Fields, Recurring, Edit Tasks); Done only (Baselines, Format); Cancel · Picture ▾ · Print (Print); Close · Save As… ▾ · Copy Picture (Chart for Slides); Cancel · Merge · Replace (Import: Replace is red) |
| Esc and scrim close | 18 of 19 measured; the folder-link dialog (`#fileSyncModalBg`) is a mandatory first-run gate and ignores both (M-20) |
| Focus on open | first field: Task, Plan, Baselines, Edit Tasks, Recurring, Calendar; dialog itself: confirm; **nothing (focus stays on the page): the other 11** (M-05) |
| Roles | `dialog` ×25, `alertdialog` ×1 (the confirmation). Import is `dialog` although it is an alert shell (M-06) |
| Hit areas | column filter 18 → 24 effective; Resource Sheet currency link 22 × 15 → 28 × 22; **group chevron 14 × 14 → 14** (M-02); Gantt link handle 11 × 11 (M-11) |
| Context menu (task row) | 14 top-level items, 5 groups, 3 one-level submenus (Task Mode, Task Type, Color), Delete last and red with "Del" |
| Toast | `role="status"`, `aria-live="polite"`, errors `role="alert"` and stay |
| Tooltips | 135 static `title`s: 10 over 75 characters (up to 192), none lowercase-initial; 1 shows ⌘ on Windows |

---

## 5. Findings

Type: **Inc** Inconsistency, **DS** Design-system deviation, **HIG** HIG deviation, **Doc** Doc gap. HIG pages (fetched): Keyboards <https://developer.apple.com/design/human-interface-guidelines/keyboards>, Toolbars <…/toolbars>, Sheets <…/sheets>, Accessibility <…/accessibility>, Icons <…/icons>, Context menus <…/context-menus>.

| ID | Category | Finding | Type | Locations | DESIGN.md | HIG | Prev. | Sev | Eff | RC | Recommendation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M-01 | Contrast | `.btn-link` text is `--accent` (`#2c62c9` on dark): 2.58 : 1 on the dark dialog surface (`More Options`, `Add Slide Names…` in Chart for Slides, measured); 12 px / 600, so 4.5 : 1 applies. Light is fine (≈ 5.8). 14 `.btn-link` uses. | HIG, DS | `index.html:884` (also `:895–896` where the filter-head link already uses `--blue-text`, `:1675`, `:1741`) | §2.1 ("text ≥ 4.5 : 1 on every surface in both themes"; the status-text blues exist for this) | Accessibility (4.5 : 1 for text up to 17 pt; check light and dark) | F-08 (same cause, only `.rst-cur` fixed) | **H** | S | RC-C | `color: var(--blue-text)`; extend `verify_design_rules.py` to sample one `.btn-link` in a dark dialog. |
| M-02 | Accessibility | The group chevron is a tabbable `<button class="chevron">` with no `title`, `aria-label` or `aria-expanded`, 14 × 14 px, and shows a focus ring when tabbed to. Group-header rows built by "Group by" use `aria-hidden` + `tabindex=-1` (4881), so the two disagree. | HIG, DS | `index.html:6904` (rows), `:4881` (group headers), `:1120` (CSS) | §9 (accessible name, expanded state), §5.1 / §9 (hit areas under 20 px get an invisible `::before`), §5.7 | Accessibility (macOS minimum control 20 × 20 pt; label custom controls) | none | M | S | RC-B | `title="Collapse"` / `"Expand"` (the observer copies it to `aria-label`), `aria-expanded`, and a `::before` that grows the target to 24 px. |
| M-03 | Contrast | On a selected (blue) row the "On Schedule" status pill is 4.07 : 1 (white-ish text on the translucent pill over the accent band), in light and dark. Other pills pass (4.67–5.8). | DS, HIG | `.status-pill.st-on-schedule` inside `.grid-row.selected` | §3 (pills keep ≥ 4.5 : 1 in the blue and grey states) | Accessibility | none | M | S | RC-C | Give the selected-row pill a stronger fill or solid white text. |
| M-04 | Context menu | The task row menu has 14 top-level items in **5 groups** (Edit / Mark / modes / Color; Add Task Below, Add Empty Line; Duplicate / Copy / Cut / Paste; Indent / Outdent; Delete) and shows "Del" as text. The guide allows ≤ 3 groups (ClearDesk wrote its four into §12 as exception U-07); Milestone has no such entry. The shortcut-hint rule itself is decided (old F-07). | DS, HIG, Doc | `showRowMenu` (the `rowMenu` element); row menu screenshot | §5.5 (≤ 3 groups, ⌫ not "Del") | Context menus ("about three groups", "small number of items") | F-07 (hints decided) | L | S | RC-A | Merge "Add Task Below / Add Empty Line" into the Duplicate group and Indent / Outdent into the first, or record the 5 groups as a decision; use ⌫ for the Delete hint. |
| M-05 | Dialogs | 11 of 18 dialogs measured open without moving focus into the dialog (activeElement stays on the body / the last page control): Reschedule, Level, Rules, Format, Fields, Print (which has a Title field), Chart for Slides, Import, Help, Shortcuts, About. A keyboard user has to Tab into the dialog; the Tab trap only engages on the first press. **Built:** `focusIntoDialog()` in the dialog observer (first text field or list, else the primary button, else the dialog itself; never a close button; the folder picker excluded). Task, Plan, Baselines, Edit Tasks, Recurring and Calendar focus their first field. | DS, HIG | each dialog's opener; `printModalBg`, `slideChartModalBg`, `rescheduleModalBg`, `levelModalBg`, … | §6.3 (first text field, else primary button, else first control; destructive: none), DIALOG-SHELL §3.4 | Sheets (Cancel / Done placement); Keyboards (full keyboard access) | none (ClearDesk V-01 did this centrally) | M | S | RC-D | Built: one focus rule on `open` (see the finding). |
| M-06 | Dialogs | Import (`.modal.alert.alert-wide`) is `role="dialog"`; the guide says `alertdialog` for Import. Its buttons read Cancel · Merge · Replace; the guide says Cancel · Replace · Merge. | DS | `#importModalBg` | §6.2 / §6.3 | Alerts (not re-fetched) | none | L | S | RC-A | Make it `alertdialog`; document the button order Milestone chose. |
| M-07 | Toolbar | The Gantt / Tasks bar now holds seven capsules (sidebar toggle, Add Task ▾, indent / outdent, undo / redo, Edit / Duplicate / Copy / Delete, view switch, table, calendar / settings). The recorded decision (old F-18) was "keep the labelled toolbar"; the labelled buttons are gone, so the stated reason no longer fits, but the group count is still well over three. | DS, HIG | `index.html:2397` (`#addTaskBtn`) and the toolbar markup around it | §19.4 (≤ 3 groups, one primary action, ⋯ overflow defined) | Toolbars ("aim for a maximum of three" groups; define the overflow menu) | F-18 | L | M | RC-A | Re-decide and rewrite the F-18 note; the HIG-friendly shape is leading (toggle, title, Add Task), centre (edit group, view switch), trailing (undo / redo, settings). |
| M-08 | Typography | `.gantt-slip` (the baseline-slip badge) uses weight 650; the system has four weights (400 / 500 / 600 / 700). | DS | `index.html:1496` | §2.2 | — | none | L | S | RC-E | `font-weight: 600`. |
| M-09 | Radius | Eleven radii off the ladder: Gantt bars `7px` (15 elements), `.ap-btn` `7px`, milestone `3.5px`, group bar / handles `2px`, `.gantt-card` `12px` (= `--r-l`), the `.tick` focus ring `4px` (= `--r-xs`, added in the last session), and `.help-tip` still reads the retired alias `var(--radius)`. | DS | `index.html:1461, 1472, 1485, 1505, 1510, 1891, 2168, 2276` | §2.3 ("one name per value; do not invent radii") | — | U-14 (ClearDesk; the alias was removed there) | L | S | RC-E | Use `--r-l` / `--r-xs`; add `--r-bar: 7px` (or `calc(var(--bar-h) * .35)`) for bars and write it down. |
| M-10 | Cursor | The Gantt uses `grab` / `grabbing` on bars and the row drag, `ew-resize` on bar handles, `crosshair` on the link handle, and a `grabbing` cursor on the whole page while a column moves. The guide says "no `grab` cursor". These are visible draggable objects, so the cursors are reasonable; they are just not written down. | Doc | `index.html:825, 1024, 1108, 1461, 1490, 1500, 1504` | §1.5 (list of allowed exceptions) | Pointing devices (not fetched) | none | L | S | RC-A | Add them to §1.5 as the Gantt exceptions. |
| M-11 | Hit areas | The Gantt link-drag handle is 11 × 11 px (hit area could not be grown by `elementFromPoint` probing), the bar resize edges are 7 px wide. These are precision drag handles, not click targets, but §9 asks for ≥ 20 × 20 measured. | HIG, DS | `.link-handle`, `.resize-handle` (`index.html:1490–1505`) | §9, §5.1 (invisible `::before`) | Accessibility (20 × 20 pt minimum on macOS) | none | L | S | RC-B | Grow the handle's hit area with a `::before` (visually unchanged). Needs visual check on hover. |
| M-12 | Gantt header | At Fit zoom the first timeline labels are clipped to "2.." and "Q.." at the left edge (tick 19 px wide, text wider). | Inc | `.gantt-tick` (`index.html:1430–1435`) | §5.4 ("truncate with an ellipsis and give the full text as a `title`") | — | none | L | S | — | Drop the first label if it cannot fit, or give the tick a `title`. |
| M-13 | Responsive | With the sidebar hidden (≤ 800 px) the plan title in the toolbar shrinks to 7–25 px (a single letter, "M") at some widths between 740 and 800 px in Tasks and Gantt, and is whole at others (700 px in Tasks); the value changes with the resize timing. | Inc | toolbar title (`#barTitle`, `.bar-title`) at ≤ 800 px | §19.4 (a bar steps down by its own width, nothing clipped) | Toolbars (titles under about 15 characters; leave room for controls) | none | L | S | — | Hide the title below the width where it cannot show 8 characters. Needs visual check. |
| M-14 | Tooltips | 10 `title`s are longer than 75 characters (up to 192: the predecessor syntax hint at line 6868, the Even Charts hint 159); the Plan-settings tooltip shows "(⌘,)" on Windows while the search tooltip is rewritten to "Ctrl+H". | DS | `index.html:2335, 2444, 2556, 2709, 2794, 2812, 3026, 6868, 6942, 8184` | §5.7 (75 characters at most), §15 | Keyboards (symbols localised) | none | L | S | RC-F | Shorten or move the long ones into the dialog text; rewrite glyphs in `title`s with the same helper as the Shortcuts sheet. |
| M-15 | PWA | `theme-color` is a single static `#f6f8fa` (manifest `theme_color` / `background_color` the same); the script sets `#f2f3f7` for light and `#171925` for dark after load. Three different light values, and no per-scheme metas. | DS | `index.html:15`, `:10776`, `manifest.json` | §14 (two `theme-color` metas, one per scheme, matching the chrome colour) | — | none | L | S | RC-A | Two metas (`#f2f3f7` light, `#171925` dark), manifest to match. |
| M-16 | Documentation | The design system describes ClearDesk: modes (Tasks / Notes / Prompts), board tile, detail panel, find bar, 300 px sidebar floating at 1100 px, `cleardesk.html`. Milestone's sidebar is 268 px and docks down to 800 px; the Gantt chart, bar colours and states, timeline header, link arrows, Today line, list columns, task dialog groups, Print and Chart for Slides dialogs, exports and the Slide Name / On Slide marks are not described anywhere in `design-system/`. `tokens.css` lacks 30 variables the app uses (`--panel`, `--panel-2`, `--text-dim`, `--text-faint`, `--task-*`, `--status-*`, `--warning`, `--row-h`, `--head-h`, `--accent-hover`, `--primary`, …) and defines 13 the app does not (`--sel-band`, `--sel-sub-tint`, `--find-*`, `--pill-plate`, …). The rules live in CLAUDE.md (≈ 1,400 lines). | Doc | `design-system/DESIGN.md`, `tokens.css` | whole guide; §2.6, §12, §19 | — | none (ClearDesk U-/V-series do not apply) | **M** | L | RC-A | See section 8. |
| M-17 | Documentation | `icons.json` has 118 icons; the app's registry has 171 (53 planner icons are missing: `chart-gantt`, `route`, `calendar-check`, `gear`, `moon`, `file-excel`, `toggle-on`, …). `DESIGN.md` says 118. | Doc | `design-system/icons.json`, `DESIGN.md:11` | file table, §4 | — | none | L | S | RC-A | Regenerate `icons.json` from the app and say "171". |
| M-18 | Documentation | `DIALOG-SHELL.md` describes a sheet as `.modal` with 24 px padding, 16 px gap, `.modal-head` and `.modal-actions`; Milestone's dialogs are three bars (header, body, footer) with hairlines, padding on the children, an ✕ in the header and eight widths (320, 340, 400, 440, 560, 680, 840, 1040). `DESIGN.md` §6.2 lists 380 / 360 / 420 / 860. Footers also carry things the shells do not (Picture ▾, Save As… ▾, Close). | Doc | `design-system/DIALOG-SHELL.md`, `DESIGN.md` §6.2 | §6.1–6.2 | Sheets | none | M | M | RC-A | Describe Milestone's shell and widths. |
| M-19 | Documentation | 43 padding / margin / gap values off the 2…40 scale (3, 5, 7, 15, 18, 22, 26, 30, 52, 56, 60) and 23 z-index values (up to 9999) are not documented, although the guide says reserved widths must be. | Doc | e.g. `index.html:630, 910, 1056, 1779, 1903, 2059`; z-index lines 827–828 (9998 / 9999), 1510 (390) | §2.3 | — | none | L | S | RC-A | Add a "measured values" and a z-index table. |
| M-20 | Documentation | The folder-link dialog ("Welcome to Milestone" / "Choose a folder to continue") cannot be closed with Esc or the scrim and has no Cancel; it is a deliberate gate, but §6.3 says Esc cancels and §12 does not list it. | Doc | `openFileSyncModal` (`index.html:13820`) | §6.3, §12 | Sheets ("always provide a way out"; not quoted exactly in the fetched page: "provide an alternative to the Done button") | none | L | S | RC-A | Write it into the exceptions table with its reason. |
| M-21 | Documentation | 30 hex strings live in the script (Gantt, print, PNG / SVG chart, Excel palettes, the Corporate brand palette). §2.1 allows literals only in token definitions, the note palette, print CSS and e-mail HTML. They have to be literal because the output leaves the app, but the guide does not say so. | Doc | `index.html` (Print, Chart for Slides, Excel export code) | §2.1 | — | none | L | S | RC-A | Add "export palettes" to the allowed list and name where they live. |
| M-22 | Colours | Two residual colour literals in rules: `#fff` and `rgba(0,0,0,.25)` on the Gantt resize handle, `rgba(255,255,255,.22)` on the dark sidebar toggle. | DS | `index.html:1492, 576` | §2.1 | — | F-10 (partly back) | L | S | RC-E | `var(--on-accent)` and a token for the shadow. |
| M-23 | Icons | Four inline `<svg>` drawings are outside the registry (a panel glyph, a folder, two chevron strokes). | DS | `index.html:2333, 2886, 9920` | §4.1, §11 step 3 | Icons | none | L | S | RC-A | Move them into the registry. |

No finding for: Tab order (the whole page is reachable, with a 3 px ring on every control tried), Reduce Motion, text sizes and weights (apart from M-08), hover / selection transitions (none on rows or bars), arrow cursor on controls, accessible names (apart from M-02), toast roles, dialog `aria-modal` and labels, one-level submenus, hide-not-dim in the row menu.

---

## 6. Documented exceptions

`DESIGN.md` §12 is ClearDesk's table. Milestone's own decisions live in CLAUDE.md; this is how they hold.

| Decision (Milestone) | Does the code still follow it? | Does the reason still hold? | Note |
|---|---|---|---|
| Keyboard shortcut hints stay in the row menu (old F-07) | Yes ("Del" on Delete) | Yes (no menu bar) | use ⌫ per §5.5 (M-04) |
| Find a task is `/`, ⌥⌘F on a Mac, Ctrl+H on Windows (F-14, F-15) | Yes (search tooltip rewritten per platform) | Yes | |
| Text size 90 / 100 / 115 / 130 %, 200 % ignored at the owner's request (F-16) | Yes | Yes | |
| Toolbar kept as is (F-18) | The toolbar changed (labelled buttons are now icon-only) | **No longer as written** | M-07 |
| No "Add Task" row in the Gantt view | Yes (Tasks view only) | Yes (list and chart scroll together) | |
| Mandatory folder dialog without Esc / Cancel | Yes | Yes | not written into the guide (M-20) |
| Selected row = solid accent with white text | Yes | Yes | pill fails 4.5 : 1 (M-03) |
| Filled red button in confirmations only | Yes (Delete, Replace) | Yes | |
| Sidebar icons neutral grey | Yes | Yes | |

---

## 7. Regressions

- **Old audit F-01 … F-18:** F-01 (Reduce Motion) holds: all durations collapse under `prefers-reduced-motion`. F-02 / F-03 / F-04 (title style): sheet titles are title style ("Rename Plan", "Level Resources"). F-09 (hit areas) holds (`.rst-cur` 28 × 22). F-12 holds (Baselines ends **Done**). F-14 holds. **Back in part:** F-08 (readable link blue): only `.rst-cur` / `.rst-days-link` were changed, so `.btn-link` fails in dark dialogs (M-01). F-10 (colour tokens): 6 literal lines left, 2 of them new in the Gantt (M-22).
- **`DESIGN.md` §10 mistakes:** 4 (a transition on selection / hover): none, rows and bars have `0s`. 11 (`cursor: pointer` on controls): one rule, for links. 14 (literals in inline styles): 66 inline styles, none with a colour. 2 (`width: auto` on a masked icon), 13 (unscoped variables), 17–19: not seen in the screens driven.

---

## 8. Proposed changes to `DESIGN.md` (paste-ready)

1. **Title and file table:** *"# Design system (ClearDesk and Milestone) … Source of truth: `index.html` of each app. Milestone-specific rules are in section 21."* (and replace `cleardesk.html` with `index.html` in the first paragraph).
2. **New §21 "Milestone: the planner" (outline to fill):** *list and Gantt share one row height (`--row-h` 32) and scroll together; bar colours come from `--task-*` and status from `--status-*`; a manual task's bar is dashed; the group bar is 8 px; link arrows, the Today line and the baseline slip badge (weight 600); handles: bar resize edges 7 px, link handle 11 px with a `::before` hit area; the sidebar is 268 px and floats at or below 800 px; the row menu has five groups; exports (Print, Chart for Slides, Excel, CSV, XML) use their own literal palettes.*
3. **§1.5 cursors:** add *"Gantt: `grab` / `grabbing` on a draggable bar or row, `ew-resize` on a bar edge, `crosshair` on the link handle."*
4. **§2.1:** add *"Links use `--blue-text` (readable on both themes); `--accent` is for fills."* and *"Exports (print, PNG / SVG, Excel) keep their own literal palettes."*
5. **§2.3 radius:** add `--r-bar` 7 for bars and *"nested radius = parent − inset"*; list the measured values (3, 5, 7, 15, 18, 22, 26, 30, 52, 56, 60 px) and a z-index ladder (0–6 content, 60–95 chrome, 100 dialogs in Milestone, 130 / 200 / 210 confirm, 390–500 floating cards and menus, 9998–9999 drag ghost).
6. **§6.2 widths:** *"320 About, 340 alert, 400 Import, 440 Plan / Sync, 560 inspector dialogs, 680 settings dialogs, 840 Help / Shortcuts, 1040 Print / Chart for Slides."* and describe the header / body / footer bars.
7. **§6.3:** *"A first-run gate (the folder dialog) has no Esc, scrim or Cancel; it closes only when a folder is chosen."* Also *"A dialog puts focus on its first field (else its primary button, else itself), never on its ✕."*
8. **§5.5:** *"The task row menu has up to five groups and three one-level submenus (decided)."* (or reduce, see M-04).
9. **§12:** replace the ClearDesk table by one table per app, or add a Milestone table with the nine rows in section 6.
10. **§14:** *"`theme-color` has two metas (`#f2f3f7` light, `#171925` dark); the manifest uses the light one."*
11. **`tokens.css`:** regenerate from `index.html` (Milestone's 154 variables) and list the per-pane hooks (`--sidebar-w`, `--task-cols`, `--grid-pane-width`, `--task-form-h`, `--rs-cols`, …).
12. **`icons.json`:** regenerate from the app (171 icons).

---

## 9. Porting checklist status (`DESIGN.md` §11)

| Step | Status | Note |
|---|---|---|
| 1 `tokens.css`, theme by `data-theme` | **Partial** | the app has its own 154 variables; `tokens.css` is ClearDesk's (M-16) |
| 2 System font, 7 sizes, 4 weights, `cursor: default` | **Done** | weight 650 once (M-08); Gantt cursors (M-10) |
| 3 Icon registry, one render function, four sizes | **Done** | 4 inline drawings (M-23); `icons.json` stale (M-17) |
| 4 Shell: sidebar, bars, gutter, glass on chrome | **Partial** | sidebar 268 / 800 px, not 300 / 1100 (M-16); toolbar title squeezed at 740–800 px (M-13) |
| 5 Components in order | **Done** | |
| 6 Selection with blue / grey zones, one focus ring | **Partial** | ring consistent; one pill fails on the blue row (M-03) |
| 7 Behaviours: undo toast, soft delete, hide-not-dim, Esc / Return, focus return | **Partial** | focus now moves in for every dialog (M-05, built) |
| 8 Two durations, reduced motion / transparency / contrast | **Done** | all three media queries present |
| 9 Contrast pass, hit-area pass, automated scan | **Done** | `tests/verify_design_rules.py` has the scan, contrast and hit areas; add the dark `.btn-link` and the pill (M-01, M-03) |
| 10 Exceptions written down | **Partial** | in CLAUDE.md, not in the guide (M-16, M-20) |

---

## 10. Needs visual check

- The sidebar resizer shows no ring on keyboard focus (`outline: none`, measured "none 3px"); confirm its `:focus-visible` hint is visible.
- The Gantt link handle hit area on hover (11 × 11 px) and the 7 px bar edges.
- The toolbar title width at 740–800 px: the measured width changed between runs (7 to 72 px), so the cause may be resize timing.
- Contrast of icons and focus rings (3 : 1): only text was sampled. The Chart for Slides and Print preview text in the dark theme is SVG on a white sheet and was excluded from the sample.
- Dialogs not opened: Export to Excel, CSV, foreign import, Replace, folder files, resource days, sync conflicts (they need data or file state; they use the same shell).
- Drag and drop feedback in the list and Gantt (the drop line, the ghost, the not-allowed pointer), the Task Form, the Resource Plan view, and the one-menu-at-a-time rule for the toolbar menus were not exercised.
- Print and the exported files were not rendered; the update banner, install and the service worker were not run on an installed copy.
- VoiceOver reading order.

---

## 11. Skipped categories

- **Menu bar:** a web app has none; its commands are in the toolbar, the Data / Help menus and the context menus.
- **Window behaviour (macOS):** a single page in a tab or PWA window.
- **Text overflow and localisation:** English only; dates and numbers follow the date format chosen in Plan settings.
- **Compact screens and mobile (§19.6):** HIG-only in the guide, not built.
