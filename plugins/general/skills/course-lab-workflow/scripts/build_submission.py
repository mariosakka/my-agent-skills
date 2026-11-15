"""Build a Moodle submission (Word + PDF) from a restricted markdown file, in the look of a team's Word-made submissions.

Run from the course repository root inside its environment (needs python-docx, pygments, and LibreOffice or Word):
    python tools/build_submission.py lab-N/moodle-submission/lab-N-moodle-submission.md \
        -o lab-N/moodle-submission/Lab-N-Moodle-Submission-<Topic>.pdf
Writes <stem>.docx next to the PDF (kept) and converts it to PDF with headless LibreOffice (Word through COM is the fallback).
Set SOFFICE below if LibreOffice is installed elsewhere.

Markdown subset (everything else is plain text; maths is plain Unicode, never LaTeX):
  # Title                       centered bold 16 (the first line)
  **Team 4: ...**               a line that is only bold = centered grey subtitle under the title
  Members:                      bold paragraph; followed by "- " bullets
  ## 1. Heading                 bold 13        ### Sub heading   bold 11
  paragraph                     inline **bold**, *italic*, `code`
  - item / 1. item              bullet / numbered lists
  | a | b |  pipe table         header row bold on grey, thin borders; |:--|--:| aligns columns
  ```python ... ```            code: light grey box, Consolas 9, syntax-highlighted (Pygments, Visual Studio light colours)
  ```text ... ```              program output: dark box, light Consolas 9
  > formula                     centered Cambria Math line (consecutive > lines = several lines)
  ![caption](path.png)          centered image (path relative to the .md), italic caption under it
  ---pagebreak---               page break
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

from docx import Document
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Keyword, Name, Number, Operator, String
from docx.enum.section import WD_ORIENT  # noqa: F401  (kept for A4/Letter edits)
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Inches, Pt, RGBColor

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"
BODY, MONO, MATH = "Calibri", "Consolas", "Cambria Math"
GREY, CODE_FILL, OUT_FILL, HEAD_FILL = RGBColor(0x59, 0x59, 0x59), "F2F2F2", "1E1E1E", "F2F2F2"
TEXT_W = Inches(6.5)


# ---------------------------------------------------------------- docx helpers
def shade(cell, fill):
    pr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear"); el.set(qn("w:color"), "auto"); el.set(qn("w:fill"), fill)
    pr.append(el)


def borders(table, color="BFBFBF", size=4):
    pr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(size)); e.set(qn("w:space"), "0"); e.set(qn("w:color"), color)
        b.append(e)
    pr.append(b)


def cell_margins(table, top=60, bottom=60, left=100, right=100):
    pr = table._tbl.tblPr
    m = OxmlElement("w:tblCellMar")
    for side, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa")
        m.append(e)
    pr.append(m)


def fix_widths(table, widths):
    table.autofit = False
    for row in table.rows:
        for c, w in zip(row.cells, widths):
            c.width = w


def keep_with_next(p, on=True):
    p.paragraph_format.keep_with_next = on


def font(run, name=BODY, size=11, bold=None, italic=None, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    if italic is not None: run.italic = italic
    if color is not None: run.font.color.rgb = color


INLINE = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`)")


def add_inline(p, text, size=11, color=None, bold=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            r = p.add_run(part[2:-2]); font(r, size=size, bold=True, color=color)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = p.add_run(part[1:-1]); font(r, MONO, size - 1.5, color=color)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = p.add_run(part[1:-1]); font(r, size=size, italic=True, bold=bold, color=color)
        else:
            r = p.add_run(part); font(r, size=size, bold=bold, color=color)


def para(doc, text="", size=11, align=None, before=0, after=6, **kw):
    p = doc.add_paragraph()
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(before), Pt(after)
    p.paragraph_format.line_spacing = 1.08
    if align is not None:
        p.alignment = align
    if text:
        add_inline(p, text, size, **kw)
    return p


def wrap(line, width=92):
    """Break an over-long code line at a space: [(prefix, start, end)] slices of `line`; later slices get the indentation plus two spaces."""
    out, indent, start = [], re.match(r"\s*", line).group(), 0
    prefix = ""
    while len(prefix) + len(line) - start > width:
        cut = line.rfind(" ", start + len(indent) + 1, start + width - len(prefix))
        if cut <= start + len(indent):
            break
        out.append((prefix, start, cut)); start, prefix = cut + 1, indent + "  "
    return out + [(prefix, start, len(line))]


CODE_INK = RGBColor(0x1F, 0x1F, 0x1F)
PALETTE = [(Keyword, RGBColor(0x00, 0x00, 0xFF)), (Operator.Word, RGBColor(0x00, 0x00, 0xFF)),
           (Name.Builtin, RGBColor(0x26, 0x7F, 0x99)), (Name.Function, RGBColor(0x79, 0x5E, 0x26)),
           (Name.Class, RGBColor(0x26, 0x7F, 0x99)), (Name.Decorator, RGBColor(0x79, 0x5E, 0x26)),
           (String, RGBColor(0xA3, 0x15, 0x15)), (Number, RGBColor(0x09, 0x86, 0x58))]


def token_color(tok):
    for kind, col in PALETTE:
        if tok in kind:
            return col
    return CODE_INK


def highlight(lines):
    """Per source line, one colour per character, from the Pygments Python lexer."""
    chars = []
    for tok, text in lex("\n".join(lines), PythonLexer()):
        chars += [token_color(tok)] * len(text)
    out, pos = [], 0
    for ln in lines:
        out.append(chars[pos:pos + len(ln)]); pos += len(ln) + 1
    return out


def box(doc, lines, fill, color, size=9, lang=None):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders(t, "BFBFBF" if fill == CODE_FILL else "1E1E1E")
    cell_margins(t, 80, 80, 120, 120)
    fix_widths(t, [TEXT_W])
    c = t.rows[0].cells[0]; shade(c, fill)
    lines = [ln.expandtabs(4) for ln in lines]
    colors = highlight(lines) if lang == "python" else [[color] * len(ln) for ln in lines]
    first = True
    for raw, cols in zip(lines, colors):
        for prefix, a, b in wrap(raw):
            p = c.paragraphs[0] if first else c.add_paragraph()
            first = False
            p.paragraph_format.space_after = p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            if prefix:
                font(p.add_run(prefix), MONO, size, color=color)
            k = a
            while k < b:
                e = k
                while e < b and cols[e] == cols[k]:
                    e += 1
                font(p.add_run(raw[k:e]), MONO, size, color=cols[k]); k = e
            if a == b and not prefix:
                font(p.add_run(" "), MONO, size, color=color)
    para(doc, "", after=4)


def table(doc, rows, aligns):
    n = len(rows[0])
    t = doc.add_table(rows=len(rows), cols=n)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    borders(t); cell_margins(t)
    fix_widths(t, [int(TEXT_W / n)] * n)
    for i, row in enumerate(rows):
        for j in range(n):
            c = t.rows[i].cells[j]; p = c.paragraphs[0]
            p.paragraph_format.space_after = p.paragraph_format.space_before = Pt(0)
            p.alignment = {"r": WD_ALIGN_PARAGRAPH.RIGHT, "c": WD_ALIGN_PARAGRAPH.CENTER}.get(aligns[j], WD_ALIGN_PARAGRAPH.LEFT)
            add_inline(p, row[j] if j < len(row) else "", 10.5, bold=True if i == 0 else None)
            if i == 0: shade(c, HEAD_FILL)
    para(doc, "", after=4)


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


# ---------------------------------------------------------------- markdown -> docx
def build_docx(md_path, docx_path):
    base = os.path.dirname(os.path.abspath(md_path))
    lines = open(md_path, encoding="utf8").read().replace("\r\n", "\n").split("\n")
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Inches(1)
    st = doc.styles["Normal"]; st.font.name = BODY; st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), BODY)

    i, title_done = 0, False
    while i < len(lines):
        ln = lines[i]
        if ln.strip() == "---pagebreak---":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif ln.startswith("```"):
            kind, j = ln[3:].strip().lower(), i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            body = lines[i + 1:j]
            box(doc, body, OUT_FILL if kind in ("text", "output", "txt") else CODE_FILL,
                RGBColor(0xE6, 0xE6, 0xE6) if kind in ("text", "output", "txt") else CODE_INK, lang=kind)
            i = j
        elif ln.startswith("# "):
            para(doc, "", after=0).paragraph_format.space_before = Pt(0)
            p = para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER, before=18, after=6)
            font(p.add_run(ln[2:].strip()), size=16, bold=True)
            title_done = True
        elif ln.startswith("### "):
            p = para(doc, "", before=8, after=4); font(p.add_run(ln[4:].strip()), size=11, bold=True); keep_with_next(p)
        elif ln.startswith("## "):
            p = para(doc, "", before=14, after=6); font(p.add_run(ln[3:].strip()), size=13, bold=True); keep_with_next(p)
        elif title_done and i < 6 and re.fullmatch(r"\*\*.+\*\*", ln.strip()):
            p = para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER, after=10)
            font(p.add_run(ln.strip()[2:-2]), size=11, color=GREY)
        elif re.fullmatch(r"\*\*[^*]+:\*\*|[A-Z][A-Za-z ]*:", ln.strip()) and "".join(lines[i + 1:i + 3]).lstrip().startswith("- "):
            p = para(doc, "", before=6, after=4); font(p.add_run(ln.strip().strip("*")), bold=True); keep_with_next(p)
        elif ln.lstrip().startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\s*\|[\s:|-]+\|\s*", lines[i + 1]):
            aligns = ["r" if c.endswith(":") and not c.startswith(":") else "c" if c.startswith(":") and c.endswith(":") else "l"
                      for c in split_row(lines[i + 1])]
            rows, j = [split_row(ln)], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append(split_row(lines[j])); j += 1
            table(doc, rows, aligns)
            i = j - 1
        elif ln.startswith(">"):
            j, body = i, []
            while j < len(lines) and lines[j].startswith(">"):
                body.append(lines[j].lstrip("> ").rstrip()); j += 1
            for b in body:
                p = para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER, before=2, after=2)
                font(p.add_run(b), MATH, 12)
            para(doc, "", after=2)
            i = j - 1
        elif re.match(r"!\[.*\]\(.+\)\s*$", ln.strip()):
            cap, src = re.match(r"!\[(.*)\]\((.+)\)", ln.strip()).groups()
            path = src if os.path.isabs(src) else os.path.join(base, src)
            p = para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER, before=4, after=2); keep_with_next(p)
            from PIL import Image
            with Image.open(path) as im:
                w = min(TEXT_W, Emu(int(im.size[0] / 96 * 914400)))
            p.add_run().add_picture(path, width=w)
            if cap:
                p = para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER, after=8); font(p.add_run(cap), size=10, italic=True)
        elif re.match(r"\s*(-|\d+\.)\s+", ln):
            numbered = bool(re.match(r"\s*\d+\.", ln))
            m = re.match(r"\s*(?:-|(\d+)\.)\s+(.*)", ln)
            p = doc.add_paragraph(style="List Number" if numbered else "List Bullet")
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, m.group(2))
        elif ln.strip():
            para(doc, ln.strip())
        i += 1
    doc.save(docx_path)


# ---------------------------------------------------------------- docx -> pdf
def to_pdf(docx_path, pdf_path):
    out = tempfile.mkdtemp()
    try:
        exe = SOFFICE if os.path.exists(SOFFICE) else shutil.which("soffice")
        if exe:
            profile = "file:///" + tempfile.mkdtemp().replace("\\", "/")      # private profile: works while LibreOffice is open
            subprocess.run([exe, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", out, docx_path],
                           check=False, capture_output=True, timeout=180)
        made = os.path.join(out, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        if not os.path.exists(made):
            word_to_pdf(docx_path, made)
        shutil.move(made, pdf_path)
    finally:
        shutil.rmtree(out, ignore_errors=True)


def word_to_pdf(docx_path, pdf_path):
    """Fallback: Microsoft Word through COM (Windows, Word installed)."""
    import comtypes.client  # noqa
    word = comtypes.client.CreateObject("Word.Application")
    try:
        d = word.Documents.Open(os.path.abspath(docx_path)); d.SaveAs(os.path.abspath(pdf_path), FileFormat=17); d.Close()
    finally:
        word.Quit()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input"); ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    docx = os.path.splitext(a.output)[0] + ".docx"
    build_docx(a.input, docx)
    to_pdf(docx, a.output)
    if not os.path.exists(a.output):
        sys.exit("PDF conversion failed (LibreOffice and Word both unavailable?)")
    print(f"wrote {docx} and {a.output}")


if __name__ == "__main__":
    main()
