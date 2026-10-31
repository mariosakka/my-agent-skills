# Example layout (one possibility, not required)

A lab course where each assignment gets a simple and an in-depth notebook:

```
lab-N/
  shared/                          reusable functions: return values only, no print or plot
  explanation-notebooks/
    jupyter notebooks/             <name>.ipynb (+ images/ with the SVG diagrams)
    visual explanations/<name>/    <name>.md + figures/ committed; <name>.pdf generated, not committed
```

- Code, tables-as-code and hand calculations stay in the notebooks; the markdown and PDF omit them.
- Notebooks are executed before the docs are built.
- For material without code, replace the notebooks by `<name>.md` files and keep the same `<name>/` folder with figures and the PDF.

Choose any layout that keeps four things apart: the source, the explanations you write, the generated markdown companion with its figures, and the generated PDFs (not committed).
