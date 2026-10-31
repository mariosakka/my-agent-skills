"""inspect_source.py, extract_text.py and extract_images.py on tiny fixtures built in a temp dir.

docx / pptx / xlsx are written by hand as zip + XML (the scripts read them with the standard library only); the PDF is
made with fpdf2 and skipped when fpdf2 or a PDF reader (pymupdf / pypdf) is missing.
"""
import json
import os
import struct
import zlib
from pathlib import Path
from zipfile import ZipFile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
INSPECT, TEXT, IMAGES = (SCRIPTS / f"{n}.py" for n in ("inspect_source", "extract_text", "extract_images"))

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CORE = ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
        '<dc:title>Fixture Title</dc:title><dc:creator>Jane Doe</dc:creator>'
        '<dcterms:created>2026-01-02T03:04:05Z</dcterms:created></cp:coreProperties>')


def png(size, noisy):
    """A valid RGB PNG. noisy=True is incompressible (> 2 KB), noisy=False is a few dozen bytes."""
    raw = b"".join(b"\x00" + (os.urandom(size * 3) if noisy else bytes(size * 3)) for _ in range(size))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


BIG, SMALL = png(64, True), png(2, False)
assert len(BIG) > 2048 > len(SMALL)


def zipfile_of(path, files):
    with ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def docx(tmp_path):
    def p(text, style=None):
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"

    cell = lambda t: f"<w:tc><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"
    table = f"<w:tbl><w:tr>{cell('Name')}{cell('Value')}</w:tr><w:tr>{cell('alpha')}{cell('1')}</w:tr></w:tbl>"
    body = (p("Main Title", "Title") + p("Chapter One", "Heading1") + p("Plain paragraph text.") + p("a list entry", "ListParagraph")
            + table + p("Section 1.1", "Heading2"))
    return zipfile_of(tmp_path / "doc.docx", {
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
        "docProps/core.xml": CORE, "word/media/image1.png": BIG, "word/media/tiny.png": SMALL})


@pytest.fixture
def pptx(tmp_path):
    def slide(title, bullets):
        sp_title = (f'<p:sp><p:nvSpPr><p:cNvPr id="1" name="t"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
                    f'<p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>')
        paras = "".join(f"<a:p><a:r><a:t>{b}</a:t></a:r></a:p>" for b in bullets)
        sp_body = (f'<p:sp><p:nvSpPr><p:cNvPr id="2" name="b"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:txBody>{paras}</p:txBody></p:sp>')
        return f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>{sp_title}{sp_body}</p:spTree></p:cSld></p:sld>'

    notes = (f'<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="1" name="n"/><p:cNvSpPr/>'
             '<p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>Say this aloud</a:t></a:r></a:p></p:txBody>'
             '</p:sp></p:spTree></p:cSld></p:notes>')
    rel = lambda i, kind, target: f'<Relationship Id="{i}" Type="http://x/{kind}" Target="{target}"/>'
    rels = lambda *r: f'<Relationships xmlns="{PKG}">{"".join(r)}</Relationships>'
    return zipfile_of(tmp_path / "deck.pptx", {
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
                                '<p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": rels(rel("rId1", "slide", "slides/slide1.xml"), rel("rId2", "slide", "slides/slide2.xml")),
        "ppt/slides/slide1.xml": slide("Opening slide", ["first point", "second point"]),
        "ppt/slides/slide2.xml": slide("Closing slide", ["last point"]),
        "ppt/slides/_rels/slide1.xml.rels": rels(rel("rId1", "notesSlide", "../notesSlides/notesSlide1.xml"),
                                                 rel("rId2", "image", "../media/image1.png")),
        "ppt/notesSlides/notesSlide1.xml": notes,
        "ppt/media/image1.png": BIG, "docProps/core.xml": CORE})


@pytest.fixture
def xlsx(tmp_path):
    cell = lambda ref, v, t=None, f=None: (f'<c r="{ref}"' + (f' t="{t}"' if t else "") + ">" + (f"<f>{f}</f>" if f else "") + f"<v>{v}</v></c>")
    rows = ('<row r="1">' + cell("A1", 0, "s") + cell("B1", 1, "s") + cell("C1", 2, "s") + "</row>"
            '<row r="2">' + cell("A2", 3, "s") + cell("B2", 10) + cell("C2", 20, f="B2*2") + "</row>"
            '<row r="3">' + cell("A3", 4, "s") + cell("B3", 30) + cell("C3", 60, f="B3*2") + "</row>")
    shared = "".join(f"<si><t>{t}</t></si>" for t in ("Item", "Qty", "Double", "apples", "pears"))
    return zipfile_of(tmp_path / "book.xlsx", {
        "xl/workbook.xml": f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="http://x/ws" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst xmlns="{S}">{shared}</sst>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{S}"><sheetData>{rows}</sheetData></worksheet>',
        "xl/media/image1.png": BIG, "docProps/core.xml": CORE})


