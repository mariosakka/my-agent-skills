# Course overview

A short cumulative report that gathers every lab: what each sheet asked, how it was solved, the key principles with diagrams, and the relationships that are easy to miss. It grows by one part per lab, so keep it short (about 2 to 4 PDF pages per lab) and do not go deep; the lab documents hold the detail.

## Layout

```
overview/
  parts/00-introduction.md           the course in one picture (a diagram of how the labs connect) and shared conventions
  parts/NN-lab-N.md                  one per lab, NN = 10 x N
  parts/90-key-relationships.md      ideas that cut across labs, then the formulas to know by heart
  figures/                           reused lab diagrams and charts, prefixed labN-
  overview.md                        generated (committed)
  overview.pdf                       generated (never committed)
```

Each part starts with a `# ` chapter heading (a lab part: `# Lab N: <short topic>`), and uses `##` and `###` below it.

## A lab part

- One plain sentence on what the lab is about.
- `## What the sheet asked`: one bullet per question, labelled as in the sheet, including the optional extension.
- `## How we solved it`: short numbered steps with the method and the key results and their numbers (identical to the lab documents). Function names in backticks only, no code blocks, no hand calculations.
- `## Key principles`: a `###` per concept, each defined in a blockquote box at its first use (`> **Term** (unit): definition.`), 2 to 4 lines, no opening glossary. A concept already defined in an earlier lab is not defined again: point back to it.
- `## Relationships worth remembering`: bullets with the non-obvious links and the reason for each (which way a change pushes the result, what dominates, traps from the sheet).
- Reuse the lab's own SVG diagrams and chart PNGs (copy them into `overview/figures/`), 3 to 6 per lab, each with an italic caption. A new graph is allowed only if a small script produces it from the lab's `shared/` code.

Follow the `explanation-notebooks` writing rules (definitions at first use, interpretation, no tables, no ASCII art). The cross-lab chapter lists the ideas that come back in several labs (balances, resistances, comparing at the same operating point, diminishing returns, linear models near a reference point) and ends with the formulas.

## Build

```
python tools/build_overview.py
```

`scripts/build_overview.py` joins `overview/parts/*.md` in file-name order, adds a frontmatter title and a subtitle listing the labs found, writes `overview/overview.md` and renders `overview/overview.pdf` with the `report-to-pdf` skill (set `REPORT_TO_PDF_SCRIPT` to its `build_report_pdf.py`, or install the skill under `~/.claude/plugins`). Run it from the repository root. Each `# ` heading becomes a chapter with its own page.

## Update routine

When a lab is solved: add `overview/parts/NN-lab-N.md` and its figures, update the introduction's diagram and the cross-lab chapter, rebuild, and look at the new pages. Do not commit the PDF.
