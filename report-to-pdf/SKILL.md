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
| `# Title`                          | Title-page title only (first one found; consumed, not repeated in the body). Any *further* `#` in the body is treated the same as `##`. |
| `## Section`                       | Body section heading: starts a new page, left accent bar, bold 16pt — and gets a Table of Contents entry. |
| `### Subsection` (and `####`+)      | Bold 12pt + underline rule, no page break, **no TOC entry** (keeps the TOC scannable — matches the reference script's TOC being top-level-sections-only). |
| Paragraph text                     | Justified-left body paragraph, 10pt. |
| `- item` / `* item`                | Bullet list (•). |
| `1. item`                          | Numbered list. |
| ```` ```lang ... ``` ````          | Shaded, bordered monospace code block; the language tag (if present) is printed as a small italic label above the block. No syntax highlighting. |
| `\| a \| b \|` with a `---` separator row | Bordered table, bold header row, zebra-striped body rows, word-wrapped cells, equal column widths. |
| `---` / `***` / `___` on its own line | Vertical spacer (not a page break). |
| `**bold**`, `*italic*`, `` `code` ``, `[text](url)` | Inline emphasis/link markup is **stripped, not rendered** — text prints plain (link becomes `text (url)`). See Limitations. |

## Limitations (v1)

- **No inline bold/italic spans.** fpdf's core/DejaVu fonts don't
  support mixed bold/plain runs inside a single `multi_cell` without
  manual per-character width tracking, which was judged not worth it
  for a first version — the reference script has the same limitation.
  `**bold**` and `` `code` `` render as plain text with the markers
  removed.
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
- **Table columns are equal-width.** No per-column width hints from
  Markdown; wide/narrow content columns will get the same width.

## Testing performed

Run against a real report,
`~/Documents/work/docs/internship-2026-code-review.md` (h1/h2/h3
headings, bullet lists, bold text, inline code, fenced ```typescript
code blocks, no tables): produced a clean 18-page, 94KB PDF with a
correctly back-filled TOC (8 `##`-level entries with accurate page
numbers via dot leaders), no page-overflow in any code block, and no
duplicated headings. Verified with `pdfinfo`/`pdftotext -layout`.

Also exercised with a synthetic `.md` covering frontmatter (including
`accent` override), a pipe table with a long wrapped cell, a fenced
```python``` block, and inline `**bold**`/`` `code` ``/`[link](url)``
markup — rendered a clean 3-page PDF with correct TOC, wrapped table
cells, zebra striping, and stripped inline markup.
