---
name: posterly
description: "Build an academic conference poster (ICML/NeurIPS/ICLR/CVPR/etc.) as a single HTML/CSS file and render it to print-ready PDF via headless Chromium. Use when user says \"做海报\", \"poster\", \"ICML/NeurIPS/ICLR poster\", or asks to design/edit a research poster."
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, AskUserQuestion, WebFetch, WebSearch
---

# posterly — HTML/CSS Academic Poster Workflow

A poster is **one HTML file** styled for an exact print canvas, rendered to PDF via Playwright + Chromium. Iterate by **measuring**, not eyeballing — the screen preview lies; only `emulate_media("print")` at the correct viewport tells the truth.

## Mental model

```
   HTML (with @page { size: W H })
     │
     ▼  print-emulate Chromium at W×96 × H×96 px viewport
     │
     ▼  data-measure-role tags identify columns/hero/footer-strip
     │
     ├──→ tools/poster_check.py measure  (HARD GATE — spread < 5 px,
     │                                    gap-to-strip ∈ [30,50] px,
     │                                    poster bbox aligns to page
     │                                    within ±2 px)
     ├──→ tools/poster_check.py preflight  (LaTeX residue, math `<`, missing imgs)
     ├──→ tools/render_preview.py  (PDF + thumbnail)
     └──→ tools/poster_check.py verify-final  (PDF page count / dims / size)
```

The skill is venue- and lab-neutral by default. Pick a template from `templates/README.md`, edit `:root` design tokens for your colors, fill TODO placeholders with your paper's content.

## Canvas constants

| Constant | Value | Notes |
|---|---|---|
| `--u` (CSS unit) | print = `1mm`, screen = `1.6px` | Use `calc(N * var(--u))` for ALL sizing. |
| Print viewport (px) | `W_in × 96` × `H_in × 96` | Computed by `poster_check`/`render_preview`. |
| Body cols | 2 / 3 / 4, or 1 hero + 1 column | Per template. |
| Strict alignment | **spread < 5 px** (aim < 3) | Hard, non-negotiable gate. |

## Workflow

### Step 0 — Pull the venue's official poster guidelines

Conference specs change year-to-year and vary wildly between venues:

- ICML often goes 60×36 in landscape; **ICLR has been 24×36 in portrait** in recent years; **NeurIPS** historically allowed multiple sizes; **CVPR** has used A0 portrait. Don't assume.
- Font minimums (≥24pt body for some venues), bleed margins, allowed orientations, on-poster logos, anonymity rules, QR-code policies — all vary.

Procedure:
1. `WebSearch` for `"<venue> <year> poster instructions"` or `"<venue> <year> poster size"`.
2. `WebFetch` the venue's official page; extract **dimensions, orientation, font-size floor, logo policy, anonymity rules, file-format requirement, template link if any**.
3. If paywalled or down, check OpenReview's call-for-papers or ask the user for the relevant section.
4. Echo the extracted spec back to the user in one short table **BEFORE** drafting. Confirm before proceeding — a wrong canvas size invalidates every alignment decision downstream.

### Step 0.5 — Design discovery (one round of AskUserQuestion)

Don't pick a template silently. Ask the user, in one batch:

- **Layout**: "Which gallery template fits best? (a) 4-column landscape, (b) hero + supporting column landscape, (c) 2-column portrait." Show them `templates/README.md`'s table.
- **Palette**: "Lab/venue colors? E.g. `#XXX` accent + `#YYY` highlight. Default = neutral slate-blue + gold."
- **Logos**: "Which logos to include? Paths or URLs."
- **Corresponding-author marker**: "Which author gets `✉`? Any starred (`★`) co-authors?"

Persist the user's answers as you go — re-reading them later prevents "improvement" loops that revert deliberate decisions.

### Step 1 — Confirm content & figures

Once layout is picked, ask once:
- **Source paper** path (`paper-overleaf/.../main.tex` ideal). Read the abstract, intro, headline results. Don't draft from memory — pull actual numbers, dataset names, equations.
- **Figures**: match `images/` filenames to paper figures.
- **Items to preserve/exclude**: which sections to drop, any "do not revert" notes.

