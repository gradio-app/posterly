# Templates gallery

Each template is a **self-contained, neutral** HTML file: no lab branding, no paper content — only TODO placeholders. Copy one to your working dir as `poster.html`, edit `:root` design tokens, swap TODOs for your content, then iterate via `tools/poster_check.py measure` + `tools/render_preview.py`.

Every layout-critical element carries `data-measure-role` so the measurement script can locate columns / hero / footer regions across templates.

## Picking a template

| Template | Canvas | Layout | Use when |
|---|---|---|---|
| **landscape_4col_neutral** | 60 × 36 in landscape | header → optional banner → **4 columns** → optional takeaways → footer | Standard ML conference poster (ICML / NeurIPS / generic). You have ~3–5 content cards per column. Mix of figures, equations, tables. The default choice. |
| **landscape_hero_neutral** | 60 × 36 in landscape | header → **hero panel (1.5fr)** + supporting column (1fr) → takeaways → footer | The paper's main figure or system diagram IS the visual hook. You want one big illustration on the left and 3–4 short cards on the right. No framework banner (hero replaces it). |
| **portrait_2col_neutral** | 24 × 36 in portrait | header → **2 columns** → footer (no banner, no takeaways strip) | ICLR / CVPR portrait spec, or any venue with portrait orientation. Vertical space is precious — banner + takeaways are dropped; final card on right column acts as a takeaways callout. |

## Adding a new template

A new template **MUST**:

1. Set `@page { size: <W>in <H>in }` (or `mm`/`cm`/`pt`) inside a `<style>` block — the canvas parser fails if absent.
2. Carry `data-measure-role="poster"` on the root poster element.
3. Use these roles consistently:
   - `header` on the title block
   - `banner` on a horizontal banner row (optional)
   - `body` on the body grid container
   - `column` on each vertical content column
   - `card` on each content card inside columns
   - `hero` on a hero panel (mutually-exclusive with framework banner)
   - `footer-strip` on a takeaways / highlight strip (optional)
   - `footer` on the bottom info bar (logos, QR, contacts)
4. Use the `--u` unit system (`1.6px` screen, `1mm` print) for ALL sizing via `calc(N * var(--u))` — never bare px except for hairlines.
5. Keep all paper-specific content as `TODO` placeholders — neutral templates only.

Add a row in the table above and link it in `SKILL.md` Step 3.
