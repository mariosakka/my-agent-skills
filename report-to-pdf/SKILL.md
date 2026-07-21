---
name: report-to-pdf
description: Render a Markdown report (headings, paragraphs, bullet/numbered lists, fenced code blocks, pipe tables, bold/italic/inline-code, optional YAML-ish frontmatter) into a polished, deterministically-styled PDF — title page with brand accent bar and optional logo, running header/footer, auto-generated back-filled Table of Contents, left-accent-bar section headings, shaded/bordered code blocks, and zebra-striped bordered tables. Use when the user wants to turn a markdown review/report/writeup into a client- or mentor-ready PDF, asks to "export this markdown as a PDF", "make this report look professional", "convert my .md to PDF", or wants the *same* fixed layout every time (no LLM-improvised formatting) for repeatable, brand-consistent document output. Same visual language as the ColeteOnline Magento user-guide PDF generator, just driven by parsing a real .md file instead of a hand-authored Python content list.
allowed-tools: Bash(python3:*) Read
---

# report-to-pdf — Markdown report to polished PDF

Deterministic, script-driven Markdown-to-PDF renderer. It parses a
constrained "report" Markdown subset with a small hand-rolled block
parser (no external Markdown library) and lays it out through fpdf2
with the same visual conventions as the ColeteOnline Magento module's
`build-user-guide.py` generator — title page, header/footer, TOC,
accent-bar section headings, shaded code blocks, bordered/zebra-striped
tables. The layout logic never changes between runs on the same input:
same report in, same-looking PDF out, every time — no LLM in the
render loop.

## When to use

- "Turn this markdown review into a PDF for the mentor."
- "Export my report as a polished PDF."
- "I want this every time to look the same, not re-formatted by an
  LLM each run."
- Any `.md` report/writeup that has headings, lists, code blocks, or
  tables and needs a client/mentor/brand-quality PDF version.

## How to run

```bash
python3 .claude/skills/report-to-pdf/scripts/build_report_pdf.py <input.md> [options]
```

Options:
- `-o / --output <path>` — output PDF path (default: `<input>.pdf`
  next to the source file).
- `--logo <path>` — optional logo image (PNG/WebP/JPEG, anything
  Pillow can open) centered on the title page.
- `--title`, `--subtitle`, `--version`, `--vendor` — override the
  corresponding frontmatter values (see below); CLI flags win.
- `--accent "R,G,B"` — override the accent color used for the title
  page's top bar and section-heading accent bars (default
  `220,50,50`, ColeteOnline red).

The script auto-installs `fpdf2` and `Pillow` via
`pip install --user` if either import fails, mirroring the reference
script's Pillow auto-install. Both were verified importable and the
script was run end-to-end during development (see Testing below).

## Markdown conventions it expects

Optional frontmatter block at the very top of the file:

```markdown
---
title: My Report Title
subtitle: A one-line subtitle
version: 1.0
vendor: ColeteOnline SRL
accent: 220,50,50
---
```

All keys are optional and fall back sensibly:
- `title` — falls back to the first `# H1` heading found in the body,
  then to the input filename.
- `subtitle` — falls back to empty (omitted from the title page).
- `version` — falls back to today's date (`YYYY-MM-DD`).
- `vendor` — falls back to empty (copyright line omitted from the
  title page footer if not set).
- `accent` — falls back to the ColeteOnline brand red `220,50,50`.

Body Markdown, and how each element renders:

