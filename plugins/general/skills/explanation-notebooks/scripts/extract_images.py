"""Save the images embedded in a source file to a folder and write an index (index.md).

    python extract_images.py FILE OUTDIR [--render]

docx / pptx / xlsx: copied from the zip's media folder (standard library only). pptx index shows the slide.
pdf: embedded images via PyMuPDF (pip install pymupdf) or pypdf (pip install pypdf); index shows the page.
--render  also save every page / slide as page-NNN.png, so charts and diagrams that are drawn
          (vector) rather than embedded are captured too.
          pdf: needs PyMuPDF. pptx: needs LibreOffice (`soffice` on PATH) plus PyMuPDF.
Small images (< 2 KB, usually bullets and logos) are skipped; pass --keep-small to keep them.
"""
import argparse, os, shutil, subprocess, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _source as S

MIN_BYTES = 2048


def from_zip(path, kind, out, keep_small):
    z = zipfile.ZipFile(path)
    where = {}
    if kind == "pptx":
        for n, files in S.pptx_slide_media(z).items():
            for f in files:
                where.setdefault(f, []).append("slide %d" % n)
    rows = []
    for name in S.media(z):
        data = z.read(name)
        if len(data) < MIN_BYTES and not keep_small:
            continue
        dest = os.path.join(out, os.path.basename(name))
        open(dest, "wb").write(data)
        rows.append((os.path.basename(name), ", ".join(where.get(name, [])) or "-", len(data) // 1024 or 1))
    return rows


def from_pdf(path, out, keep_small):
    kind, doc = S.open_pdf(path)
    rows = []
    if kind == "pymupdf":
        for pno, page in enumerate(doc, 1):
            for img in page.get_images(full=True):
                info = doc.extract_image(img[0])
                if len(info["image"]) < MIN_BYTES and not keep_small:
                    continue
                name = "p%03d-x%d.%s" % (pno, img[0], info["ext"])
                open(os.path.join(out, name), "wb").write(info["image"])
                rows.append((name, "page %d" % pno, len(info["image"]) // 1024 or 1))
    else:
        for pno, page in enumerate(doc.pages, 1):
            for img in page.images:
                if len(img.data) < MIN_BYTES and not keep_small:
                    continue
                name = "p%03d-%s" % (pno, img.name)
                open(os.path.join(out, name), "wb").write(img.data)
                rows.append((name, "page %d" % pno, len(img.data) // 1024 or 1))
    return rows


def render(path, kind, out):
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            sys.exit("--render needs PyMuPDF: pip install pymupdf")
    src, tmp = path, None
    if kind == "pptx":
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            sys.exit("--render for pptx needs LibreOffice (soffice on PATH). Alternative: export the deck to PDF and render that.")
        tmp = tempfile.mkdtemp()
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, path], check=True, capture_output=True)
        src = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    rows = []
    for i, page in enumerate(fitz.open(src), 1):
        name = "page-%03d.png" % i
        page.get_pixmap(dpi=110).save(os.path.join(out, name))
        rows.append((name, "rendered page %d" % i, os.path.getsize(os.path.join(out, name)) // 1024 or 1))
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("outdir")
    ap.add_argument("--render", action="store_true", help="also render pages / slides to PNG")
    ap.add_argument("--keep-small", action="store_true", help="keep images under 2 KB")
    a = ap.parse_args()
    kind = S.kind_of(a.file)
    if kind not in ("docx", "pptx", "xlsx", "pdf"):
        sys.exit("%s files have no embedded images to extract." % kind)
    os.makedirs(a.outdir, exist_ok=True)
    rows = from_pdf(a.file, a.outdir, a.keep_small) if kind == "pdf" else from_zip(a.file, kind, a.outdir, a.keep_small)
    if a.render:
        if kind == "docx" or kind == "xlsx":
            sys.exit("--render supports pdf and pptx only (export the file to PDF first).")
        rows += render(a.file, kind, a.outdir)
    lines = ["# Images from %s" % os.path.basename(a.file), "", "| file | origin | KB |", "|---|---|---|"]
    lines += ["| %s | %s | %s |" % r for r in rows]
    open(os.path.join(a.outdir, "index.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("%d image(s) written to %s (index.md lists origin)" % (len(rows), a.outdir))
