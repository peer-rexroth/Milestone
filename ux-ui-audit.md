# Milestone – UX/UI audit (consistency and Apple HIG)

Audit date: 2026-10-30. **Read-only: no application, test or design-system file was changed.** The only file written is this report. Measuring scripts and screenshots live outside the project (scratchpad).

HIG base URL: `https://developer.apple.com/design/human-interface-guidelines/` (pages fetched in Markdown form, see "HIG pages used"). IDs: root causes **R-**, findings **F-**.

---

## Status (2026-10-30)

The five most important issues are **built** (tests: `tests/verify_audit_top5.py`, full suite: every suite passes except `verify_stress` seed 5, which fails intermittently on the code from before these changes as well, 3 of 5 runs): **F-01** Reduce Motion, **F-02 / F-03 / F-04** title-style wording, **F-05 / F-06** context menus for plan rows and Resource Sheet rows, **F-10** colour tokens, **F-14** ⌥⌘F on a Mac. F-12 (Baselines footer) is also done: Done instead of Close, and Set Baseline moved into the dialog. **F-16 is ignored at the owner's request.** Also done: F-17 (the Edit Tasks dialog marks the wrong field with a red border and bubble as well as the toast; Reschedule, Level and Plan have no validation of that kind; the Calendar sheet's day and break errors stay toast-only; test `tests/verify_bulk_field_errors.py`), F-08 and F-09 (the Resource Sheet's currency and Days off links use the readable link blue and a 28 x 23 hit area), F-13 (About and the backup list use the chosen date format) and the title-style button labels (Add Task, Add Resource, Scroll to Task). **F-11 was a misreading**: the Print footer's Picture group is a separate cluster on the leading edge (the Help-button pattern) and Cancel / Print are still the trailing pair; moving it into the options column put it below the fold, so it was left as it was. F-07 and F-15 are decided and written into CLAUDE.md ("Keyboard decisions"). F-18 is decided: keep the toolbar as it is (an explicit request, documented in CLAUDE.md). Nothing in the audit is open. Wording note: the older CLAUDE.md line "titles are sentence case" was replaced by the design guide's rule (sheet titles in title style).

---

## 1. Summary

**Target platform.** A web app / installable PWA written to look and behave like a macOS app (Chrome/Edge on macOS is the primary target; Safari is only supported without file linking). HIG guidance for **macOS** is applied. Because it runs in a browser, the native menu bar, multiple windows and system text-size (Dynamic Type) do not exist; those categories are skipped or treated as accepted deviations.

**UI stack.** One file, `milestone.html` (14,323 lines: CSS lines 196–2237, markup, then script), no build step, no dependencies. Icons: Font Awesome class names mapped to an inline outline-SVG registry (121 distinct icons, one family). Design tokens: `:root` custom properties in the same file (`--fs-*`, `--ico-*`, `--r-*`, `--dur-*`, `--hover`, `--pressed`, `--cap-*`, light and dark); the design system is documented in `design-system/DESIGN.md`, `DIALOG-SHELL.md`, `tokens.css`.

**Overall assessment.** The app is unusually consistent for a single hand-written file. All 19 dialogs I could open share one shell (16px radius, 17/600 title, Cancel then primary at the trailing end), every dialog closes with Esc and with a click outside, the confirmation alert follows the HIG (Cancel leading, destructive action trailing, no default button on a destructive question, filled red only for the destructive choice), type and icon sizes come from a scale, there is no `transition: all`, no native `alert()`/`confirm()`, every icon-only button I swept has a name, and light-mode text contrast has no failures in Tasks, Gantt or Resource Sheet. The remaining problems are small and cluster around three things: **wording and capitalization that drifted between menus, dialog titles and the sibling app ClearDesk**, **context menus built only for task rows**, and **a few accessibility baselines that were never added** (Reduce Motion above all).

**The 5 most important issues**

1. **F-01** No `prefers-reduced-motion` handling anywhere (0 matches in the file), while the app animates (spinner, jump flash, 13 transitions). HIG: respond to Reduce Motion.
2. **F-05 / F-06** Context menus exist only on task rows, group headers and column headers. Sidebar plan rows and Resource Sheet rows give the browser's own menu, although the plan commands (Rename, Duplicate, Unlink, Delete) exist elsewhere. HIG: support context menus consistently.
3. **F-02 / F-03** Menu and dialog wording is mixed: the row context menu mixes sentence style ("Edit task…", "Add task below", "Delete 3 tasks") with title style ("Mark Complete", "Add Empty Line"); sheet titles are sentence style ("Local backups") while the menu item that opens them is title style ("Local Backups…"), and ClearDesk's rule is title-style sheet titles.
4. **F-10** Colours still hard-coded in rules (`#fff`, `#bf8700`, rgba shadows: 25 lines), so these do not follow the theme tokens.
5. **F-14** Find and replace is **Ctrl+H** on every platform. HIG: avoid Control as a modifier; on a Mac Ctrl+H is also "delete backward" in text fields.

---

## 2. Root causes

| ID | Root cause | Related findings | Recommended fix | Effort |
|---|---|---|---|---|
| R-01 | No single list of menu / dialog labels; each was written where it was needed, so capitalization and wording drift | 5 (F-02, F-03, F-04, F-12, F-07) | One `LABELS` pass: title style for menu items and sheet titles, sentence style only for alert questions; copy the rule into `design-system/DESIGN.md` and add a test that scans `item(` / `<h2>` strings | S |
| R-02 | The context menu was designed for the task list and never generalised to the other surfaces | 3 (F-05, F-06, F-07) | Add menus for sidebar plan rows and Resource Sheet rows, built from the same `showRowMenu` item helpers; keep shortcut hints out of them | M |
| R-03 | Accessibility baselines (media queries, minimum sizes) were handled per component, not globally | 4 (F-01, F-08, F-09, F-16) | Add one `@media (prefers-reduced-motion: reduce)` block; re-measure the two small resource-sheet links; keep the text-size choice documented as an accepted deviation | S |
| R-04 | Token set is complete for surfaces and text but not for a few fixed colours (white on accent, amber warning, shadows) | 1 (F-10) | Use `--on-accent`, a `--warning` token with a defined value, and `--shadow*` tokens; add the "no colour literal outside token definitions" scan ClearDesk already has | S |
| R-05 | Dialog footers are built per dialog, so the two with extra buttons differ from the rule | 2 (F-11, F-12) | Put secondary actions (Copy / PNG / SVG) in the dialog body or a pull-down; make Baselines end *Cancel · Set Baseline* | S |
| R-06 | Two date formatters: the user's chosen format (`fmtDate`) and the browser locale (`fmtDateY`) | 1 (F-13) | Route `fmtDateY` through `dateFmtInfo()` | S |
| R-07 | Keyboard shortcuts chosen to avoid browser conflicts rather than to follow macOS | 2 (F-14, F-15) | Add `Mod+Alt+F` for Find and replace (keep Ctrl+H on Windows only); document why ⌘F stays with the browser | S |
| R-08 | Form errors are reported through the toast (92 error-toast call sites) instead of beside the field | 1 (F-17) | Needs a visual check first; if confirmed, show the message under the field in dialogs and keep the toast for page-level events | M |
| R-09 | Toolbar grew by requested additions (labelled selection buttons, chip, Find, Columns) | 1 (F-18) | Decision, not a defect: keep, or move Edit / Duplicate / Copy / Delete icon-only into one group | M |

---

## 3. Quick wins (High or Medium severity, effort S)

| ID | Finding | Fix |
|---|---|---|
| F-01 | No Reduce Motion handling | One media query that stops `fa-spin`, `jumpFlash` and the `--dur-*` transitions |
| F-02 | Row context menu mixes sentence and title style | Title-style the 7 labels in `showRowMenu` |
| F-03 | Sheet titles are sentence style, the menu items that open them are title style | Title-style the 8 sheet titles |

---

## 4. Inventory

Counts come from the stylesheet and markup of `milestone.html` and from computed styles measured in headless Chrome (1400×900; Tasks, Gantt and Resource Sheet views; light and dark).

**Component duplication and drift**

| Variant | Where | Count |
|---|---|---|
| Dialog shell (`.modal-bg` > `.modal`) | 26 `.modal-bg` ids (task, plan, excel, csv, import, foreign import, bulk, replace, print, backups, file sync, folder files, fields, resource days, calendar, rules, format, baseline, recur, reschedule, level, sync conflicts, help, shortcuts, about, confirm) | 26 |
| Confirmation | `openConfirmModal({…})` | 12 call sites |
| Toast | `showToast` | 161 calls, 92 of them errors |
| Native `alert` / `confirm` / `prompt` | none | 0 |
| Inline `style="…"` in markup / JS | | 68 |
| `!important` in CSS | | 52 |
| `transition: all` | none | 0 |

**Background colours and surfaces**

| Variant | Source | Notes |
|---|---|---|
| Dialog `rgba(255,255,255,.97)` light | token | all dialogs identical |
| Sidebar: translucent glass over a gradient wallpaper | tokens | body `background-color` is transparent, so tools that read it get the wrong base (see "Needs visual check") |
| Hard-coded colour literals outside token definitions | 14 lines with hex, 11 with rgba | listed in F-10 |

**Modals** (measured, 19 openable dialogs)

| Property | Result |
|---|---|
| Radius | 16px on all 19 |
| Title | 17px / 600 / start on 16; 22px / 700 on Help and Shortcuts (windows); centred 17/600 on the alert |
| Width | 340 (alert), 380 (About), 440, 560, 680, 840 (Help, Shortcuts), 1040 (Print) |
| Esc closes | 19 of 19 |
| Click outside closes | 19 of 19 (changed edits ask first, per `dirty()` checks) |
| Roles | `dialog` on 18, `alertdialog` on the confirmation; set by script at line 14249 |
| Footer | Cancel + primary on 11; Done only on Format; Close only on Backups; Close + primary on Baselines; five buttons on Print |

**Placement within modals**

| Pattern | Dialogs |
|---|---|
| *Cancel · Save* | Task, Calendar, Rules, Fields |
| *Cancel · Create / Apply / Export / Reschedule / Level resources* | Plan (new), Bulk, Excel, CSV, Recur, Reschedule, Level |
| *Done* | Format |
| *Close* | Backups |
| *Close · Set Baseline* | Baselines (F-12) |
| *Copy · PNG · SVG · Cancel · Print / Save as PDF…* | Print (F-11) |
| Destructive confirmation | *Cancel · Delete plan* (filled red, focus on the dialog, no default button) |

**Context menus**

| Surface | Menu |
|---|---|
| Task row (list and Gantt rows) | yes (`showRowMenu`, 11865) |
| Group header (Group by) | yes (`showGroupHeaderMenu`, 11889) |
| Column header (Tasks, Resource Sheet) | yes (column width menu) |
| Sidebar plan row | no |
| Resource Sheet row | no |
| Toolbar, status bar | no |

**Typography** (computed over visible text)

| Size / weight | Use | Notes |
|---|---|---|
| 12/400, 12/600, 12/500 | grid, labels, sidebar | most used |
| 11/600, 11/500, 11/400 | counts, captions | above the HIG macOS minimum of 10 pt |
| 13/500, 14/500, 14/600, 15/400 | toolbar, buttons | |
| 17/600 | dialog titles, toolbar title | |
| 22 | Help / Shortcuts title | one use |
| Weights in CSS | 600 ×81, 500 ×30, 400 ×12, 700 ×9 | four weights only |
| Font sizes written as literal px in CSS | 0 | all through `--fs-*` / `--ico-*` |
| Uppercase transform | 9 rules | section captions |

**Icons**

| Item | Result |
|---|---|
| Source | one inline-SVG registry behind Font Awesome class names, 121 icons, outline style |
| Drawn sizes | box 10 / 11 / 13 / 14px (draws 12 / 14 / 16 / 18 through the 1.26× mask) |
| Mixed libraries | none |

**Hover and interaction states**

| Mechanism | Rules using it |
|---|---|
| `var(--cap-hover)` | 13 |
| `var(--pressed)` | 12 |
| `var(--hover)` | 11 |
| `var(--bg-3)`, `brightness`, opacity | 1 each |
| `:hover` rules in total | 114 |
| Cursor on buttons and selects | `default` (the arrow, as on macOS) on every button and select measured in the three views; the hand only on links |
| `:focus-visible` rules | 20 |
| Transitions on visible elements in the three views | none (hover is instant) |
| Declared transition durations | `var(--dur-fast)` ×11, `var(--dur-base)` ×2, `.12s` literal ×2, `1s` spin, `1.4s` jump flash |

**Spacing and layout, shapes and depth**

| Radius | Count |
|---|---|
| `var(--r-s)` 39, `var(--r-xs)` 37, `999px` 33, `50%` 26, `var(--r-m)` 22, `var(--r-l)` 4, `var(--r-xl)` 3 | tokens |
| Literal `5px`, `4px`, `7px`, `var(--radius)` (old alias) | 4 one-offs |

**Feedback and notifications**

| Type | Behaviour |
|---|---|
| Toast (`#toast`) | status role; errors stay until dismissed (✕), success 2.6 s, Undo 6 s, with action 14 s; held while hovered or focused |
| Alert / confirmation | 12 sites |
| Banner / inline | the sync-conflict and "Linked" chips; date errors as a bubble (`.dt-err-bubble`, 1992) |

**Empty, loading and error states**

| State | Result |
|---|---|
| Empty | icon + title + one line ("No Tasks / Choose Add Task to start planning.", 6659); 11 references |
| Loading | one spinner (`fa-spin`) for the file check; nothing else waits long |
| Error | toast (92 sites) |

**Keyboard**: shortcuts live in one table (`SHORTCUTS`, 13851 ff.) shown in a Shortcuts dialog; modifier is `Mod` (⌘ or Ctrl) except Ctrl+H.

**Wording** (menu labels extracted): 33 title style, 5 sentence style ("Add resource", "Add task", "Link folder", "Over-allocated only", "Scroll to task"), 14 single words; plus template-literal labels in `showRowMenu` ("Edit task…", "Edit N tasks…", "Add task below", "Add sub-task", "Delete N tasks") and the group menu ("Expand this group", "Collapse this group").

---

## 5. Findings

Type: **I** = Inconsistency, **H** = HIG deviation, **B** = both. HIG URLs are under `https://developer.apple.com/design/human-interface-guidelines/`.

| ID | Category | Finding | Type | Locations | HIG reference | Severity | Effort | Root cause | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | Motion / Accessibility | No reduced-motion handling. `prefers-reduced-motion` appears nowhere in the file (`prefers-reduced-transparency` and `prefers-contrast` appear once each). The app has `fa-spin` (526), `jumpFlash` (1256) and 13 transitions. ClearDesk collapses all durations under Reduce Motion. | H | milestone.html:526, 1256, whole stylesheet | `accessibility` ("When Reduce Motion is active, … reduce automatic and repetitive animations") | Medium | S | R-03 | Add one `@media (prefers-reduced-motion: reduce)` block: stop the spinner and jump flash, set transition durations to 0 |
| F-02 | Wording | The row context menu mixes styles: sentence style "Edit task…", "Edit N tasks…", "Add task", "Add task below", "Add sub-task", "Delete N tasks" next to title style "Mark Complete", "Add Empty Line", "Change Recurrence…", "Task Mode", "Duplicate". | B | milestone.html:11869, 11880, 11885 (Delete) | `menus` ("use title-style capitalization") | Medium | S | R-01 | "Edit Task…", "Edit 3 Tasks…", "Add Task", "Add Task Below", "Add Sub-task", "Delete 3 Tasks" |
| F-03 | Wording | Sheet titles are sentence style ("Local backups", "Level resources", "Recurring task", "Reschedule remaining work", "New plan", "Export to Excel", "Plan settings", "Print or save as PDF") while the menu items that open them are title style ("Local Backups…", "Level Resources…", "Recurring Task…", "Reschedule Remaining Work…", "New Plan…"). ClearDesk's own rule is title-style sheet titles, alert titles are questions. | B | milestone.html:2704, 3010 and the other `.modal-header h2` lines; menu items at 2275 ff. | `alerts` (fragment titles take title-style capitalization), `menus` | Medium | S | R-01 | Title-style every sheet title; leave the alert titles ("Discard your changes?", "Unlink file") as sentences |
| F-04 | Wording | Group-header menu: "Expand this group" / "Collapse this group" are sentence style next to "Collapse All Groups", "Clear Grouping". | I | milestone.html:11892 | `menus` | Low | S | R-01 | "Expand Group" / "Collapse Group" |
| F-05 | Context menus | The sidebar plan rows have no context menu (only 3 `contextmenu` listeners exist: column headers ×2, task rows). Rename / Duplicate / Unlink / Delete exist only in the plan menu. ClearDesk gives every sidebar row a menu. | B | milestone.html:2253 (`#sbPlans`), 586 ff. (`.sb-plan-row`), 6555, 8009, 14073 | `context-menus` ("Support context menus consistently throughout your app") | Medium | M | R-02 | Right-click on a plan row: Switch To, Rename Plan…, Duplicate Plan…, Unlink File…, Delete Plan… (same actions as the plan menu) |
| F-06 | Context menus | Resource Sheet rows (and the Resource Plan rows) have no context menu, although Tasks rows have one and the sheet has Add / Remove commands. | B | milestone.html:8009 (only the header listens) | `context-menus` | Medium | M | R-02 | Row menu: Add Resource, Remove, Days Off… |
| F-07 | Context menus | The task row menu shows keyboard hints (⌘C, ⌘X, ⌘V). The HIG puts them in the main menus. (There is no menu bar in a web app, so the hint also helps discovery; this is a judgement call.) | H | milestone.html:11885 | `context-menus` ("Show keyboard shortcuts in your app's main menus, not in context menus") | Low | S | R-02 | Keep as is (documented), or drop the hints; decide once and write it in `DESIGN.md` |
| F-08 | Contrast | In dark mode the two resource-sheet links (`.rst-cur` "(€)" and `.rst-days-link` "Days off") estimate at 2.85:1 against a 4.5:1 minimum. Estimated with an assumed dark base colour; the glass backgrounds make an exact figure impossible from code. | H | milestone.html:1482, 1521 | `accessibility` (4.5:1 up to 17 pt) | Low | S | R-03 | **Needs visual check**, then use `--blue-text` (the dark-mode text blue) instead of `--accent` for link text |
| F-09 | Hit targets | `.rst-cur` measures 22×15 px (below the macOS minimum 20×20); the sidebar search input measures 186×17 (its wrapper is larger). `.col-filter-btn` is 18×18 but has an invisible `::before` that makes the target 26px (lines 819–824), so it is fine. | H | milestone.html:1482 (`.rst-cur`), 2246 (`#searchInput`) | `accessibility` (macOS minimum control size 20×20 pt) | Low | S | R-03 | Give `.rst-cur` the same invisible `::before` growth as the filter button |
| F-10 | Colours | Colour literals outside token definitions: `color:#fff` at 1270, 1456, 1992, 2173–2181 (should be `--on-accent`), `#bf8700` at 921, 1307, 1841 (a `--warning` fallback and two warning boxes), and rgba shadows at 554, 555, 674, 1031, 1040, 1207, 1410. ClearDesk requires tokens. | I | milestone.html:921, 1270, 1307, 1456, 1841, 1992, 2173–2181 | `accessibility` ("Prefer system-defined colors") | Low | S | R-04 | Replace with the tokens; add the literal-colour scan to the tests |
| F-11 | Placement in modals | The Print dialog footer is *Copy · PNG · SVG · Cancel · Print / Save as PDF…*: three secondary actions sit before Cancel, so Cancel is not the leading button. Every other dialog is *Cancel · primary*. | B | milestone.html:2697 | `alerts` / `sheets` (Cancel leading, default trailing) | Low | S | R-05 | Move Copy / PNG / SVG into the dialog body or a "Save Picture" pull-down; footer becomes *Cancel · Print…* |
| F-12 | Placement in modals | Baselines ends *Close · Set Baseline*; the neutral button is "Close" where every other two-button dialog says "Cancel". (Compare / Clear apply immediately inside it, which is why it says Close; the mix is what is inconsistent.) | I | milestone.html:2945 | `sheets` (Cancel dismisses without saving; Done after completing) | Low | S | R-05 | Either *Cancel · Set Baseline* with Compare moved out, or *Done* only, as Format and Backups do |
| F-13 | Localization | `fmtDateY` formats with `toLocaleDateString(undefined, …)` and ignores the date format the person chose, so the About line and each backup row show a different date format from the grid. | I | milestone.html:3920 (definition), 12991, 13929 (uses) | – (internal) | Low | S | R-06 | Build it from `dateFmtInfo()` like `fmtDate` |
| F-14 | Keyboard | Find and replace is **Ctrl+H** on every platform. HIG: avoid Control as a modifier; on a Mac Ctrl+H is "delete backward" in text fields. | H | milestone.html:11301 (comment), 13851 ff. (`SHORTCUTS` row) | `keyboards` ("Avoid using the Control key as a modifier") | Medium | S | R-07 | On a Mac use ⌥⌘F (the HIG lists Option-Command-F for the search field, the nearest standard slot), keep Ctrl+H only on Windows; show the right one in the sheet |
| F-15 | Keyboard | "Find a task" is `/` (the ⌘K shortcut was removed), not ⌘F (the standard). ⌘F stays with the browser's page find, which is a sensible choice in a web app. | H | `SHORTCUTS` 'Anywhere' group | `keyboards` (Command-F opens Find) | Low | S | R-07 | Keep, and say so in `DESIGN.md` so it is a decision, not a gap |
| F-16 | Typography / Accessibility | Text size offers 90 / 100 / 115 / 130 % (`uiScale`). The HIG asks for at least 200 %. The page is zoomable with the browser, and ClearDesk records the same limit as accepted. | H | milestone.html:3586, 10419 | `accessibility` ("enlarge text by at least 200 percent") | Low | M | R-03 | Accepted deviation; keep it listed |
| F-17 | Forms and validation | 92 of 161 toast calls are errors. Whether a bad value in a dialog (for example an end before a start, an empty plan name) is shown beside the field or only as a toast over the dialog could not be confirmed from code. Dates do get an inline bubble (`.dt-err-bubble`). | I | milestone.html:1992, 10358 | `alerts` ("avoid using an alert merely to provide information") | Medium | M | R-08 | **Needs visual check** in the Reschedule, Level, Recurring and Bulk dialogs; keep errors next to the field |
| F-18 | Toolbar | The Tasks toolbar carries text-labelled buttons next to icon buttons, more than three groups (Undo/Redo, Add Task split button, Indent/Outdent, selection chip with four labelled buttons, Find, Columns). The design was an explicit request, documented in CLAUDE.md. | H | milestone.html:2206, 2306; CLAUDE.md "Toolbar" section | `toolbars` ("aim for a maximum of three" groups; "prefer symbols"; "keep actions with text labels separate") | Low | M | R-09 | **Decided: keep** (owner's choice) |

---

## 6. Proposed consistency rules

| Category | Rule |
|---|---|
| Components | A new dialog uses `.modal-bg > .modal` with `.modal-header` and `.modal-footer`; a question uses `openConfirmModal`; no new footer layouts |
| Colours | No colour literal outside a token definition; text on an accent fill is `--on-accent` |
| Modals | Sheets: title-style title, ✕, Cancel then primary; "Done" only when changes apply as you type; Esc and a click outside close (asking first when changed) |
| Modal placement | Cancel leading, the default action trailing; extra actions go in the body or a pull-down, never before Cancel |
| Context menus | Every row-like object (task, plan, resource) has one; unavailable items are hidden; groups: change, add, copy, structure, delete last; no more than three groups; no shortcut hints |
| Placement of controls | Primary action trailing; icon-only buttons have a `title`, copied to `aria-label` |
| Navigation | One selected row in the sidebar (neutral fill); the view tabs keep the same selected look |
| Forms | Error text beside the field, not only in a toast; a field's error clears on the next valid input |
| Lists and tables | Truncated text ends in an ellipsis and has the full text as tooltip |
| Empty / loading / error | Icon + title-style title + one line; spinner only for waits over about a second; errors name the next step |
| Feedback | Success toast 2.6 s, Undo 6 s, errors stay until dismissed |
| Destructive actions | Undoable deletes act at once and offer Undo; unrecoverable ones use the alert with a filled red button and no default |
| Typography | Sizes only from `--fs-11…22`; weights 400 / 500 / 600 / 700 |
| Icons | One outline family, drawn at 12 / 14 / 16 / 18 |
| Hover and focus | Fill from `--hover`, `--pressed` or `--cap-hover`; a keyboard ring on `:focus-visible`; arrow cursor on controls, hand only on links |
| Tooltips | Sentence case starting with a verb; a command keeps its name and shortcut |
| Spacing, shapes | Radii from `--r-xs … --r-xl`, 999px and 50% only for pills and circles |
| Motion | Durations from `--dur-fast` / `--dur-base`; all motion stops under Reduce Motion |
| Keyboard | Modifier is ⌘ (Ctrl elsewhere); never Control alone on a Mac; list shortcuts only in the Shortcuts sheet |
| Wording | Menu items and sheet titles in title style; alert titles as sentences; "Unlink", "Duplicate", "Cancel" everywhere |

---

## 7. Needs visual check

- **F-08** Dark-mode contrast of `.rst-cur` and `.rst-days-link` (estimated 2.85:1; glass backgrounds make it code-uncheckable).
- **F-09** Rendered size of the `.rst-cur` hit area and the sidebar search field.
- **F-17** Where validation messages appear in the Reschedule, Level, Recurring, Bulk and Plan dialogs.
- Dark-mode contrast in general: the sweep assumed a dark base of rgb(30,33,45) taken from a screenshot; three further low values ("Change folder…", "Clear all", "Send feedback") belong to menus that were not open, so they are not findings.
- Dialog heights on a short window (the Task dialog measured 846 px tall in a 900 px window; the Calendar, Rules, Format and Fields sheets are all 810 px whatever their content).
- Truncation tooltips in the grid and the sidebar, and drag-and-drop feedback (grab / grabbing cursors, drop lines): **not audited in depth in this pass**.
- Responsive behaviour below 1100 px: CLAUDE.md records measurements at six widths; **not re-measured here**.

---

## 8. Skipped categories

| Category | Reason |
|---|---|
| Menu bar | A web app has no native menu bar; its commands live in the toolbar, the Data / Help menus and the right-click menus |
| Window behaviour (macOS) | A single page in a browser tab or PWA window; the browser owns minimum size, full screen and windows |
| Text overflow and localization (languages) | The app is English only (`lang="en"`, no string table); only the date and time formatting is user-configurable (F-13) |

---

## HIG pages used

alerts, sheets, context-menus, menus, toolbars, typography (default 13 pt / minimum 10 pt for macOS), accessibility (contrast 4.5:1, control sizes 28 / 20 pt, Reduce Motion, 200 % text), undo-and-redo, keyboards (standard shortcuts, Control as a modifier), the-menu-bar. Fetched as `…/<page>.md` on 2026-10-30. Colour, materials, motion and pointing-devices pages were not fetched; claims on those topics are limited to the accessibility page above.

## Method and limits

- Code facts (counts, line numbers) from `milestone.html` as of commit `8d2bae5` plus one uncommitted line (the Unlink icon).
- Rendered facts from Playwright (headless Chromium, 1400×900, no file-system API so the mandatory folder dialog does not cover the app): every dialog opened with its real opener and measured; computed-style sweep over the Tasks, Gantt and Resource Sheet views; WCAG contrast over every visible text element in light and dark.
- 19 of 26 dialogs measured; the remaining ones (file sync, folder files, import, foreign import, replace, sync conflicts, resource days) need data or file state that the sweep did not set up. They use the same `.modal` shell.
- No screenshots are embedded; one dark-mode screenshot was used to correct a measuring error.
