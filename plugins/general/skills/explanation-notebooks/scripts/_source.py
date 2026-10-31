"""Shared readers for inspect_source.py, extract_text.py and extract_images.py.

docx, pptx and xlsx are plain zip files of XML, so they are read with the standard library only.
PDF needs PyMuPDF (`pip install pymupdf`) or pypdf (`pip install pypdf`). Everything else is stdlib.
"""
import csv, io, os, re, sys, zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KINDS = {".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx", ".xlsm": "xlsx", ".csv": "csv", ".tsv": "csv",
         ".pdf": "pdf", ".md": "text", ".txt": "text", ".rst": "text", ".html": "html", ".htm": "html",
         ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".webp": "image", ".bmp": "image"}
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
      "dc": "http://purl.org/dc/elements/1.1/", "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
      "dcterms": "http://purl.org/dc/terms/"}


def q(prefix, tag):
    return "{%s}%s" % (NS[prefix], tag)


def kind_of(path):
    k = KINDS.get(os.path.splitext(path)[1].lower())
    if not k:
        sys.exit("Unsupported file type: %s (supported: %s)" % (path, ", ".join(sorted(KINDS))))
    return k


def read_text_file(path):
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return open(path, encoding=enc).read()
        except (UnicodeError, UnicodeDecodeError):
            continue


def xml(z, name):
    return ET.fromstring(z.read(name))


def core_props(z):
    """title / author / dates from docProps/core.xml, page-like counts from docProps/app.xml."""
    out = {}
    if "docProps/core.xml" in z.namelist():
        r = xml(z, "docProps/core.xml")
        for key, path in (("title", "dc:title"), ("author", "dc:creator"), ("created", "dcterms:created"),
                          ("modified", "dcterms:modified"), ("subject", "dc:subject")):
            pre, tag = path.split(":")
            el = r.find(q(pre, tag))
            if el is not None and (el.text or "").strip():
                out[key] = el.text.strip()
    return out


def media(z):
    return [n for n in z.namelist() if re.match(r"(word|ppt|xl)/media/", n) and not n.endswith("/")]


# ---------------------------------------------------------------- docx
def docx_blocks(z):
    """[(kind, style, text)] in document order. kind: 'p' paragraph, 'table' (text = rows joined by newlines)."""
    body = xml(z, "word/document.xml").find(q("w", "body"))
    out = []
    for el in body:
        if el.tag == q("w", "p"):
            style = el.find("w:pPr/w:pStyle", NS)
            style = style.get(q("w", "val")) if style is not None else ""
            text = "".join(t.text or "" for t in el.iter(q("w", "t")))
            if text.strip():
                out.append(("p", style, text))
        elif el.tag == q("w", "tbl"):
            rows = []
            for tr in el.iter(q("w", "tr")):
                cells = ["".join(t.text or "" for t in tc.iter(q("w", "t"))).strip() for tc in tr.iter(q("w", "tc"))]
                rows.append(" | ".join(cells))
            out.append(("table", "", "\n".join(rows)))
    return out


def heading_level(style):
    m = re.match(r"(?i)heading\s*(\d)", style or "")
    if m:
        return int(m.group(1))
    return 1 if (style or "").lower() == "title" else 0


# ---------------------------------------------------------------- pptx
def pptx_slides(z):
    """[(number, title, [text paragraphs], notes)] in presentation order."""
    pres = xml(z, "ppt/presentation.xml")
    rels = {r.get("Id"): r.get("Target") for r in xml(z, "ppt/_rels/presentation.xml.rels")}
    order = [rels[s.get(q("r", "id"))] for s in pres.iter(q("p", "sldId"))]
    out = []
    for n, target in enumerate(order, 1):
        name = "ppt/" + target.lstrip("/").replace("ppt/", "", 1) if not target.startswith("/") else target.lstrip("/")
        root = xml(z, name)
        title, paras = "", []
        for sp in root.iter(q("p", "sp")):
            ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
            is_title = ph is not None and ph.get("type") in ("title", "ctrTitle")
            lines = ["".join(t.text or "" for t in p.iter(q("a", "t"))) for p in sp.iter(q("a", "p"))]
            lines = [l for l in lines if l.strip()]
            if is_title and lines:
                title = " ".join(lines)
            else:
                paras += lines
        for tbl in root.iter(q("a", "tbl")):
            for tr in tbl.iter(q("a", "tr")):
                paras.append(" | ".join("".join(t.text or "" for t in tc.iter(q("a", "t"))) for tc in tr.iter(q("a", "tc"))))
        notes = ""
        relname = "ppt/slides/_rels/%s.rels" % os.path.basename(name)
        if relname in z.namelist():
            for r in xml(z, relname):
                if r.get("Type", "").endswith("/notesSlide"):
                    nname = os.path.normpath(os.path.join("ppt/slides", r.get("Target"))).replace("\\", "/")
                    if nname in z.namelist():
                        nroot = xml(z, nname)
                        parts = []
                        for sp in nroot.iter(q("p", "sp")):
                            ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
                            if ph is not None and ph.get("type") == "body":
                                parts += ["".join(t.text or "" for t in p.iter(q("a", "t"))) for p in sp.iter(q("a", "p"))]
                        notes = "\n".join(p for p in parts if p.strip())
        out.append((n, title, paras, notes))
    return out


