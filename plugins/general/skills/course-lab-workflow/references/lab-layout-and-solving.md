# Lab layout and solving

Follow the course repository's own layout when it has one. This is the layout that worked for a numbered course repository (worked example: an energy-management course, labs 2 to 6).

```
lab-N/
  <assignment>.pdf                       the sheet, never edited
  shared/                                reusable code that only returns values (no print, plots or UI), plus its tests
  explanation-notebooks/
    jupyter notebooks/                   <name>-simple.ipynb, <name>-in-depth.ipynb, images/ (SVG diagrams)
    visual explanations/<name>/          <name>.md + figures/ (committed), <name>.pdf (never committed)
  moodle-submission/                     submission source, runner script, figures (see moodle-submission.md)
overview/                                cumulative report (see course-overview.md)
tools/                                   build scripts: docs, submission, overview
```

Register each new lab in the root README table and in the docs build script's job list.

## Solve a lab

1. **Read the sheet twice.** Extract its text, then render each page to an image and look at it: `pdftotext` garbles Greek letters, subscripts, symbols and figures. Note every sub-question, the optional extension and the sheet's own reminders and warnings.
2. **Put all computation in `shared/`.** Sheet data, constants, formulas and algorithms live there as functions that return values, with an assert-based or pytest test next to them. Notebooks and runner scripts import them and never define their own `def` or lambda for a computation; inline definitions are allowed only for drawing helpers (annotations, plot style). A calculation a notebook needs goes into `shared/` first, with a test. Before finishing, scan each notebook's code cells for inline computation.
3. **Compute every number by running code**, then check the key results independently (a quick hand calculation or a second formula), and against any example the sheet gives (for instance an "about 80 %" in the text).
4. **Write two executed notebooks** that answer every sub-question, including the optional extension: a simple one (plain words, analogies, minimal maths) and an in-depth one (precise definitions, formulas, assumptions, limits). Run them from their own folder, with `shared/` added to `sys.path` by a relative path. The writing rules (definitions in a box at first use, no opening glossary, interpretation of values, no tables, no meta comments) come from the `explanation-notebooks` skill; follow them instead of restating them.
5. **Draw spatial and process ideas as real SVG files** in `images/`, with an italic `*Figure: ...*` caption line below each reference. Every device, instrument or piece of equipment that gets defined has its own labelled diagram right after its definition box. Render each SVG and look at it: labels must not overlap and arrows must show. Never use ASCII art.
6. **Build the markdown companion and the PDF** with the `report-to-pdf` skill: notebook to markdown plus figures, then markdown to PDF. A full build rasterises every SVG and takes minutes: run it in the background and build only the labs you changed. Render a few PDF pages to PNG and look at them (figures present, boxes not clipped, no raw `$...$`).
7. **Optional deliverables**: the Moodle submission and the course overview, when the user asks for them.

## Commit rules

- Commit the notebooks, `shared/`, `images/`, the markdown companions and their `figures/`, the submission source and the overview parts. Never commit PDFs (the assignment's or the built ones) or `.docx` files.
- Commit and push only when asked. Stage explicit paths; check `git status` for deletions or edits you did not make before committing.
- A repository on Google Drive prints a harmless `bad object refs/desktop.ini` / repack error on every git command; the commit and push still succeed.

## Environment

- Run everything through the project environment (`conda run -n <env> python ...`). On Windows, starting the environment's `python.exe` directly skips the DLL paths and plotting crashes. `conda run` cannot take multi-line `-c` scripts: put them in a file.
- Add a package to the shared environment file only when something needs it, and say so.
- Execute notebooks before building (`jupyter nbconvert --to notebook --execute --inplace`); the docs build does not run them.

## Parallel agents

Labs are independent, so one agent per lab can run at the same time. Give each agent only its own `lab-N/` folder, and let a single agent (or the main one) edit the shared index files: the root README, the build script's job list, the instruction files. Tell agents not to commit; the main agent verifies their numbers and commits.
