# Teaching from different source material

Run `scripts/inspect_source.py` first; it reports the type, size, structure and warnings. Then extract with `extract_text.py` and `extract_images.py`.

## Slides (pptx)

- **Extract:** slide titles, bullets, tables, **speaker notes** (`extract_text.py` prints them), images (`--render` for slides drawn with shapes or charts; needs LibreOffice).
- **Ask:** what does the presenter say that the bullets only hint at? What does the audience need to already know?
- **Pitfalls:** bullets are cues, not explanations; the explanation is in the notes or in the speaker's head, so expand each bullet into a defined concept. Slide order is not always teaching order; reorder by first use.

## Spreadsheet (xlsx)

- **Extract:** sheet names, first rows, row and column counts, the number of formulas.
- **Ask:** what question does each sheet answer? Which cells are inputs, which are results?
- **Pitfalls:** the file stores formulas and their last cached value; the extractor shows cached values, so a stale file shows stale numbers. Hidden sheets, merged cells and named ranges carry meaning. Open the file itself to read the formula text when the logic matters.

## Dataset (csv, or a data sheet)

- **Extract:** header, row count, per-column type, range, missing values, top categories (`extract_text.py` prints these).
- **Ask:** what does one row represent, in what unit and time step is each column, which columns are inputs and which are outcomes?
- **Pitfalls:** decimal commas and semicolon separators, units hidden in the header, silently missing values, a time column that is not sorted. State the cleaning assumptions in the explanation. Use a notebook so the reader can rerun the analysis.

## Paper or report (pdf)

- **Extract:** metadata and outline (`inspect_source.py`), text per page, embedded figures (`extract_images.py`, `--render` for vector charts).
- **Ask:** what is the claim, the method, the evidence and the limit? Which terms does the paper assume?
- **Pitfalls:** a scanned PDF has no text layer (the inspector warns "pages without text"): run OCR before extracting. Two-column layouts interleave text; check the order. Equations extract as broken characters: re-type the ones that matter. Cite the paper's own numbers exactly.

## Document (docx, md, txt, html)

- **Extract:** headings outline, paragraphs, tables, images.
- **Ask:** who wrote it for whom, and what does it assume? Which sections are procedures, which are reference?
- **Pitfalls:** tracked changes and comments are not in the text; headings may be styled by hand and not detected as headings; tables flatten to rows of `cell | cell`.

## Pasted brief or no file

Treat the brief as the source: list the concepts it names, decide the learner and scope with the user, then follow the same workflow.

## Whatever the source

- Keep a list of **facts and figures taken from the source**; use the same ones in the simple and the in-depth version.
- Anything the source leaves out but the reader needs (a definition, a unit, a prerequisite) is yours to add, in the chapter where it is first used.
- Say where an assumption is yours and not the source's.
