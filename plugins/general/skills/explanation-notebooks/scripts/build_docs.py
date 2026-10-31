"""Rebuild the markdown companion and the PDF of every notebook of a lab.

Run from the repo root inside the conda env:
    conda run -n human-centric-ai-for-energy-labs python tools/build_docs.py lab-2 lab-3 lab-4
    (no argument = all labs)

For each notebook this writes  <lab>/explanation-notebooks/visual explanations/<name>/<name>.md  (+ figures/)  and  <name>.pdf.
Code cells, display equations (lab 2) and the hand-calculation sections are left out.
The PDF is rendered from the markdown by the `report-to-pdf` skill (SVG figures, definition boxes, captions, math).
Set REPORT_TO_PDF_SCRIPT to its build_report_pdf.py if it is not found under ~/.claude/plugins.
Notebooks are NOT executed here: run them first (jupyter nbconvert --to notebook --execute --inplace <nb>).
"""
import glob, os, re, shutil, subprocess, sys
import nbformat as nbf
from nbconvert import MarkdownExporter

JN = "explanation-notebooks/jupyter notebooks"
TE = "explanation-notebooks/visual explanations"
L2A, L2B = f"lab-2/{JN}/lab-2-plus-lecture-challenge", f"lab-2/{JN}/only-lab-2"


def find_renderer():
    env = os.environ.get("REPORT_TO_PDF_SCRIPT")
    if env and os.path.exists(env):
        return env
    pattern = os.path.expanduser("~/.claude/plugins/**/report-to-pdf/scripts/build_report_pdf.py")
    hits = sorted(glob.glob(pattern, recursive=True), key=os.path.getmtime, reverse=True)
    return hits[0] if hits else None


def starts(c, prefix):
    return c.cell_type == "markdown" and c.source.lstrip().startswith(prefix)


def strip_display_eq(c):
    if c.cell_type == "markdown":
        c.source = re.sub(r"\$\$.*?\$\$", "", c.source, flags=re.S)
    return c


keep_all = lambda c: True
no_step4 = lambda c: not starts(c, "## Step 4")
no_hand = lambda c: not starts(c, "## Hand calculation")
no_pmv_maths = lambda c: not starts(c, "## 0.7 How PMV and PPD are computed")

# notebook, which cells to keep, per-cell edit
JOBS = {
    "lab-2": [(f"{L2B}/lab-2.ipynb", no_step4, strip_display_eq),
              (f"{L2B}/lab-2-simple.ipynb", no_step4, strip_display_eq),
              (f"{L2A}/lab-2-in-depth.ipynb", no_step4, strip_display_eq),
              (f"{L2A}/lab-2-in-depth-simple.ipynb", no_step4, strip_display_eq)],
    "lab-3": [(f"lab-3/{JN}/lab-3-in-depth.ipynb", no_pmv_maths, lambda c: c),
              (f"lab-3/{JN}/lab-3-simple.ipynb", keep_all, lambda c: c)],
    "lab-4": [(f"lab-4/{JN}/lab-4-in-depth.ipynb", no_hand, lambda c: c),
              (f"lab-4/{JN}/lab-4-simple.ipynb", no_hand, lambda c: c)],
}


def build(nb_path, keep, edit, renderer):
    lab = nb_path.split("/")[0]
    name = os.path.splitext(os.path.basename(nb_path))[0]
    nb_dir = os.path.dirname(nb_path)
    out = os.path.join(lab, TE, name)
    shutil.rmtree(os.path.join(out, "figures"), ignore_errors=True)
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    nb = nbf.read(nb_path, as_version=4)
    nb.cells = [edit(c) for c in nb.cells if keep(c)]

    # markdown companion: executed outputs become figures/output_*.png, diagrams are copied next to them
    exp = MarkdownExporter()
    exp.exclude_input = True
    body, res = exp.from_notebook_node(nb, resources={"output_files_dir": "figures"})
    for fname, data in res["outputs"].items():
        with open(os.path.join(out, fname), "wb") as f:
            f.write(data)

    def copy_svg(m):
        src = os.path.normpath(os.path.join(nb_dir, m.group(2)))
        shutil.copy(src, os.path.join(out, "figures", os.path.basename(src)))
        return f"![{m.group(1)}](figures/{os.path.basename(src)})"
    body = re.sub(r"!\[([^\]]*)\]\(([^)\s]+\.svg)\)", copy_svg, body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    with open(os.path.join(out, name + ".md"), "w", encoding="utf8", newline="\n") as f:
        f.write(body)

    # PDF: report-to-pdf reads the same markdown, plus a frontmatter title for the cover page
    title = re.match(r"#\s+(.+)", body).group(1).strip()
    rest = re.sub(r"\A#\s+.+\n\s*", "", body)
    intro = re.match(r"([^#\-*>`!\n][^\n]{0,240})\n\s*\n(?=#)", rest)    # one short line before the first heading becomes the cover subtitle
    subtitle = ""
    if intro:
        subtitle = "subtitle: " + intro.group(1).replace("*", "").replace(":", " -") + "\n"
        rest = rest[intro.end():]
    src_md = os.path.join(out, name + ".pdf-source.md")
    with open(src_md, "w", encoding="utf8", newline="\n") as f:
        f.write(f"---\ntitle: {title}\n{subtitle}---\n\n" + rest)
    pdf = os.path.join(out, name + ".pdf")
    try:
        subprocess.run([sys.executable, renderer, src_md, "-o", pdf], check=True, capture_output=True)
    finally:
        os.remove(src_md)
    print(name, "md", len(body), "chars; pdf", os.path.getsize(pdf) // 1024, "KB")


if __name__ == "__main__":
    renderer = find_renderer()
    if renderer is None:
        sys.exit("report-to-pdf not found: install the skill or set REPORT_TO_PDF_SCRIPT to its scripts/build_report_pdf.py")
    for lab in sys.argv[1:] or JOBS:
        for job in JOBS[lab]:
            build(*job, renderer)
