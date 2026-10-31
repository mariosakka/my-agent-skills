# Shared rules (simple and in-depth)

Apply to any subject and any source: physics, statistics, a programming language, law, a company process. Both versions follow these.

## First use means first use

- Define a term in the chapter where the reader first needs it, before relying on it.
- Do not define a chapter-3 term in chapter 1 "to be safe", and do not hide a definition inside an unrelated earlier chapter.
- No opening glossary. A short dedicated sub-section is fine only if it sits directly before the first use. A reference list at the very end is fine; it does not replace in-place definitions.
- If a title, figure caption or early sentence uses a term before its chapter, reword it or move the definition up to it.
- Expand every acronym at first use (full name once, then the acronym).
- The source's own vocabulary is not free: a word the source assumes (a unit, a standard, a tool) is a term to define for this reader.

## Definition boxes

Write every full definition as its own markdown blockquote, so it stands out as a box in the PDF:

```
> **Term** (unit): what it is, in one or two sentences.
```

One blockquote per term, separated by a blank line. Figures, formulas and interpretation stay outside the box. Acronym expansions and one-clause parentheticals stay inline.

## Introduction pattern

In the chapter of first use: what it is (one plain sentence) → what it does here → analogy → units, scale or typical values → why it matters here → then use the term freely. Depth of each step differs per version (see the simplified and detailed rules).

## Values and results

- Interpret every number or result the explanation shows: what it means for the reader, with a comparison ("65 % dissatisfied: about two in three people complain"). Never narrate how it was obtained.
- State the assumption that drives it.
- No meta commentary ("I computed it like this", "what this document does"), no first person.

## Form

- No tables: use graphs, or short bullet lists when there is no data to plot.
- Draw every spatial or process concept (a diagram per idea; keep diagram files next to the document and check the labels do not overlap).
- Diagrams are real images (SVG or a plotted figure), never ASCII art or arrows typed in a code block: they print as raw monospace text in the PDF. If a diagram needs a sketch first, replace it with the image before building.
- Code, data wrangling and hand calculations stay in the notebook; the markdown companion and the PDF omit them.
- Use a notebook when there is code or data to run; plain markdown otherwise. Either way produce a markdown companion and a PDF.

## Self-check pass

List the terms you introduced and run, for a notebook:

```
python scripts/first_use.py notebook.ipynb "term one,term two,\bAB\b"
```

For plain markdown, search the file for each term. The first hit for each term must be in the place that defines it. An earlier hit means the term is used before it is explained.