### Step 1.5 — Content audit (strongly recommended)

Before laying out, the draft must be audited for paper-to-poster fidelity. Past sessions caught real bugs ONLY here — paper said "20× fewer" but the table gave 16×, "fewest trajectories" was an overclaim vs the actual baselines, theorem preconditions were silently dropped. Skip this and you will discover errors only when standing next to the printed poster.

**How to run it (in order of preference):**

1. **External LLM reviewer with file access (best).** If you have Codex MCP, GPT-5 with file access, another Claude session, or any reviewer that can `Read` paper source files, use that. Recommended defaults if you have Codex MCP: `model="gpt-5.5"`, `model_reasoning_effort="xhigh"`, `sandbox="danger-full-access"` (read-only audit). Send the evidence pack + reviewer prompt below.

2. **Self-audit (fallback).** Walk every numeric claim on the poster and find its `file:line` in the paper source. Build the claim → evidence table by hand. Slower, easier to miss things, but better than skipping.

**Evidence pack the reviewer needs:**
1. The current `poster.html` (full)
2. Paper source path(s) so the reviewer can `Read` the `.tex` and any `results/` CSVs
3. For every numeric claim, the paper `file:line` where the number originates
4. For every theorem/claim, the paper statement verbatim with all preconditions

**Reviewer prompt template** (use this verbatim, fill bracketed parts):

```
Audit the academic-poster draft at [poster.html abs path] against the paper at [main.tex abs path] (and any results in [results dir]). For every number, claim, theorem, dataset name, and method-comparison on the poster, produce a claim → evidence table:

  | claim on poster | paper file:line | paper says (verbatim) | match? |

Mark "match?" as: OK / NUMERIC-MISMATCH / OVERCLAIM / MISSING-PRECONDITION / NOT-IN-PAPER / SCOPE-NARROWED.

Then list every NON-OK row as a problem to fix before printing. Be skeptical — "all <method> methods" claims, "best by Nx" claims, and theorem statements without their epsilon/regularity preconditions are the most common silent errors.
```

You may proceed to Step 2 **only after every finding is either fixed or explicitly recorded as "user-acknowledged tradeoff"**. Do not silently defer.

### Step 2 — Image preprocessing (optional but reduces re-renders)

For each paper figure you'll use:

1. **Autocrop whitespace** with PIL.ImageChops so the figure fills its card.
2. **Re-export at ≥ 2× the rendered px**. A `200u × 120u` figure print-rendered at 96 ppi → ~756 × 454 px. Source PNGs must be ≥ 1500 × 900 to look crisp at print.
3. **QR codes**: request at ≥ 2× rendered px (e.g., 480×480 if displayed at ~240 px).

### Step 3 — Scaffold from the gallery

1. `cp templates/<chosen>.html <work-dir>/poster.html`.
2. Edit the `:root` design tokens (single block; affects everything).
3. Replace `<title>`, header (title/subtitle/authors/affiliation), banner (if any), column cards, takeaways strip (if any), footer.
4. Match the template's `data-measure-role` scheme — DO NOT remove these attributes. The measurement script depends on them.

Tools live in `tools/` and read `@page` from the HTML, so they're canvas-agnostic — the same commands work for ICLR portrait and ICML landscape.

### Step 4 — Render + measure loop (HARD GATE)

```bash
# After every layout change:
python <skill>/tools/poster_check.py measure poster.html
```