| Markdown                          | Renders as                                                |
|------------------------------------|------------------------------------------------------------|
| `# Title`                          | The *very first* `#` in the file is the title-page title only (consumed, not repeated in the body). Any **later** `#` is a real major heading (see below). |
| `# Major Section` (after the first `#`) | **Major heading.** Always starts its own fresh page (unless the cursor is already at the top of a blank page), big colored left bar, bold 16pt, black text — and gets a Table of Contents entry. Use for genuine top-level divisions only; each one costs a page. |
| `## Subsection`                    | **Subheading.** Bold 13pt, accent-colored text with a short accent-colored underline (visually distinct from both tiers above and below) — does **not** force a page break, just continues the flow. Still gets a TOC entry. Has its own "don't strand a heading at the very bottom of a page" check. |
| `### Sub-subsection` (and `####`+) | **Tertiary heading.** Bold 12pt, neutral gray, full-width thin rule, no page break, **no TOC entry** (keeps the TOC scannable). |
| Paragraph text                     | Justified-left body paragraph, 10pt. |
| `- item` / `* item`                | Bullet list (•). |
| `1. item`                          | Numbered list. |
| ```` ```lang ... ``` ````          | Shaded, bordered monospace code block; the language tag (if present) is printed as a small italic label above the block. No syntax highlighting. |
| `\| a \| b \|` with a `---` separator row | Bordered table, bold header row, zebra-striped body rows, word-wrapped cells, equal column widths. |
| `---` / `***` / `___` on its own line | Vertical spacer (not a page break). |
| `**bold**` | Real bold text, via fpdf2's built-in `markdown=True` renderer. |
| `[text](url)` | A real, clickable PDF link annotation — just the display text is shown, not the raw URL — styled in a distinct link color. |
| `*italic*` / `_italic_` | Rendered italic (folded into fpdf2's native `__italic__` form internally). |
| `` `code` `` | Inline code backticks are stripped — no monospace-inline support, renders as plain text. |

Headings, paragraphs, bullets, numbered items, and table cells all
render through fpdf2's `markdown=True` path, so **bold** and
`[text](url)` links work everywhere text appears, including inside
headings and table cells. Fenced code blocks are the one exception —
their content is rendered completely literally (no markdown parsing),
so a code sample containing literal `**`, `__`, or `[]()` won't be
misinterpreted.

## Limitations (v1)

- **No images.** `![alt](path)` is not parsed in v1 (the reference
  script's "screenshot not available" placeholder logic wasn't
  ported since it's not needed for text-only mentor/review reports).
  A logo image is still supported for the title page via `--logo`.
- **No nested lists.** List items are flat; an indented continuation
  line under a bullet/numbered item is appended to that item's text
  (word-wrap), not rendered as a nested sub-list.
- **TOC is `##`-level only.** `###`+ headings don't get TOC entries
  by design (see table above) — deep documents get a scannable TOC
  instead of a huge one.
- **TOC entries beyond what fits on page 1 are clipped, not
  overflowed onto a second page.** The back-filled TOC lives entirely
  on the title page; a report with a very large number of `#`/`##`
  headings (20+) may not show every entry. This is a deliberate
  tradeoff — the alternative (letting the TOC auto-page-break mid
  back-fill) previously corrupted whatever page came right after the
  title page, which is a far worse failure mode than a few missing
  TOC rows.
- **Table columns are equal-width.** No per-column width hints from
  Markdown; wide/narrow content columns will get the same width. A
  single unbreakable long value (e.g. a long identifier with no
  spaces) in a narrow column will still be forced to break mid-word
  rather than overflow the cell.
- **Code blocks don't reflow, but do shrink to fit.** A code line
  wider than the page is never wrapped (would break monospace
  alignment) — instead the whole block's font size shrinks uniformly
  (down to a 5.5pt floor) so it stays inside its box.

## Testing performed

Run against a real, large report,
`~/Documents/work/docs/internship-2026-categorized-report.md` (six
top-level sections, ~24 `#`/`##`-level headings, dozens of fenced
```typescript``` code blocks including some with very long single
lines — long GitHub URLs as markdown links, long TypeScript union
types — bullet lists, a multi-row table, and a long two-line-wrapping
subtitle): produced a clean 32-page, 155KB PDF. Verified with
`pdfinfo`, `pdftotext -layout`, and by rasterizing individual pages
to PNG (`pdftoppm`) for visual inspection, plus programmatic link
verification via `pypdf` (96 real `/Link` annotations found, each
with the correct GitHub URI).

This same real-world test caught and fixed four genuine rendering
bugs during development (**do not reintroduce these**):
1. `render_h1` used `cell()` (no wrapping) for the heading text — a
   long `##` heading would overflow horizontally past the page edge
   instead of wrapping. Fixed by switching to `multi_cell()` with a
   pre-measured dry-run pass to size the accent bar to the wrapped
   height.
2. The title page's subtitle/version/copyright lines used `cell()`
   with `align="C"` — long centered text draws from a computed
   x-offset that can run off *both* edges of the page when the text
   is wider than the page. Fixed by switching all three to
   `multi_cell()`.
3. `write_toc()`'s page-1 back-fill left `auto_page_break` enabled;
   with enough TOC entries to run past the bottom of page 1, fpdf2's
   automatic page-break fired *while `self.page` was artificially
   pinned to 1*, corrupting the page that actually followed the title
   page. Fixed by disabling auto-page-break for the whole back-fill
   (matching the technique `title_page()` already used for the
   copyright line) and clipping entries that don't fit instead.
4. `render_h1` decided whether to force a page break by counting
   calls (`if self._h1_count > 1: add_page()`) — the assumption being
   that the *first* h1 heading ever rendered is always right at the
   top of a fresh page. That's false whenever a report has intro
   content (paragraphs, a table) before its first section heading:
   that first heading would render wherever the intro left the
   cursor, mid-page, right after unrelated content — reproduced
   exactly by this report's own front-matter intro pushing "1. Design
   Patterns" down instead of onto its own page. Fixed by checking
   cursor position instead of call count: force a page break unless
   the cursor is still sitting at the top margin (nothing rendered on
   the current page yet).
5. `##` and `#` were both treated as the same heading tier (both
   forced a page break). Two consecutive headings with nothing
   between them — a bare `#` major heading immediately followed by a
   `##` (e.g. "1. Design Patterns" directly followed by "1.1
   Controller layer...") — meant the second heading's forced page
   break left the first stranded alone on an otherwise-blank page.
   Fixed by splitting into a real three-tier hierarchy: only `#`
   forces a page break now; `##` became a visually distinct
   "subheading" tier (accent-colored text, short colored underline)
   that never forces its own page, with its own "don't strand a
   heading at the bottom of a page" space check instead; `###`+ kept
   the original bold+gray+rule tertiary treatment. This also made
   subheadings look meaningfully different from major headings, not
   just a smaller copy of the same style.

Also exercised with a synthetic `.md` covering frontmatter (including
`accent` override), a pipe table with a long wrapped cell, a fenced
```python``` block, and inline `**bold**`/`` `code` ``/`[link](url)``
markup — rendered a clean 3-page PDF with correct TOC, wrapped table
cells, zebra striping, real clickable links, and real bold/italic
text.