def pptx_slide_media(z):
    """{slide number: [media paths]} from each slide's relationships."""
    pres = xml(z, "ppt/presentation.xml")
    rels = {r.get("Id"): r.get("Target") for r in xml(z, "ppt/_rels/presentation.xml.rels")}
    res = {}
    for n, s in enumerate(pres.iter(q("p", "sldId")), 1):
        target = rels[s.get(q("r", "id"))]
        relname = "ppt/slides/_rels/%s.rels" % os.path.basename(target)
        res[n] = []
        if relname in z.namelist():
            for r in xml(z, relname):
                if r.get("Type", "").endswith("/image"):
                    res[n].append(os.path.normpath(os.path.join("ppt/slides", r.get("Target"))).replace("\\", "/"))
    return res


# ---------------------------------------------------------------- xlsx
def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_sheets(z):
    """[(sheet name, rows, formula count)]; rows = list of lists of cached values (formulas keep their cached result)."""
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in xml(z, "xl/sharedStrings.xml").iter(q("s", "si")):
            shared.append("".join(t.text or "" for t in si.iter(q("s", "t"))))
    wb = xml(z, "xl/workbook.xml")
    rels = {r.get("Id"): r.get("Target") for r in xml(z, "xl/_rels/workbook.xml.rels")}
    out = []
    for sh in wb.iter(q("s", "sheet")):
        target = rels[sh.get(q("r", "id"))]
        name = target.lstrip("/") if target.startswith("/") else "xl/" + target
        rows, formulas = [], 0
        for row in xml(z, name).iter(q("s", "row")):
            vals = []
            for c in row.findall("s:c", NS):
                idx = col_index(c.get("r"))
                vals += [""] * (idx + 1 - len(vals))
                v, t = c.find("s:v", NS), c.get("t")
                if c.find("s:f", NS) is not None:
                    formulas += 1
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(q("s", "t")))
                else:
                    val = v.text if v is not None and v.text is not None else ""
                vals[idx] = val
            rows.append(vals)
        out.append((sh.get("name"), rows, formulas))
    return out


# ---------------------------------------------------------------- csv
def csv_rows(path):
    text = read_text_file(path)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def column_stats(rows):
    """First row is the header. Returns [(name, summary string)]."""
    if not rows:
        return []
    head, body = rows[0], rows[1:]
    out = []
    for i, name in enumerate(head):
        vals = [r[i].strip() for r in body if i < len(r)]
        full = [v for v in vals if v != ""]
        nums = []
        for v in full:
            try:
                nums.append(float(v.replace(",", ".")))
            except ValueError:
                break
        if full and len(nums) == len(full):
            out.append((name, "numeric: min %.4g, max %.4g, mean %.4g, missing %d" % (min(nums), max(nums), sum(nums) / len(nums), len(vals) - len(full))))
        else:
            top = {}
            for v in full:
                top[v] = top.get(v, 0) + 1
            best = ", ".join("%s (%d)" % kv for kv in sorted(top.items(), key=lambda kv: -kv[1])[:3])
            out.append((name, "text: %d distinct, missing %d, top: %s" % (len(top), len(vals) - len(full), best)))
    return out


# ---------------------------------------------------------------- pdf
def open_pdf(path):
    """Returns ('pymupdf', doc) or ('pypdf', reader). Exits with an install hint if neither is available."""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            fitz = None
    if fitz is not None and hasattr(fitz, "open"):
        return "pymupdf", fitz.open(path)
    try:
        from pypdf import PdfReader
        return "pypdf", PdfReader(path)
    except ImportError:
        sys.exit("PDF support needs a package: pip install pymupdf  (or: pip install pypdf)")


def pdf_page_texts(kind, doc):
    if kind == "pymupdf":
        return [p.get_text() for p in doc]
    return [(p.extract_text() or "") for p in doc.pages]


def pdf_image_counts(kind, doc):
    if kind == "pymupdf":
        return [len(p.get_images(full=True)) for p in doc]
    return [len(list(p.images)) for p in doc.pages]


# ---------------------------------------------------------------- html
class _Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.skip, self.imgs, self.tables = [], 0, 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "li", "tr", "br"):
            self.out.append("\n")
        self.imgs += tag == "img"
        self.tables += tag == "table"

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(path):
    p = _Html()
    p.feed(read_text_file(path))
    return re.sub(r"\n{3,}", "\n\n", "".join(p.out)).strip(), p


def md_headings(text):
    return [(len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{1,6})\s+(.*)$", text, re.M)]