Targets (defaults; configurable via flags):
- **`spread < 5 px`** across the last-card-bottoms of all columns (+ any hero panel). Aim `< 3 px`.
- **`gap to footer-strip/footer ∈ [30, 50] px`** — card shadow visible but cards don't float.
- **`position align ≤ 2 px`** (authoritative) — the `[data-measure-role="poster"]` bounding box must sit at `(0, 0)` to `(viewport_w, viewport_h)` within `--position-tol-px`. This IS the full-canvas requirement: a poster whose bbox aligns to the page is necessarily full-bleed. Catches `transform: translate*`, mis-positioned `position: absolute`, stray body margin in print, and CSS source-order cascade bugs where a screen rule wins over a print override.
- **`canvas-fill ∈ [95 %, 101 %]`** (coarse early diagnostic) — `[data-measure-role="poster"]` width/height ratio against the print viewport. Fires before the position check when the ratio is FAR off, with a more diagnostic error message that points at the common `@media print { :root { --u: 1mm } }` omission (renders at ~42 %) or hardcoded `width > @page` (renders at >100 %). For borderline 95–99 % cases, position-align is the truth. Tune via `--min-canvas-fill` / `--max-canvas-fill`. **Safe-area design** belongs as internal padding on a full-bleed `.poster`, NOT as a smaller poster — a smaller poster fails position-align.

**This gate is non-negotiable.** If `measure` exits non-zero, fix the layout — do NOT continue to render. Common fixes:
- spread > 5: shrink the column with the lowest last-card by reducing a paragraph's `margin-bottom` by 1u, trimming one line, or shrinking a fixed-height figure by 5u.
- gap > 50 everywhere: body-grid is too tall; grow a card or accept whitespace.
- gap < 30 anywhere: banner/header outgrew its slot; check `.framework-banner` rendered height.
- position misaligned (the usual full-canvas failure): make `.poster` full-bleed (`width: 100%; height: 100%; margin: 0; padding: 0` in `@media print`); remove any `transform: translate*` or `position: absolute` offsets; ensure `html, body { margin: 0; padding: 0 }` in the print media query; and check that the print `@media` block comes AFTER the screen `.poster` rule so source-order cascade resolves the print override winning.
- canvas-fill < 95 % (diagnostic fired first): poster forgot `@media print { :root { --u: 1mm } }` so it renders at screen scale. Add the override.
- canvas-fill > 101 % (diagnostic fired first): hardcoded `width: 1600px` (or similar non-`--u`-based size) exceeds `@page`. Replace with `calc(N * var(--u))`.

