# Pitfalls

Lessons that cost time before.

- **Escape bugs in LaTeX written from Python.** In a normal Python string `"\alpha"` becomes a bell character and `"\tau"` becomes a tab followed by `au`; the PDF then shows broken symbols such as `1/lpha_E`. Write LaTeX in raw strings (`r"\alpha"`), build it with `chr(92)`, or write the markdown with an editor tool, never through a normal string in a script. After editing notebook text from a script, scan the markdown cells for control characters (`\x00` to `\x08`, `\x0b`, `\x0c`, `\x0e` to `\x1f`) and for tabs inside formulas.
- **Pasted code and heredocs lose backslashes.** Put scripts that contain backslashes in files written with the editor tool instead of shell heredocs, and check the written text.
- **Figures that do not fit leave blank space.** In the PDF renderer an image that does not fit in the rest of a page moves to the next page, leaving a gap. A newer `report-to-pdf` shrinks a figure to the room left (down to 70 % of its height); a short page right before a new chapter heading is intentional, since each chapter starts on a new page.
- **Never ASCII diagrams.** A sketch in a code block prints as raw monospace text in the PDF. Draw an SVG and reference it with a caption.
- **Verify every agent's numbers yourself.** Recompute the key results of each lab from the sheet's formulas before accepting a delegated solution, and compare the printed output with the document. Check claims that look unusual (for example a loss "wiping out most of the output" when the number says 8 %).
- **Mixed-up percentages.** State what was held equal when comparing ratios; recheck a percentage against the numbers it is built from.
- **Other sessions edit the same checkout.** Before committing, run `git status` and `git branch --show-current`: files you did not touch may be modified or deleted, and the repository may be on someone else's branch. Stage explicit paths, leave out changes you did not make (ask before committing a deletion you did not make), and move a commit that landed on the wrong branch with a cherry-pick instead of pushing it.
- **Do not commit build output.** PDFs and `.docx` files stay untracked. Check `git diff --cached --name-only` for them, for `desktop.ini`, caches and temporary test files left in the working tree by other agents.
- **Scratch files collide between parallel agents.** Give each agent its own file names in the shared scratch folder, and delete temporary test copies after a test render.
- **Console encoding.** A script that prints non-ASCII text through `conda run` can crash on Windows with a `cp1252` error; encode with `errors="replace"` before printing, or write to a file.
- **Inline math in the PDF renderer is Unicode text.** A fraction or an `\underbrace` inside `$...$` prints as raw text; write such formulas as display math or as plain text with a sentence next to them.
