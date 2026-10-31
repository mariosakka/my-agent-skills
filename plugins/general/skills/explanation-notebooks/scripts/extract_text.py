"""Extract the text of a source file as markdown-like text with the structure kept:
headings (docx/md/html), slide titles + bullets + speaker notes (pptx), sheet names + first rows
(xlsx), header + column statistics + first rows (csv), per-page text (pdf).

    python extract_text.py FILE [-o OUT.md] [--max-chars N] [--rows N]

--max-chars N   stop after N characters (default: no limit)
--rows N        rows shown per sheet / csv (default 20)
docx / pptx / xlsx / csv / md / txt / html need only the standard library.
pdf needs PyMuPDF (pip install pymupdf) or pypdf (pip install pypdf); scanned pdfs have no text and need OCR.
xlsx formulas are not evaluated: you see the values Excel cached when the file was saved.
"""
import argparse, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _source as S


def table(rows, limit):
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    out = [" | ".join(str(c) for c in r) for r in rows[:limit]]
    if len(rows) > limit:
        out.append("... %d more rows" % (len(rows) - limit))
    return "\n".join(out)


def extract(path, rows=20):
    kind = S.kind_of(path)
    out = []
    if kind == "docx":
        for typ, style, text in S.docx_blocks(zipfile.ZipFile(path)):
            lvl = S.heading_level(style)
            if typ == "table":
                out.append("[table]\n" + text)
            elif lvl:
                out.append("#" * lvl + " " + text)
            elif style.lower().startswith("list"):
                out.append("- " + text)
            else:
                out.append(text)
    elif kind == "pptx":
        for n, title, paras, notes in S.pptx_slides(zipfile.ZipFile(path)):
            block = ["## Slide %d: %s" % (n, title or "(no title)")] + ["- " + p for p in paras]
            if notes:
                block.append("Speaker notes: " + notes.replace("\n", " "))
            out.append("\n".join(block))
    elif kind == "xlsx":
        for name, data, formulas in S.xlsx_sheets(zipfile.ZipFile(path)):
            out.append("## Sheet: %s (%d rows, %d formulas; values are cached results)" % (name, len(data), formulas))
            out.append(table(data, rows))
    elif kind == "csv":
        data = S.csv_rows(path)
        out.append("## %s (%d rows)" % (os.path.basename(path), max(len(data) - 1, 0)))
        out.append("\n".join("- %s: %s" % kv for kv in S.column_stats(data)))
        out.append("First rows:\n" + table(data, rows + 1))
    elif kind == "pdf":
        k, doc = S.open_pdf(path)
        for i, t in enumerate(S.pdf_page_texts(k, doc), 1):
            out.append("## Page %d" % i)
            out.append(t.strip() or "(no text on this page: scanned or image-only, needs OCR)")
    elif kind == "html":
        out.append(S.html_text(path)[0])
    elif kind == "text":
        out.append(S.read_text_file(path))
    else:
        sys.exit("%s is an image: nothing to extract as text (read it directly or use OCR)." % path)
    return "\n\n".join(out) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-o", "--out", help="write to this file instead of stdout")
    ap.add_argument("--max-chars", type=int, default=0)
    ap.add_argument("--rows", type=int, default=20)
    a = ap.parse_args()
    text = extract(a.file, a.rows)
    if a.max_chars and len(text) > a.max_chars:
        text = text[:a.max_chars] + "\n... [truncated at %d characters]\n" % a.max_chars
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(text)
        print("wrote %s (%d chars)" % (a.out, len(text)))
    else:
        sys.stdout.write(text)
