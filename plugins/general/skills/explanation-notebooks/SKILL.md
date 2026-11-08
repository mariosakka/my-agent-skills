---
name: explanation-notebooks
description: Use when teaching or explaining any subject from source material (a .docx, .pptx, .xlsx, .csv, .pdf, markdown, web page, or a pasted brief) — producing a simple and/or in-depth explanation as notebooks or markdown, with diagrams, a markdown companion and a PDF — or when reviewing such material for undefined terms, missing explanations or filler. Includes helper scripts that extract metadata, text and images from the source, and rules for introducing new concepts in any field.
---

# Explanation notebooks

Turn any source material into teaching material a newcomer can read cold: a **simple** version, an **in-depth** version, or both, each with a markdown companion and a PDF. The subject does not matter (physics, law, statistics, a programming language, a company handbook); the source can be a document, slides, a spreadsheet, a dataset or a paper.

## Core principle

A reader should never meet a word they were not told about. Every concept is explained **in the chapter where it is first used**, plainly, before the text relies on it.

## Workflow

1. **Inspect** the source: `scripts/inspect_source.py FILE` (type, title, author, dates, pages / slides / sheets, headings outline, table and image counts, warnings such as scanned pages).
2. **Extract** text and images: `scripts/extract_text.py FILE -o text.md` and `scripts/extract_images.py FILE images/` (add `--render` to capture drawn charts and slides as PNG).
3. **Decide** the learner (who they are, what they know), the scope (what the explanation must let them do) and the chapter order. `references/source-types.md` says what to look for in each kind of source.
4. **Plan the terms**: list every concept the reader needs and the chapter where each is first used. That chapter is where it gets defined.
5. **Write** the version(s) (rules below). Use a notebook when there is code or data to run; otherwise plain markdown. Draw each spatial or process idea as a diagram.
6. **Self-check**: `scripts/first_use.py NOTEBOOK "term1,term2"` (notebooks) — the first hit of each term must be in the cell that defines it. For plain markdown, search the file for each term and confirm the first hit is its definition.
7. **Build** the markdown companion and the PDF. The PDF is rendered from the markdown by the **`report-to-pdf`** skill (SVG figures, definition boxes, captions, math); `scripts/build_docs.py` shows the notebook-to-markdown-to-PDF pipeline (see `references/build-and-pitfalls.md`). Do not commit PDFs.

## Pick the rules for the version you are writing

| Asked for | Read |
|---|---|
| a simple / simplified version | `references/shared-rules.md` + `references/simplified-rules.md` |
| an in-depth / detailed version | `references/shared-rules.md` + `references/detailed-rules.md` |
| both | all three; keep the two versions consistent (same facts and figures, same chapter order, same terms defined in the same chapters) |

Shared rules in one line: define each term at first use in the chapter where it is used (no opening glossary, acronyms expanded, each definition in a blockquote box), interpret values instead of narrating the method, no tables, draw spatial and process concepts and every defined device as real images (no ASCII diagrams), no filler.

## Helper scripts

```
python scripts/inspect_source.py FILE [--json]
python scripts/extract_text.py   FILE [-o OUT.md] [--max-chars N] [--rows N]
python scripts/extract_images.py FILE OUTDIR [--render] [--keep-small]
python scripts/first_use.py NOTEBOOK "term1,term2,\bK\b"
```

| Source | Needs |
|---|---|
| docx, pptx, xlsx, csv, md, txt, html | nothing beyond Python (they are read as zip + XML or text) |
| pdf | `pip install pymupdf` (or `pypdf`); scanned PDFs have no text and need OCR |
| `--render` of pdf / pptx | pymupdf; pptx also needs LibreOffice (`soffice`) on PATH |
| image size | `pip install pillow` (optional) |

Every script has `--help`. xlsx formulas are shown as the values Excel cached, not recalculated.

## References

- `references/shared-rules.md`, `simplified-rules.md`, `detailed-rules.md`: how to explain.
- `references/source-types.md`: teaching from slides, spreadsheets, papers, documents and datasets.
- `references/example-layout.md`: one worked folder layout (a lab course); adapt it, it is not required.
- `references/build-and-pitfalls.md`: the current notebook-to-PDF build and its known problems.