@pytest.fixture
def csvfile(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("city,temp,note\nBucharest,10,cold\nParis,14,\nRome,18,warm\nOslo,2,cold\n", encoding="utf-8")
    return p


@pytest.fixture
def mdfile(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# Top\n\ntext\n\n## Second\n\nmore text here\n\n### Third\n", encoding="utf-8")
    return p


@pytest.fixture
def htmlfile(tmp_path):
    p = tmp_path / "page.html"
    p.write_text("<html><head><style>p{}</style><script>var x=1;</script></head><body><h1>Page head</h1><p>Body text</p>"
                 "<h2>Sub</h2><table><tr><td>c</td></tr></table><img src='a.png'></body></html>", encoding="utf-8")
    return p


@pytest.fixture
def pdffile(tmp_path):
    fpdf = pytest.importorskip("fpdf")
    if not any(__import__("importlib").util.find_spec(m) for m in ("pymupdf", "fitz", "pypdf")):
        pytest.skip("no PDF reader (pymupdf / pypdf) installed")
    (tmp_path / "pic.png").write_bytes(BIG)
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Hello PDF teaching material on page one with enough words.")
    pdf.image(str(tmp_path / "pic.png"), x=20, y=40, w=40)
    pdf.add_page()
    pdf.set_y(20)
    pdf.cell(0, 10, "Second page of the document has more text as well.")
    out = tmp_path / "doc.pdf"
    pdf.output(str(out))
    return out


@pytest.fixture
def pngfile(tmp_path):
    p = tmp_path / "pic.png"
    p.write_bytes(BIG)
    return p


def info(py, path):
    r = py(INSPECT, path, "--json")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ---------------------------------------------------------------- inspect_source
def test_inspect_docx(py, docx):
    d = info(py, docx)
    i = d["info"]
    assert (i["type"], i["title"], i["author"], i["tables"], i["images"]) == ("docx", "Fixture Title", "Jane Doe", 1, 2)
    assert i["created"].startswith("2026-01-02") and i["paragraphs"] == 5 and i["words"] > 5
    assert d["outline"] == [[1, "Main Title"], [1, "Chapter One"], [2, "Section 1.1"]]


def test_inspect_pptx(py, pptx):
    d = info(py, pptx)
    assert (d["info"]["slides"], d["info"]["slides_with_notes"], d["info"]["images"]) == (2, 1, 1)
    assert d["outline"] == [[1, "1. Opening slide"], [1, "2. Closing slide"]]


def test_inspect_xlsx_counts_formulas_and_shape(py, xlsx):
    i = info(py, xlsx)["info"]
    assert i["sheets"] == [{"name": "Data", "rows": 3, "cols": 3, "formulas": 2}]
    assert "cached" in i["note"]


def test_inspect_csv(py, csvfile):
    i = info(py, csvfile)["info"]
    assert (i["type"], i["rows"], i["columns"]) == ("csv", 4, ["city", "temp", "note"])


def test_inspect_markdown_and_html_outlines(py, mdfile, htmlfile):
    d = info(py, mdfile)
    assert d["outline"] == [[1, "Top"], [2, "Second"], [3, "Third"]] and d["info"]["type"] == "text"
    h = info(py, htmlfile)
    assert (h["info"]["images"], h["info"]["tables"]) == (1, 1)
    assert [1, "Page head"] in h["outline"] and [2, "Sub"] in h["outline"]
    assert "var x" not in json.dumps(h)


def test_inspect_pdf(py, pdffile):
    i = info(py, pdffile)["info"]
    assert i["type"] == "pdf" and i["pages"] == 2 and i["images"] >= 1 and i["words"] > 10


def test_inspect_image_reports_type(py, pngfile):
    i = info(py, pngfile)["info"]
    assert i["type"] == "image" and ("pixels" in i or "pillow" in i["note"])


def test_inspect_plain_output_lists_fields_and_outline(py, docx):
    r = py(INSPECT, docx)
    assert r.returncode == 0
    assert "type:" in r.stdout and "outline:" in r.stdout and "- Chapter One" in r.stdout


# ---------------------------------------------------------------- extract_text
def text_of(py, path, *args):
    r = py(TEXT, path, *args)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_text_docx_keeps_headings_lists_and_tables(py, docx):
    t = text_of(py, docx)
    assert "# Main Title" in t and "# Chapter One" in t and "## Section 1.1" in t
    assert "- a list entry" in t and "Plain paragraph text." in t
    assert "[table]\nName | Value\nalpha | 1" in t


def test_text_pptx_has_titles_bullets_and_notes(py, pptx):
    t = text_of(py, pptx)
    assert "## Slide 1: Opening slide" in t and "- first point" in t and "## Slide 2: Closing slide" in t
    assert "Speaker notes: Say this aloud" in t
    assert t.index("Slide 1") < t.index("Slide 2")


def test_text_xlsx_shows_sheet_and_cached_values(py, xlsx):
    t = text_of(py, xlsx)
    assert "## Sheet: Data (3 rows, 2 formulas" in t
    assert "Item | Qty | Double" in t and "apples | 10 | 20" in t and "pears | 30 | 60" in t


def test_text_xlsx_rows_limit(py, xlsx):
    t = text_of(py, xlsx, "--rows", "1")
    assert "... 2 more rows" in t and "apples" not in t


def test_text_csv_has_column_stats(py, csvfile):
    t = text_of(py, csvfile)
    assert "(4 rows)" in t
    assert "- temp: numeric: min 2, max 18, mean 11" in t
    assert "- note: text: 2 distinct, missing 1, top: cold (2)" in t
    assert "First rows:" in t and "Bucharest | 10 | cold" in t


def test_text_markdown_html_and_pdf(py, mdfile, htmlfile, pdffile):
    assert "## Second" in text_of(py, mdfile)
    h = text_of(py, htmlfile)
    assert "# Page head" in h and "Body text" in h and "var x" not in h and "p{}" not in h
    p = text_of(py, pdffile)
    assert "## Page 1" in p and "## Page 2" in p and "Hello PDF teaching" in p


def test_text_max_chars_truncates_and_out_writes_file(py, docx, tmp_path):
    t = text_of(py, docx, "--max-chars", "30")
    assert "[truncated at 30 characters]" in t
    out = tmp_path / "out.md"
    r = py(TEXT, docx, "-o", out)
    assert r.returncode == 0 and "wrote" in r.stdout
    assert "# Chapter One" in out.read_text(encoding="utf-8")


def test_text_of_an_image_is_refused_with_a_message(py, pngfile):
    r = py(TEXT, pngfile)
    assert r.returncode != 0 and "is an image" in r.stderr


# ---------------------------------------------------------------- extract_images
def run_images(py, src, out, *args):
    r = py(IMAGES, src, out, *args)
    assert r.returncode == 0, r.stderr
    return r


def test_images_docx_skips_tiny_images_and_writes_index(py, docx, tmp_path):
    out = tmp_path / "imgs"
    r = run_images(py, docx, out)
    assert "1 image(s)" in r.stdout
    assert (out / "image1.png").read_bytes() == BIG and not (out / "tiny.png").exists()
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "# Images from doc.docx" in index and "| image1.png |" in index


def test_images_keep_small_keeps_the_tiny_ones(py, docx, tmp_path):
    out = tmp_path / "imgs"
    run_images(py, docx, out, "--keep-small")
    assert (out / "image1.png").exists() and (out / "tiny.png").exists()


def test_images_pptx_index_names_the_slide(py, pptx, tmp_path):
    out = tmp_path / "imgs"
    run_images(py, pptx, out)
    assert "slide 1" in (out / "index.md").read_text(encoding="utf-8")


def test_images_xlsx(py, xlsx, tmp_path):
    out = tmp_path / "imgs"
    run_images(py, xlsx, out)
    assert (out / "image1.png").exists()


def test_images_pdf_extracts_embedded_image_with_page(py, pdffile, tmp_path):
    out = tmp_path / "imgs"
    run_images(py, pdffile, out)
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "page 1" in index
    assert any(p.suffix in (".png", ".jpeg", ".jpg") for p in out.iterdir())


def test_images_render_pdf_pages(py, pdffile, tmp_path):
    pytest.importorskip("pymupdf" if __import__("importlib").util.find_spec("pymupdf") else "fitz")
    out = tmp_path / "imgs"
    run_images(py, pdffile, out, "--render")
    assert (out / "page-001.png").exists() and (out / "page-002.png").exists()


def test_images_render_is_refused_for_docx(py, docx, tmp_path):
    r = py(IMAGES, docx, tmp_path / "o", "--render")
    assert r.returncode != 0 and "--render supports pdf and pptx only" in r.stderr


def test_images_from_a_type_without_images_is_refused(py, csvfile, tmp_path):
    r = py(IMAGES, csvfile, tmp_path / "o")
    assert r.returncode != 0 and "no embedded images" in r.stderr


# ---------------------------------------------------------------- shared behaviour
@pytest.mark.parametrize("script", [INSPECT, TEXT, IMAGES])
def test_help_works(py, script):
    r = py(script, "--help")
    assert r.returncode == 0 and "usage:" in r.stdout.lower() and "FILE" in r.stdout


@pytest.mark.parametrize("script,extra", [(INSPECT, []), (TEXT, []), (IMAGES, ["out"])])
def test_unsupported_type_names_the_supported_ones(py, tmp_path, script, extra):
    f = tmp_path / "thing.xyz"
    f.write_text("x")
    r = py(script, f, *[tmp_path / e for e in extra])
    assert r.returncode != 0
    assert "Unsupported file type" in r.stderr and "thing.xyz" in r.stderr and ".docx" in r.stderr


@pytest.mark.parametrize("script,extra", [(INSPECT, []), (TEXT, []), (IMAGES, ["out"])])
def test_missing_file_fails_and_names_the_file(py, tmp_path, script, extra):
    r = py(script, tmp_path / "nothing-here.docx", *[tmp_path / e for e in extra])
    assert r.returncode != 0
    assert "nothing-here.docx" in r.stderr
