"""Print metadata of a source file before teaching from it: type, size, title/author/dates,
page / slide / sheet counts, headings outline, table and image counts.

    python inspect_source.py FILE [--json]

Types: docx pptx xlsx csv tsv pdf md txt html png jpg.
docx / pptx / xlsx / csv / md / txt / html need nothing beyond the standard library.
pdf needs PyMuPDF (pip install pymupdf) or pypdf (pip install pypdf).
"""
import argparse, json, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _source as S


def inspect(path):
    kind = S.kind_of(path)
    info = {"file": os.path.basename(path), "type": kind, "size_kb": round(os.path.getsize(path) / 1024, 1)}
    outline = []
    if kind in ("docx", "pptx", "xlsx"):
        z = zipfile.ZipFile(path)
        info.update(S.core_props(z))
        info["images"] = len(S.media(z))
        if kind == "docx":
            blocks = S.docx_blocks(z)
            info["paragraphs"] = sum(b[0] == "p" for b in blocks)
            info["tables"] = sum(b[0] == "table" for b in blocks)
            info["words"] = sum(len(b[2].split()) for b in blocks)
            outline = [(S.heading_level(b[1]), b[2]) for b in blocks if b[0] == "p" and S.heading_level(b[1])]
        elif kind == "pptx":
            slides = S.pptx_slides(z)
            info["slides"] = len(slides)
            info["slides_with_notes"] = sum(bool(s[3]) for s in slides)
            outline = [(1, "%d. %s" % (s[0], s[1] or "(no title)")) for s in slides]
        else:
            sheets = S.xlsx_sheets(z)
            info["sheets"] = [{"name": n, "rows": len(r), "cols": max((len(x) for x in r), default=0), "formulas": f} for n, r, f in sheets]
            info["note"] = "values shown are the cached results Excel saved; formulas are counted, not evaluated"
    elif kind == "csv":
        rows = S.csv_rows(path)
        info["rows"] = max(len(rows) - 1, 0)
        info["columns"] = rows[0] if rows else []
    elif kind == "pdf":
        k, doc = S.open_pdf(path)
        texts = S.pdf_page_texts(k, doc)
        imgs = S.pdf_image_counts(k, doc)
        info["pages"] = len(texts)
        info["words"] = sum(len(t.split()) for t in texts)
        info["images"] = sum(imgs)
        if k == "pymupdf":
            md = {a: v for a, v in (doc.metadata or {}).items() if v and a in ("title", "author", "creationDate", "modDate")}
            info.update(md)
            outline = [(lvl, "%s (p.%s)" % (t, pg)) for lvl, t, pg in doc.get_toc()]
        else:
            md = doc.metadata or {}
            for a, key in (("title", "/Title"), ("author", "/Author"), ("created", "/CreationDate")):
                if md.get(key):
                    info[a] = md[key]
        blank = [i + 1 for i, t in enumerate(texts) if len(t.strip()) < 20]
        if blank:
            info["pages_without_text"] = blank
            info["warning"] = "pages without text: scanned or image-only, text extraction needs OCR (e.g. tesseract)"
    elif kind in ("text", "html"):
        if kind == "html":
            text, parser = S.html_text(path)
            info["images"], info["tables"] = parser.imgs, parser.tables
        else:
            text = S.read_text_file(path)
        info["words"] = len(text.split())
        outline = S.md_headings(text)
    else:
        try:
            from PIL import Image
            with Image.open(path) as im:
                info["pixels"] = "%dx%d" % im.size
        except ImportError:
            info["note"] = "install pillow (pip install pillow) for pixel size"
    return info, outline


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    info, outline = inspect(a.file)
    if a.json:
        print(json.dumps({"info": info, "outline": outline}, indent=1, ensure_ascii=False))
    else:
        for k, v in info.items():
            print("%-18s %s" % (k + ":", v))
        if outline:
            print("outline:")
            for lvl, t in outline[:80]:
                print("  " * lvl + "- " + t)
            if len(outline) > 80:
                print("  ... %d more" % (len(outline) - 80))
