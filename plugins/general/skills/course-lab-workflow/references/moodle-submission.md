# Moodle submission

The document a team uploads: a Word-style PDF with the answers, the code and its real output. Match the team's earlier submissions in the same repository first (render one and look at it); this is the style that worked.

## Content

Written in the team's voice ("we calculated ..."), plain wording. Letter page, Calibri, no cover page, no table of contents.

1. Title ("Laboratory N - <topic>"), team line, members (one per bullet, same spelling and order every time).
2. **Objective**: what the lab studied and what was found, in a short paragraph.
3. **Input data**: a pipe table of quantity and value with units, from the sheet, plus the equations as plain Unicode text lines.
4. **One numbered section per sub-question**, (a), (b), ...: a short explanation, the formula, a short code snippet that computes it, the real printed output, then one or two sentences interpreting the result. Answer the sheet's "why" questions physically, not just numerically.
5. **Conclusions**: three bullets with the key results.
6. **Annex: full code**: the complete runner script and the shared module.

Rules for the code and text:

- The numbers come from running the runner script (`solve_lab_N.py`, which only imports from `shared/` and prints each answer); paste its real output. The snippets in the document match the annex code.
- Strip all comments and docstrings from the submitted code (the annex and the snippets); the files in the repository keep theirs.
- No instructions about how to run the code and no mention of the repository, folders or file layout; no sentences about where the formulas are written.
- Maths in plain Unicode (`η = F_R(τα) − F_R·U_L · x`), never LaTeX. Keep the voice human: short sentences, no bold for emphasis, no filler.
- Figures made by the runner (a chart per key idea) with an italic caption.

## Build

Source: `lab-N/moodle-submission/lab-N-moodle-submission.md` in a restricted markdown (the syntax is documented at the top of `scripts/build_submission.py`: title, bold team line, bullets, pipe tables, ```python code boxes, ```text output boxes, `> ` formula lines, images with captions, `---pagebreak---`).

```
python tools/build_submission.py lab-N/moodle-submission/lab-N-moodle-submission.md -o lab-N/moodle-submission/Lab-N-Moodle-Submission-<Topic>.pdf
```

The script writes a `.docx` next to the PDF and converts it with headless LibreOffice (Word through COM is the fallback). Python code boxes are syntax-highlighted with Pygments in light Visual Studio colours; program output sits in a dark box.

Prerequisites: `python-docx`, `pygments`, and LibreOffice or Microsoft Word. Copy `scripts/build_submission.py` into the repository's `tools/` and check the `SOFFICE` path at the top.

Render every page to PNG and look at it: tables not broken, code boxes readable, figures present, no leftover markdown syntax. Do not commit the `.pdf` or `.docx`; commit the markdown source, the runner and the figures.
