# ClearDesk design system: how it looks, how it behaves, and why

An Apple-style look for a web app (a PWA used mostly in desktop Chrome on macOS), written down so it can be applied to another app. Everything here is taken from the finished ClearDesk app and the decisions made while building it. Where a decision was tried and rejected, that is said, so it is not tried again.

**Files in this folder**

| File | What it is |
|---|---|
| `DESIGN.md` | this guide |
| `tokens.css` | every colour, size, radius, shadow and motion token, light and dark, extracted from the app |
| `icons.json` | the whole icon set (118 icons): name → inner SVG markup on a 24 grid |
| `icon-sheet.html` | a preview of every icon at 32px and the four drawn sizes (open it in a browser) |
| `assets/` | the app-icon masters (`icon.svg`, `icon-maskable.svg`, `favicon.svg`) and `manifest.json`, as examples for section 14 |

Source of truth for everything: `cleardesk.html` (CSS tokens near the top of the `<style>`, the `ICONS` registry in `<head>`), and `CLAUDE.md` for the reasons.

---

## 1. Principles

1. **The chrome is glass, the content is flat** (Apple Mail's rule). The sidebar, menus, dialogs, toasts and banners are translucent and blurred; the lists, board, editor and detail panel are opaque and neutral. Do not put blur inside the content area.
2. **Quiet by default, controls appear when you point at them.** Row actions, remove buttons, hierarchy buttons and "add" toggles show on hover/focus only. The resting screen is text and a few pills.
3. **Few boxes.** Inputs inside lists are "ghost" fields (no border, a faint tint on focus). Boxed fields exist only inside dialogs. The detail panel is grouped rows (label left, value right, hairlines), not a form.
4. **Flat fills and crisp rings, no coloured glows.** No blurred coloured shadows, no gradients on buttons. Hover darkens or tints; it does not grow a shadow.
5. **The arrow cursor, everywhere.** The hand is for links only. Never `cursor: pointer` on a control.
6. **One icon per meaning, one family.** See section 4.
7. **Undo instead of "Are you sure?"** for anything that can be undone (a toast with Undo, 6 seconds). Ask only for what cannot be undone.
8. **Hide what does not apply, don't dim it** in context menus.
9. **Selection is blue only while its list is the active area**; it turns neutral grey when focus is elsewhere (as in Finder and Mail).
10. **Consistency over cleverness:** the same job looks and behaves the same in every mode.

---

## 2. Foundations

### 2.1 Colour (all in `tokens.css`)

Roles, not colours. Always use the token, never a literal. The only literals allowed are inside the token definitions, the note text-colour palette, print CSS and e-mail export HTML.

| Role | Token | Light | Dark |
|---|---|---|---|
| Accent (selection, primary button, links) | `--accent` | `#2a5fcf` | `#2c62c9` |
| Text on accent | `--on-accent` | `#fff` | `#fff` |
| Content surface | `--bg` | `#ffffff` | `#1d1f2b` |
| Secondary surface (list hover, columns) | `--bg-2` | `#f2f3f7` | `#171925` |
| Tertiary surface (code, chips) | `--bg-3` | `#e8eaf0` | `#2a2d3d` |
| Chrome surface (sidebar) | `--bg` etc. in the glass block | translucent white `.46` | translucent `rgba(34,36,52,.50)` |
| Menu / dialog / toast surface | `--glass-strong` | `#ffffff` (97%) | `#232636` (97%) |
| Hairline | `--border` | `rgba(40,44,70,.10–.13)` | `rgba(255,255,255,.10–.14)` |
| Text | `--text` | `#15161b` | `#f5f6fa` |
| Secondary text | `--text-2` | text at 74% | text at 74% |
| Tertiary text | `--text-3` | text at 62% | text at 62% |
| Destructive | `--danger` | `#d92d20` | same |
| Status colours | `--blue-text`, `--green-text`, `--red-text`, `--amber-text` (+ `-bg` tints) | `#0959c8`, `#1a7a36`, `#c4281f`, `#8a4b00` | `#8cc2ff`, `#8ee6a4`, `#ff9a92`, `#ffc566` |
| Toolbar capsule fill | `--cap-fill` / `--cap-hover` / `--cap-on` | `rgba(60,60,67,.08 / .16 / .18)` | `rgba(255,255,255,.10 / .19 / .22)` |
| Focus ring | `--focus-ring`, `--focus-edge` | `#9bbcf6`, `#89aae6` | `#417391`, `#3c6f8c` |

- **Contrast:** text ≥ 4.5:1 on every surface in both themes, including on the selected row (`--text-3` was raised to .62 for this). White text on `--accent` is ≥ 4.5:1.
- **Colour is never the only cue:** status has a dot and text, an unresolved include is red *and* wavy-underlined, overdue is a colour *and* a calendar glyph.
- **Dark mode is a second full set of values**, not an inversion. Define the same variables in both blocks (a variable only the light block sets leaks into dark).
- **Theme** follows the system live; the user may override with Light / Dark. It is a per-device preference, never synced.
- **Neutral blue-grey** palette (a hint of blue in every grey: `#f2f3f7`, `#171925`), not pure grey.

### 2.2 Typography

- **One family:** the system stack (`--font`: `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`); monospace only for code (`--mono`: `'SF Mono', 'Fira Code', 'Cascadia Code', monospace`). No serif anywhere (the toolbar's italic *I* is the system italic).
- **Seven sizes, nothing in between:** `--fs-11` 11, `--fs-12` 12, `--fs-13` 13 (the default control text), `--fs-14` 14 (body, list rows), `--fs-15` 15 (fields in dialogs), `--fs-17` 17 (dialog titles, panel title), `--fs-22` 22 (page titles).
- **Weights:** 400, 500, 600, 700 only. Titles and bold row text 600; pills 500–600; section labels 600 uppercase with letter-spacing `.04–.08em` at 11–12px.
- **macOS minimums:** default 13pt, nothing below 10pt for text. Control glyphs (tick marks, tiny chevrons) are icons, not text, and use the `--gl-8…10` tokens (`--gl-8` draws about 10px, the smallest glyph anywhere; the old 6 and 7 are gone, U-10).
- Line height 1.45–1.7 in body copy; dialogs 1.6.
- **Text size setting:** Small 90%, Medium 100% (default), Large 115%, Extra Large 130%, applied as CSS `zoom` on `<html>` (so every layout measure scales). The HIG asks for up to 200%; browser zoom covers that.

### 2.3 Spacing, radius, elevation

- **Spacing scale:** 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40 (1px hairlines allowed). Odd values (3, 5, 7, 9…) are snapped to the nearest step. Reserved widths (for a capsule, a copy button) are measured, not spacing choices, and may be any number: document them.
- **One left gutter** `--gutter` 20px: every pane's content starts 20px in, so switching modes keeps the margin.
- **Radius ladder:** `--r-xs` 4 (chips, tiny), `--r-s` 8 (rows, controls), `--r-m` 10 (cards, fields, buttons), `--r-l` 12 (bars), `--r-xl` 16 (menus, dialogs, columns), plus `999px` for pills and capsules and `50%` for circles. One name per value; do not invent radii.
- **Toolbar controls are capsules** (fully rounded); content uses the ladder.
- **Elevation:** three levels `--elev-1/2/3` (`0 1px 2px .12`, `0 6px 18px .14`, `0 8px 32px .18`); menus and dialogs use `--glass-shadow` plus an inner top highlight `--glass-rim` (a 1px inset white line, the "lit edge"). Dark mode shadows are stronger, rims weaker.
- **Hairlines, not borders:** 1px, `--border`. Cards and board tiles have *no* outline: they are set off by fill (`--bg` on a `--bg-2` column) and a whisper of shadow in light mode.

### 2.4 Materials (the glass)

- Sidebar, menus, popovers, dialogs, toast, banner: `background: var(--glass-strong)` (≈97% opaque) with `backdrop-filter: var(--glass-blur)` (blur 26–28px), 1px `--glass-edge` border, `--r-xl` radius, `--glass-shadow` and the `--glass-rim` inset highlight.
- **`backdrop-filter` cannot see through a parent that has its own**, so only body-level surfaces blur. Popovers that live *inside* the content use the near-opaque `--glass-strong` without blur (at 88% the content underneath ghosted through).
- The window background is a soft graphite wallpaper (`--wall`), the web stand-in for macOS vibrancy.
- Fallbacks: `prefers-reduced-transparency`, `prefers-contrast` and browsers without `backdrop-filter` get solid chrome and a flat wallpaper.
- Real lens refraction (SVG displacement) was deliberately skipped.

### 2.5 Motion

- **Two durations only:** `--dur-fast` 120ms (hover, colour, opacity reveals, small state changes) and `--dur-base` 200ms (panels sliding, widths, menus, drops, the checkbox pop). Easing `ease`; entry animations `ease-out`.
- **No overshoot, no spring, no bounce.** (A `cubic-bezier(.34,1.56,.64,1)` on buttons was removed.)
- **The checkbox pop** is 1.15× over 200ms and plays only for the box you just ticked, never on a re-render or a view switch.
- **Selection and hover are instant:** no colour transition on rows or cards (a 120ms fade left a trail of half-faded rows when moving the pointer or holding an arrow key).
- `prefers-reduced-motion` collapses every animation and transition to ~0.
- A scrolling column pauses hover (`pointer-events: none` on its cards for 140ms after the last scroll event) so the card under a still pointer does not repaint every frame.

### 2.6 Layout (a Notes-style window, no top bar)

- The **sidebar runs the full window height**: header (toggle + a three-icon mode switch), search, lists, the tools bar (link-file chip + Data / Appearance / Help capsule), counts footer. Width 300 (clamp 260–480, draggable, double-click resets).
- Every column starts with its own **52px bar** with a hairline under it, so baselines line up across sidebar header, list header and editor toolbar.
- A **docked detail panel** (420px) beside the list, not an overlay: the list stays visible, ↑/↓ move the selection and the panel together, Esc closes it. Under 800px it floats.
- Three-pane shape for document modes: list (300, resizable 200–600) + editor (text capped at 900px, left-aligned) + optional inspector (340, resizable 260–560; floats over the editor under 740px).
- The sidebar collapses (⌥⌘S) and starts collapsed under 800px, where it floats.
- **Navigation details are in section 19; a general, rearrangeable layout system (Xcode / Pages / Mail style regions) is in section 20.**

---

## 3. Selection, focus, hover

- **Selected task = ONE solid accent row with white text; its subtasks sit on a light accent tint** (`--sel-sub-tint`, 9% light / 16% dark), identical for one task or many. On a list row the solid part is the first grid row, on a board tile the top block (checkbox, title, secondary line, tags). Badges become translucent white, checkboxes white; inside the tinted part every colour is back to normal (the content re-points `--text*` / `--border*` to the un-selected `--ink*` values). Chosen from four mocks (keep the whole block solid / solid title line / deeper solid / tint only) because Apple's outline views make the parent row solid and leave its children alone, and a tall solid block was too heavy. A task with no (or collapsed) subtasks is a single solid row. An **accent bar** on the left edge was built and **rejected** (it reads as Material, not Apple) — do not rebuild it.
- **Grey when focus is elsewhere:** when the pointer/keyboard/focus is in the detail panel, sidebar, quick-add field, an editor, or the window is inactive, the selection becomes a neutral fill (`rgba(60,60,67,.18)` light / `rgba(255,255,255,.22)` dark, transparent border) and everything inside looks as it does unselected. Typing in any text field also makes it grey. The grey state has the same two parts (a grey band on a lighter grey body), pills on it keep ≥ 4.5:1 (the badge is its own colour at 11% light / 20% dark over the page colour, not a white plate), and the title / date text in Notes and Prompts rows measured 4.9:1 or better in both themes.
- **Never rebuild the list to move the highlight**: toggle a class on the rows that exist (a rebuild flashes, loses hover, scroll and focus).
- **Hover is a fill** (`--bg-2` for rows, `--cap-hover` for capsules); hover must not beat selection (`:hover:not(.selected)`).
- **Editable cells** (priority, status, due) react on the **pill only** on hover (brightness + soft halo), never on the whole cell. On the selected row they show a small chevron so they read as pop-up buttons; unselected rows stay calm.
- **One focus ring** (Apple Mail's search-field ring): a ~3pt band in `--focus-ring` with the control's own border taking `--focus-edge`. Inputs show it on `:focus-visible`; clickable non-inputs get it as a 3px outline for keyboard focus only. The browser's default blue ring is switched off everywhere (a clicked `<select>` kept it).
- A control is not left ringed after a mouse choice: blur a `<select>` after a pointer change, and blur buttons/checkbox divs after a real click. Keyboard users keep focus.
- Borderless fields in the panel show only the caret with the mouse; by keyboard the whole rounded row rings.
- Inline rename fields are quiet: no border, no halo, a soft tint, the caret and the selected text.

---

## 4. Icons

### 4.1 The family

- **Outline only.** 24×24 grid, **2-unit stroke**, round caps and joins, `currentColor`, `fill: none`. No filled glyphs (so a "star" is an outline; a favourite is shown by colour).
- Keep drawings inside the 4–20 box so optical size is the same across icons (a rounded square is `4.5…19.5`).
- **Four drawn sizes:** 12 (chevrons, tiny marks), 14 (badges, chips, row marks), 16 (lists, sidebar, menus, icon buttons, search fields), 18 (toolbars). Nothing else.
- **Effective line weight scales with size** (as SF Symbols do): 1.17px at 14, 1.33px at 16, 1.5px at 18. Do not set a different stroke per context.
- **A hand-drawn icon must render at the same line weight as a registry icon of that size** (rendered line = stroke × drawn size ÷ viewBox). Chevrons drawn as background images need their own stroke: 1.3 on a 12px-wide box, 1.2 on an 8px one. Measure the stroke of the path, not the svg element.
- **Large symbols (empty states, 45px drawn) use a thin 0.9-unit stroke** (≈1.7px). Rendering them at stroke 2 gives a 3.8px line that is heavy next to everything else.
- **Two ways to draw the same registry:**
  - *Masked glyph:* `<i class="fa-solid fa-NAME">` with a CSS rule `.fa-NAME { --fa: url("data:image/svg+xml,…") }` and `mask: var(--fa) center / calc(1.26 * 100%) no-repeat; background: currentColor; width:1em; height:1em`. Icons draw **1.26× their font-size**, so use size tokens `--ico-12|14|16|18` (each `calc(N / 1.26)`), not raw px. Sizes follow `font-size`.
  - *Inline svg* (`class="tb-ico2"`, 18px, stroke 2; menus `svg.mi`, 16px) for toolbars and menus.
- **Never give a masked icon `width: auto`**: it is an empty box that gets its width from `1em`, so `auto` collapses it to zero and its button shows as an empty circle.
- **Colour follows state:** default grey (`--text-2`), white on a selected/blue hover row, red on danger items, amber for lock/favourite on.
- **Text-style toolbar glyphs** (B, I, U, S, A): letters at weight 600, 15px (the italic I is 500, 16px so a slanted letter is not heavier). The text-colour **A** has a 14×3px bar underneath showing the last colour used (grey until one is chosen), as in Pages.
- Menu/toolbar icons sit left of the label with a 10px gap, vertically centred to the text, in a 16px (menus) or 18px (toolbars) box.

### 4.2 Vocabulary: one icon per meaning (never borrow another action's icon)

| Meaning | Icon name | Notes |
|---|---|---|
| Copy | `copy` | two squares; **never the clipboard** (Apple's clipboard means Paste) |
| Duplicate | `duplicate` | the same two squares with a plus |
| Export | `arrow-up-from-bracket` | arrow out of a tray, everywhere |
| Import | `arrow-down-to-bracket` | arrow into a tray |
| Open elsewhere / Open in / Open Link | `arrow-up-right-from-square` | **not** the Export glyph |
| Delete | `trash` (`trash-can` draws the same) | |
| Remove from a list | `xmark` on a chip, `minus` on a +/− bar | |
| Close | `xmark` | |
| Edit / Rename | `pen` | |
| Open Details / info | `circle-info` | |
| New (compose) | a square with a pen | |
| Prompts | `braces` | curly braces |
| Compare | `diff` | a rounded square, a + above a − |
| Swap / move sideways | `arrows-left-right` | only for "Distribute columns evenly" (it reads as swap) |
| New folder / subfolder | `folder-plus` | `folder-open` = link a file/folder, `folder` = plain |
| Undo / Redo | `undo` / `redo` | hooked arrows; the circular arrow `rotate-left` is for *Restore* and *Reset* |
| Lock / unlock | `lock` / `lock-open` | amber while locked |
| Pin / Favourite | `thumbtack` / `star` | |
| Show/hide panel | a framed box with a side column | |
| Check / complete | `check`, `circle-check` | round checklist items match the icon |

The icon set: `icons.json`, preview in `icon-sheet.html`. To add an icon: draw it on the 24 grid, add it to the registry under a name that states its meaning, never reuse another action's name.

---

## 5. Components

### 5.1 Buttons

- `.btn`: 14px, 8×14 padding, `--r-m`, 1px `--glass-edge` border, a soft `--bg-3` fill; **hover darkens** (no shadow). The small variant (`btn-sm`) is 13px.
- **Primary:** flat accent fill, white text, no gradient, no coloured glow; white text on it stays ≥ 4.5:1.
- **Danger (filled red)** appears only inside a confirmation (Delete, Replace, Discard). Everywhere else a destructive command is **plain red text** (e.g. the panel's Delete).
- **Round bar buttons** (new, lock, favourite, ⋯, panel toggle): plain symbols on `--cap-fill`, no border or rim; only a toggled state changes the fill (amber for lock/favourite, `--cap-on` for an open panel).
- **Capsule groups** (`.tool-group`): joined segments on one `--cap-fill` capsule, 3px inset, 2px gap, segments 30×34. Group related commands (Undo/Redo; ↑ ↓; Insert row/column…).
- **Icon-only buttons get a tooltip *and* an `aria-label`** (see 5.7). Open in + more share one capsule like Apple's Share + ⋯.
- Buttons that open a menu are **pull-down buttons**; pickers that show a current value are **pop-up buttons** (soft fill, stacked ⌃⌄ chevrons).
- Call `.blur()` after a click so a lingering focus ring does not appear on the next key press.

#### Shape language: discs, pills, capsules

One shape per job, so the same kind of thing always looks the same:

| Shape | Used for | Rule |
|---|---|---|
| **Disc** (circle) | every **icon-only button** (`.icon-btn`: row actions, the panel's close, delete, indent, the sidebar's + and projects-shown, the banner's ✕, hierarchy buttons, fold-all), the round bar buttons, checkboxes and subtask circles, the toolbar's round lock / ⋯ | sizes `--ib-s` 22, `--ib-m` 26, bar buttons 36 (`--bar-ctl-h`); a single base rule gives width, height, 50% radius and the `--pressed` hover. A new icon button gets `.icon-btn`, never its own radius |
| **Pill** (fully rounded, wider than tall) | priority / status / due badges, tags, filter chips, a segment inside a capsule group, pop-up buttons | tinted fill, never outlined; hover = brighten + soft pill-shaped halo |
| **Capsule** (a pill holding several controls) | toolbar groups, the row's hover actions, the mode switch | one `--cap-fill` surface, 3px inset, each button a 22px disc inside; the hovered button fills (`--pressed`, or translucent white on a blue row), **no ring** |
| **Rounded rectangle** | rows (`--r-s`), cards and fields (`--r-m`), bars (`--r-l`), menus / dialogs / columns (`--r-xl`) | the radius ladder in 2.3, no one-off values |
| **Square** (exceptions) | the Global Variables +/- bar (macOS style) and the code-block copy chip | stay square on purpose |

- **The board tile has one ⋯ disc** (26px) in its bottom-right corner, not a capsule of five buttons (five ran over the subtask field and the last line). It floats, so it never changes the tile's height. On the **solid blue part** it is translucent white; on the **light tint** (a tile with visible subtasks) it keeps the normal capsule look (`--bg-3` fill, `--ink-border`, `--pressed` hover), so it reads the same as an unselected tile's. In the grey (inactive) state it is the normal capsule on both.
- **A capsule on a row is centred on the solid band**, not on the whole row: with subtasks the row is taller, and a capsule centred on the full height would sit on the boundary. Measured: the capsule centre equals the band centre (223 = 223 plain, 261 = 261 with subtasks).
- **An icon is centred in its disc** (measure the drawn box against the button's box, not by eye).
- **Hit areas under 20px** (table grips, the edge "+", remove ×) keep their look and get an invisible `::before`; corner and row grips sit against a resizer, so theirs extends away from it only.

### 5.2 Pills, badges, tags, chips

- Pills are fully rounded, 11–12px, weight 500–600, tinted fill + matching text (never outlined): priority (high red, medium amber, low green), status (not started grey, in progress purple, done green), due (grey, red when overdue, amber today).
- Tags: tinted fill, text in the tag colour, weight 500, **no outline** (the same tag looks identical in the sidebar, a row and the panel). Inactive filter chips stay neutral; the fill alone says "on".
- Status and priority have a colour **dot** in menus (`PRIORITY_DOT` / `STATUS_DOT`).

### 5.3 Fields

- **Ghost row** for adding (after Apple Reminders' new-item line): a faint round checkbox (or "+") then a borderless input with a muted placeholder; a hairline under it turns accent on focus. No box, no dashed border.
- **Boxed field** only in dialogs: 1px `--border`, `--r-m`, 8×12 padding, 15px, `--bg-2` fill.
- **Selects:** `appearance: none` with a thin chevron drawn as a background image (one data-URI per theme, since a URI cannot read CSS variables). The opened list is the OS menu.
- Number and date inputs match the other fields; no raw `tt.mm.jjjj` shows: show formatted text with an invisible native input laid over it.
- **Checkboxes are round** (`<div role="checkbox" tabindex="0">`): 19px for the main item, 16px for subtasks/steps/sub-steps/ghost, in every view. An invisible `::before` grows the click area to ~28px. A custom checkbox div needs a global handler so Space/Enter re-clicks it, and the click must blur it (or it swallows the next Space/Enter).

### 5.4 Lists and rows

- **Row = grid of columns** with a fixed floor width, titles wrap (`overflow-wrap:anywhere`). Column widths are measured from content (include the selected-row chevron and the widest locale date), then given a few px of buffer.
- **Row actions are an overlay**, not a grid column: a small capsule at the right end of the title cell, visible on hover, focus-within and the selected row, `pointer-events:none` while invisible, with padding on the title so it wraps before the capsule. It floats at the card's bottom-right on board tiles.
- **Sortable headers:** click cycles ascending → descending → default; undated items stay last in both directions.
- Truncate with an ellipsis and give the full text as a `title`.
- **Board tile:** a title first, one quiet secondary line (status text only when not default, a flag for high priority, date with calendar glyph, repeat mark), tags as chips. Subtasks are indented to the title's text column; each level is a step smaller (14/600 → 13/400 secondary).
- **Empty state:** a thin large icon (see 4.1) at 40% opacity over a title-style label ("No Tasks", "No Matching Notes"), centred; no call-to-action button where a quick-add row already exists.

### 5.5 Menus, popovers, context menus

- **Surface:** glass (2.4), `--r-xl`, 230px wide for the main menu, small option menus at a fixed `--submenu-w` 164px so Priority/Status/Due/Move look the same everywhere.
- **Row:** 8px radius, a 22px tick column for the current value (✓ at the left for single-choice lists, at the right for toggle states), then a dot or 16px icon, then the label. **Hover fills the row with the accent and turns text white**, as in a macOS pop-up; a destructive item turns white on it too.
- **Context-menu rules:** Title-style labels ("Open Details", "Add Subtask", "Move to"); few items; **one level of submenu** (hover or click to open, flips left and nudges up when near the edge); **hide unavailable items** (do not dim); separators group (≤ 3 groups) and are cleaned up when a group empties; Delete is last, red; the ⌫ glyph hint, not "Del".
- Every context-menu command also exists in a visible control (toolbar, panel, ⋯ button).
- A menu **never changes the selection**; it acts on the whole selection if the clicked row is part of it, else on that row.
- Position with the real layout rect (measure the zoom factor from an element), then pull the menu 16px inside the window edge.
- **Cell popovers** are appended *inside* the clicked cell and positioned with CSS, not from `getBoundingClientRect()` (unreliable under the UI zoom). The Due popover opens leftwards (it is the last column).
- **One pop-up at a time.** Opening any menu, popover or dropdown (sidebar Data / Appearance / Help, toolbar menus, filter, a cell popover, a row menu) first closes every other one (`closeMenusExcept(keepId)`): buttons that stop the click from bubbling never reach the outside-click handler, so each opener must close the rest itself. Three menus open together was a real bug.
- A popover opened inside a selected (blue) row must re-point its text and border variables to the un-selected values, or it inherits white text on a white surface.

### 5.6 Feedback

- **Toast:** bottom-right, glass, 13px, a live region (`role="status"`, `role="alert"` for errors). Success 2.4s, with Undo 6s; **held while the pointer or focus is on it**. **An error toast stays until dismissed** (a ✕ button), per the HIG's warning about time-boxed messages.
- **Banners** are quiet neutral bars (a small amber icon, one pill action, ✕), not coloured blocks. A first-run notice is a banner, not a modal.
- **Inline messages** for form validation, in red, under the field, saying what to do.
- **A new-version banner** compares server headers and offers Reload.

### 5.7 Tooltips

Native `title` attributes (browser delay and style), always paired with an `aria-label` on icon-only controls. The pairing is automatic: write the `title`, and a small observer copies it into `aria-label` for any button with no text of its own (and follows later title changes); a test scans the markup so a nameless icon-only button cannot be added (U-16). Truncated text gets its full text as a `title` too.

---

## 6. Dialogs, sheets and modals (the Apple feeling)

### 6.1 Which surface for which job
- **Alert dialog** (centre, small): only for something that **cannot be undone** (delete permanently, delete all, unlink, replace all data).
- **Form dialog / sheet:** a scoped task closely tied to the current context (new folder, edit project, link a file, AI apps).
- **Settings-style window** (Help, Keyboard Shortcuts, About): a macOS System Settings layout, see 6.4.
- **Popover or menu** for anything quick and local; **a side panel** for editing a single item next to its list.
- Do **not** use a modal for repeated edit-and-observe work (the HIG: use a panel or a window). We kept Compare as a modal on purpose; in a new app prefer a pane.

**Two shells, no third.** Everything you fill in is a **sheet**; everything that asks a question is an **alert**. Help / Shortcuts / About / Global Variables are *windows* with their own sidebar layout and are not dialogs. Full CSS, markup and rules for porting: `DIALOG-SHELL.md`.

| | Sheet (`.modal` + `.modal-head`) | Alert (`.modal.alert`) |
|---|---|---|
| Header | left-aligned title 17/600, optional one-line subtitle, **no header icon** | a round 40px tinted icon (`.alert-ico`, danger red or accent), centred title and sentence |
| Buttons | Cancel then the primary, right-aligned | full-width, stacked as a row of equal buttons (`.alert-wide` for three) |
| Used for | folder, project, new file, link file, AI apps, data files | confirm, Import (Cancel · Replace · Merge), Compare's "Discard changes?" |

An alert can open **over** a sheet (it stacks at a higher z-index and closes on its own: Esc, Cancel, outside click, its button), which removed the old inline-confirm workaround inside Compare.

### 6.2 Anatomy of a dialog
- **Scrim:** `rgba(20,24,50,.22)` (`--scrim-glass`) plus `backdrop-filter: blur(4px)` over the whole window; fades in 120ms (`--dur-fast`); the dialog itself does not slide.
- **Panel:** glass-strong (97%) with blur, 1px `--glass-edge`, **`--r-xl` 16px**, `--glass-shadow` and the inner top rim highlight. Padding **24px**, flex column, **gap 14px**.
- **Width:** 380px standard (360 narrow lists, 420 link/sync, 860 × min(700px, 88vh) settings), `max-width: 90vw`.
- **Title** 17px / 600, left-aligned, no close button on small dialogs. **Body** 14px, `--text-2`, line-height 1.6, complete sentences. An optional 12px `--text-3` sub-line under the title.
- **Fields** boxed (5.3), full width, 15px.
- **Button row:** right-aligned, gap 8px, **Cancel on the left, the primary action on the right** (the trailing side is the default). Title-style, one or two words, a verb that says the result ("Replace", "Create", "Save"), never "OK" except in a purely informational alert, never "Yes/No".

### 6.3 Behaviour
- **Esc cancels; clicking the scrim cancels** (except where unsaved work would be lost: ask inline first).
- **Return = the default (primary) action.** A **destructive confirm has no default button** (focus goes to the dialog itself, so Return does nothing; Cancel is never made the default: the HIG says to give no button the default instead). A plain confirm focuses its button.
- **Focus** moves into the dialog when it opens and **returns to where it came from** when it closes; Tab / Shift+Tab wrap inside.
- **One close path** (`closeModal(id)`) for every dialog, which also drops that dialog's pending state.
- **Only one sheet at a time**, but a **confirmation alert stacks over a sheet**: it has its own return-focus and close path and Esc closes it first, then the sheet (Compare routes Esc through its own close request so unsaved edits ask first, wherever focus is).
- **Dialogs that edit a draft end Cancel · Save (or Create)**; dialogs whose changes apply as you go end in **Done** only and say so ("Saved as you type").
- **Filled red** only in a destructive confirmation (Delete, Replace, Discard). (The HIG would leave the button un-red when the person deliberately chose the destructive action, e.g. Empty Trash; this app styles it red anyway as a house rule. Keep it consistent.)
- **Roles:** every dialog is `role="dialog"` (the confirm is `role="alertdialog"`), `aria-modal="true"`, labelled by its title; the live toast is separate.
- **Do not confirm undoable deletes.** Remove at once and offer Undo in a toast that says what happened to the contents ("3 tasks moved to Inbox").

### 6.4 The System-Settings-style window (Help, Shortcuts, About)
- Left: a **tinted sidebar**: a round close button where macOS puts its window controls, a capsule search field, the topics as inset rounded rows with the **solid accent on the current one**. Right: a **large title** that follows the topic ("Search results" while searching) and grouped content.
- Content in **grouped cards**: each section's rows sit in one rounded, softly tinted list with hairlines between rows; a short icon on each row; keys shown as key caps in the system font on the right.
- No header bar and no hairline between the halves. In a narrow window the sidebar becomes a strip across the top.
- **Keyboard-driven:** opens with focus on the topic list; ↑/↓/Home/End switch topic, → or Tab enters the text, ← goes back; **/** jumps to search; Esc clears the search first, a second Esc closes.
- **About** is a button-less centred panel like macOS's: the real app icon (22% corner radius), name, tagline, credit line, privacy line, a round close control at the top-left. No version line unless the app has one.
- Search reads the static HTML of the panes and marks the matching words; the dialog reopens on the topic last read.

### 6.5 A small thing worth copying
The first-run "link a file" prompt is a **quiet banner**, never a modal; the dialog it opens is a grouped list of choices (round icon, title, description, chevron) with a quiet amber notice — the Help dialog's list idiom reused.

---

> **Dialog shells (supersedes the header advice above where they differ):** two shells only, a *sheet* for anything you fill in (left title + optional subtitle, no header icon) and an *alert* for anything that asks a question (round icon, centred text, full-width buttons), and a confirmation stacks over the dialog that asked it. Full CSS, markup and behaviour rules for porting are in `DIALOG-SHELL.md`.

## 7. Behaviour patterns

- **Keyboard first:** ↑/↓ move the selection, Return opens, Space toggles/collapses, Tab adds a child (subtask → step → sub-step chain), Esc closes/cancels, Delete removes, F2 renames, N focuses quick-add. Arrow keys cross the quick-add field (↓ into the list, ↑ from the first row back to the field). Modifier clicks: ⌘ extends, ⇧ selects a range.
- **Double-click opens the detail; a single click only selects.** (Single-click-to-open was tried and reverted.) Double-click on the title text renames.
- **Enter in quick-add leaves the field** with the new item selected, so Tab adds a child straight away.
- **Quick-add shorthand** (`!high`, `#project`, `@tag`, a date word) with a live preview; Shift+Enter bypasses parsing.
- **Pickers show their value**: the quick-add project picker, the sort menu (Date edited / created / Title), toggles with ticks.
- **Soft delete everywhere** ("Recently Deleted", 30 days) with Restore and Delete Permanently (the latter asks).
- **Drag and drop:** an accent insertion line shows where it lands; a target that cannot accept gets the not-allowed pointer and a faint red edge; sub-steps only reorder within their parent.
- **Linked file sync** is a single quiet chip (amber Link file, green Linked, red Reconnect), merge by last-writer-wins with tombstones so deleted items never come back.
- **Narrow windows:** the sidebar floats, the panel floats, toolbars give way in steps (buttons collapse into a menu; the order is documented per bar), and a bar stays one row down to a ~680px pane.

---

## 8. Wording

- **Title-style capitalisation** for menu items and buttons: "Open Details", "Copy Note", "Insert Row Above"; short prepositions stay lower-case ("Move to"). Alert titles that are sentences use sentence style.
- **Cancel** is always the dismiss word. Verbs for actions ("Delete", "Replace", "Create"); the same term for the same thing (Duplicate everywhere, Recently Deleted everywhere).
- Placeholders say what to type and what happens ("Add a task…", "Web address, e-mail or phone number").
- Empty-state labels are title-style nouns ("No Prompts").
- No "Are you sure?" copy: say what will happen and what is lost.

---

## 9. Accessibility

- Text ≥ 4.5:1 (check both themes and the selected row); large/bold text ≥ 3:1.
- **Hit areas ≥ 20×20pt on macOS** (28 is the comfortable default): small controls keep their look and get an invisible `::before` that enlarges the click area. **Measure it** (`elementFromPoint` around the control), do not trust the CSS: inset values count from the padding box, inside the border.
- Every control has an accessible name; custom controls have roles (`checkbox`, `button`, `menuitem`, `dialog`, `status`, `alert`); open/expanded/active-descendant states are set when menus and editors toggle.
- Dialogs trap focus and return it; menus open with the first item focused when opened from the keyboard.
- Honour `prefers-reduced-motion`, `prefers-reduced-transparency` and `prefers-contrast`.
- **Do not auto-dismiss errors.** Do not use colour alone.
- Screen-reader reading order follows the visual order; the list is a `listbox`, rows are options.

---

## 10. Mistakes we made (so you do not)

1. Borrowing an icon for a second meaning (the Export arrow for "Open in", the clipboard for Copy). One icon, one meaning.
2. A masked icon with `width: auto` (an empty circle).
3. Rendering a large icon from a 2-unit stroke (3.8px, heavy).
4. A transition on selection/hover (trails of half-faded rows).
5. Rebuilding the whole list to move the highlight (flashes, loses scroll and hover).
6. Forced layout inside the render function (measuring `scrollHeight` right after `innerHTML` doubled the cost of switching tasks).
7. A rounded `overflow: hidden` clip over a large painted subtree (made a scrolling editor feel sluggish on a real GPU even though a headless trace could not see it): trust the real browser over headless numbers.
8. White text rules scoped to the selected row leaking into popovers opened inside it (blank white boxes).
9. A white-on-blue override that was not removed when the grey "inactive" state arrived: scope every blue-state rule with the active condition.
10. Coloured glows on buttons and heavy borders on cards: Apple's look is flat fills and crisp rings.
11. `cursor: pointer` on controls.
12. Dimmed menu items instead of hidden ones; confirm dialogs for undoable deletes; Cancel as the default button.
13. Unscoped CSS variables: the light block silently set a variable the dark block did not.
14. Hard-coded literals in inline styles (they bypass every token and the dark theme).
15. Using the browser's default focus ring, then painting a square one inside a rounded row.
16. Letting several pop-ups stay open because each opener stops the click from bubbling (the outside-click handler never ran).
17. Giving a control on a tinted part of a selected row the on-blue (translucent white) look: it needs the normal look there, or it vanishes on the light tint.
18. Centring a row's capsule on the whole row instead of the solid band, so it sits on the boundary when subtasks make the row tall.
19. A confirmation that closes every dialog (so a dialog could not ask over itself), worked around with an inline bar.

---

## 11. Porting checklist (do these in order)

1. Copy `tokens.css`; switch theme with `data-theme` on `<html>`; follow the system with `prefers-color-scheme`.
2. Set the system font, the 7-size scale and the four weights; set `cursor: default` globally and the hand only on links.
3. Add the icon registry (`icons.json`) and one rendering function/class; fix the four sizes and the vocabulary (4.2). Never add an icon outside the registry.
4. Build the shell: full-height sidebar, 52px bars per column, 20px gutter, glass on chrome only, flat content.
5. Add the components in this order: buttons and capsule groups, pills, fields (ghost + boxed), rows with the hover capsule, menus/popovers, the dialog shell, the toast.
6. Implement selection with the active/inactive (blue/grey) zones and the one focus ring.
7. Wire the behaviours: Undo toast instead of confirms, soft delete, hide-not-dim menus, Esc/Return rules, focus return.
8. Add the motion tokens (two durations), reduced-motion/transparency/contrast fallbacks.
9. Run a contrast pass in both themes and a hit-area pass; add an automated scan that fails on literal colours, radii, font sizes and `cursor: pointer`.
10. Write the exceptions down (the things that deliberately differ from the HIG, and why) next to the code, as ClearDesk's `CLAUDE.md` does.

**Reference screens to compare against while porting:** the task list with a selected row, the task panel (grouped rows), a context menu with a submenu, the confirm dialog, the Help window, the board tile, an empty state, the Notes toolbar (letters + icons), and the Prompts toolbar (capsule groups).

---

## 12. Where we deliberately differ from the HIG (and why)

The app was audited against Apple's Human Interface Guidelines (29 findings, most fixed). These are the places where we **chose** to differ or accept a gap. They look like bugs to someone porting the system; they are not. Change one only with a new decision.

| Decision | HIG says | We do | Why |
|---|---|---|---|
| Shortcut hints in context menus (⌫ on Delete, ⇧⌘↵ on Open in) | show shortcuts in the menu bar, not in context menus | keep them | a web app has no menu bar, so the hint is the only on-screen reminder; the Shortcuts dialog is the full list |
| No menu bar | provide the standard menus | the sidebar's Data / Appearance / Help menus + the Shortcuts dialog | a web app cannot; add real menus if it is ever packaged (Electron/Tauri) |
| Text size tops out at 130% | allow at least 200% | four stops: 90 / 100 / 115 / 130 | decided: browser zoom covers 200%; at 200% the window is effectively < 800 CSS px |
| Compare (a diff editor) is a modal sheet | repeated edit-and-observe belongs in a window or panel | kept as a modal | decided after mocking three alternatives (a pane in the main window, its own window, a docked panel); the modal was judged good enough. In a new app prefer the pane |
| Selected row = solid accent with white text | "appropriate feedback"; no style prescribed | solid | a tinted block with an accent bar was built and rejected as not Apple-like; the bar is a Material/web pattern |
| Filled red button in confirmations that the person chose | do not style a deliberately chosen destructive button red | red for Delete / Replace / Discard | house rule: one rule everywhere, plain red text outside confirmations |
| Task row context menu is long (four submenus) | few items | kept | decided: Repeat, Status, Priority and Due all stay reachable in one place |
| "Pin" in Notes, "Favorite" in Prompts | one term per concept | two words | they are different concepts in the app (pinned to the top of a list vs. a Favorites filter); decided to keep |
| English-only strings | localisation | hard-coded English (dates use the locale) | a product decision; if localised, move strings to one table and use `Intl.PluralRules` |
| Native browser tooltips | consistent tooltips | `title` attributes | accepted; always paired with an `aria-label` |

Table "+" and grips: closed (U-11, U-10). Their hit areas were measured at 20×20 or more with `elementFromPoint`, the "+" is a 10px glyph in a 14px disc, and there is a keyboard menu (Shift+F10).

---

## 13. Reusable patterns worth copying

**The detail panel as grouped rows** (Reminders / System Settings style, not a form). Groups of rows: label left in secondary text, value right, hairlines between, no boxes, sentence-case labels. A row that picks from a list is a plain text value plus stacked chevrons, with a **real `<select>` laid invisibly over the whole row** (`opacity:0`, `position:absolute; inset:0`), so the OS menu, the keyboard and screen readers work and the row is the click target. A date row shows formatted text with an invisible native `type=date` over it (`showPicker()`), never the raw control. Notes is a borderless auto-growing textarea (`field-sizing: content`, with a measure-one-frame-later fallback; never measure inside the render function). Footer: the main action as a pill, Delete as plain red text.

**The inspector panel** (right of an editor): slides in and out (the toolbar spans the whole editor pane above it, and a trailing toolbar button toggles it, the Apple inspector pattern); default open only in wide windows (≥ 1400px); under 740px it floats over the editor with a shadow; resizable by a grip at its left edge (width in a CSS variable, per device); Esc or a click on the editor closes it when floating, without changing the saved choice.

**The `/` block menu** in a rich-text editor: type "/" at the start of a line or after a space, followed by non-space text ("and/or", "1/2" and URLs never trigger it); a small glass menu opens at the caret listing grouped items (text styles, lists, inserts) with the Markdown shortcut as the hint; ↑ ↓ ↵ Tab pick, Esc closes and stays closed for that token; it never opens on paste or undo; it opens above the caret when there is no room below; the editor is a `combobox` only while it is open.

**The link popover:** a 320px popover anchored under the link/selection/caret (not full width), a grouped form with a *Text* row and a *Link* row, a blue **Done**, and **Remove Link** when on a link. The hint line says what the typed address will do ("Opens in a new tab / your mail app / your phone app") or, in red, why it is not a link. Enter applies, Esc or a click outside dismisses it.

**The code-block copy chip:** an icon-only copy button in the block's top-right corner, no header, no label; it shows on hover, caret-in-block or keyboard focus (always on touch), turns into a green check for 1.4s, and lives in an overlay layer outside the editable body so it is never saved or copied with the note.

**Quick-add field:** a ghost row with a "+" at the left, a muted placeholder, a project pop-up at the right end, a live preview of what the shorthand parsed to; Enter leaves the field with the new item selected.

**Tables in an editor, Apple-Notes style:** no second toolbar; hover grips and an edge "+"; a grip click only selects the row/column; options on right-click; the same four menus (toolbar, row/column grip, whole table, keyboard) built from one set of helpers.

**A column-width / pane resizer:** 4–6px hit strip on the edge, pointer events measured once for the UI zoom, double-click resets, ←/→ nudge by 16px (Shift 48), clamped, stored per device.

**Soft-delete trash view** in every mode: the same banner ("removed after 30 days" + Delete All), the same rows with solid selection, Restore and Delete Permanently as two toolbar icon buttons and in the context menu.

---

## 14. App icon and installing it as an app (PWA)

- **The mark:** curly braces around a bold check on a blue vertical gradient (`#52B5FF` → `#0B6BE8`); the glyph is white at stroke 1.7 (braces at 85% opacity, the check at 2). `assets/icon.svg` is the master: a **full-bleed 1024 square with no baked-in rounding, shadow or gloss**, so the system can mask and light it. Keep the artwork inside the maskable safe zone (the central ~80%).
- `assets/favicon.svg`: the same drawing on a rounded square with slightly heavier strokes, for tab size. `assets/icon-maskable.svg`: the same drawing with the glyph smaller, inside the safe zone.
- **PNG renders:** 180, 192, 512 from `icon.svg`, plus a 512 maskable. Render with headless Chrome at the exact pixel size, and **bump the cache name in the service worker** (`CACHE_NAME`) whenever shell files change, so installed copies refresh.
- **`manifest.json`** (`assets/manifest.json`): a stable `id`, `display: standalone`, categories, **separate `any` icons (192/512) and a `maskable` one**, `theme_color` / `background_color`, and three **jump-list `shortcuts`** (New Task / New Note / New Prompt → `?new=task|note|prompt`). A tiny launch function reads `?new=`, removes it from the address, and runs the action. Shortcuts only appear after the app is installed afresh.
- `<meta name="theme-color">` twice, one per colour scheme, matching the chrome colour.
- **Not used on purpose:** window-controls-overlay, screenshots in the manifest.
- **Safari cannot install this kind of PWA on macOS**; the launcher script opens it in Chrome/Edge. Offline support needs the http server (not `file://`).
- **A new-version notice** (a quiet banner with Reload) compares the page's server headers on load, on tab focus and hourly, and when a new service worker takes over.

---

## 15. Keyboard conventions

- **App-wide:** `/` focus search · `N` new item (or focus quick-add) · `?` shortcuts · ⌘Z undo (also undoes the last delete, move or duplicate while not typing) · Esc closes the panel/dialog, then clears the selection.
- **Lists:** ↑ ↓ move, Return opens, Space toggles/collapses, Tab adds a child (and Tab again indents the chain), F2 renames, Delete removes, ⌘A selects all, ⌘/⇧-click extends/ranges. ↑ from the first row returns to the quick-add field.
- **Mode switching: ⌥⌘1 / ⌥⌘2 / ⌥⌘3** (Ctrl+Alt on Windows). Plain ⌘1–⌘3 are the browser's tab shortcuts; ⌥⌘S toggles the sidebar (⌘B too, but not in an editor where it is Bold); ⌥⌘I toggles an inspector; ⌃⌘C (Ctrl+Alt+C) copies a note because ⌘⇧C opens Chrome's inspector.
- **Editor:** ⌘B/I/U, ⌘K link, ⌘P print, ⌘↵ leaves a table or code block (and copies a prompt), Shift+F10 / the Menu key open the context menu for the focused item, Option+↑/↓ reorder a focused folder.
- **Compare view:** F7 / ⇧F7 next/previous difference (⌥F5 as an alternative), ⌘S saves, Esc closes (asking first when there are changes).
- **Key labels are written once in neutral words** ("Cmd/Ctrl", "Menu key") and rewritten per platform at start (⌘ ⇧ ⌥ ⌫ ⎋ ↩ ⇥ on a Mac; Ctrl+, Delete, Esc, Enter, Tab elsewhere). Key caps use the system font so the glyphs are readable. One row = one key combination = one key cap; alternatives are separate rows. The Shortcuts dialog lists keyboard shortcuts only; mouse gestures live in Help.
- **Do not take** system shortcuts (⌘Q, ⌘W, ⌘T, ⌘⇧C, ⌘1–9 …); keep arrow keys native inside text fields and selects.
- **When arrows work:** the list keeps ↑/↓ unless the cursor is in one of the panel's own fields (arrows belong to the field). Esc or a click on the list hands them back.

---

## 16. Settings: per device vs synced

- **Per device, never synced:** theme (Light/Dark/Auto), sidebar width and collapsed state, list and inspector widths, the open item, the selected folder, sort choices, the chosen view mode.
- **Exception:** the text size is saved in the data, so it follows you to another device.
- **Synced with the data:** the data itself, the project order, which projects show in "All Tasks" (with a timestamp so the newer copy wins).
- A synced file must never push one device's display choice onto another.

---

## 17. Smaller details worth knowing

- **Tag colours:** only three (blue, teal, purple), each as a dot + tinted background + text. Colours are stored as *names*, never raw colours, so themes can re-shade them.
- **Editor text colours:** six named text colours (`red orange green blue purple gray`) and six highlights (`yellow green blue pink purple gray`) stored as names (`data-tc`, `data-hl`) and shaded per theme with `--nc-*` / `--nh-*`; the copy/print export maps names to light inline colours because e-mail clients cannot read CSS variables. The toolbar shows the last text colour as the bar under "A".
- **Print:** a `@media print` block hides everything except the note, forces white/black, and prints the copy-note HTML.
- **Dates:** format with the user's locale (`toLocaleDateString`); size the date column from the widest locale ("28 de mar." needs 108px, English 89px) and leave a buffer.
- **Menu icons are inline SVG from the same registry** (so the right-click menus and the buttons never differ); an icon name with no drawing renders nothing, which is the signal that one is missing.
- **Notes about security that affect design:** any HTML that reaches the editor goes through one allow-list sanitiser, so pasted content can never bring in its own styles, ids or scripts; ids that reach markup are validated once at the data boundary.
- **A "last resort" for headless checks:** the test suite evaluates the real code against a fake DOM in JavaScriptCore (no Node needed), which catches wrong-render-function bugs; real typing, measuring and focus need a browser driven over the DevTools protocol (see 18).

---

## 18. How to verify like we did

1. **Mock first.** For any visual or interaction decision, build a static HTML mock with the options side by side (light and dark), open it in the browser, and let the person choose. Several rejected ideas (tinted selection, three Compare layouts, a different Compare icon) were decided this way in minutes.
2. **Measure, do not guess.** Read computed styles in a real browser: stroke weights (`stroke-width × rendered width / viewBox`), font sizes, hit areas, transition durations of every element, contrast against the *sampled* background under each text run.
3. **Drive the real thing.** Real mouse and key events over the DevTools protocol (`Input.dispatchMouseEvent`, `Input.dispatchKeyEvent`, `Input.insertText`); a fake DOM or `execCommand` does not fire `beforeinput` or real focus changes. Take screenshots in light *and* dark and at narrow widths.
4. **Compare before and after.** When refactoring CSS (e.g. moving inline styles into classes), dump computed styles for a list of selectors on the old and new files and diff them; expect no differences except the ones you meant.
5. **Do not trust headless performance for GPU raster.** It showed no regression for a rounded clip that made scrolling feel sluggish on a real display. Verify perf claims with repeated runs and prefer the user's real-browser report.
6. **Keep a short rules file** (`CLAUDE.md` here) that records each rule *and the reason or the rejected alternative*, updated in the same change. It is what stopped regressions here.

---

## 19. Navigation

Sources: measured from ClearDesk (marked **ClearDesk**), and Apple's HIG pages *Sidebars*, *Split views*, *Tab bars*, *Toolbars* (which now contain the navigation-bar guidance) and *Panels*, fetched while writing this (marked **HIG**). The mobile patterns at the end are **HIG only, not built or tested here**.

### 19.1 Sidebar (the main navigation on desktop)

- **What belongs in it** (HIG): the top-level areas and collections (folders, projects, smart views). Keep it **two levels deep at most**; deeper hierarchies get a content list between the sidebar and the detail (that is why ClearDesk has sidebar → list → editor). **ClearDesk:** one level of subfolders, nothing deeper.
- **Rows** (ClearDesk): `.nav-item` and `.project-row`: 6–8px vertical padding, 8px gap, `--r-m` radius, 13px; a 14px leading icon (the registry's outline icons, grey), the label (500 weight, ellipsis when long, full name as a tooltip), the **count** at the right (12px, tertiary text).
- **Current location:** the active row gets a **quiet neutral fill** (`--bg-2`) and heavier text (600 for projects). The sidebar's selection is *not* the accent colour (the accent is used for the content list's selection and the primary button), so there is no blue/grey "focus elsewhere" state to manage in the sidebar. The HIG still wants the current selection **persistently highlighted in each pane that leads to the detail**; the active row, the toolbar title and the list selection together do that.
- **Sections:** an 11px / 600 / uppercase / `.08em` / tertiary-text label; collapsible with a small chevron (Tags), or a "+" at the right (Projects, Folders). Collapse state is per device.
- **Smart views** (All Tasks, My Day, This Week, Overdue; All Notes, Pinned; All Prompts, Favorites) sit above the user's own collections, with counts. They are navigation too: they have context menus where there is something to offer.
- **Hover capsule instead of reserved buttons:** a project row's Edit/Delete float just left of the count on hover/focus and take **no width**, so counts line up with the rows above; while the capsule shows the name gives up 76px.
- **Reordering and moving:** drag a folder/project onto a sibling (a line above/below shows where), Option+↑/↓ on a focused one, Move Up/Down in its menu; dragging an item onto a folder moves it.
- **Symbols:** familiar outline icons per row; user-chosen project icons come from a fixed picker. Sidebar icons stay neutral grey (HIG: colour only with a clear purpose; the system accent colour applies if you use it).
- **Hide and show:** a toggle in the sidebar header and a floating copy while hidden; ⌥⌘S; it starts hidden in narrow windows and **floats** over the content there (picking something closes it again without saving the choice). HIG: let people hide it, offer more than one way to bring it back, **don't hide it by default** in wide windows.
- **Avoid critical actions at the bottom** (HIG): people move windows so the bottom edge hides. ClearDesk's bottom tools bar only holds secondary things (link-file status, Data / Appearance / Help menus that open upward, a counts footer).
- **Width:** 300 default, 260–480, draggable, double-click resets, arrow keys when the divider is focused; per device. 260 is what the bottom bar needs in its widest state: re-measure if it grows.

### 19.2 The mode switch (top-level areas without a tab bar)

On desktop the app's three areas (Tasks, Notes, Prompts) are a **three-segment icon control** in the sidebar header, beside the sidebar toggle: segments **40 × 28**, 18px outline icons (circled check, note, curly braces), the selected one a filled capsule, a tooltip and `aria-label` each (with the shortcut: ⌥⌘1 / ⌥⌘2 / ⌥⌘3). It replaces a tab bar. Don't stretch it across the sidebar; size it to its icons. (On a compact screen this becomes a real tab bar, see 19.6.)

### 19.3 Search

A capsule field at the top of the sidebar: magnifier at the left, placeholder says what is searched ("Search tasks…", "Search notes…"). `/` focuses it from anywhere (outside text fields). A search covers **every** folder and is titled "Search results" (it ignores the folder filter); typing opens the first result when the current item is not one; matches are highlighted in the text (a CSS highlight, nothing added to the note).

### 19.4 The window bar (toolbar), one per column

**ClearDesk:** every column starts with its own **52px bar** and a hairline under it, so the baselines line up across the sidebar header, the list header and the editor toolbar. There is no top app bar and no window title bar.

HIG toolbar layout (follow it when building a bar):
- **Leading:** sidebar toggle, then the view **title** (a word or short phrase, **under ~15 characters**; never the app name; leave it empty if the content already says it, as Notes does).
- **Centre:** the common controls for the content.
- **Trailing:** things that must always stay visible: buttons that open an **inspector**, search, the **More (⋯)** menu, and **one primary action** (Done / Save / Copy) at the far end.
- **At most three groups**, each a joined capsule; keep text-labelled buttons apart from icon buttons; prefer symbols **without borders** (the group's capsule is the container); don't tint bars.
- **Overflow:** define what moves into the ⋯ menu as the bar narrows; don't create layouts that overflow by default. Every toolbar command must also exist as a menu command (in a web app: in a ⋯ menu or the Shortcuts list).
- **ClearDesk's main bar:** title (22 / 700, `-0.01em`) with a 12px subtitle ("3 open · 1 overdue", plus "· K selected" for two or more) · selection capsule (Complete, Priority ▾, Due ▾, Move ▾ | Duplicate, Delete; disabled with no selection, acting on the whole selection through the same code path as the context menu) · **Filter** button (shows a count; a ✕ clears) · **view switch** (List | Board, segmented) · **Sort** pull-down (shows the base key). The board adds a **group-by** segmented control (Project | Status).
- **Filters** live in a popover from the Filter button (chips inside), not in the sidebar.
- **Rules:** icon-only buttons have tooltips and `aria-label`s; a disabled button stays visible (a toolbar is not a menu; do not hide toolbar items, only dim them).

### 19.5 Current-location cues and state

- Where am I: the active sidebar row + the bar title + the subtitle + the highlighted list selection.
- **Restore** the last view, filters and open item per device on launch (not synced).
- **No back/forward and no breadcrumb:** the hierarchy is flat. Closing the detail panel (✕ or Esc) is the way back. If your app has a drill-down, use the standard **Back chevron** (a round icon button, never a text "Back") and show the parent's title.
- An item's folder is shown as a path in its meta line when it matters.

### 19.6 Compact screens and mobile (HIG only, not built or tested here)

- **Tab bar** for top-level sections: use it for **navigation, never actions**; ≤ 5 tabs; every tab has an **icon and a one-word label** (icon above label in compact, side by side in regular); never hide or disable a tab (explain an empty section instead); badges only for critical information; avoid an overflow "More" tab. Prefer a tab bar first on phones; where there are many areas, use the **adaptable** form that converts to a sidebar on a wide screen (iPad).
- **Navigation bar** (the toolbar's top bar on phones): a **large title** that shrinks when you scroll, the standard Back chevron at the leading edge, actions at the trailing edge, a search field below or in a dedicated search tab.
- **Split views** need a regular width; on a compact width use **push navigation** (list → detail → back) and present the inspector as a **sheet**.
- **Detail edits** that were a docked panel on desktop become a sheet with Cancel (leading) and Done (trailing).
- **Hit targets:** 44×44pt default, 28×28 minimum on touch (macOS: 28 / 20).

---

## 20. A flexible layout system (Xcode, Pages, Mail, System Settings)

ClearDesk's window is one fixed arrangement (sidebar | list | editor | inspector). To support other kinds of apps, treat the window as a set of **regions** that any app can choose from, arrange and collapse, using the same rules everywhere. Sources: HIG *Split views*, *Sidebars*, *Panels*, *Toolbars* (fetched); how Xcode, Pages, Keynote, Mail and System Settings arrange regions is from general knowledge of those apps (not verified against documentation here). **ClearDesk** shows the three-pane and the board + docked panel versions in practice.

### 20.1 Regions

| Region | Role | Examples | Typical size |
|---|---|---|---|
| **Toolbar** | commands, title, search, inspector toggles | every app | 52px tall (per column) or one for the window |
| **Navigator / Sidebar** | top-level navigation; selection leads to the next pane | Finder, Mail, Xcode's navigator, Pages' thumbnails | 220–300 (ClearDesk 300, 260–480) |
| **List / Content list** | the items of the selected collection | Mail's message list, Notes' list | 280–320, 200–600 |
| **Canvas / Editor** | the primary content; takes all remaining width | a note, a document page, Xcode's code editor | flexible, text capped at ~900px for reading |
| **Inspector** | details and settings for the **current selection**, updates as it changes | Pages' Format, Xcode's inspectors, ClearDesk's Variables panel | 260–340 (ClearDesk 340, 260–560; the task panel 420) |
| **Bottom panel** | a secondary working area under the canvas | Xcode's debug area/console, a timeline, a terminal | 120–300 tall, draggable |
| **Tab strip / jump bar** | switching between open documents or locating inside one | Xcode's editor tabs and jump bar, a browser | 28–32px tall |
| **Status / footer bar** | counts, zoom, state | Pages' word count and zoom, ClearDesk's counts | 24–32px tall |
| **Floating panel / HUD** | quick, non-modal controls over the content | Fonts, Colors, an Inspector window | 240–340 wide |

### 20.2 Layout patterns (which regions each uses)

```
A  Source list + content          (Finder, System Settings, a library)
   ┌ toolbar ───────────────────────────┐
   │ sidebar │ content                  │
   └────────────────────────────────────┘

B  Three-pane                      (Mail, Notes, ClearDesk's Notes/Prompts)
   │ sidebar │ list │ editor ─ [inspector] │

C  Document                        (Pages, Keynote)
   ┌ toolbar: insert groups · title · inspector toggles ┐
   │ navigator (thumbnails) │ canvas │ inspector (tabs) │
   └ status: zoom, counts ──────────────────────────────┘

D  Workbench / IDE                 (Xcode)
   ┌ toolbar: run controls · activity · view toggles ───┐
   │ navigator │ tab strip + jump bar │ inspector       │
   │ (tabs of  │ editor (can split)   │ (tabs)          │
   │  navigators)├────────────────────┤                 │
   │           │ bottom panel (debug)  │                 │
   └────────────────────────────────────────────────────┘

E  Settings                        (System Settings)
   │ sidebar (search) │ grouped rows (title on the right) │

F  Board + docked detail           (ClearDesk's Tasks; Kanban apps)
   │ sidebar │ board columns ─ [detail panel 420] │

G  Compact single column           (phones, narrow windows)
   one pane at a time; push navigation; tab bar; sheets for detail/inspector
```

Pick one pattern as the **base** and let the others be modes of it. A document app (C) and an IDE (D) differ mainly in whether the navigator holds *one* kind of thing and whether a bottom panel exists.

### 20.3 Rules that hold for every region

1. **Every region is collapsible** by (a) a button in the toolbar (leading edge for the navigator, trailing edge for the inspector, the bar's own edge for the bottom panel), (b) a command in a menu, (c) a keyboard shortcut (ClearDesk: ⌥⌘S sidebar, ⌥⌘I inspector; Xcode uses ⌘0 / ⌥⌘0 / ⇧⌘Y for navigator / inspector / debug area). **Provide more than one way to bring it back** (HIG), and don't hide the navigator by default on wide windows.
2. **Every divider is thin (1px) with a 4–6px invisible hit strip** (HIG: prefer the thin divider; keep it visible, so set minimum sizes); dragging resizes, double-click resets, arrow keys nudge (16px, Shift 48), focus ring on the strip. Clamp every size with a **min and max** (and the editor keeps ≥ 380px next to an inspector).
3. **The canvas takes the flexible width.** Fixed-width regions use CSS variables; the canvas is `minmax(0, 1fr)` so it can shrink and scroll. Cap line length for reading (~900px for text).
4. **Remember layout per device**: widths, which regions are open, the last open item. Never sync it.
5. **Collapse in priority order as the window narrows**: the inspector goes first (it floats over the canvas, then hides), then the list column narrows, then the navigator floats over the content with a scrim-free shadow. Use container queries on the region's container, not just the viewport. The toolbar gives way in steps (insert buttons → one menu → icon-only → ⋯ overflow).
6. **Floating** regions sit on top of the content with a shadow, close on Esc or a click on the content, and do not change the saved open/closed choice.
7. **Selection in each pane is persistently highlighted**, and it is accent-coloured only in the pane that has focus (section 3).
8. **Inspectors follow the selection** (they update as it changes); a window that always shows the same item is a window, not an inspector (HIG *Panels*). Prefer a split-view pane to a floating panel for an inspector in a single-window app.
9. **Panels (floating windows) are for repeated adjustment of the selection with simple controls** (sliders, steppers); they are titled with a noun ("Fonts", "Inspector"), hide when the app is inactive, and are not listed as documents.
10. **Each region has an empty state** (an icon, a title-style label, at most one action).
11. **Focus zones:** keyboard focus moves between regions with a predictable key (ClearDesk: Tab in dialogs, arrow keys to cross from the quick-add field into the list); the active region owns the arrow keys; text fields own them while they have the cursor.
12. **Tab strip** (documents): a segmented row of titled tabs with a close ✕ on hover, the active tab on the content colour and the others on `--bg-2`; a dot for unsaved changes; ⌘W closes, ⌃Tab cycles; never more than the width allows (scroll, don't shrink below ~96px). *Not built in ClearDesk.*
13. **Bottom panel:** collapsible, draggable height, remembers its height; carries its own small toolbar (filter, clear, close) so it never needs the window toolbar. *Not built in ClearDesk.*

### 20.4 A skeleton to start from (CSS)

```css
.window { display: grid; height: 100vh;
  grid-template-columns: [nav] var(--nav-w, 0px) [list] var(--list-w, 0px) [canvas] minmax(0, 1fr) [insp] var(--insp-w, 0px);
  grid-template-rows: [bar] 52px [body] minmax(0, 1fr) [bottom] var(--bottom-h, 0px) [status] var(--status-h, 0px); }
.region { min-width: 0; min-height: 0; overflow: hidden; }
.region[hidden-by-user] { display: none; }
/* below a width, a region floats instead of taking a column */
@container window (max-width: 900px) { .region.insp { position: absolute; right: 0; top: 52px; bottom: 0; width: min(340px, 100%); box-shadow: var(--elev-3); } }
.divider { position: relative; width: 1px; background: var(--border); }
.divider::before { content: ""; position: absolute; inset: 0 -3px; cursor: col-resize; }   /* the 6px hit strip (the resize cursor is the one exception to "arrow everywhere") */
```
Describe a window in data so apps can differ without new CSS:
```js
const layout = { regions: [
  { id: 'nav',   side: 'leading',  size: [220, 300, 480], collapsible: true, key: 'Alt+Cmd+S', floatBelow: 800 },
  { id: 'list',  side: 'leading',  size: [200, 300, 600], collapsible: true, floatBelow: 700 },
  { id: 'canvas', side: 'center' },
  { id: 'insp',  side: 'trailing', size: [260, 340, 560], collapsible: true, key: 'Alt+Cmd+I', floatBelow: 740 },
  { id: 'debug', side: 'bottom',   size: [120, 200, 400], collapsible: true, key: 'Shift+Cmd+Y' } ],
  hideOrder: ['insp', 'list', 'nav'] };            // what goes first when the window narrows
```
A small layout function reads this, writes the CSS variables, persists them per device, installs the toggles and shortcuts, and applies `hideOrder`.

### 20.5 Mapping from app type to pattern

| App type | Pattern | Regions | Notes |
|---|---|---|---|
| Notes, mail, prompts | B | nav, list, canvas, optional inspector | ClearDesk Notes / Prompts |
| Task manager with a board | F (or B) | nav, canvas (list or board), docked detail | ClearDesk Tasks |
| Document editor (text, slides) | C | toolbar with insert groups, thumbnails navigator, canvas, format inspector, status bar | zoom and counts in the status bar |
| Code / data / design workbench | D | navigator with switchable tabs, tabbed editor, inspector, bottom panel | add the tab strip, jump bar and bottom panel from 20.3 |
| Settings or a configuration screen | E | sidebar of topics, grouped rows | ClearDesk's Help / Shortcuts windows |
| Phone or narrow window | G | one pane, tab bar, sheets | see 19.6 |
