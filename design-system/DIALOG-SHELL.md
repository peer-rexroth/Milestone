# Dialog shell (ClearDesk) — how to apply it in another app

Two shells, each with one job. Anything you fill in is a **sheet**; anything that asks a question is an **alert**.
Windows with their own sidebar (Help, Shortcuts, About, a settings panel) are neither: they keep their own layout.

| | Sheet (`.modal`) | Alert (`.modal.alert`) |
|---|---|---|
| Use for | New / edit forms, pickers, link / file dialogs | Confirm, destructive confirm, "Import: replace or merge?" |
| Header | Left-aligned title (17 / 600) + optional one-line subtitle (13, tertiary). **No header icon** | Round 40 px tinted icon, centred title, centred sentence |
| Body | Fields / grouped list | One or two sentences |
| Buttons | Trailing: Cancel, then the primary | Full-width, side by side, centred: Cancel (or the safe choice), then the action |
| Width | 380 (420 with a list) | 340 (400 with three buttons) |

## 1. CSS (needs your colour tokens: `--accent`, `--accent-tint`, `--danger`, `--text-2`, `--text-3`, `--r-xl`; see `tokens.css`)

```css
.modal { padding: 24px; width: 380px; max-width: 90vw; display: flex; flex-direction: column; gap: 16px; }
.modal h3 { font-size: 17px; font-weight: 600; }
.modal p  { font-size: 14px; color: var(--text-2); line-height: 1.6; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }

/* sheet header: title + optional subtitle */
.modal-head h3 { font-size: 17px; font-weight: 600; }
.modal-head p  { margin-top: 2px; font-size: 13px; color: var(--text-3); line-height: 1.4; }

/* alert */
.modal.alert { width: 340px; text-align: center; align-items: center; gap: 12px; padding: 24px 24px 20px; }
.modal.alert.alert-wide { width: 400px; }                         /* three buttons */
.alert-ico { width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
             background: var(--accent-tint); color: var(--accent); }
.alert-ico.danger { background: color-mix(in srgb, var(--danger) 14%, transparent); color: var(--danger); }
.modal.alert .modal-actions { align-self: stretch; justify-content: center; margin-top: 8px; }
.modal.alert .modal-actions .btn { flex: 1; justify-content: center; }

/* a confirmation sits above any other dialog */
#confirmModalBg { z-index: 210; }                                  /* other dialog backdrops are 200 */
```

The surface (background, 1px hairline, 16 px radius, shadow, blur) is whatever your menus and popovers already use; the
shell does not define one.

## 2. Markup

```html
<!-- sheet -->
<div class="modal" role="dialog" aria-modal="true" aria-labelledby="t">
  <div class="modal-head"><h3 id="t">Link a data file</h3><p>Keep the app in sync across devices.</p></div>
  …fields or a grouped list…
  <div class="modal-actions"><button class="btn">Cancel</button><button class="btn btn-primary">Create</button></div>
</div>

<!-- alert -->
<div class="modal alert" role="alertdialog" tabindex="-1" aria-modal="true" aria-labelledby="ct" aria-describedby="cb">
  <span class="alert-ico danger" aria-hidden="true"><!-- 20 px outline icon --></span>
  <h3 id="ct">Delete this note permanently?</h3>
  <p id="cb">It will be removed for good. This cannot be undone.</p>
  <div class="modal-actions"><button class="btn">Cancel</button><button class="btn btn-danger">Delete</button></div>
</div>
```

Icons: a destructive alert uses the trash (or a warning triangle for "Discard changes?"), a plain one an info circle;
a sheet has none in its header (icons live inside its list rows).

## 3. Behaviour (what makes stacking work)

1. **The confirmation closes alone.** Esc, Cancel, a click outside it and its own button close *only* the alert
   (`closeConfirmModal(cancelled)`); never "close all dialogs" from it. The dialog that asked stays open underneath.
2. **Esc closes the top dialog first.** Global Esc handler, before anything else: if the alert is open, close it and
   return. A dialog that guards unsaved edits (Compare) must also catch Esc itself, wherever the focus is, and ask
   through the alert instead of closing.
3. **Return focus** to what had it when the alert opened (keep this separate from the parent dialog's own
   "return focus" variable, or the alert overwrites it).
4. **Destructive alerts have no default button** (focus goes to the dialog, Return does nothing, Esc cancels); a
   non-destructive one focuses its action. The first button is the safe one and is labelled for what it does
   ("Keep Editing"), not always "Cancel".
5. The confirm API takes `{title, body, confirmLabel, cancelLabel, icon, danger, action, onCancel}`; the dialog that
   asked passes `onCancel` to clear its own "asking" flag.

## 4. What to change in an existing app

- Give every confirmation and "choose one of these actions" dialog the alert markup; delete any inline confirm bar a
  dialog built for itself.
- Remove icons from sheet headers; make the title weight 600 everywhere (no 700 / letter-spacing variant).
- One gap (16) and one padding (24) for every `.modal`.
- Move the confirm backdrop to the higher z-index and change its close path (point 1 and 2 above).
- Leave sidebar-style windows alone.
