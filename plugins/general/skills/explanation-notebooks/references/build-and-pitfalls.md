# Build and pitfalls

## Pipeline

notebook -> markdown companion (+ `figures/`) -> PDF through the **`report-to-pdf`** skill.

`scripts/build_docs.py` is a reference implementation (copy and edit its `JN`, `TE` and `JOBS`):

1. `nbconvert` `MarkdownExporter` with inputs excluded turns the notebook into `<name>.md`; executed charts become `figures/output_*.png`, SVGs referenced from the notebook are copied next to them. Per-notebook cell filters drop cells such as hand calculations or display equations.
2. The first `# Title` becomes the PDF cover title (frontmatter `title:`); a single short line before the first heading becomes the subtitle.
3. `report-to-pdf`'s `scripts/build_report_pdf.py` renders the markdown to `<name>.pdf`: SVG and PNG figures, italic caption lines, blockquote definition boxes, code and output blocks, math.

The script finds the renderer under `~/.claude/plugins` or via the `REPORT_TO_PDF_SCRIPT` environment variable. Run from the repo root inside the project environment: `python scripts/build_docs.py [lab ...]`. Notebooks are not executed by the build: execute them first.

For material with no notebook, write the markdown directly (same conventions) and call `build_report_pdf.py` on it.

## Pitfalls

- Rasterising SVGs through a headless browser is slow (a few minutes for dozens of diagrams); build only the folders you changed.
- Math is rendered by the renderer's backend chain (real LaTeX if installed, else matplotlib mathtext, else Unicode). Inline math is always Unicode text; write formulas that matter as display math.
- Malformed bold such as `****Term** $x$**` shows literal `**`; write `**Term $x$**`.
- Notebook relative paths (`sys.path`, data files) break when folders move; re-run every notebook from its new location.
- `conda run` cannot take multi-line `-c` scripts; put them in a file.
- Check a build by rendering a few PDF pages to PNG (PyMuPDF) and looking at them: figures present, boxes not clipped, no empty pages.
- Do not commit PDFs; commit the markdown and `figures/`.

## Diagrams

Write each diagram as an SVG file in `images/`, reference it from the notebook as an image followed by an italic `*Figure: ...*` caption line, and render it to check labels do not overlap before building.
