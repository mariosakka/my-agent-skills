---
name: exam-quiz-site
description: Use when the user wants a local quiz website built from an exam question dump (a PDF or text of multiple-choice, multi-select, hotspot, drag-and-drop or Yes/No questions with answers), with timed mode, previous/next, practice-wrong-only and reset. Covers extracting the questions with parallel agents, verifying them against the source, flagging doubtful answers, and serving a single-file site locally.
---

# Exam quiz site

Turns an exam-dump PDF into a local, single-file quiz site plus a verified `questions.json`. The extraction and the audits are the hard part; the site is a ready template.

## Deliverables

- `questions.json`: the question bank (schema below).
- `index.html`: copy of `assets/index.html`. It loads `questions.json` with `fetch`, so it must be served over HTTP (`python -m http.server 8901 --bind 127.0.0.1`), not opened as a file.
- Site features (already in the template): timed mode (60 s per question, stops when an answer is picked, Pause/Resume), a running stopwatch with a finish summary when timed mode is off, Prev/Next (arrow keys too), Check answer with explanation, "Practice wrong only", unanswered-only, shuffled, Reset question, Reset all, progress saved in `localStorage`, ordering questions, a Microsoft Learn practice-test look (Segoe UI, blue accent, bordered answer boxes, Correct/Incorrect panel with explanation and Learn-more links), case studies shown as a tabbed panel beside the question (see below), "possibly wrong" banner for questions with `sus`, optional "From Microsoft docs" block and links from `docs_*` fields. The bank file can be chosen with `index.html?data=other.json` (default `questions.json`); progress is stored per file name.

## Schema

```json
{"id": 1, "type": "single|multi|matrix|matching|ordering", "question": "full text, code included, no 'Question N' header",
 "options": [{"key": "A", "text": "..."}], "answer": ["D"],
 "items": [{"text": "statement or blank label", "options": ["Yes", "No"], "answer": "No"}],
 "explanation": "from the source, condensed",
 "sus": "optional: string with why the marked answer may be wrong, or true plus sus_reasons: [strings]",
 "validation_status": "optional label shown in the banner",
 "docs_explanation": "optional (hidden when identical to explanation)", "docs_note": "optional",
 "docs_url": "optional https URL", "docs_urls": ["optional https URLs"]}
```

- `single` and `multi` use `options` + `answer`. `matrix` (HOTSPOT, DRAG DROP, Yes/No sets, "select the answer that completes the sentence") uses `items` only; for drag-drop, each target is an item and `options` is the full pool. `matching` is rendered exactly like `matrix`. `ordering` (arrange N actions in sequence) uses `options` with unique keys and `answer` as the ordered list of keys.
- Scoring always follows the source's marked answer. Doubts go in `sus` and `docs_*`; never silently change the key.

## Workflow

1. **Inspect the source first.** `pdftotext -enc UTF-8` (without `-enc UTF-8` Windows output can break). Count `Question: N` headers against the stated total, count `HOTSPOT`/`DRAG DROP`, and check whether answers for those live only in images. Render pages to PNG (PyMuPDF, ~90 dpi) into the scratchpad.
2. **Split by question range** (about 25-30 questions each) using the page where each range starts; each slice runs to the page where the next starts (questions straddle pages).
3. **Extract in parallel**, one agent per slice, each writing its own `qNNN-MMM.json` (never one shared file). Give every agent the schema above, the PDF path, the PNG folder, and the rules: copy text exactly, read hotspot/drag-drop answers from the red boxes in the images, cross-check the `Answer:` line against the explanation, add a `note` when unsure, validate before reporting. Check the prompt before launching: a placeholder prompt wastes an agent.
4. **Merge and validate**: `python scripts/validate_questions.py questions.json --expect <N>`. Then cross-check single/multi answers against the PDF's own `Answer:` lines with a regex (stricter than `[A-H]+`, which also matches the letters in "Explanation").
5. **Re-verify the suspects** in parallel: questions whose answer image was blank, whose answer came from the explanation, duplicates of an option text, garbled stems, options that do not fit the stem (a pasted-in wrong option pool is common).
6. **Audit in two independent passes, in parallel** (agents write reports only, never edit `questions.json`):
   - *Source fidelity*: re-read every question from the PDF text and images and diff text, options, answer and matrix pools.
   - *Docs correctness*: map each question to the official study-guide skill and fetch the matching Microsoft Learn/docs page. Every verdict must quote a page that was actually fetched; otherwise it is `unverified`, never `ok`. Expect outdated or renamed services and defective source items.
7. **Apply** fixes for extraction errors; turn real doubts into `sus` banners and `docs_*` fields. Agents often skip their own spot-checks, so run the validator and a few manual spot checks yourself.
8. **Look for duplicates and patterns** (token overlap on question plus options; boilerplate stems like "Select Yes or No" make naive similarity useless). Dropping a duplicate changes the numbering, so ask first.
9. **Serve and test in a browser**: load a question, check, wrong-only, timed (stop on pick, pause), reset. Clear the test answers from `localStorage` afterwards.

## Pitfalls seen

- A source can disagree with the docs, with itself (explanation vs marked answer), or be garbled; record it, do not "fix" it.
- A PDF explanation can be a placeholder; mark it, or write one and say it is bank-authored.
- The page fetches `questions.json` by default; keep it next to `index.html` or open `index.html?data=<file>`.
- Case studies: the background is the text before the last line of `question` (the last line is the question itself). The template lays it out as tabs using the known headings `H1` (Background, Current environment, ...) and `H2` (Channels, Data sources, ...) near the top of the script's case-study section, then bullets and `Label:` runs. These lists come from the AB-620 bank; for a new exam, add its headings there, otherwise unknown headings render as plain paragraphs. The layout never drops or reorders text; check this by comparing the word sequence of the source and the rendered panel, which was done for all four AB-620 variants.
- Git Bash `/tmp` and Windows Python `/tmp` are different folders; use the scratchpad with absolute Windows-style paths.
- Before zipping the project, delete intermediate files (per-slice JSON, audit reports, extra copies of the bank) and keep `index.html`, `questions.json`, and optionally the source PDF.