`poster_check.py measure` also has these safety nets (so a false PASS shouldn't happen):
- Missing `[data-measure-role="poster"]` = hard fail.
- Empty columns = hard fail (override: `--allow-empty-column`).
- Missing footer-strip AND footer = hard fail (override: `--allow-no-footer-gap`).
- MathJax intended (a `<script src="…mathjax…">` tag or `window.MathJax` config is present) but no `<mjx-container>` rendered, while TeX delimiters (`$…$` / `$$…$$` / `\(…\)` / `\[…\]`) remain in body text = hard fail (CDN block, script error). A page that just *describes* TeX syntax in prose without ever loading MathJax is NOT failed.
- MathJax typeset timeout = hard fail (override: `--mathjax-timeout-ms`).
- `@page` size missing AND no `--canvas` override = exit 2.

Run preflight in parallel:

```bash
python <skill>/tools/poster_check.py preflight poster.html
```

Catches: LaTeX residue (`\ref{`, `\cite{`, `\textbf{`, lone `\ `), bare `<` inside `$…$` math (MathJax mis-parses as HTML tag), missing local images, missing `data-measure-role="poster"`, unknown role values.

### Step 5 — Render + visual inspection

```bash
python <skill>/tools/render_preview.py poster.html
pdftoppm -r 100 poster_preview.pdf poster_check -png -f 1 -l 1
# then Read the resulting PNG
```

For dense regions, crop with PIL and read the slice — full poster at r=100 is ~6000 px wide; useful regions (header, banner, takeaways, one column) at full res reveal text wrapping issues invisible in the thumbnail.

### Step 6 — Polish

After alignment is solid, run the **visual polish gate**:

```bash
python <skill>/tools/poster_check.py polish poster.html
```

This is a **soft** gate (exits 0 by default; pass `--strict` to fail on warnings). It surfaces three failure modes that the hard alignment gate cannot see — figure sizing relative to its aspect ratio, typography orphans, and column whitespace pretending to be balance. See **§Visual polish gates** below for the rule for each WARN class and the correct fix. Fix every WARN unless you explicitly judge it acceptable for this poster.

Other polish:
- **`text-wrap: balance`** on banner/takeaways prose — fixes ragged-right and single-word-orphan lines.
- Match QR visual height to adjacent institutional logo (same `--u` value).

**Step 6.5 — Final review (strongly recommended)**: send the rendered PDF (or its high-res PNG slices) AND the HTML to the same kind of reviewer used in Step 1.5 (external LLM if available, self-audit otherwise). Same evidence-pack rule. The reviewer prompt focuses on three things distinct from Step 1.5:
1. **Visual rhetoric**: does the poster's narrative carry? Are the headline numbers prominent? Is the framework banner readable from 2 m?
2. **Residue**: any `\ref{`, `\cite{`, leftover `TODO`, raw `<` in math, missing image, broken QR link.
3. **Final claim audit**: re-check numbers and overclaims AFTER content has been polished — polish often introduces new claims ("a key advantage of…") that were not in the original draft.

Fix every finding before declaring the poster done.

### Step 7 — Final verification

```bash
python <skill>/tools/poster_check.py verify-final poster_preview.pdf \
    --canvas 60x36in --max-size-mb 20
# or read the expected canvas from the companion HTML:
python <skill>/tools/poster_check.py verify-final poster_preview.pdf \
    --from-html poster.html
```

Checks: page count == 1, dimensions match canvas, file size ≤ limit. `--canvas` accepts inch dimensions (`60x36in`) or named sizes (`A0 portrait`, `A1 landscape`). By default rejects swapped W/H unless the PDF declares `Page rot ∈ {90, 270}` or you pass `--allow-rotated`. `--from-html <path>` reads `@page { size: … }` from the HTML so they can't drift apart.

Then report to the user:
- File path of PDF
- Final spread (px) and gap-to-footer range
- Any unresolved Codex feedback
- Page-fit confirmation

## Visual polish gates (Step 6 — soft gate)

Alignment passes but the poster can still look amateur. These three failure modes recurred across sessions enough to be promoted to first-class checks. `tools/poster_check.py polish` surfaces each as a WARN; the rules below explain how to fix.

### Gate A — Figure sizing by aspect ratio

A figure too small for its column is more wasteful than one too big. Pick width by the figure's intrinsic aspect ratio (`AR = naturalWidth / naturalHeight`), NOT by a fixed default:

| AR range | Shape | Aim for | `polish` warns below / above |
|---|---|---|---|
| `AR > 1.3` | Wide (workflow diagram, comparison chart) | **70–100%** of card width | < **65%** ⇒ FIG/WIDE. **Do NOT use image-left/text-right** in a narrow column — text gets squeezed to nothing. |
| `0.8 ≤ AR ≤ 1.3` | Square-ish (block diagram, scatter) | **55–75%** of card width | < **55%** ⇒ FIG/SQUARE. |
| `AR < 0.8` | Tall (multi-series bar, long pipeline) | **45–60%**, paired with **text-right** | > **70%** at full width ⇒ FIG/TALL (recommends side text). |

Thresholds are tunable via `--wide-min-ratio` / `--square-min-ratio` / `--tall-max-ratio`. The defaults are the "aim for" lower bound, so anything inside the documented "aim for" range passes the gate cleanly.

A figure whose `<img>` fails to load (missing file, 404, or unreachable remote URL) reports zero natural size and warns as **FIG/BROKEN** — it will be blank in print. SVGs are exempt (they legitimately report zero intrinsic size); the probe covers card `<img>` only, not the hero panel image.

Concrete bad case (prior session): `co-consideration.png` (AR ≈ 1.41) shipped at 41 % column width. The whitespace beside it conveyed nothing and the figure was unreadable from 2 m. Fix: 66 % width, no text-right.

### Gate B — Typography orphans

`measure` checks card bottoms; it does NOT see a `↑` or superscript that wrapped alone onto its own line — a small but jarring artifact 2 m away.

Known orphan-prone patterns:
- Stat numbers with trailing arrows: `1.18–1.30× ↑`, `18.24% ↓`
- Number + unit / multiplier: `4096 × 4096`, `7 nm`, `2248×`
- Trailing footnote markers: `BraVE*`, `MEAN§`

Defenses (preferred → fallback):

1. **`white-space: nowrap`** on the smallest element whose innerText must stay one line (`.stat-num`, `.hs-stat .num`, `.takeaway-num`). Blanket — text simply does not break.
2. **Non-breaking glue** between the last two tokens: `1.18–1.30×&nbsp;↑`. Use when nowrap would overflow a tight card.
3. **Reword to put the marker first**: `↑ 1.18–1.30× speedup` — arrow becomes the line's first token, can't orphan.

`polish` flags an element (`[class*="stat"], [class*="num"], .takeaway-num, .hs-stat, .headline-num`) only when its text **ends with a whitespace-separated trailing glyph** from `↑↓↔×÷±§¶†‡*°%` and lacks `white-space: nowrap` — i.e. a lone glyph token that could wrap by itself, like `1.18–1.30× ↑` or `18.24% ↓`. It does **not** catch fused forms such as `4096 × 4096`, `7 nm`, `2248×`, `BraVE*`, or `MEAN§` (the text doesn't end on a space-separated glyph) — guard those by hand with the defenses above.

### Gate C — Content-driven balance, not space-between-driven

`justify-content: space-between` on a column is a shortcut to bottom-align last cards across columns. It works ONLY when the cards' natural heights are within ~5% of each other. When they aren't, space-between fills the delta with empty pixels — usually one giant gap in the column with the smallest content.

**Symptom**: a column with one short card followed by 25 + mm of whitespace. Reads as "this column ran out of things to say".

**Wrong fix**: shrink `gap` globally to hide the whitespace. Peers still have meaningful internal gaps; reducing them makes the others claustrophobic.

**Right fix**: ADD MEANINGFUL CONTENT to the short column until it's within ~5 % of its peers' natural height. From the paper, recover:
- Sub-claims that were footnotes or implicit assumptions
- A 2–3 bullet "challenges" or "design choices" recap
- A short caption beside a previously-bare figure

Concrete bad case (prior session): the SnipSnap Motivation column shipped with a one-line "three challenges" summary, leaving a 13 mm space-between gap. Fix: expanded into 3 bullets matching the paper's challenge framing — column balanced via content, not whitespace.

`polish` warns when a column with computed `justify-content: space-between` has an inter-card gap exceeding 5 % of the column's height (i.e., space-between is doing more work than the column gap CSS suggests). Tune via `--max-space-between-fill`.

## Universal pitfalls (apply to all templates)

1. **`<` raw in MathJax inline** → may be HTML-parsed before MathJax sees it (mode-dependent). Prefer `\lt` everywhere. Preflight catches `(?<!\\)<(?![=/!])` inside `$…$` / `$$…$$` / `\(…\)` / `\[…\]` — i.e. raw `<` NOT preceded by a backslash and NOT followed by `=` / `/` / `!`. The `<=` case is intentionally exempt (single MathJax token, parsed atomically — no HTML-tokenizer ambiguity); preflight stays quiet about it, but `\le` reads more naturally in print.
2. **`\ ` (backslash-space) from LaTeX** → renders literally. Strip when porting from `.tex`. Preflight catches.
3. **Screen-mode measurement is misleading.** Always use `tools/poster_check.py measure` — never eyeball the screen render.
4. **Pre-compact `\\ ` and lone `<`** — preflight catches before render.
5. **`text-wrap: balance` needs Chromium ≥ 114** — Playwright's bundled Chromium is fine.

## Layout-shared pitfalls (column-based templates)

6. **`overflow: hidden` on `.body-grid` clips card shadows.** If last card sits at body-grid bottom, its 30-px shadow is cut and visually merges into the strip below.
7. **`padding-bottom` on `.column` does NOT push cards down.** Cards stack from top in flex; padding-bottom only reserves space. To shrink, edit card content directly.
8. **Title-block can dominate header height.** Shrinking logos/QR doesn't help if `.title-block` is already the tallest cell.
9. **Banner can grow from `.banner-stats`.** Big numbers cascade into body-grid shrinkage.
10. **`box-shadow: 0 2u 6u` extends ~30 px** below the card. Final last-card-bottom must be ≥ 30 px above the strip below.
11. **Image-left + text-right inside a narrow column wastes the image.** For wide images in narrow cols, keep image-on-top + caption-below.

## When to call an external LLM reviewer (three checkpoints)

The skill works fine without one, but a second pair of eyes reliably catches paper-to-poster fidelity bugs you'll otherwise discover next to the print station. Three natural checkpoints:

1. **Content critique** (Step 1.5) — does the poster's prose / numbers / claims match the paper?
2. **Theorem & equation pass** (after Step 3) — are theorem preconditions complete? Equations rendered correctly?
3. **Final polish** (Step 6.5) — fresh eyes on the assembled poster for residue and overclaims.

The bias is **send when uncertain**. Cost: 2-3 min. Cost of a silent error in a poster you'll print and stand next to for 2 hours: high.

**Recommended reviewer settings (if you have Codex MCP):** `model="gpt-5.5"`, `model_reasoning_effort="xhigh"`, `sandbox="danger-full-access"` (read-only review; the sandbox often fails to start in containers / nested namespaces and the audit is read-only anyway). Any other capable reviewer LLM that can `Read` paper files works equally well — see Step 1.5 for the canonical prompt template.

## Tools

```
tools/
├── poster_check.py   ← CLI: measure / preflight / polish / verify-final
├── render_preview.py ← CLI: print-emulated PDF + thumbnail PNG
└── _posterly/        ← internal modules (canvas parser, Playwright + settle, etc.)
```

- `poster_check.py`:
  - `measure` — **hard** alignment gate (column-bottom spread < 5 px, gap-to-footer in [30, 50] px, canvas-fill ∈ [95 %, 101 %] as a coarse diagnostic, and poster bbox aligns to the page within ±2 px — the bbox-alignment check is the authoritative full-canvas requirement).
  - `preflight` — static HTML lint (LaTeX residue, math `<`, missing images, role validation).
  - `polish` — **soft** visual gate (figure sizing by AR, broken images, typography orphans, space-between fill). Warns by default; `--strict` to fail. Hard-fails if the poster has no `[data-measure-role]` markup at all (silent PASS would be a worse bug).
  - `verify-final` — `pdfinfo`-based PDF sanity (page count, dimensions, file size).
- `render_preview.py` — Playwright print-emulated PDF + scaled PNG thumbnail.

All scripts read `@page { size: W H }` from the input HTML so the same code handles ICML 60×36 landscape, ICLR 24×36 portrait, CVPR A0, etc. without flags.

## Templates

See `templates/README.md` for the gallery. Current set:
- `landscape_4col_neutral.html` (60×36 in, 4 cols)
- `landscape_hero_neutral.html` (60×36 in, hero + supporting col)
- `portrait_2col_neutral.html` (24×36 in, 2 cols)

Adding a template: keep it neutral (no lab branding), preserve `data-measure-role` scheme, document the row in `templates/README.md`.

## Key rules

- **Never invent paper numbers.** Read the `.tex` source. Bench numbers, datasets, model names — all verifiable.
- **Card-shadow visibility is non-negotiable.** A poster looks cheap when shadows are clipped.
- **Strict alignment is non-negotiable.** Spread < 5 px or it's not done — do not report success until `measure` exits 0.
- **Preserve user-judgment decisions across sessions.** "Do not revert" notes (`✉ stays on Author X`, `α-sensitivity card removed`) — re-read the user's prior messages before "improving" a section.
